// Message.jsx
// -----------
// Renders a single chat bubble. There are three kinds of message:
//   - "user"      : what the person typed
//   - "assistant" : a reply from the bot, shown WITH its metadata row
//   - "error"     : a readable error (422 / 503), never a blank screen
//
// The assistant bubble carries the exact data-testid attributes the assignment
// requires, so the UI can be auto-tested. Assistant text is rendered as Markdown
// (models often reply in Markdown — tables, lists, bold, headings).

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Models sometimes emit literal <br> tags. Convert them to real newlines so the
// Markdown renderer lays them out instead of printing "<br>" as text. (We do NOT
// render raw HTML, which keeps things safe from injected markup.)
function tidyMarkdown(text) {
  return (text || "").replace(/<br\s*\/?>/gi, "\n");
}

export default function Message({ msg }) {
  if (msg.role === "user") {
    return (
      <div className="bubble user">
        <div className="bubble-text">{msg.content}</div>
      </div>
    );
  }

  if (msg.role === "error") {
    return (
      <div className="bubble error">
        <div className="bubble-text">⚠️ {msg.content}</div>
      </div>
    );
  }

  // --- assistant message (with metadata) ---
  const m = msg.metadata || {};
  return (
    <div className="bubble assistant" data-testid="assistant-message">
      {/* Render the reply as Markdown. remark-gfm adds tables, strikethrough, etc. */}
      <div className="bubble-text markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {tidyMarkdown(msg.content)}
        </ReactMarkdown>
      </div>

      <div className="meta">
        {/* Exactly LIVE_INFERENCE or LLM_CACHE */}
        <span className="meta-chip" data-testid="meta-source">
          {m.resolution_source}
        </span>
        <span className="meta-chip" data-testid="meta-model">
          {m.model}
        </span>
        <span className="meta-chip" data-testid="meta-latency">
          {m.latency_ms} ms
        </span>
        <span className="meta-chip" data-testid="meta-input-tokens">
          in: {m.input_tokens}
        </span>
        <span className="meta-chip" data-testid="meta-output-tokens">
          out: {m.output_tokens}
        </span>
        {/* Extra context (not required, but useful in the demo). */}
        {m.key_id ? <span className="meta-chip subtle">key: {m.key_id}</span> : null}
        {typeof m.fallback_attempts === "number" ? (
          <span className="meta-chip subtle">fallbacks: {m.fallback_attempts}</span>
        ) : null}
      </div>
    </div>
  );
}
