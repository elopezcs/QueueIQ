import React from "react";
import ChatWidget from "./ChatWidget.jsx";

export default function ChatbotModal({
  isOpen,
  onClose,
  messages,
  onSend,
  disabled,
  done,
  progress,
  onFinish,
  onReset,
  loading,
  hasResults = false,
  loginRequired = false,
  onLoginClick,
  onRegisterClick,
  preferredLanguage = "en",
}) {
  if (!isOpen) return null;

  return (
    <>
      <div className="modal-backdrop" onClick={onClose}></div>

      <div className="modal">
        <div className="modal-header">
          <h2>QueueIQ Assistant</h2>
          <button className="modal-close" onClick={onClose}>x</button>
        </div>

        <div className="modal-body">
          <ChatWidget
            messages={messages}
            onSend={onSend}
            disabled={disabled}
            done={done}
            progress={progress}
            onFinish={onFinish}
            onReset={onReset}
            loading={loading}
            hasResults={hasResults}
            loginRequired={loginRequired}
            onLoginClick={onLoginClick}
            onRegisterClick={onRegisterClick}
            preferredLanguage={preferredLanguage}
          />
        </div>
      </div>
    </>
  );
}
