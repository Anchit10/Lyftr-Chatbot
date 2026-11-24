# Lyftr Chatbot — LLM Chatbot with Key Failover and Response Caching

A small full-stack AI chatbot: **React (Vite)** frontend, **FastAPI** backend,
**SQLite** storage, with **LiteLLM** as the model gateway. It supports multi-turn
conversations, automatic **key failover**, and **response caching**, and reports
per-request metadata (source, model, latency, tokens) for every reply.

> The app ships in **mock mode** (`MOCK_LLM=true`), so the whole stack runs and
> all tests pass with **no real API keys**. Add real keys when you're ready.

---

## 1. Live URLs

> _Deploy step — fill these in after deploying (see "Run locally" for the build)._

- **Frontend:** https://lyftr-chatbot-wheat.vercel.app
- **Backend:** https://lyftr-chatbot-scgj.onrender.com
- **Health check:** https://lyftr-chatbot-scgj.onrender.com/health

---

## 2. Run locally

### With Docker (recommended)

```bash
cp .env.example .env     # create your env file (works as-is, in mock mode)
make up                  # build + start everything
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Health: http://localhost:8000/health

Stop it with:

```bash
make down
```

The SQLite database lives on a named Docker volume mounted at `/data`, so your
chat history survives container restarts.

### Without Docker

**Backend:**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' ../.env | xargs)   # or set env vars yourself
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev        # serves on http://localhost:3000
```

### Using real API keys (Gemini example)

1. Get an API key from Google AI Studio (free tier). Make **two** keys (two keys
   enable failover — they can be two Gemini keys or two different providers).
2. In `.env` set:

   ```env
   LLM_API_KEYS=<real_key_1>,<real_key_2>
   MOCK_LLM=false
   LLM_MODEL=gemini/gemini-2.0-flash
   ```
3. `make up` again. LiteLLM uses the `provider/model` naming convention, so other
   providers work by changing `LLM_MODEL` (e.g. `groq/llama-3.1-8b-instant`).

---

## 3. Design decisions

**Key fallback.** The key pool comes from `LLM_API_KEYS` (first key = `key_1`,
second = `key_2`, …). A request walks the pool top to bottom; if a key fails
(rate limit, quota, or a 5xx), the gateway moves to the next key automatically.
If **every** key fails, the API returns a clean `503 {"detail": "all providers
unavailable"}` and nothing is written to history. The response reports `key_id`
(which key answered) and `fallback_attempts` (how many failed before it).

**Why explicit failover + cache instead of LiteLLM's router internals.** LiteLLM
is the gateway that actually calls the providers (`litellm.completion`). The
failover loop and cache are implemented explicitly on top so the response
metadata (`key_id`, `fallback_attempts`, `resolution_source`) matches the API
contract exactly and is easy to reason about and test.

**Caching.** The cache key is the **model + the full message list** sent to the
model (system prompt + history + new message). The cache is checked **before** any
key is used, so a cache hit never touches a provider: it returns the identical
reply, the originally-stored token counts, `key_id: null`, `fallback_attempts: 0`,
and `resolution_source: LLM_CACHE`. A fresh answer reports `LIVE_INFERENCE`. The
cache is in-memory (allowed by the spec); it resets on restart.

**SQLite session storage.** History is stored per `session_id` in a single
`messages` table (the schema from the assignment). The backend rebuilds the
conversation for each request by reading that session's history, so the bot
remembers earlier turns. The system prompt is applied per request and is **not**
stored in history. Sessions are fully independent. The DB file lives on a mounted
volume so it persists across restarts.

**Tokens are per request.** `input_tokens` / `output_tokens` are for that one
request only, never a running total.

**Errors are always JSON** with a `detail` field — `422` for bad input, `503`
when all keys fail, `404` for an unknown session — never a stack trace or HTML.

---

## 4. Verification

### Health

```bash
curl http://localhost:8000/health
# {"status":"ok","keys_configured":2,"cache_enabled":true}
```

### A normal reply (live inference)

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo","message":"What is the capital of France?"}'
# metadata.resolution_source = "LIVE_INFERENCE", key_id = "key_1", fallback_attempts = 0
```

### A cache hit

Send the **same first message** in a **new** session — the second response has
`resolution_source: "LLM_CACHE"`, `key_id: null`, and a **lower latency_ms**:

```bash
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo2","message":"What is the capital of France?"}'
```

### Failover on demand (the test hook)

`X-Simulate-Failure` forces specific keys to fail **for that one request only**
(requires `ENABLE_FAILURE_SIMULATION=true`):

```bash
# key_1 fails -> key_2 answers (200, fallback_attempts = 1)
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Simulate-Failure: key_1=429' \
  -d '{"session_id":"demo3","message":"failover please"}'

# every key fails -> clean 503, nothing added to history
curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H 'X-Simulate-Failure: *=429' \
  -d '{"session_id":"demo4","message":"all down"}'
```

You can also do this from the UI using the **"Simulate failure"** field.

### Per-message token usage in the UI

Every assistant bubble shows a metadata row: source, model, latency, input tokens,
output tokens (and the key that answered). These use the required `data-testid`
attributes (`meta-source`, `meta-model`, `meta-latency`, `meta-input-tokens`,
`meta-output-tokens`).

### Stored history

```bash
curl http://localhost:8000/sessions/demo/messages
```

### Run the tests

```bash
make test        # or: cd backend && pytest -q
```

18 tests cover health, chat + validation (422), caching, failover + 503, key
rate-limiting, and multi-turn session storage.

---

## 5. Setup Used

- **Editor:** _<your editor, e.g. VS Code>_
- **AI tools:** _<what you used, e.g. Claude>_
- **Languages/frameworks:** Python 3.12 + FastAPI, React 18 + Vite, SQLite, LiteLLM
- **Containers:** Docker + Docker Compose (multi-stage images)

---

## 6. Bonus features

- **Mock mode** so the whole stack runs and all tests pass with zero real keys.
- **In-UI failover trigger** (the "Simulate failure" field) and a system-prompt
  field, both optional.
- **Live backend health indicator** in the header (keys configured + cache state).
- **15-test automated suite** covering every contract behavior.
- **Catch-all JSON error handler** so even unexpected 500s return `{"detail": ...}`,
  never an HTML page.

---

## Project structure

```
lyftr-chatbot/
├── backend/
│   ├── app/
│   │   ├── config.py     # env-var configuration
│   │   ├── db.py         # SQLite storage
│   │   ├── cache.py      # in-memory response cache
│   │   ├── llm.py        # LiteLLM gateway: failover + cache + simulate-failure
│   │   ├── models.py     # Pydantic request/response models
│   │   └── main.py       # FastAPI app + the 3 endpoints
│   ├── tests/            # pytest suite (mock mode, no real keys needed)
│   ├── requirements.txt
│   └── Dockerfile        # multi-stage
├── frontend/
│   ├── src/              # React app (App.jsx, components, api.js)
│   ├── package.json
│   ├── nginx.conf
│   └── Dockerfile        # multi-stage (Node build -> Nginx)
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

## API contract (quick reference)

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | `{status, keys_configured, cache_enabled}` |
| `POST /chat` | body `{session_id, message, system_prompt?}` → `{session_id, reply, metadata}` |
| `GET /sessions/{session_id}/messages` | stored history, oldest first, no system prompt |

`metadata` = `resolution_source`, `model`, `latency_ms`, `input_tokens`,
`output_tokens`, `key_id`, `fallback_attempts`.
