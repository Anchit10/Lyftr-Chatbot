"""
main.py
-------
The FastAPI application. Exposes exactly the three endpoints from the contract:

    GET  /health
    POST /chat
    GET  /sessions/{session_id}/messages

Everything else (DB, cache, failover) is delegated to the modules in this package
so this file reads like a table of contents for the API.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import cache, config, db, llm
from .models import ChatRequest, ChatResponse, HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run once at startup: create the SQLite table before the first request."""
    db.init_db()
    yield


app = FastAPI(title="Lyftr LLM Chatbot", version="1.0.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS: let the deployed frontend origin call this backend from the browser.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """
    Returns 200 once the app is running, the database is reachable and the key
    pool is loaded.
    """
    # Touch the DB so we only report "ok" if SQLite actually works.
    db.init_db()
    return HealthResponse(
        status="ok",
        keys_configured=len(config.KEY_POOL),
        cache_enabled=config.CACHE_ENABLED,
    )


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    # The X-Simulate-Failure test hook. Only honored when the backend has
    # ENABLE_FAILURE_SIMULATION=true. Invalid bodies are rejected by Pydantic
    # (-> 422) before we ever reach this function.
    x_simulate_failure: str | None = Header(default=None),
) -> ChatResponse:
    # 1. Work out the system prompt for this turn (request overrides default).
    system_prompt = body.system_prompt or config.DEFAULT_SYSTEM_PROMPT

    # 2. Build the full message list the model will see:
    #    system prompt + stored history for this session + the new user message.
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for past in db.get_history(body.session_id):
        messages.append({"role": past["role"], "content": past["content"]})
    messages.append({"role": "user", "content": body.message})

    # 3. Parse the simulate-failure header (ignored unless the flag is on).
    simulate = (
        llm.parse_simulate_header(x_simulate_failure)
        if config.ENABLE_FAILURE_SIMULATION
        else {}
    )

    # 4. Ask the gateway for a reply. If every key fails we return a clean 503
    #    and DO NOT write anything to history.
    try:
        result = llm.generate(messages, simulate)
    except llm.AllProvidersUnavailable:
        raise HTTPException(status_code=503, detail="all providers unavailable")

    # 5. Success: persist the user message and the assistant reply (with its
    #    metadata). Only happens on a real 200 — failed requests never touch
    #    history.
    db.add_message(body.session_id, "user", body.message)
    db.add_message(body.session_id, "assistant", result["reply"], metadata={
        "resolution_source": result["resolution_source"],
        "model": result["model"],
        "latency_ms": result["latency_ms"],
        "input_tokens": result["input_tokens"],
        "output_tokens": result["output_tokens"],
        "key_id": result["key_id"],
        "fallback_attempts": result["fallback_attempts"],
    })

    # 6. Return the contract-shaped response.
    return ChatResponse(
        session_id=body.session_id,
        reply=result["reply"],
        metadata={
            "resolution_source": result["resolution_source"],
            "model": result["model"],
            "latency_ms": result["latency_ms"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "key_id": result["key_id"],
            "fallback_attempts": result["fallback_attempts"],
        },
    )


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}/messages
# ---------------------------------------------------------------------------
@app.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str) -> dict:
    """
    Returns the stored history of one session, oldest first, WITHOUT the system
    prompt. Unknown session -> 404.
    """
    if not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    messages = []
    for row in db.get_history(session_id):
        item = {"role": row["role"], "content": row["content"]}
        # Assistant rows carry metadata; user rows don't.
        if row["metadata"] is not None:
            item["metadata"] = row["metadata"]
        messages.append(item)

    return {"session_id": session_id, "messages": messages}


# ---------------------------------------------------------------------------
# Make sure EVERY error is JSON with a "detail" field (never an HTML page or a
# stack trace), as the contract requires. FastAPI already does this for
# HTTPException and 422; this catch-all covers any unexpected 500.
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "internal server error"})
