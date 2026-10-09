import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";

export default function ChatBox({ projectId, getCode, language }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [includeCode, setIncludeCode] = useState(true);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    api
      .history(projectId)
      .then(setMessages)
      .catch((e) => setError(e.message));
  }, [projectId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || sending) return;

    setInput("");
    setError("");
    setSending(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "" },
    ]);

    try {
      await api.chatStream(
        {
          project_id: projectId,
          message: text,
          code: includeCode ? getCode() : null,
          language,
        },
        (chunk) => {
          setMessages((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, content: last.content + chunk };
            return copy;
          });
        }
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chatbox">
      <div className="panel-title">Chat</div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <p className="muted">Ask anything about your code or programming.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.role === "assistant" ? (
              m.content ? (
                <div className="markdown">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <span className="muted">Thinking...</span>
              )
            ) : (
              m.content
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="chat-input">
        <label className="check">
          <input
            type="checkbox"
            checked={includeCode}
            onChange={(e) => setIncludeCode(e.target.checked)}
          />
          Include my code
        </label>
        <div className="row">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask the assistant..."
            disabled={sending}
          />
          <button className="primary" onClick={send} disabled={sending || !input.trim()}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}