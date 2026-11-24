"""
models.py
---------
Pydantic models define the request/response SHAPES and the validation rules.

When a request breaks these rules, FastAPI automatically returns
HTTP 422 with a JSON body shaped like {"detail": ...} — which is exactly what
the contract's "Errors" table asks for. We don't have to write that by hand.
"""

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Body of POST /chat."""

    # session_id: required, 1-128 chars. An unknown id simply starts a new session.
    session_id: str = Field(..., min_length=1, max_length=128)

    # message: required. We validate length AFTER trimming whitespace (1-4000).
    message: str

    # system_prompt: optional; overrides the default system prompt for this turn.
    system_prompt: str | None = None

    @field_validator("message")
    @classmethod
    def message_must_be_1_to_4000_after_trim(cls, value: str) -> str:
        trimmed = value.strip()
        if len(trimmed) < 1:
            raise ValueError("message must not be empty")
        if len(trimmed) > 4000:
            raise ValueError("message must be at most 4000 characters")
        return trimmed


class ChatMetadata(BaseModel):
    """The per-reply metadata block returned by POST /chat."""

    resolution_source: str          # "LIVE_INFERENCE" or "LLM_CACHE"
    model: str                      # model name that produced the reply
    latency_ms: int                 # server-measured time, milliseconds
    input_tokens: int               # prompt tokens for THIS request
    output_tokens: int              # completion tokens for THIS reply
    key_id: str | None              # which key answered (null on cache)
    fallback_attempts: int          # keys that failed before this one (0 on cache)


class ChatResponse(BaseModel):
    """Full body of a successful POST /chat (HTTP 200)."""

    session_id: str
    reply: str
    metadata: ChatMetadata


class HealthResponse(BaseModel):
    """Body of GET /health."""

    status: str
    keys_configured: int
    cache_enabled: bool
