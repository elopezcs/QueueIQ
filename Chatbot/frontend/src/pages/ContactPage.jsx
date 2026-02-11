import React, { useState } from "react";

export default function ContactPage() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    subject: "",
    message: ""
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    alert("Thank you for your message! We'll get back to you soon.");
    setFormData({
      name: "",
      email: "",
      phone: "",
      subject: "",
      message: ""
    });
  };

  return (
    <div className="page-container">
      <div className="page-header" style={{ backgroundColor: "#E2E8E4" }}>
        <h1>Contact Us</h1>
        <p>We'd love to hear from you</p>
      </div>

      <section className="panel">
        <div className="contact-container">
          <div className="contact-info">
            <h2>Get in Touch</h2>
            <div className="info-item">
              <h3>Address</h3>
              <p>
                QueueIQ Headquarters<br/>
                123 Healthcare Drive<br/>
                Medical City, MC 12345<br/>
                United States
              </p>
            </div>

            <div className="info-item">
              <h3>Phone</h3>
              <p>
                Main: +1 (555) 123-4567<br/>
                Support: +1 (555) 987-6543<br/>
                Hours: Monday - Friday, 9AM - 6PM EST
              </p>
            </div>

            <div className="info-item">
              <h3>Email</h3>
              <p>
                General: info@queueiq.com<br/>
                Support: support@queueiq.com<br/>
                Sales: sales@queueiq.com
              </p>
            </div>

            <div className="info-item">
              <h3>Follow Us</h3>
              <div className="social-links">
                <a href="#" style={{ color: "#FFCCBB" }}>LinkedIn</a>
                <a href="#" style={{ color: "#6EB5C0" }}>Twitter</a>
                <a href="#" style={{ color: "#006C84" }}>Facebook</a>
              </div>
            </div>
          </div>

          <div className="contact-form-wrapper">
            <form onSubmit={handleSubmit} className="contact-form">
              <h2>Send us a Message</h2>
              
              <div className="form-group">
                <label htmlFor="name">Full Name *</label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleChange}
                  required
                  placeholder="Your name"
                />
              </div>

              <div className="form-group">
                <label htmlFor="email">Email Address *</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  required
                  placeholder="your@email.com"
                />
              </div>

              <div className="form-group">
                <label htmlFor="phone">Phone Number</label>
                <input
                  type="tel"
                  id="phone"
                  name="phone"
                  value={formData.phone}
                  onChange={handleChange}
                  placeholder="+1 (555) 000-0000"
                />
              </div>

              <div className="form-group">
                <label htmlFor="subject">Subject *</label>
                <input
                  type="text"
                  id="subject"
                  name="subject"
                  value={formData.subject}
                  onChange={handleChange}
                  required
                  placeholder="How can we help?"
                />
              </div>

              <div className="form-group">
                <label htmlFor="message">Message *</label>
                <textarea
                  id="message"
                  name="message"
                  value={formData.message}
                  onChange={handleChange}
                  required
                  placeholder="Your message here..."
                  rows="6"
                ></textarea>
              </div>

              <button type="submit" className="btn">Send Message</button>
            </form>
          </div>
        </div>
      </section>

      <section className="panel" style={{ backgroundColor: "#f9f9f9", textAlign: "center" }}>
        <h2>Our Office Locations</h2>
        <div className="locations-grid">
          <div className="location-card">
            <div className="location-placeholder" style={{ backgroundColor: "#FFCCBB" }}>
              New York
            </div>
            <h3>North America HQ</h3>
            <p>123 Healthcare Drive, Medical City, MC 12345</p>
          </div>
          <div className="location-card">
            <div className="location-placeholder" style={{ backgroundColor: "#6EB5C0" }}>
              London
            </div>
            <h3>Europe Office</h3>
            <p>456 Medical Lane, Healthcare City, HC 67890</p>
          </div>
          <div className="location-card">
            <div className="location-placeholder" style={{ backgroundColor: "#006C84" }}>
              Singapore
            </div>
            <h3>Asia Pacific Office</h3>
            <p>789 Clinic Street, Hospital City, HC 11111</p>
          </div>
        </div>
      </section>
    </div>
  );
}
