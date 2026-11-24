"""
llm.py
------
The "brain gateway". This module is where the three interesting behaviours live:

  1. CACHING      - check the cache before calling any provider.
  2. FAILOVER     - walk the key pool top to bottom; if a key fails
                    (rate limit / quota / 5xx), try the next one.
  3. SIMULATE-FAIL- the X-Simulate-Failure test hook can force specific keys to
                    "fail" for a single request, so failover can be demoed
                    without burning real keys.

LiteLLM is the gateway that actually talks to the model providers (Gemini, etc.)
via `litellm.completion`. We layer explicit cache + failover on top so the
response metadata (key_id, fallback_attempts, resolution_source) is exactly what
the API contract asks for.

Set MOCK_LLM=true (the default) to return a fake but realistic answer with no
real API key — handy for local runs and the test suite.
"""

import time

from . import cache, config

# Resolution source labels, exactly as the contract spells them.
LIVE_INFERENCE = "LIVE_INFERENCE"
LLM_CACHE = "LLM_CACHE"


class AllProvidersUnavailable(Exception):
    """Raised when every key in the pool failed. Becomes an HTTP 503."""


def parse_simulate_header(header_value: str | None) -> dict[str, int]:
    """
    Parse the X-Simulate-Failure header into a {key_id: status} map.

    Examples:
        "key_1=429"            -> {"key_1": 429}
        "key_1=429,key_2=500"  -> {"key_1": 429, "key_2": 500}
        "*=429"                -> {"*": 429}   (means EVERY key)

    A malformed pair is simply ignored (we never crash on a bad header).
    """
    result: dict[str, int] = {}
    if not header_value:
        return result
    for pair in header_value.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        key_id, _, status = pair.partition("=")
        key_id = key_id.strip()
        status = status.strip()
        if key_id and status.isdigit():
            result[key_id] = int(status)
    return result


def _simulated_status(key_id: str, simulate: dict[str, int]) -> int | None:
    """
    Decide whether THIS key should pretend to fail for this request.
    A "*" entry applies to every key.
    """
    if key_id in simulate:
        return simulate[key_id]
    if "*" in simulate:
        return simulate["*"]
    return None


def _estimate_tokens(text: str) -> int:
    """
    A rough token estimate used only in MOCK mode (~4 characters per token).
    Real mode uses the exact usage numbers reported by the provider.
    """
    return max(1, len(text) // 4)


def _call_mock(messages: list[dict]) -> tuple[str, int, int]:
    """
    Fake model call. Returns (reply_text, input_tokens, output_tokens).
    Deterministic so tests are stable; adds a small delay so a real-looking
    latency shows up in the UI (and so cache hits are clearly faster).
    """
    time.sleep(config.MOCK_LATENCY_MS / 1000.0)

    last_user = ""
    for msg in reversed(messages):
        if msg["role"] == "user":
            last_user = msg["content"]
            break

    reply = f"(mock reply) You said: {last_user}"
    # Input tokens = every message we sent; output tokens = the reply.
    input_tokens = sum(_estimate_tokens(m["content"]) for m in messages)
    output_tokens = _estimate_tokens(reply)
    return reply, input_tokens, output_tokens


def _call_real(messages: list[dict], api_key: str) -> tuple[str, int, int]:
    """
    Real model call through LiteLLM. Returns (reply_text, input_tokens, output_tokens).
    Raises on any provider error (caught by the failover loop as a key failure).
    """
    import litellm  # imported lazily so MOCK mode / tests don't need it loaded

    response = litellm.completion(
        model=config.LLM_MODEL,
        messages=messages,
        api_key=api_key,
    )
    reply = response["choices"][0]["message"]["content"] or ""
    usage = response.get("usage", {}) or {}
    input_tokens = int(usage.get("prompt_tokens", 0))
    output_tokens = int(usage.get("completion_tokens", 0))
    return reply, input_tokens, output_tokens


def generate(messages: list[dict], simulate: dict[str, int]) -> dict:
    """
    Produce one assistant reply and all its metadata.

    `messages` is the full list sent to the model: system prompt + history +
    the new user message.

    Returns a dict shaped like the /chat "metadata" block plus the reply:
        {
          reply, resolution_source, model, latency_ms,
          input_tokens, output_tokens, key_id, fallback_attempts
        }

    Raises AllProvidersUnavailable (-> HTTP 503) if every key failed.
    """
    started = time.perf_counter()
    model = config.LLM_MODEL

    # --- 1. CACHE CHECK (happens before any provider / key is touched) --------
    cache_key = cache.make_key(model, messages)
    if config.CACHE_ENABLED:
        hit = cache.get(cache_key)
        if hit is not None:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return {
                "reply": hit["reply"],
                "resolution_source": LLM_CACHE,
                "model": model,
                "latency_ms": latency_ms,
                "input_tokens": hit["input_tokens"],
                "output_tokens": hit["output_tokens"],
                "key_id": None,            # cache hits never involve a key
                "fallback_attempts": 0,    # and never fail over
            }

    # --- 2. FAILOVER LOOP over the key pool ----------------------------------
    failures_before_success = 0

    for key_id, api_key in config.KEY_POOL:
        # 2a. Should this key pretend to fail for this one request?
        forced_status = _simulated_status(key_id, simulate)
        if forced_status is not None:
            failures_before_success += 1
            continue  # move on to the next key, just like a real failure

        # 2b. Try the real (or mock) call. Any exception = this key failed.
        try:
            if config.MOCK_LLM:
                reply, input_tokens, output_tokens = _call_mock(messages)
            else:
                reply, input_tokens, output_tokens = _call_real(messages, api_key)
        except Exception as exc:
            # Log WHY this key failed so the real reason (auth / bad model /
            # network) shows up in `docker compose logs backend` instead of
            # being hidden behind the generic 503.
            print(
                f"[llm] key {key_id} call failed: {type(exc).__name__}: {exc}",
                flush=True,
            )
            failures_before_success += 1
            continue  # fall over to the next key

        # 2c. Success! Store in cache so the next identical request is a hit.
        if config.CACHE_ENABLED:
            cache.set(cache_key, reply, input_tokens, output_tokens)

        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "reply": reply,
            "resolution_source": LIVE_INFERENCE,
            "model": model,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "key_id": key_id,
            "fallback_attempts": failures_before_success,
        }

    # --- 3. Every key failed -> 503 ------------------------------------------
    raise AllProvidersUnavailable()
