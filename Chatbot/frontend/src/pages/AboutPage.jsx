import React from "react";

export default function AboutPage() {
  return (
    <div className="page-container">
      <div className="page-header" style={{ backgroundColor: "#FFCCBB" }}>
        <h1>About QueueIQ</h1>
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
          </div>

          <div className="about-image" style={{ backgroundColor: "#6EB5C0" }}>
            <div className="placeholder-image-large">
              Mission & Vision
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="about-content about-content-reverse">
          <div className="about-section">
            <h2>Our Story</h2>
            <p>
              Founded in 2024, QueueIQ emerged from a simple observation: healthcare facilities 
              struggle with inefficient queue management systems. Our team of experts combined 
              artificial intelligence, behavioral psychology, and operational excellence to create 
              a solution that works seamlessly across different clinic environments.
            </p>
            <p>
              Today, QueueIQ serves numerous healthcare facilities, helping them manage thousands 
              of patient arrivals daily with unprecedented efficiency.
            </p>
          </div>

          <div className="about-image" style={{ backgroundColor: "#006C84" }}>
            <div className="placeholder-image-large">
              Our Story
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="stats-grid">
          <div className="stat-card">
            <h3>500+</h3>
            <p>Healthcare Facilities</p>
          </div>
          <div className="stat-card">
            <h3>2M+</h3>
            <p>Patients Served</p>
          </div>
          <div className="stat-card">
            <h3>95%</h3>
            <p>Satisfaction Rate</p>
          </div>
          <div className="stat-card">
            <h3>24/7</h3>
            <p>Support Available</p>
          </div>
        </div>
      </section>
    </div>
  );
}
