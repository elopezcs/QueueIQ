import React from "react";

export default function HomePage() {
  return (
    <div className="page-container">
      <header className="header">
        <h1>QueueIQ ArrivalSignal</h1>
        <p className="subtitle">Pre-arrival intake for operational queue planning (non-diagnostic)</p>
      </header>

      <section className="panel hero-section">
        <div className="hero-content">
          <h2>Welcome to QueueIQ</h2>
          <p>
            Our advanced chatbot system helps streamline clinic operations by intelligently routing 
            patient arrivals based on their needs and queue conditions.
          </p>
          <button className="btn hero-btn" onClick={() => window.scrollIntoView()}>
            Get Started
          </button>
        </div>
        <div className="hero-image">
          <div 
            className="placeholder-image" 
            style={{ backgroundColor: "#6EB5C0" }}
          >
            Chat Interface
          </div>
        </div>
      </section>

      <section className="features-section">
        <h2>Key Features</h2>
        <div className="features-grid">
          <div className="feature-card" style={{ borderTopColor: "#FFCCBB" }}>
            <div className="feature-icon" style={{ backgroundColor: "#FFCCBB" }}>🔄</div>
            <h3>Smart Routing</h3>
            <p>Intelligent patient routing based on queue conditions and priority levels.</p>
          </div>
          <div className="feature-card" style={{ borderTopColor: "#6EB5C0" }}>
            <div className="feature-icon" style={{ backgroundColor: "#6EB5C0" }}>💬</div>
            <h3>Interactive Chat</h3>
            <p>Engaging chatbot interface for pre-arrival data collection.</p>
          </div>
          <div className="feature-card" style={{ borderTopColor: "#006C84" }}>
            <div className="feature-icon" style={{ backgroundColor: "#006C84" }}>📊</div>
            <h3>Real-time Analytics</h3>
            <p>Monitor queue status and patient flow in real-time.</p>
          </div>
          <div className="feature-card" style={{ borderTopColor: "#E2E8E4" }}>
            <div className="feature-icon" style={{ backgroundColor: "#E2E8E4" }}>🔒</div>
            <h3>Secure & Reliable</h3>
            <p>Enterprise-grade security for patient data protection.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
