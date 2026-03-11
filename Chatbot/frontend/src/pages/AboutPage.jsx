import React from "react";

export default function AboutPage() {
  return (
    <div className="page-container">
      <div className="page-header">
        <h1>About QueueIQ</h1>
        <p>Transforming healthcare operations through intelligent queue management</p>
      </div>

      <section className="panel">
        <div className="about-content">
          <div className="about-section">
            <h2>Our Mission</h2>
            <p>
              QueueIQ is dedicated to revolutionizing healthcare operations through intelligent 
              queue management and patient flow optimization. We believe that better queue management 
              leads to improved patient experiences and more efficient healthcare delivery.
            </p>
            <ul className="about-list">
              <li>✓ Reduce patient wait times</li>
              <li>✓ Optimize clinic resources</li>
              <li>✓ Enhance patient satisfaction</li>
            </ul>
          </div>

          <div className="about-image" style={{ backgroundColor: "var(--color-water)", display: "flex", alignItems: "center", justifyContent: "center", color: "white", fontSize: "48px" }}>
            🎯
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="about-content about-content-reverse">
          <div className="about-section">
            <h2>Our Story</h2>
            <p>
              Founded by a team of passionate students from Conestoga College, QueueIQ emerged from a simple observation: healthcare facilities 
              struggle with inefficient queue management systems. Our team combined 
              artificial intelligence, behavioral psychology, and operational excellence to create 
              a solution that works seamlessly across different clinic environments.
            </p>
            <p>
              Today, QueueIQ aims to serve numerous healthcare facilities, helping them manage thousands 
              of patient arrivals daily with unprecedented efficiency.
            </p>
          </div>

          <div className="about-image" style={{ backgroundColor: "var(--color-azure)", display: "flex", alignItems: "center", justifyContent: "center", color: "white", fontSize: "48px" }}>
            🚀
          </div>
        </div>
      </section>

      <section className="panel">
        <h2 style={{ textAlign: "center", color: "var(--color-azure)", marginBottom: "32px" }}>Our Impact</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon">🏥</div>
            <h3>500+</h3>
            <p>Healthcare Facilities</p>
          </div>
          <div className="stat-card">
            <div className="stat-icon">👥</div>
            <h3>2M+</h3>
            <p>Patients Served</p>
          </div>
          <div className="stat-card">
            <div className="stat-icon">⭐</div>
            <h3>95%</h3>
            <p>Satisfaction Rate</p>
          </div>
          <div className="stat-card">
            <div className="stat-icon">⏱️</div>
            <h3>-40%</h3>
            <p>Wait Times</p>
          </div>
        </div>
      </section>
    </div>
  );
}
