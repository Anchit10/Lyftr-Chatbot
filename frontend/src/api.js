// api.js
// -------
// All calls to the backend live here, so the UI components stay simple.
//
// The backend base URL comes from the VITE_API_URL env var (baked in at build
// time by Vite). Defaults to http://localhost:8000 for local dev.

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// POST /chat -> { session_id, reply, metadata } on success.
// On an error status (422 / 503) the backend returns { detail: ... }; we throw
// an Error carrying that detail text so the UI can show it in the chat.
export async function sendChat({ sessionId, message, systemPrompt, simulateFailure }) {
  const headers = { "Content-Type": "application/json" };

  // The X-Simulate-Failure test hook is only sent if the caller provides it.
  if (simulateFailure) {
    headers["X-Simulate-Failure"] = simulateFailure;
  }

  const body = { session_id: sessionId, message };
  if (systemPrompt && systemPrompt.trim()) {
    body.system_prompt = systemPrompt.trim();
  }

  const resp = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const data = await resp.json().catch(() => ({ detail: "unexpected error" }));

  if (!resp.ok) {
    // Turn {detail: "..."} into a readable error message.
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : "Request failed (" + resp.status + ")";
    throw new Error(detail);
  }

  return data;
}

// GET /health -> used to show whether the backend is reachable.
export async function getHealth() {
  const resp = await fetch(`${BASE_URL}/health`);
  if (!resp.ok) throw new Error("backend not healthy");
  return resp.json();
}
