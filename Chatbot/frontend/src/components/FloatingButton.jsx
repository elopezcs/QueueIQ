import React from "react";

export default function FloatingButton({ onClick, isActive, hasSession, onStartSession, disabled }) {
  const handleClick = () => {
    if (!hasSession) {
      onStartSession();
    } else {
      onClick();
    }
  };

  return (
    <button 
      className={`floating-button ${isActive ? "active" : ""}`}
      onClick={handleClick}
      disabled={disabled}
      title={hasSession ? "Open QueueIQ Assistant" : "Start intake and chat"}
    >
      <span className="button-icon">💬</span>
    </button>
  );
}
