import React, { useEffect, useRef, useState } from "react";

export default function ChatWidget({ messages, onSend, disabled, done, progress, onFinish, onReset, loading, hasResults = false, loginRequired = false, onLoginClick, onRegisterClick }) {
  const [text, setText] = useState("");
  const listRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!loading && !done && inputRef.current) {
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 10);
    }
  }, [loading, done]);

  function submit(e) {
    e.preventDefault();
    const msg = text.trim();
    if (!msg) return;
    setText("");
    onSend(msg);
    if (inputRef.current) {
      inputRef.current.focus();
    }
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
        {messages.length === 0 && !loginRequired && (
          <div className="muted">Start intake to begin.</div>
        )}

        {loginRequired && (
          <div className="bubble assistant warning">
            <div className="role">assistant</div>
            <div>
              Welcome! Please log in or create a free account to start your intake.
              <div className="auth-actions" style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <button className="btn" type="button" onClick={onLoginClick}>Log in</button>
                <button className="btn secondary" type="button" onClick={onRegisterClick}>Register</button>
              </div>
            </div>
          </div>
        )}

        {messages.map((m, idx) => (
          <div key={idx} className={`bubble ${m.role}`}>
            <div className="role">{m.role}</div>
            <div>{m.content}</div>
          </div>
        ))}
        {loading && (
          <div className="bubble assistant loading">
            <div className="role">assistant</div>
            <div><span className="loader-spinner" /> Thinking...</div>
          </div>
        )}
      </div>

      <div className="chatInput">
        {!done ? (
          <form onSubmit={submit} className="chat-form">
            <input
              ref={inputRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={disabled || loginRequired ? "Log in to chat" : "Type your message..."}
              disabled={disabled || loginRequired}
              maxLength={2000}
              style={{ flex: 1 }}
            />
            <button className="btn" disabled={disabled || loginRequired}>
              Send
            </button>
          </form>
        ) : (
          <div className="chat-actions">
            <button className="btn secondary" onClick={onReset} style={{ flex: 1 }}>
              Reset
            </button>
            {!hasResults && (
              <button className="btn" onClick={onFinish} style={{ flex: 1 }}>
                Finish
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
