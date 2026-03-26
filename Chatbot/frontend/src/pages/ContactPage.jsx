import React, { useState } from 'react';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_PATTERN = /^[0-9+()\-\s]{7,20}$/;

function validateContactForm(formData) {
  const errors = {};
  if (String(formData.name || '').trim().length < 2) {
    errors.name = 'Enter your full name.';
  }
  if (!String(formData.email || '').trim()) {
    errors.email = 'Enter your email address.';
  } else if (!EMAIL_PATTERN.test(String(formData.email || '').trim())) {
    errors.email = 'Enter a valid email address.';
  }
  if (String(formData.phone || '').trim() && !PHONE_PATTERN.test(String(formData.phone || '').trim())) {
    errors.phone = 'Enter a valid phone number.';
  }
  if (String(formData.subject || '').trim().length < 3) {
    errors.subject = 'Enter a short subject.';
  }
  if (String(formData.message || '').trim().length < 10) {
    errors.message = 'Message must be at least 10 characters.';
  }
  return errors;
}

function hasErrors(errors) {
  return Object.values(errors).some(Boolean);
}

export default function ContactPage() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    subject: '',
    message: '',
  });
  const [formErrors, setFormErrors] = useState({});
  const [successNotice, setSuccessNotice] = useState('');

  function handleChange(event) {
    const { name, value } = event.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));
    setFormErrors((prev) => ({ ...prev, [name]: '' }));
    setSuccessNotice('');
  }

  function handleSubmit(event) {
    event.preventDefault();
    const nextForm = {
      name: String(formData.name || '').trim(),
      email: String(formData.email || '').trim(),
      phone: String(formData.phone || '').trim(),
      subject: String(formData.subject || '').trim(),
      message: String(formData.message || '').trim(),
    };
    const nextErrors = validateContactForm(nextForm);
    if (hasErrors(nextErrors)) {
      setFormErrors(nextErrors);
      setSuccessNotice('');
      return;
    }
    setFormData({ name: '', email: '', phone: '', subject: '', message: '' });
    setFormErrors({});
    setSuccessNotice("Thank you for your message. We'll get back to you soon.");
  }

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Contact Us</h1>
        <p>We'd love to hear from you</p>
      </div>

      <section className="panel">
        <div className="contact-container">
          <div className="contact-info">
            <h2>Get in Touch</h2>
            <p style={{ color: '#555', marginBottom: '32px', lineHeight: '1.6' }}>
              Have questions about QueueIQ? Our team is here to help. Fill out the form or reach out to us directly.
            </p>

            <div className="info-item">
              <h3>Address</h3>
              <p>
                QueueIQ Headquarters<br />
                123 Healthcare Drive<br />
                Medical City, MC 12345<br />
                United States
              </p>
            </div>

            <div className="info-item">
              <h3>Phone</h3>
              <p>
                Main: +1 (555) 123-4567<br />
                Support: +1 (555) 987-6543<br />
                Hours: Monday - Friday, 9AM - 6PM EST
              </p>
            </div>

            <div className="info-item">
              <h3>Email</h3>
              <p>
                General: info@queueiq.com<br />
                Support: support@queueiq.com<br />
                Sales: sales@queueiq.com
              </p>
            </div>

            <div className="info-item">
              <h3>Follow Us</h3>
              <div className="social-links">
                <a href="#" style={{ color: 'var(--color-azure)' }}>LinkedIn</a>
                <a href="#" style={{ color: 'var(--color-water)' }}>Twitter</a>
                <a href="#" style={{ color: 'var(--color-peach)' }}>Facebook</a>
              </div>
            </div>
          </div>

          <div className="contact-form-wrapper">
            <form onSubmit={handleSubmit} className="contact-form" noValidate>
              <h2>Send us a Message</h2>

              <div className="form-group">
                <label htmlFor="name">Full Name *</label>
                <input type="text" id="name" name="name" value={formData.name} onChange={handleChange} placeholder="Your name" className={formErrors.name ? 'input-error' : ''} />
                {formErrors.name ? <div className="field-error-text">{formErrors.name}</div> : null}
              </div>

              <div className="form-group">
                <label htmlFor="email">Email Address *</label>
                <input type="email" id="email" name="email" value={formData.email} onChange={handleChange} placeholder="your@email.com" className={formErrors.email ? 'input-error' : ''} />
                {formErrors.email ? <div className="field-error-text">{formErrors.email}</div> : null}
              </div>

              <div className="form-group">
                <label htmlFor="phone">Phone Number</label>
                <input type="tel" id="phone" name="phone" value={formData.phone} onChange={handleChange} placeholder="+1 (555) 000-0000" className={formErrors.phone ? 'input-error' : ''} />
                {formErrors.phone ? <div className="field-error-text">{formErrors.phone}</div> : null}
              </div>

              <div className="form-group">
                <label htmlFor="subject">Subject *</label>
                <input type="text" id="subject" name="subject" value={formData.subject} onChange={handleChange} placeholder="How can we help?" className={formErrors.subject ? 'input-error' : ''} />
                {formErrors.subject ? <div className="field-error-text">{formErrors.subject}</div> : null}
              </div>

              <div className="form-group">
                <label htmlFor="message">Message *</label>
                <textarea id="message" name="message" value={formData.message} onChange={handleChange} placeholder="Your message here..." rows="6" className={formErrors.message ? 'input-error' : ''}></textarea>
                {formErrors.message ? <div className="field-error-text">{formErrors.message}</div> : null}
              </div>

              {successNotice ? <div className="inline-notice">{successNotice}</div> : null}
              <button type="submit" className="btn contact-submit-btn">
                Send Message
              </button>
            </form>
          </div>
        </div>
      </section>

      <section className="panel" style={{ backgroundColor: 'var(--color-air)', textAlign: 'center', marginTop: '32px' }}>
        <h2>Our Office Locations</h2>
        <div className="locations-grid">
          <div className="location-card">
            <div className="location-placeholder" style={{ backgroundColor: 'var(--color-peach)', fontSize: '48px' }}>
              NA
            </div>
            <h3>North America HQ</h3>
            <p>123 Healthcare Drive, Medical City, MC 12345</p>
          </div>
          <div className="location-card">
            <div className="location-placeholder" style={{ backgroundColor: 'var(--color-water)', fontSize: '48px' }}>
              EU
            </div>
            <h3>Europe Office</h3>
            <p>456 Medical Lane, Healthcare City, HC 67890</p>
          </div>
          <div className="location-card">
            <div className="location-placeholder" style={{ backgroundColor: 'var(--color-azure)', fontSize: '48px' }}>
              AP
            </div>
            <h3>Asia Pacific Office</h3>
            <p>789 Clinic Street, Hospital City, HC 11111</p>
          </div>
        </div>
      </section>
    </div>
  );
}

