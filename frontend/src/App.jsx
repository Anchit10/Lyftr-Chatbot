// App.jsx
// -------
// The whole chat screen. Kept intentionally small and in one component so it is
// easy to read end to end.
//
// Behaviour required by the assignment:
//   - a new session starts on each page load
//   - send a message, see the multi-turn conversation
//   - each assistant reply shows its metadata (source / model / latency / tokens)
//   - errors (422 / 503) appear as a readable message, never a blank screen
//   - optional system-prompt field
//   - optional X-Simulate-Failure field so failover is easy to demo in the video

import { useEffect, useRef, useState } from "react";
import Message from "./components/Message.jsx";
import { sendChat, getHealth } from "./api.js";

// Generate a fresh random session id. The backend treats any unknown id as a
// new session, so this is all we need to "start a new session on page load".
function newSessionId() {
  return "s-" + Math.random().toString(36).slice(2, 10);
}

export default function App() {
  const [sessionId] = useState(newSessionId); // fixed for this page load
  const [messages, setMessages] = useState([]); // {role, content, metadata?}
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [simulateFailure, setSimulateFailure] = useState("");
  const [sending, setSending] = useState(false);
  const [health, setHealth] = useState(null);

  const scrollRef = useRef(null);

  // Check the backend is reachable once, on load (shows a small status line).
  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  // Keep the newest message in view.
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    // Optimistically show the user's message.
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);

    try {
      const data = await sendChat({
        sessionId,
        message: text,
        systemPrompt,
        simulateFailure: simulateFailure.trim() || undefined,
      });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply, metadata: data.metadata },
      ]);
    } catch (err) {
      // 422 / 503 etc. -> readable error bubble, never a blank screen.
      setMessages((prev) => [...prev, { role: "error", content: err.message }]);
    } finally {
      setSending(false);
    }
  }

  // Enter sends; Shift+Enter makes a new line.
  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Lyftr Chatbot</h1>
        <div className="status">
          {health ? (
            <span>
              backend ok · {health.keys_configured} keys ·{" "}
              cache {health.cache_enabled ? "on" : "off"}
            </span>
          ) : (
            <span className="status-bad">backend unreachable</span>
          )}
          <span className="session">session: {sessionId}</span>
        </div>
      </header>

      {/* Optional controls: system prompt + the failover demo hook. */}
      <section className="controls">
        <label>
          System prompt (optional)
          <input
            type="text"
            data-testid="system-prompt-input"
            placeholder="e.g. You are a helpful pirate."
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
          />
        </label>
        <label>
          Simulate failure (optional, e.g. key_1=429 or *=429)
          <input
            type="text"
            placeholder="leave empty for normal replies"
            value={simulateFailure}
            onChange={(e) => setSimulateFailure(e.target.value)}
          />
        </label>
      </section>

      {/* The conversation. */}
      <main className="messages" ref={scrollRef}>
        {messages.length === 0 ? (
          <p className="empty">Say something to start the conversation.</p>
        ) : (
          messages.map((msg, i) => <Message key={i} msg={msg} />)
        )}
      </main>

      {/* Composer. */}
      <footer className="composer">
        <textarea
          data-testid="chat-input"
          rows={2}
          placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button
          data-testid="send-button"
          onClick={handleSend}
          disabled={sending || !input.trim()}
        >
          {sending ? "…" : "Send"}
        </button>
      </footer>
    </div>
  );
}
