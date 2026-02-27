import React from "react";

export default function PrivacyPage() {
  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Privacy & Policy</h1>
        <p>Your data security and privacy are our top priorities</p>
      </div>

      <div className="privacy-grid">
        <section className="panel privacy-content">
          <div className="policy-section">
            <h2>Privacy Policy</h2>
            <p className="last-updated">
              <strong>Last Updated: February 2026</strong>
            </p>

            <div className="policy-card">
              <h3><span className="policy-icon">📝</span> 1. Introduction</h3>
              <p>
                QueueIQ ("we", "our", or "us") is committed to protecting your privacy. This Privacy Policy 
                explains our practices regarding the collection, use, and protection of your personal information.
              </p>
            </div>

            <div className="policy-card">
              <h3><span className="policy-icon">📊</span> 2. Information We Collect</h3>
              <ul>
                <li>Personal identification information (name, email, phone number, address)</li>
                <li>Patient intake data collected through our chatbot</li>
                <li>Usage analytics and website interaction data</li>
                <li>Device information and IP address</li>
              </ul>
            </div>

            <div className="policy-card">
              <h3><span className="policy-icon">⚙️</span> 3. How We Use Your Information</h3>
              <ul>
                <li>To provide and improve our services</li>
                <li>To communicate with you about your account</li>
                <li>To comply with legal obligations</li>
                <li>To enhance user experience and optimize performance</li>
                <li>To prevent fraud and ensure security</li>
              </ul>
            </div>

            <div className="policy-card">
              <h3><span className="policy-icon">🔒</span> 4. Data Security</h3>
              <p>
                We implement industry-standard security measures to protect your personal information 
                from unauthorized access, alteration, disclosure, or destruction. All data is encrypted 
                in transit and at rest using SSL/TLS protocols.
              </p>
            </div>

            <div className="policy-card">
              <h3><span className="policy-icon">🏥</span> 5. HIPAA Compliance</h3>
              <p>
                QueueIQ is HIPAA compliant and maintains strict standards for handling Protected Health 
                Information (PHI). We ensure that all patient data is protected in accordance with HIPAA 
                regulations and industry best practices.
              </p>
            </div>

            <div className="policy-card">
              <h3><span className="policy-icon">🤝</span> 6. Third-Party Sharing</h3>
              <p>
                We do not sell, trade, or rent your personal information to third parties. We only share 
                information when necessary to provide services, comply with legal requirements, or with 
                your explicit consent.
              </p>
            </div>

            <div className="policy-card">
              <h3><span className="policy-icon">👤</span> 7. User Rights</h3>
              <p>
                You have the right to:
              </p>
              <ul>
                <li>Access your personal data</li>
                <li>Request correction of inaccurate data</li>
                <li>Request deletion of your data</li>
                <li>Opt-out of marketing communications</li>
                <li>Data portability</li>
              </ul>
            </div>

            <div className="policy-card">
              <h3><span className="policy-icon">✉️</span> 8. Contact Us</h3>
              <p>
                For privacy-related inquiries, please contact us at: <strong>privacy@queueiq.com</strong>
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
