import React from "react";

export default function PrivacyPage() {
  return (
    <div className="page-container">
      <div className="page-header" style={{ backgroundColor: "#006C84" }}>
        <h1>Privacy & Policy</h1>
      </div>

      <section className="panel privacy-content">
        <div className="policy-section">
          <h2>Privacy Policy</h2>
          <p>
            <strong>Last Updated: February 2026</strong>
          </p>

          <h3>1. Introduction</h3>
          <p>
            QueueIQ ("we", "our", or "us") is committed to protecting your privacy. This Privacy Policy 
            explains our practices regarding the collection, use, and protection of your personal information.
          </p>

          <h3>2. Information We Collect</h3>
          <ul>
            <li>Personal identification information (name, email, phone number, address)</li>
            <li>Patient intake data collected through our chatbot</li>
            <li>Usage analytics and website interaction data</li>
            <li>Device information and IP address</li>
          </ul>

          <h3>3. How We Use Your Information</h3>
          <ul>
            <li>To provide and improve our services</li>
            <li>To communicate with you about your account</li>
            <li>To comply with legal obligations</li>
            <li>To enhance user experience and optimize performance</li>
            <li>To prevent fraud and ensure security</li>
          </ul>

          <h3>4. Data Security</h3>
          <p>
            We implement industry-standard security measures to protect your personal information 
            from unauthorized access, alteration, disclosure, or destruction. All data is encrypted 
            in transit and at rest using SSL/TLS protocols.
          </p>

          <h3>5. HIPAA Compliance</h3>
          <p>
            QueueIQ is HIPAA compliant and maintains strict standards for handling Protected Health 
            Information (PHI). We ensure that all patient data is protected in accordance with HIPAA 
            regulations and industry best practices.
          </p>

          <h3>6. Third-Party Sharing</h3>
          <p>
            We do not sell, trade, or rent your personal information to third parties. We only share 
            information when necessary to provide services, comply with legal requirements, or with 
            your explicit consent.
          </p>

          <h3>7. User Rights</h3>
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

          <h3>8. Contact Us</h3>
          <p>
            For privacy-related inquiries, please contact us at: privacy@queueiq.com
          </p>
        </div>
      </section>
    </div>
  );
}
