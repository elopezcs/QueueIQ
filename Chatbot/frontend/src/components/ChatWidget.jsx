import React, { useEffect, useRef, useState } from "react";

export default function ChatWidget({ messages, onSend, disabled, done, progress, onFinish, onReset }) {
  const [text, setText] = useState("");
  const listRef = useRef(null);

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  function submit(e) {
    e.preventDefault();
    const msg = text.trim();
    if (!msg) return;
    setText("");
    onSend(msg);
  }

  return (
    <div className="chat">
      <div className="chatHeader">
        <div>
          <strong>Chat</strong>
        </div>
        <div className="muted">
          Turns: {progress.turn_count}/{progress.max_turns} {done ? "(done)" : ""}
        </div>
      </div>

      <div className="chatList" ref={listRef}>
        {messages.length === 0 && (
          <div className="muted">Start intake to begin.</div>
        )}

        {messages.map((m, idx) => (
          <div key={idx} className={`bubble ${m.role}`}>
            <div className="role">{m.role}</div>
            <div>{m.content}</div>
          </div>
        ))}
      </div>

      <div className="chatInput">
        {!done ? (
          <form onSubmit={submit} style={{ display: "flex", gap: "8px", width: "100%" }}>
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={disabled ? "Chat disabled" : "Type your message..."}
              disabled={disabled}
              maxLength={2000}
              style={{ flex: 1 }}
            />
            <button className="btn" disabled={disabled}>
              Send
            </button>
          </form>
        ) : (
          <div style={{ display: "flex", gap: "8px", width: "100%" }}>
            <button className="btn secondary" onClick={onReset} style={{ flex: 1 }}>
              Reset
            </button>
            <button className="btn" onClick={onFinish} style={{ flex: 1 }}>
              Finish
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
