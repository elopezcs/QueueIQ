import React, { useState } from "react";
import ChatWidget from "./ChatWidget.jsx";

export default function ChatbotModal({ isOpen, onClose, messages, onSend, disabled, done, progress, onFinish, onReset }) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="modal-backdrop" onClick={onClose}></div>

      {/* Modal */}
      <div className="modal">
        <div className="modal-header">
          <h2>QueueIQ Assistant</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
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
          />
        </div>
      </div>
    </>
  );
}
