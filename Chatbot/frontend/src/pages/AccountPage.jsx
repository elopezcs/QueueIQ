import React, { useEffect, useState } from 'react';

import {
  deleteQueuePatientRecord,
  getActiveQueueRecords,
  getPublicTraceabilityDetail,
  getQueueControlClinics,
  predictQueueSurge,
  predictQueueWaitTime,
  updateQueuePatientTriage,
} from '../api';

const DASHBOARD_URLS = {
  patient: import.meta.env.VITE_PATIENT_DASHBOARD_URL || 'http://127.0.0.1:8501?view=patient',
  reception: import.meta.env.VITE_RECEPTION_DASHBOARD_URL || 'http://127.0.0.1:8501?view=reception',
  manager: import.meta.env.VITE_MANAGER_DASHBOARD_URL || 'http://127.0.0.1:8501?view=manager',
};

const EMPTY_PATIENT_PROFILE = {
  fullName: '',
  preferredLanguage: 'en',
  dateOfBirth: '',
  sex: '',
  heightCm: '',
  weightKg: '',
  bloodGroup: '',
  allergies: '',
  medications: '',
  chronicConditions: '',
  pastSurgeries: '',
  primaryPhysician: '',
  emergencyContactName: '',
  emergencyContactPhone: '',
  smokingStatus: '',
  pregnancyStatus: '',
  mobilityNotes: '',
  medicalNotes: '',
};

const EMPTY_STAFF_PROFILE = {
  fullName: '',
  jobTitle: '',
  department: '',
  licenseType: '',
  licenseNumber: '',
  licenseExpiry: '',
  specialty: '',
  certifications: '',
  yearsExperience: '',
  languagesSpoken: '',
  shiftPreference: '',
  supervisorName: '',
  employmentStartDate: '',
  staffNotes: '',
};

function formatDateTime(value) {
  if (!value) {
    return 'Not available';
  }
  return new Date(value).toLocaleString([], {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatDateOnly(value) {
  if (!value) {
    return 'Not available';
  }
  return new Date(value).toLocaleDateString([], {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatTimeOnly(value) {
  if (!value) {
    return 'Not available';
  }
  return new Date(value).toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatDurationMinutes(value) {
  const totalMinutes = Number(value);
  if (!Number.isFinite(totalMinutes)) {
    return 'Not available';
  }
  const safeMinutes = Math.max(0, Math.round(totalMinutes));
  const hours = Math.floor(safeMinutes / 60);
  const minutes = safeMinutes % 60;
  if (hours === 0) {
    return `${minutes}m`;
  }
  if (minutes === 0) {
    return `${hours}h`;
  }
  return `${hours}h ${minutes}m`;
}

function normalizeQueueExplorerClinic(clinic) {
  return {
    id: String(clinic?.clinic_id || clinic?.id || ''),
    name: String(clinic?.clinic_name || clinic?.name || ''),
  };
}

function normalizeQueueExplorerRecord(record) {
  return {
    recordId: String(record?.record_id ?? ''),
    clinicName: String(record?.clinic_name || record?.clinicName || ''),
    patientId: String(record?.patient_id ?? record?.patientId ?? ''),
    arrivalTime: record?.arrival_time || record?.arrivalTime || '',
    priority: Number(record?.priority ?? 0),
    estDuration: Number(record?.est_duration ?? record?.estDuration ?? 0),
    chatSessionId: String(record?.chat_session_id || record?.chatSessionId || ''),
  };
}

function formatProbabilityLabel(value) {
  const probability = Number(value);
  if (!Number.isFinite(probability)) {
    return 'Not available';
  }
  return `${Math.round(Math.max(0, Math.min(1, probability)) * 100)}%`;
}

function getSurgeRiskLabel(value) {
  const probability = Number(value);
  if (!Number.isFinite(probability)) {
    return 'Unavailable';
  }
  if (probability >= 0.7) {
    return 'High surge risk';
  }
  if (probability >= 0.4) {
    return 'Moderate surge risk';
  }
  return 'Low surge risk';
}

function formatWaitElapsed(value) {
  if (!value) {
    return 'Not available';
  }
  const parsed = new Date(value).getTime();
  if (!Number.isFinite(parsed)) {
    return 'Not available';
  }
  const elapsedMinutes = Math.max(0, Math.round((Date.now() - parsed) / 60000));
  return formatDurationMinutes(elapsedMinutes);
}

function defaultDurationForPriority(priority) {
  return { 1: 60, 2: 40, 3: 20, 4: 10, 5: 5 }[Number(priority)] || 5;
}

function formatClinicFallback(value) {
  return String(value || '')
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function formatRoleLabel(value) {
  const role = String(value || '').toLowerCase();
  if (role === 'staff') {
    return 'Staff';
  }
  if (role === 'manager') {
    return 'Manager';
  }
  return 'Patient';
}

function formatTimeBucketLabel(value) {
  const normalized = String(value || '').toLowerCase();
  if (normalized === 'upcoming') {
    return 'Upcoming';
  }
  if (normalized === 'past') {
    return 'Past';
  }
  return 'Today';
}

function relativeLabel(value) {
  const now = new Date();
  const target = new Date(value);
  const diffDays = Math.round((target.getTime() - now.getTime()) / 86400000);
  if (diffDays === 0) {
    return 'Today';
  }
  if (diffDays === 1) {
    return 'Tomorrow';
  }
  if (diffDays > 1) {
    return `In ${diffDays} days`;
  }
  if (diffDays === -1) {
    return 'Yesterday';
  }
  return `${Math.abs(diffDays)} days ago`;
}

function resolveClinicLabel(clinics, clinicId) {
  if (!clinicId) {
    return 'Not assigned';
  }
  const match = clinics.find((clinic) => clinic.id === clinicId);
  return match ? match.name : formatClinicFallback(clinicId);
}

function sectionCopy(currentUser, activeSection) {
  const role = String(currentUser?.role || '').toLowerCase();
  if (!currentUser) {
    return {
      title: 'QueueIQ Account Access',
      description: 'Patients can register directly, while staff and manager workflows open after sign-in.',
    };
  }
  if (role === 'patient' && activeSection === 'profile') {
    return {
      title: 'Patient Profile',
      description: 'Review the account details connected to your chatbot-based appointments.',
    };
  }
  if (role === 'staff' && activeSection === 'profile') {
    return {
      title: 'Staff Profile',
      description: 'Review your clinic assignment and the details tied to your staff access.',
    };
  }
  if (role === 'staff') {
    return {
      title: 'Staff Dashboard',
      description: 'Use your clinic search tools to review today, upcoming, and past appointments.',
    };
  }
  if (role === 'manager' && activeSection === 'dashboard') {
    return {
      title: 'Manager Appointment Dashboard',
      description: 'Search appointments by patient, email, booking token, or appointment ID across one clinic or all clinics.',
    };
  }
  if (role === 'manager' && activeSection === 'add-member') {
    return {
      title: 'Add Member Dashboard',
      description: 'Search all staff accounts, review clinic assignments, and open the add-member form when you need a new staff account.',
    };
  }
  if (role === 'manager') {
    return {
      title: 'Simulation Dashboard',
      description: 'Open QueueControl to explore queue behavior and make better clinic operations decisions.',
    };
  }
  return {
    title: 'My Appointments',
    description: 'Start the chatbot to assess your visit, then book directly from the final QueueIQ result.',
  };
}

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function isValidEmail(value) {
  return EMAIL_PATTERN.test(String(value || '').trim());
}

function validateLoginForm(form) {
  const email = String(form.email || '').trim();
  const password = String(form.password || '');
  if (!email) {
    return 'Enter your email address.';
  }
  if (!isValidEmail(email)) {
    return 'Enter a valid email address.';
  }
  if (!password.trim()) {
    return 'Enter your password.';
  }
  return '';
}

function validateRegisterForm(form) {
  const fullName = String(form.fullName || '').trim();
  const email = String(form.email || '').trim();
  const password = String(form.password || '');
  if (fullName.length < 2) {
    return 'Enter your full name.';
  }
  if (!email) {
    return 'Enter your email address.';
  }
  if (!isValidEmail(email)) {
    return 'Enter a valid email address.';
  }
  if (password.trim().length < 8) {
    return 'Password must be at least 8 characters.';
  }
  return '';
}

function validateStaffForm(form) {
  const fullName = String(form.fullName || '').trim();
  const email = String(form.email || '').trim();
  const password = String(form.password || '');
  if (fullName.length < 2) {
    return 'Enter the staff member full name.';
  }
  if (!email) {
    return 'Enter the staff member email address.';
  }
  if (!isValidEmail(email)) {
    return 'Enter a valid staff email address.';
  }
  if (password.trim().length < 8) {
    return 'Temporary password must be at least 8 characters.';
  }
  if (!String(form.clinicId || '').trim()) {
    return 'Choose a clinic assignment.';
  }
  return '';
}

function validateStaffSearch(form) {
  const patientQuery = String(form.patientQuery || '').trim();
  if (patientQuery.length > 120) {
    return 'Search text must be 120 characters or less.';
  }
  if (form.scheduledFrom && form.scheduledTo) {
    const from = new Date(form.scheduledFrom).getTime();
    const to = new Date(form.scheduledTo).getTime();
    if (Number.isFinite(from) && Number.isFinite(to) && from > to) {
      return 'The start date must be earlier than the end date.';
    }
  }
  return '';
}

function collectLoginErrors(form) {
  const errors = {};
  const email = String(form.email || '').trim();
  const password = String(form.password || '');
  if (!email) {
    errors.email = 'Enter your email address.';
  } else if (!isValidEmail(email)) {
    errors.email = 'Enter a valid email address.';
  }
  if (!password.trim()) {
    errors.password = 'Enter your password.';
  }
  return errors;
}

function collectRegisterErrors(form) {
  const errors = {};
  const fullName = String(form.fullName || '').trim();
  const email = String(form.email || '').trim();
  const password = String(form.password || '');
  if (fullName.length < 2) {
    errors.fullName = 'Enter your full name.';
  }
  if (!email) {
    errors.email = 'Enter your email address.';
  } else if (!isValidEmail(email)) {
    errors.email = 'Enter a valid email address.';
  }
  if (password.trim().length < 8) {
    errors.password = 'Password must be at least 8 characters.';
  }
  return errors;
}

function collectStaffFormErrors(form) {
  const errors = {};
  const fullName = String(form.fullName || '').trim();
  const email = String(form.email || '').trim();
  const password = String(form.password || '');
  if (fullName.length < 2) {
    errors.fullName = 'Enter the staff member full name.';
  }
  if (!email) {
    errors.email = 'Enter the staff member email address.';
  } else if (!isValidEmail(email)) {
    errors.email = 'Enter a valid staff email address.';
  }
  if (password.trim().length < 8) {
    errors.password = 'Temporary password must be at least 8 characters.';
  }
  if (!String(form.clinicId || '').trim()) {
    errors.clinicId = 'Choose a clinic assignment.';
  }
  return errors;
}

function hasFieldErrors(errors) {
  return Object.values(errors).some(Boolean);
}

function normalizePatientProfile(currentUser) {
  const profile = currentUser?.medical_profile || {};
  return {
    fullName: currentUser?.full_name || '',
    preferredLanguage: profile.preferred_language || 'en',
    dateOfBirth: profile.date_of_birth || '',
    sex: profile.sex || '',
    heightCm: profile.height_cm ?? '',
    weightKg: profile.weight_kg ?? '',
    bloodGroup: profile.blood_group || '',
    allergies: profile.allergies || '',
    medications: profile.medications || '',
    chronicConditions: profile.chronic_conditions || '',
    pastSurgeries: profile.past_surgeries || '',
    primaryPhysician: profile.primary_physician || '',
    emergencyContactName: profile.emergency_contact_name || '',
    emergencyContactPhone: profile.emergency_contact_phone || '',
    smokingStatus: profile.smoking_status || '',
    pregnancyStatus: profile.pregnancy_status || '',
    mobilityNotes: profile.mobility_notes || '',
    medicalNotes: profile.medical_notes || '',
  };
}

function normalizeStaffProfile(currentUser) {
  const profile = currentUser?.professional_profile || {};
  return {
    fullName: currentUser?.full_name || '',
    jobTitle: profile.job_title || '',
    department: profile.department || '',
    licenseType: profile.license_type || '',
    licenseNumber: profile.license_number || '',
    licenseExpiry: profile.license_expiry || '',
    specialty: profile.specialty || '',
    certifications: profile.certifications || '',
    yearsExperience: profile.years_experience ?? '',
    languagesSpoken: profile.languages_spoken || '',
    shiftPreference: profile.shift_preference || '',
    supervisorName: profile.supervisor_name || '',
    employmentStartDate: profile.employment_start_date || '',
    staffNotes: profile.staff_notes || '',
  };
}

function collectPatientProfileErrors(form) {
  const errors = {};
  if (String(form.fullName || '').trim().length < 2) {
    errors.fullName = 'Enter your full name.';
  }
  if (form.heightCm !== '' && Number(form.heightCm) <= 0) {
    errors.heightCm = 'Enter a valid height.';
  }
  if (form.weightKg !== '' && Number(form.weightKg) <= 0) {
    errors.weightKg = 'Enter a valid weight.';
  }
  return errors;
}

function collectStaffProfileErrors(form) {
  const errors = {};
  if (String(form.fullName || '').trim().length < 2) {
    errors.fullName = 'Enter your full name.';
  }
  if (form.yearsExperience !== '' && Number(form.yearsExperience) < 0) {
    errors.yearsExperience = 'Years of experience cannot be negative.';
  }
  return errors;
}

function AppointmentList({ clinics, appointments, emptyMessage }) {
  if (!appointments.length) {
    return <p className="muted">{emptyMessage}</p>;
  }

  return (
    <div className="appointment-history-list professional-history-list">
      {appointments.map((appointment, index) => (
        <article key={appointment.appointment_id} className="history-entry-card">
          <div className="history-entry-rail">
            <span className="history-entry-dot" />
            {index !== appointments.length - 1 ? <span className="history-entry-line" /> : null}
          </div>
          <div className="history-entry-content">
            <div className="history-entry-topline">
              <div>
                <h4>{resolveClinicLabel(clinics, appointment.clinic_id)}</h4>
                <div className="muted small">Booked for {formatDateTime(appointment.scheduled_for)}</div>
              </div>
              <span className={`status-pill ${appointment.status === 'scheduled' ? 'scheduled' : 'completed'}`}>{appointment.status}</span>
            </div>
            <div className="history-entry-details appointment-detail-grid">
              <div>
                <span className="meta-label">Date</span>
                <span>{formatDateOnly(appointment.scheduled_for)}</span>
              </div>
              <div>
                <span className="meta-label">Time</span>
                <span>{formatTimeOnly(appointment.scheduled_for)}</span>
              </div>
              <div>
                <span className="meta-label">Relative</span>
                <span>{relativeLabel(appointment.scheduled_for)}</span>
              </div>
              <div>
                <span className="meta-label">Description</span>
                <span>{appointment.description || 'No description added.'}</span>
              </div>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

function DemoAccessCards({ clinics, demoUsers, authLoading, onDemoLogin }) {
  const visibleDemoUsers = demoUsers.slice(0, 6);
  if (!visibleDemoUsers.length) {
    return null;
  }

  return (
    <section className="panel account-panel">
      <div className="panel-heading-row">
        <div>
          <h2 className="section-title">Local Demo Access</h2>
          <p className="section-subtitle">Use these seeded accounts to verify patient, staff, and manager flows locally.</p>
        </div>
      </div>
      <div className="auth-entry-grid">
        {demoUsers.length > visibleDemoUsers.length ? <div className="muted small">Showing {visibleDemoUsers.length} of {demoUsers.length} demo accounts.</div> : null}
        {visibleDemoUsers.map((user) => (
          <article key={user.email} className="auth-card">
            <div>
              <div className="eyebrow-label">{formatRoleLabel(user.role)}</div>
              <h3>{user.full_name}</h3>
            </div>
            <div className="muted small">{user.email}</div>
            {user.clinic_id ? <div className="muted small">Clinic: {resolveClinicLabel(clinics, user.clinic_id)}</div> : null}
            <button type="button" className="btn secondary" onClick={() => onDemoLogin(user.email)} disabled={authLoading}>
              Open Demo Account
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

function StaffResultsTable({ clinics, staffAppointments }) {
  if (!staffAppointments.results.length) {
    return <p className="muted">No appointments matched the current filters.</p>;
  }

  return (
    <div className="table-responsive">
      <table className="results-table">
        <thead>
          <tr>
            <th>Patient</th>
            <th>Booking Token</th>
            <th>Email</th>
            <th>Clinic</th>
            <th>Date</th>
            <th>Time</th>
            <th>Status</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {staffAppointments.results.map((appointment) => (
            <tr key={appointment.appointment_id}>
              <td>{appointment.full_name}</td>
              <td>{appointment.booking_token || `BKG-${String(appointment.appointment_id || '').toUpperCase()}`}</td>
              <td>{appointment.email}</td>
              <td>{resolveClinicLabel(clinics, appointment.clinic_id)}</td>
              <td>{formatDateOnly(appointment.scheduled_for)}</td>
              <td>{formatTimeOnly(appointment.scheduled_for)}</td>
              <td>{appointment.status}</td>
              <td>{appointment.description || 'No description added.'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProfileIdentityCard({ clinics, currentUser }) {
  return (
    <article className="auth-card profile-identity-card">
      <div className="eyebrow-label">Account</div>
      <h3>{currentUser.full_name}</h3>
      <div className="profile-meta-row">
        <span>Email</span>
        <strong>{currentUser.email}</strong>
      </div>
      <div className="profile-meta-row">
        <span>Role</span>
        <strong>{formatRoleLabel(currentUser.role)}</strong>
      </div>
      <div className="profile-meta-row">
        <span>Email verified</span>
        <strong>{currentUser.email_verified ? 'Yes' : 'No'}</strong>
      </div>
      <div className="profile-meta-row">
        <span>Clinic</span>
        <strong>{resolveClinicLabel(clinics, currentUser.clinic_id)}</strong>
      </div>
    </article>
  );
}

function PatientProfileSection({ clinics, currentUser, onBeginBookingJourney, onUpdateProfile, profileSaving, profileNotice }) {
  const [form, setForm] = useState(EMPTY_PATIENT_PROFILE);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    setForm(normalizePatientProfile(currentUser));
    setErrors({});
  }, [currentUser]);

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: '' }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = collectPatientProfileErrors(form);
    if (hasFieldErrors(nextErrors)) {
      setErrors(nextErrors);
      return;
    }
    await onUpdateProfile({
      full_name: form.fullName.trim(),
      preferred_language: form.preferredLanguage || 'en',
      date_of_birth: form.dateOfBirth,
      sex: form.sex,
      height_cm: form.heightCm === '' ? null : Number(form.heightCm),
      weight_kg: form.weightKg === '' ? null : Number(form.weightKg),
      blood_group: form.bloodGroup,
      allergies: form.allergies,
      medications: form.medications,
      chronic_conditions: form.chronicConditions,
      past_surgeries: form.pastSurgeries,
      primary_physician: form.primaryPhysician,
      emergency_contact_name: form.emergencyContactName,
      emergency_contact_phone: form.emergencyContactPhone,
      smoking_status: form.smokingStatus,
      pregnancy_status: form.pregnancyStatus,
      mobility_notes: form.mobilityNotes,
      medical_notes: form.medicalNotes,
    });
  }

  return (
    <section className="panel account-panel">
      <div className="panel-heading-row profile-header-row">
        <div>
          <h2 className="section-title">Profile</h2>
          <p className="section-subtitle">Keep your saved health background up to date so the chatbot can personalize future intake questions.</p>
          <div className="muted small">Book Appointment takes you back to the home page and opens the chatbot intake flow.</div>
        </div>
        <button type="button" className="btn" onClick={onBeginBookingJourney}>Book Appointment</button>
      </div>
      <div className="profile-layout-grid">
        <ProfileIdentityCard clinics={clinics} currentUser={currentUser} />
        <form className="auth-card profile-editor-card" onSubmit={handleSubmit} noValidate>
          <div><div className="eyebrow-label">Health Profile</div><h3>Update personal and medical details</h3></div>
          <div className="profile-form-grid two-column">
            <div className="field"><label htmlFor="patient-full-name">Full name</label><input id="patient-full-name" type="text" value={form.fullName} onChange={(event) => updateField('fullName', event.target.value)} className={errors.fullName ? 'input-error' : ''} />{errors.fullName ? <div className="field-error-text">{errors.fullName}</div> : null}</div>
            <div className="field">
              <label htmlFor="patient-preferred-language">Preferred language</label>
              <select id="patient-preferred-language" value={form.preferredLanguage} onChange={(event) => updateField('preferredLanguage', event.target.value)}>
                <option value="en">English</option>
                <option value="fr">French</option>
                <option value="es">Spanish</option>
              </select>
            </div>
            <div className="field"><label htmlFor="patient-dob">Date of birth</label><input id="patient-dob" type="date" value={form.dateOfBirth} onChange={(event) => updateField('dateOfBirth', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-sex">Sex</label><input id="patient-sex" type="text" value={form.sex} onChange={(event) => updateField('sex', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-blood-group">Blood group</label><input id="patient-blood-group" type="text" value={form.bloodGroup} onChange={(event) => updateField('bloodGroup', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-height">Height (cm)</label><input id="patient-height" type="number" min="0" step="0.1" value={form.heightCm} onChange={(event) => updateField('heightCm', event.target.value)} className={errors.heightCm ? 'input-error' : ''} />{errors.heightCm ? <div className="field-error-text">{errors.heightCm}</div> : null}</div>
            <div className="field"><label htmlFor="patient-weight">Weight (kg)</label><input id="patient-weight" type="number" min="0" step="0.1" value={form.weightKg} onChange={(event) => updateField('weightKg', event.target.value)} className={errors.weightKg ? 'input-error' : ''} />{errors.weightKg ? <div className="field-error-text">{errors.weightKg}</div> : null}</div>
            <div className="field field-span-2"><label htmlFor="patient-allergies">Allergies</label><textarea id="patient-allergies" rows="3" value={form.allergies} onChange={(event) => updateField('allergies', event.target.value)} /></div>
            <div className="field field-span-2"><label htmlFor="patient-medications">Current medications</label><textarea id="patient-medications" rows="3" value={form.medications} onChange={(event) => updateField('medications', event.target.value)} /></div>
            <div className="field field-span-2"><label htmlFor="patient-conditions">Chronic conditions</label><textarea id="patient-conditions" rows="3" value={form.chronicConditions} onChange={(event) => updateField('chronicConditions', event.target.value)} /></div>
            <div className="field field-span-2"><label htmlFor="patient-surgeries">Past surgeries</label><textarea id="patient-surgeries" rows="3" value={form.pastSurgeries} onChange={(event) => updateField('pastSurgeries', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-physician">Primary physician</label><input id="patient-physician" type="text" value={form.primaryPhysician} onChange={(event) => updateField('primaryPhysician', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-smoking">Smoking status</label><input id="patient-smoking" type="text" value={form.smokingStatus} onChange={(event) => updateField('smokingStatus', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-emergency-name">Emergency contact name</label><input id="patient-emergency-name" type="text" value={form.emergencyContactName} onChange={(event) => updateField('emergencyContactName', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-emergency-phone">Emergency contact phone</label><input id="patient-emergency-phone" type="text" value={form.emergencyContactPhone} onChange={(event) => updateField('emergencyContactPhone', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-pregnancy">Pregnancy status</label><input id="patient-pregnancy" type="text" value={form.pregnancyStatus} onChange={(event) => updateField('pregnancyStatus', event.target.value)} /></div>
            <div className="field"><label htmlFor="patient-mobility">Mobility notes</label><input id="patient-mobility" type="text" value={form.mobilityNotes} onChange={(event) => updateField('mobilityNotes', event.target.value)} /></div>
            <div className="field field-span-2"><label htmlFor="patient-medical-notes">Additional medical notes</label><textarea id="patient-medical-notes" rows="4" value={form.medicalNotes} onChange={(event) => updateField('medicalNotes', event.target.value)} /></div>
          </div>
          {profileNotice ? <div className={`inline-notice ${profileNotice.toLowerCase().includes('success') ? '' : 'error'}`}>{profileNotice}</div> : null}
          <button type="submit" className="btn" disabled={profileSaving}>{profileSaving ? 'Saving...' : 'Save Profile'}</button>
        </form>
      </div>
    </section>
  );
}

function StaffProfileSection({ clinics, currentUser, onUpdateProfile, profileSaving, profileNotice }) {
  const [form, setForm] = useState(EMPTY_STAFF_PROFILE);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    setForm(normalizeStaffProfile(currentUser));
    setErrors({});
  }, [currentUser]);

  function updateField(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setErrors((current) => ({ ...current, [field]: '' }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextErrors = collectStaffProfileErrors(form);
    if (hasFieldErrors(nextErrors)) {
      setErrors(nextErrors);
      return;
    }
    await onUpdateProfile({
      full_name: form.fullName.trim(),
      job_title: form.jobTitle,
      department: form.department,
      license_type: form.licenseType,
      license_number: form.licenseNumber,
      license_expiry: form.licenseExpiry,
      specialty: form.specialty,
      certifications: form.certifications,
      years_experience: form.yearsExperience === '' ? null : Number(form.yearsExperience),
      languages_spoken: form.languagesSpoken,
      shift_preference: form.shiftPreference,
      supervisor_name: form.supervisorName,
      employment_start_date: form.employmentStartDate,
      staff_notes: form.staffNotes,
    });
  }

  return (
    <section className="panel account-panel">
      <div className="panel-heading-row profile-header-row">
        <div>
          <h2 className="section-title">Profile</h2>
          <p className="section-subtitle">Keep your operational role, credentialing, and scheduling details current for the clinic team.</p>
        </div>
      </div>
      <div className="profile-layout-grid">
        <ProfileIdentityCard clinics={clinics} currentUser={currentUser} />
        <form className="auth-card profile-editor-card" onSubmit={handleSubmit} noValidate>
          <div><div className="eyebrow-label">Professional Profile</div><h3>Update staff details</h3></div>
          <div className="profile-form-grid two-column">
            <div className="field"><label htmlFor="staff-full-name">Full name</label><input id="staff-full-name" type="text" value={form.fullName} onChange={(event) => updateField('fullName', event.target.value)} className={errors.fullName ? 'input-error' : ''} />{errors.fullName ? <div className="field-error-text">{errors.fullName}</div> : null}</div>
            <div className="field"><label htmlFor="staff-job-title">Job title</label><input id="staff-job-title" type="text" value={form.jobTitle} onChange={(event) => updateField('jobTitle', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-department">Department</label><input id="staff-department" type="text" value={form.department} onChange={(event) => updateField('department', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-specialty">Specialty</label><input id="staff-specialty" type="text" value={form.specialty} onChange={(event) => updateField('specialty', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-license-type">License type</label><input id="staff-license-type" type="text" value={form.licenseType} onChange={(event) => updateField('licenseType', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-license-number">License number</label><input id="staff-license-number" type="text" value={form.licenseNumber} onChange={(event) => updateField('licenseNumber', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-license-expiry">License expiry</label><input id="staff-license-expiry" type="date" value={form.licenseExpiry} onChange={(event) => updateField('licenseExpiry', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-experience">Years of experience</label><input id="staff-experience" type="number" min="0" step="0.1" value={form.yearsExperience} onChange={(event) => updateField('yearsExperience', event.target.value)} className={errors.yearsExperience ? 'input-error' : ''} />{errors.yearsExperience ? <div className="field-error-text">{errors.yearsExperience}</div> : null}</div>
            <div className="field field-span-2"><label htmlFor="staff-certifications">Certifications</label><textarea id="staff-certifications" rows="3" value={form.certifications} onChange={(event) => updateField('certifications', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-languages">Languages spoken</label><input id="staff-languages" type="text" value={form.languagesSpoken} onChange={(event) => updateField('languagesSpoken', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-shift">Shift preference</label><input id="staff-shift" type="text" value={form.shiftPreference} onChange={(event) => updateField('shiftPreference', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-supervisor">Supervisor name</label><input id="staff-supervisor" type="text" value={form.supervisorName} onChange={(event) => updateField('supervisorName', event.target.value)} /></div>
            <div className="field"><label htmlFor="staff-employment-date">Employment start date</label><input id="staff-employment-date" type="date" value={form.employmentStartDate} onChange={(event) => updateField('employmentStartDate', event.target.value)} /></div>
            <div className="field field-span-2"><label htmlFor="staff-notes">Staff notes</label><textarea id="staff-notes" rows="4" value={form.staffNotes} onChange={(event) => updateField('staffNotes', event.target.value)} /></div>
          </div>
          {profileNotice ? <div className={`inline-notice ${profileNotice.toLowerCase().includes('success') ? '' : 'error'}`}>{profileNotice}</div> : null}
          <button type="submit" className="btn" disabled={profileSaving}>{profileSaving ? 'Saving...' : 'Save Profile'}</button>
        </form>
      </div>
    </section>
  );
}

function ManagerStaffDirectory({ clinics, directory, loading, error }) {
  if (loading) {
    return <p className="muted">Loading staff members...</p>;
  }
  if (error) {
    return <div className="inline-notice error">{error}</div>;
  }
  if (!directory.results.length) {
    return <p className="muted">No staff members matched the current search.</p>;
  }

  return (
    <div className="staff-directory-grid">
      {directory.results.map((member) => (
        <article key={member.patient_id} className="staff-member-card">
          <div className="staff-member-topline">
            <div>
              <div className="eyebrow-label">{resolveClinicLabel(clinics, member.clinic_id)}</div>
              <h3>{member.full_name}</h3>
            </div>
            <span className="role-badge staff">Staff</span>
          </div>
          <div className="staff-member-meta">{member.email}</div>
          <div className="staff-member-meta">Email verified: {member.email_verified ? 'Yes' : 'No'}</div>
          <div className="staff-member-meta">Created: {formatDateTime(member.created_at)}</div>
          <div className="staff-member-meta">Last login: {member.last_login_at ? formatDateTime(member.last_login_at) : 'Never'}</div>
        </article>
      ))}
    </div>
  );
}

function AddMemberModal({ clinics, isOpen, onClose, onCreateStaff, staffCreationLoading, staffCreationNotice }) {
  const [staffForm, setStaffForm] = useState({ fullName: '', email: '', password: '', clinicId: clinics[0]?.id || '' });
  const [staffFormErrors, setStaffFormErrors] = useState({});

  useEffect(() => {
    if (clinics.length && !staffForm.clinicId) {
      setStaffForm((current) => ({ ...current, clinicId: clinics[0].id }));
    }
  }, [clinics, staffForm.clinicId]);

  useEffect(() => {
    if (!isOpen) {
      setStaffForm((current) => ({ ...current, fullName: '', email: '', password: '' }));
      setStaffFormErrors({});
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  function updateStaffField(field, value) {
    setStaffForm((current) => ({ ...current, [field]: value }));
    setStaffFormErrors((current) => ({ ...current, [field]: '' }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const nextForm = {
      fullName: String(staffForm.fullName || '').trim(),
      email: String(staffForm.email || '').trim(),
      password: String(staffForm.password || ''),
      clinicId: String(staffForm.clinicId || '').trim(),
    };
    const nextErrors = collectStaffFormErrors(nextForm);
    if (hasFieldErrors(nextErrors)) {
      setStaffFormErrors(nextErrors);
      return;
    }
    const success = await onCreateStaff(nextForm);
    if (success) {
      setStaffForm({ fullName: '', email: '', password: '', clinicId: nextForm.clinicId || clinics[0]?.id || '' });
      setStaffFormErrors({});
      onClose();
    }
  }

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="overlay-card" onClick={(event) => event.stopPropagation()}>
        <div className="panel-heading-row">
          <div>
            <h2 className="section-title">Add Staff Member</h2>
            <p className="section-subtitle">Create a staff account and assign it to the correct clinic.</p>
          </div>
          <button type="button" className="btn secondary" onClick={onClose}>
            Close
          </button>
        </div>

        <form className="auth-card add-member-form" onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="modal-staff-name">Full name</label>
            <input id="modal-staff-name" type="text" value={staffForm.fullName} onChange={(event) => updateStaffField('fullName', event.target.value)} required minLength={2} className={staffFormErrors.fullName ? 'input-error' : ''} />
            {staffFormErrors.fullName ? <div className="field-error-text">{staffFormErrors.fullName}</div> : null}
          </div>
          <div className="field">
            <label htmlFor="modal-staff-email">Email</label>
            <input id="modal-staff-email" type="email" value={staffForm.email} onChange={(event) => updateStaffField('email', event.target.value)} required className={staffFormErrors.email ? 'input-error' : ''} />
            {staffFormErrors.email ? <div className="field-error-text">{staffFormErrors.email}</div> : null}
          </div>
          <div className="field">
            <label htmlFor="modal-staff-password">Temporary password</label>
            <input id="modal-staff-password" type="password" value={staffForm.password} onChange={(event) => updateStaffField('password', event.target.value)} required minLength={8} className={staffFormErrors.password ? 'input-error' : ''} />
            {staffFormErrors.password ? <div className="field-error-text">{staffFormErrors.password}</div> : null}
          </div>
          <div className="field">
            <label htmlFor="modal-staff-clinic">Clinic assignment</label>
            <select id="modal-staff-clinic" value={staffForm.clinicId} onChange={(event) => updateStaffField('clinicId', event.target.value)} required className={staffFormErrors.clinicId ? 'input-error' : ''}>
              {clinics.map((clinic) => (
                <option key={clinic.id} value={clinic.id}>
                  {clinic.name}
                </option>
              ))}
            </select>
            {staffFormErrors.clinicId ? <div className="field-error-text">{staffFormErrors.clinicId}</div> : null}
          </div>
          {staffCreationNotice ? <div className={`inline-notice ${staffCreationNotice.toLowerCase().includes('added') ? '' : 'error'}`}>{staffCreationNotice}</div> : null}
          <button className="btn" type="submit" disabled={staffCreationLoading}>{staffCreationLoading ? 'Creating...' : 'Create Staff Account'}</button>
        </form>
      </div>
    </div>
  );
}

function QueueRetriageModal({ record, isSaving, error, onClose, onSave }) {
  const [priority, setPriority] = useState(String(record?.priority || 3));
  const [estDuration, setEstDuration] = useState(String(record?.estDuration || defaultDurationForPriority(record?.priority || 3)));

  useEffect(() => {
    setPriority(String(record?.priority || 3));
    setEstDuration(String(record?.estDuration || defaultDurationForPriority(record?.priority || 3)));
  }, [record]);

  if (!record) {
    return null;
  }

  function handlePriorityChange(nextValue) {
    setPriority(nextValue);
    setEstDuration(String(defaultDurationForPriority(nextValue)));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    await onSave({
      priority: Number(priority),
      estDuration: Number(estDuration),
    });
  }

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="overlay-card queue-action-modal" onClick={(event) => event.stopPropagation()}>
        <div className="panel-heading-row">
          <div>
            <h2 className="section-title">Retriage Queue Record</h2>
            <p className="section-subtitle">Adjust priority and estimated duration for patient {record.patientId}.</p>
          </div>
          <button type="button" className="btn secondary" onClick={onClose}>Close</button>
        </div>
        <form className="queue-action-form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="queue-retriage-priority">Priority</label>
            <select id="queue-retriage-priority" value={priority} onChange={(event) => handlePriorityChange(event.target.value)}>
              <option value="1">P1</option>
              <option value="2">P2</option>
              <option value="3">P3</option>
              <option value="4">P4</option>
              <option value="5">P5</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="queue-retriage-duration">Estimated duration (minutes)</label>
            <input id="queue-retriage-duration" type="number" min="1" step="1" value={estDuration} onChange={(event) => setEstDuration(event.target.value)} />
          </div>
          {error ? <div className="inline-notice error">{error}</div> : null}
          <div className="queue-action-row">
            <button type="submit" className="btn" disabled={isSaving}>{isSaving ? 'Saving...' : 'Save Retriage'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function QueueChatDetailModal({ detailState, onClose }) {
  if (!detailState.isOpen) {
    return null;
  }

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="overlay-card queue-chat-modal" onClick={(event) => event.stopPropagation()}>
        <div className="panel-heading-row">
          <div>
            <h2 className="section-title">Chat Details</h2>
            <p className="section-subtitle">Session drill-down for the selected queue record.</p>
          </div>
          <button type="button" className="btn secondary" onClick={onClose}>Close</button>
        </div>
        {detailState.loading ? <p className="muted">Loading chat detail...</p> : null}
        {detailState.error ? <div className="inline-notice error">{detailState.error}</div> : null}
        {detailState.data ? (
          <div className="queue-chat-detail-layout">
            <div className="queue-chat-meta-grid">
              <div><span className="meta-label">Session</span><span>{detailState.data.session?.session_id || 'Not available'}</span></div>
              <div><span className="meta-label">Patient</span><span>{detailState.data.session?.patient_id || 'Not available'}</span></div>
              <div><span className="meta-label">Clinic</span><span>{detailState.data.session?.clinic_id || 'Not available'}</span></div>
              <div><span className="meta-label">Started</span><span>{formatDateTime(detailState.data.session?.started_at)}</span></div>
              <div><span className="meta-label">Ended</span><span>{formatDateTime(detailState.data.session?.ended_at)}</span></div>
              <div><span className="meta-label">Urgency</span><span>{detailState.data.session_output?.urgency_band || 'Not available'}</span></div>
            </div>
            {detailState.data.session_output ? (
              <div className="queue-chat-summary-card">
                <div className="eyebrow-label">Visit Summary</div>
                <h3>{detailState.data.session_output.visit_category}</h3>
                <p>{detailState.data.session_output.explanation}</p>
                <div className="muted small">Estimated wait: {formatDurationMinutes(detailState.data.session_output.wait_p50_minutes)} to {formatDurationMinutes(detailState.data.session_output.wait_p90_minutes)}</div>
              </div>
            ) : null}
            <div className="queue-chat-transcript">
              <div className="eyebrow-label">Transcript</div>
              {(detailState.data.messages || []).length ? (
                detailState.data.messages.map((message, index) => (
                  <article key={`${message.created_at}-${index}`} className={`queue-chat-message ${message.role === 'assistant' ? 'assistant' : 'user'}`}>
                    <div className="queue-chat-message-topline">
                      <strong>{message.role === 'assistant' ? 'Assistant' : 'User'}</strong>
                      <span>{formatDateTime(message.created_at)}</span>
                    </div>
                    <p>{message.content}</p>
                  </article>
                ))
              ) : (
                <div className="queue-explorer-empty-state">No transcript messages available for this session.</div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function QueueDeleteModal({ record, isDeleting, error, onClose, onConfirm }) {
  if (!record) {
    return null;
  }

  return (
    <div className="overlay-backdrop" onClick={onClose}>
      <div className="overlay-card queue-action-modal" onClick={(event) => event.stopPropagation()}>
        <div className="panel-heading-row">
          <div>
            <h2 className="section-title">Delete Queue Record</h2>
            <p className="section-subtitle">Remove patient {record.patientId} from the live queue for {record.clinicName}.</p>
          </div>
          <button type="button" className="btn secondary" onClick={onClose} disabled={isDeleting}>Close</button>
        </div>
        <div className="queue-action-form">
          <div className="inline-notice error">
            This removes the queue entry immediately. Use this only when the patient should no longer appear in the active queue.
          </div>
          {error ? <div className="inline-notice error">{error}</div> : null}
          <div className="queue-action-row queue-action-row-split">
            <button type="button" className="btn secondary" onClick={onClose} disabled={isDeleting}>Cancel</button>
            <button type="button" className="btn danger" onClick={onConfirm} disabled={isDeleting}>{isDeleting ? 'Deleting...' : 'Delete Record'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ClinicQueueExplorer({ currentUser }) {
  const [availableClinics, setAvailableClinics] = useState([]);
  const [selectedClinicId, setSelectedClinicId] = useState('');
  const [clinicsLoading, setClinicsLoading] = useState(false);
  const [clinicLoadError, setClinicLoadError] = useState('');
  const [explorerData, setExplorerData] = useState({
    loading: false,
    error: '',
    records: [],
    rushPrediction: null,
    waitPrediction: null,
    refreshedAt: '',
  });
  const [retriageState, setRetriageState] = useState({ record: null, isSaving: false, error: '' });
  const [chatDetailState, setChatDetailState] = useState({ isOpen: false, loading: false, error: '', data: null, sessionId: '' });
  const [deleteState, setDeleteState] = useState({ record: null, isDeleting: false, error: '' });

  useEffect(() => {
    let isCancelled = false;

    async function loadClinics() {
      setClinicsLoading(true);
      setClinicLoadError('');
      try {
        const payload = await getQueueControlClinics();
        if (isCancelled) {
          return;
        }
        const nextClinics = (payload?.clinics || [])
          .map(normalizeQueueExplorerClinic)
          .filter((clinic) => clinic.id && clinic.name);
        setAvailableClinics(nextClinics);
        setSelectedClinicId((current) => {
          if (current && nextClinics.some((clinic) => clinic.id === current)) {
            return current;
          }
          const preferredClinic = nextClinics.find((clinic) => clinic.id === currentUser?.clinic_id);
          return preferredClinic?.id || nextClinics[0]?.id || '';
        });
      } catch (error) {
        if (!isCancelled) {
          setClinicLoadError(error.message || 'Unable to load clinics.');
        }
      } finally {
        if (!isCancelled) {
          setClinicsLoading(false);
        }
      }
    }

    loadClinics();
    return () => {
      isCancelled = true;
    };
  }, [currentUser?.clinic_id]);

  const selectedClinic = availableClinics.find((clinic) => clinic.id === selectedClinicId) || null;

  useEffect(() => {
    if (!selectedClinic) {
      return undefined;
    }

    let isCancelled = false;
    let timeoutId = 0;

    async function refreshExplorer(isInitialLoad = false) {
      if (isCancelled) {
        return;
      }

      setExplorerData((current) => ({
        ...current,
        loading: isInitialLoad || !current.refreshedAt,
        error: '',
      }));

      try {
        const queuePayload = await getActiveQueueRecords();
        if (isCancelled) {
          return;
        }
        const queueRecords = (queuePayload?.records || []).map(normalizeQueueExplorerRecord);
        const clinicRecords = queueRecords.filter((record) => record.clinicName === selectedClinic.name);
        const currentTime = new Date().toISOString();
        const [rushPrediction, waitPrediction] = await Promise.all([
          predictQueueSurge({
            queueRecords: clinicRecords,
            currentTime,
          }),
          predictQueueWaitTime({
            clinicName: selectedClinic.name,
            queueRecords: clinicRecords,
            currentTime,
          }),
        ]);

        if (isCancelled) {
          return;
        }

        setExplorerData({
          loading: false,
          error: '',
          records: clinicRecords,
          rushPrediction,
          waitPrediction,
          refreshedAt: new Date().toISOString(),
        });
      } catch (error) {
        if (!isCancelled) {
          setExplorerData((current) => ({
            ...current,
            loading: false,
            error: error.message || 'Unable to refresh queue explorer data.',
          }));
        }
      } finally {
        if (!isCancelled) {
          timeoutId = window.setTimeout(() => {
            refreshExplorer(false);
          }, 2000);
        }
      }
    }

    refreshExplorer(true);
    return () => {
      isCancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [selectedClinic]);

  const rushProbability = Number(explorerData.rushPrediction?.probability ?? NaN);
  const queueSize = explorerData.records.length;
  const nextUpPatientId = explorerData.records[0]?.patientId || 'None';
  const urgentCaseCount = explorerData.records.filter((record) => record.priority === 1 || record.priority === 2).length;
  const gaugeAngle = Number.isFinite(rushProbability) ? `${Math.max(0, Math.min(1, rushProbability)) * 360}deg` : '0deg';

  async function refreshQueueExplorer() {
    if (!selectedClinic) {
      return;
    }
    const queuePayload = await getActiveQueueRecords();
    const queueRecords = (queuePayload?.records || []).map(normalizeQueueExplorerRecord);
    const clinicRecords = queueRecords.filter((record) => record.clinicName === selectedClinic.name);
    const currentTime = new Date().toISOString();
    const [rushPrediction, waitPrediction] = await Promise.all([
      predictQueueSurge({ queueRecords: clinicRecords, currentTime }),
      predictQueueWaitTime({ clinicName: selectedClinic.name, queueRecords: clinicRecords, currentTime }),
    ]);
    setExplorerData({
      loading: false,
      error: '',
      records: clinicRecords,
      rushPrediction,
      waitPrediction,
      refreshedAt: new Date().toISOString(),
    });
  }

  function openRetriage(record) {
    setRetriageState({ record, isSaving: false, error: '' });
  }

  function closeRetriage() {
    setRetriageState({ record: null, isSaving: false, error: '' });
  }

  async function saveRetriage(payload) {
    if (!retriageState.record) {
      return;
    }
    setRetriageState((current) => ({ ...current, isSaving: true, error: '' }));
    try {
      await updateQueuePatientTriage(retriageState.record.recordId, payload);
      closeRetriage();
      await refreshQueueExplorer();
    } catch (error) {
      setRetriageState((current) => ({ ...current, isSaving: false, error: error.message || 'Unable to update triage.' }));
    }
  }

  async function openChatDetail(record) {
    setChatDetailState({ isOpen: true, loading: true, error: '', data: null, sessionId: record.chatSessionId || '' });
    try {
      const data = await getPublicTraceabilityDetail(record.chatSessionId);
      setChatDetailState({ isOpen: true, loading: false, error: '', data, sessionId: record.chatSessionId || '' });
    } catch (error) {
      setChatDetailState({ isOpen: true, loading: false, error: error.message || 'Unable to load chat details.', data: null, sessionId: record.chatSessionId || '' });
    }
  }

  function closeChatDetail() {
    setChatDetailState({ isOpen: false, loading: false, error: '', data: null, sessionId: '' });
  }

  function openDelete(record) {
    setDeleteState({ record, isDeleting: false, error: '' });
  }

  function closeDelete() {
    setDeleteState({ record: null, isDeleting: false, error: '' });
  }

  async function confirmDelete() {
    if (!deleteState.record) {
      return;
    }
    setDeleteState((current) => ({ ...current, isDeleting: true, error: '' }));
    try {
      await deleteQueuePatientRecord(deleteState.record.recordId);
      closeDelete();
      await refreshQueueExplorer();
    } catch (error) {
      setDeleteState((current) => ({ ...current, isDeleting: false, error: error.message || 'Unable to delete queue record.' }));
    }
  }

  return (
    <section className="panel account-panel queue-explorer-panel">
      <div className="panel-heading-row">
        <div>
          <h2 className="section-title">Clinic Queue Explorer</h2>
          <p className="section-subtitle">Live queue volume, estimated waits, and rush-hour probability for the selected clinic.</p>
        </div>
      </div>

      <div className="queue-explorer-toolbar">
        <div className="field queue-explorer-picker">
          <label htmlFor="queue-explorer-clinic">Selected clinic</label>
          <select
            id="queue-explorer-clinic"
            value={selectedClinicId}
            onChange={(event) => setSelectedClinicId(event.target.value)}
            disabled={clinicsLoading || !availableClinics.length}
          >
            {availableClinics.map((clinic) => (
              <option key={clinic.id} value={clinic.id}>
                {clinic.name}
              </option>
            ))}
          </select>
        </div>

        <div className="queue-explorer-status">
          <span className="queue-explorer-refresh-pill">Auto refresh every 2 seconds</span>
          <span className="muted small">{explorerData.refreshedAt ? `Last updated ${formatTimeOnly(explorerData.refreshedAt)}` : 'Waiting for first refresh...'}</span>
        </div>
      </div>

      {clinicLoadError ? <div className="inline-notice error">{clinicLoadError}</div> : null}
      {explorerData.error ? <div className="inline-notice error">{explorerData.error}</div> : null}
      {clinicsLoading && !availableClinics.length ? <p className="muted">Loading clinic explorer...</p> : null}

      {selectedClinic ? (
        <div className="queue-explorer-grid">
          <div className="queue-explorer-main">
            <div className="queue-explorer-kpis">
              <article className="queue-explorer-kpi queue-explorer-kpi-primary">
                <div className="queue-explorer-kpi-label">Queue at selected clinic</div>
                <div className="queue-explorer-kpi-value">{queueSize}</div>
                <div className="queue-explorer-kpi-note">Patients currently waiting to be served.</div>
              </article>
              <article className="queue-explorer-kpi queue-explorer-kpi-next">
                <div className="queue-explorer-kpi-label">Next up</div>
                <div className="queue-explorer-kpi-value queue-explorer-kpi-value-compact">{nextUpPatientId}</div>
                <div className="queue-explorer-kpi-note">The next patient expected to be served.</div>
              </article>
              <article className="queue-explorer-kpi queue-explorer-kpi-water">
                <div className="queue-explorer-kpi-label">Average estimated wait time</div>
                <div className="queue-explorer-kpi-value">{formatDurationMinutes(explorerData.waitPrediction?.p50_minutes)}</div>
                <div className="queue-explorer-kpi-note">Average expected wait time for a new arrival.</div>
              </article>
              <article className="queue-explorer-kpi queue-explorer-kpi-peach">
                <div className="queue-explorer-kpi-label">Maximum estimated wait time</div>
                <div className="queue-explorer-kpi-value">{formatDurationMinutes(explorerData.waitPrediction?.p90_minutes)}</div>
                <div className="queue-explorer-kpi-note">Higher-end wait estimate for a new arrival.</div>
              </article>
              <article className="queue-explorer-kpi queue-explorer-kpi-urgent">
                <div className="queue-explorer-kpi-label">Urgent cases</div>
                <div className="queue-explorer-kpi-value">{urgentCaseCount}</div>
                <div className="queue-explorer-kpi-note">Patients at priority P1 or P2 currently in the selected clinic.</div>
              </article>
            </div>

            <div className="auth-card queue-explorer-table-card">
              <div className="queue-explorer-table-header">
                <div>
                  <div className="eyebrow-label">Current queue</div>
                  <h3>{selectedClinic.name}</h3>
                </div>
                <div className="muted small">{queueSize} patient{queueSize === 1 ? '' : 's'} waiting</div>
              </div>
              <div className="queue-explorer-table-hint">
                Use the action buttons at the right side of each row to retriage, remove, or open chat details.
              </div>

              {explorerData.loading && !explorerData.records.length ? <p className="muted">Refreshing queue data...</p> : null}

              {explorerData.records.length ? (
                <div className="table-responsive queue-explorer-table-wrap">
                  <table className="results-table queue-explorer-table">
                    <thead>
                      <tr>
                        <th>Position</th>
                        <th>Patient ID</th>
                        <th>Priority</th>
                        <th>Arrival</th>
                        <th>Estimated duration</th>
                        <th>Waiting so far</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {explorerData.records.map((record, index) => (
                        <tr key={record.recordId || `${record.patientId}-${record.arrivalTime}`}>
                          <td>{index + 1}</td>
                          <td>{record.patientId}</td>
                          <td>
                            <span className={`queue-priority-pill p${record.priority || 5}`}>P{record.priority || 5}</span>
                          </td>
                          <td>{formatDateTime(record.arrivalTime)}</td>
                          <td>{formatDurationMinutes(record.estDuration)}</td>
                          <td>{formatWaitElapsed(record.arrivalTime)}</td>
                          <td>
                            <div className="queue-table-actions">
                              <button type="button" className="btn secondary queue-table-action" onClick={() => openRetriage(record)}>
                                Retriage
                              </button>
                              <button type="button" className="btn danger queue-table-action" onClick={() => openDelete(record)}>
                                Delete
                              </button>
                              {record.chatSessionId ? (
                                <button type="button" className="btn secondary queue-table-action" onClick={() => openChatDetail(record)}>
                                  Chat Detail
                                </button>
                              ) : (
                                <span className="muted small">No chat</span>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="queue-explorer-empty-state">No patients are currently waiting in this clinic queue.</div>
              )}
            </div>
          </div>

          <aside className="auth-card queue-explorer-gauge-card">
            <div className="eyebrow-label">Rush-hour probability based on the live waiting queue and historical clinic data.</div>
            <h3>{selectedClinic.name}</h3>
            <div className="queue-explorer-gauge" style={{ '--queue-explorer-gauge-angle': gaugeAngle }}>
              <div className="queue-explorer-gauge-content">
                <span className="queue-explorer-gauge-value">{formatProbabilityLabel(rushProbability)}</span>
                <span className="queue-explorer-gauge-caption">{getSurgeRiskLabel(rushProbability)}</span>
              </div>
            </div>
            {/* <div className="queue-explorer-gauge-note">{getSurgeRiskLabel(rushProbability)}</div> */}
            {/* <div className="queue-explorer-gauge-meta">Based on the live waiting queue and historical clinic data.</div> */}
          </aside>
        </div>
      ) : null}

      <QueueRetriageModal
        record={retriageState.record}
        isSaving={retriageState.isSaving}
        error={retriageState.error}
        onClose={closeRetriage}
        onSave={saveRetriage}
      />
      <QueueDeleteModal
        record={deleteState.record}
        isDeleting={deleteState.isDeleting}
        error={deleteState.error}
        onClose={closeDelete}
        onConfirm={confirmDelete}
      />
      <QueueChatDetailModal detailState={chatDetailState} onClose={closeChatDetail} />
    </section>
  );
}

export default function AccountPage({
  currentUser,
  activeSection,
  demoUsers,
  authLoading,
  authError,
  bookingIntentActive,
  onLogin,
  onRegister,
  onDemoLogin,
  clinics,
  appointments,
  appointmentsLoading,
  appointmentNotice,
  onBeginBookingJourney,
  bookingLoading,
  bookingNotice,
  staffSearch,
  appliedStaffSearch,
  onStaffSearchChange,
  onStaffSearchSubmit,
  onStaffSearchReset,
  staffAppointments,
  staffLoading,
  staffError,
  managerStaffFilters,
  onManagerStaffFilterChange,
  onManagerStaffFilterReset,
  managerStaffDirectory,
  managerStaffLoading,
  managerStaffError,
  onCreateStaff,
  staffCreationLoading,
  staffCreationNotice,
  profileSaving,
  profileNotice,
  onUpdateProfile,
  isAddMemberFormOpen,
  onOpenAddMemberForm,
  onCloseAddMemberForm,
}) {
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ fullName: '', email: '', password: '' });
  const [loginErrors, setLoginErrors] = useState({});
  const [registerErrors, setRegisterErrors] = useState({});
  const [staffSearchValidationError, setStaffSearchValidationError] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [showDemoAccounts, setShowDemoAccounts] = useState(false);
  const heroCopy = sectionCopy(currentUser, activeSection);

  useEffect(() => {
    setShowHistory(false);
    if (currentUser) {
      setShowDemoAccounts(false);
    }
  }, [currentUser, activeSection]);

  function updateLoginField(field, value) {
    setLoginForm((current) => ({ ...current, [field]: value }));
    setLoginErrors((current) => ({ ...current, [field]: '' }));
  }

  function updateRegisterField(field, value) {
    setRegisterForm((current) => ({ ...current, [field]: value }));
    setRegisterErrors((current) => ({ ...current, [field]: '' }));
  }

  async function handleLoginSubmit(event) {
    event.preventDefault();
    const nextForm = {
      email: String(loginForm.email || '').trim(),
      password: String(loginForm.password || ''),
    };
    const nextErrors = collectLoginErrors(nextForm);
    if (hasFieldErrors(nextErrors)) {
      setLoginErrors(nextErrors);
      return;
    }
    const success = await onLogin(nextForm);
    if (success) {
      setLoginForm({ email: '', password: '' });
      setLoginErrors({});
    }
  }

  async function handleRegisterSubmit(event) {
    event.preventDefault();
    const nextForm = {
      fullName: String(registerForm.fullName || '').trim(),
      email: String(registerForm.email || '').trim(),
      password: String(registerForm.password || ''),
    };
    const nextErrors = collectRegisterErrors(nextForm);
    if (hasFieldErrors(nextErrors)) {
      setRegisterErrors(nextErrors);
      return;
    }
    const success = await onRegister(nextForm);
    if (success) {
      setRegisterForm({ fullName: '', email: '', password: '' });
      setRegisterErrors({});
    }
  }

  function handleStaffSearchSubmitClick() {
    const validationError = validateStaffSearch(staffSearch);
    if (validationError) {
      setStaffSearchValidationError(validationError);
      return;
    }
    setStaffSearchValidationError('');
    onStaffSearchSubmit();
  }

  function handleStaffSearchResetClick() {
    setStaffSearchValidationError('');
    onStaffSearchReset();
  }

  function handleOpenOperationalDashboard() {
    const targetUrl = isManagerDashboard ? DASHBOARD_URLS.manager : DASHBOARD_URLS.reception;
    window.open(targetUrl, '_blank', 'noopener,noreferrer');
  }

  const staffMatchCount = Number(staffAppointments?.total_results || 0);
  const activeTimeBucket = appliedStaffSearch?.timeBucket || staffSearch?.timeBucket || 'today';
  const staffTimeBucketLabel = formatTimeBucketLabel(activeTimeBucket);
  const isManagerDashboard = String(currentUser?.role || '').toLowerCase() === 'manager';
  const resolvedClinicIdForLabel = staffAppointments?.clinic_id || appliedStaffSearch?.clinicId || currentUser?.clinic_id || '';
  const activeClinicLabel = isManagerDashboard && !resolvedClinicIdForLabel
    ? 'All clinics'
    : resolveClinicLabel(clinics, resolvedClinicIdForLabel);
  const fromLabel = appliedStaffSearch?.scheduledFrom ? formatDateTime(appliedStaffSearch.scheduledFrom) : 'Any start';
  const toLabel = appliedStaffSearch?.scheduledTo ? formatDateTime(appliedStaffSearch.scheduledTo) : 'Any end';
  const staffLoadBand = staffMatchCount >= 18 ? 'high' : staffMatchCount >= 8 ? 'medium' : 'low';
  const staffLoadLabel = staffLoadBand === 'high' ? 'High Load' : staffLoadBand === 'medium' ? 'Medium Load' : 'Low Load';

  return (
    <div className="page-container login-demo-page">
      <header className="page-header login-demo-header">
        <h1>{heroCopy.title}</h1>
        <p>{heroCopy.description}</p>
      </header>

      {!currentUser ? (
        <>
          <section className="panel account-panel">
            <div className="panel-heading-row auth-panel-header">
              <div>
                <h2 className="section-title">Access Portal</h2>
                <p className="section-subtitle">Patients can register here directly. Staff and manager access starts from login.</p>
              </div>
            </div>
            {bookingIntentActive ? <div className="inline-notice">Sign in or register as a patient to finish booking the appointment you just assessed in the chatbot.</div> : null}

            <div className="auth-entry-grid">
              <form className="auth-card" onSubmit={handleLoginSubmit} noValidate>
                <div>
                  <div className="eyebrow-label">Login</div>
                  <h3>Sign in to an existing account</h3>
                </div>
                <div className="field">
                  <label htmlFor="login-email">Email</label>
                  <input id="login-email" type="email" value={loginForm.email} onChange={(event) => updateLoginField('email', event.target.value)} className={loginErrors.email ? 'input-error' : ''} autoComplete="email" />
                  {loginErrors.email ? <div className="field-error-text">{loginErrors.email}</div> : null}
                </div>
                <div className="field">
                  <label htmlFor="login-password">Password</label>
                  <input id="login-password" type="password" value={loginForm.password} onChange={(event) => updateLoginField('password', event.target.value)} className={loginErrors.password ? 'input-error' : ''} autoComplete="current-password" />
                  {loginErrors.password ? <div className="field-error-text">{loginErrors.password}</div> : null}
                </div>
                <button className="btn" type="submit" disabled={authLoading}>Log In</button>
              </form>

              <form className="auth-card" onSubmit={handleRegisterSubmit} noValidate>
                <div>
                  <div className="eyebrow-label">Register</div>
                  <h3>Create a new patient account</h3>
                </div>
                <div className="field">
                  <label htmlFor="register-name">Full name</label>
                  <input id="register-name" type="text" value={registerForm.fullName} onChange={(event) => updateRegisterField('fullName', event.target.value)} className={registerErrors.fullName ? 'input-error' : ''} autoComplete="name" />
                  {registerErrors.fullName ? <div className="field-error-text">{registerErrors.fullName}</div> : null}
                </div>
                <div className="field">
                  <label htmlFor="register-email">Email</label>
                  <input id="register-email" type="email" value={registerForm.email} onChange={(event) => updateRegisterField('email', event.target.value)} className={registerErrors.email ? 'input-error' : ''} autoComplete="email" />
                  {registerErrors.email ? <div className="field-error-text">{registerErrors.email}</div> : null}
                </div>
                <div className="field">
                  <label htmlFor="register-password">Password</label>
                  <input id="register-password" type="password" value={registerForm.password} onChange={(event) => updateRegisterField('password', event.target.value)} className={registerErrors.password ? 'input-error' : ''} autoComplete="new-password" />
                  {registerErrors.password ? <div className="field-error-text">{registerErrors.password}</div> : null}
                </div>
                <div className="inline-notice">Managers create staff accounts from the Add Member dashboard, so public registration stays patient-only.</div>
                <button className="btn" type="submit" disabled={authLoading}>Register As Patient</button>
              </form>
            </div>

            {authError ? <div className="inline-notice error">{authError}</div> : null}
          </section>

          {demoUsers.length ? (
            <section className="panel account-panel">
              <div className="panel-heading-row">
                <div>
                  <h2 className="section-title">Demo Accounts</h2>
                  <p className="section-subtitle">Click to show or hide local demo account shortcuts.</p>
                </div>
                <button type="button" className="btn secondary" onClick={() => setShowDemoAccounts((current) => !current)}>
                  Demo Accounts
                </button>
              </div>
            </section>
          ) : null}

          {showDemoAccounts ? <DemoAccessCards clinics={clinics} demoUsers={demoUsers} authLoading={authLoading} onDemoLogin={onDemoLogin} /> : null}
        </>
      ) : (
        <>
          {currentUser.role === 'patient' && activeSection === 'my-appointments' ? (
            <>
              <section className="panel account-panel">
                <div className="panel-heading-row">
                  <div>
                    <h2 className="section-title">Book A New Appointment</h2>
                    <p className="section-subtitle">Start the same chatbot intake used on the home page. Once the final wait-time result is ready, you can book directly from that result.</p>
                  </div>
                  <div className="row">
                    <button type="button" className="btn secondary" onClick={() => window.open(DASHBOARD_URLS.patient, '_blank', 'noopener,noreferrer')}>
                      Patient Dashboard
                    </button>
                    <button type="button" className="btn" onClick={onBeginBookingJourney} disabled={bookingLoading}>
                      Book Appointment
                    </button>
                  </div>
                </div>
                {bookingNotice ? <div className={`inline-notice ${bookingNotice.toLowerCase().includes('success') ? '' : 'error'}`}>{bookingNotice}</div> : null}
              </section>

              <section className="panel account-panel">
                <div className="panel-heading-row">
                  <div>
                    <h2 className="section-title">Your Appointments</h2>
                    <p className="section-subtitle">Track what is happening now, what is coming next, and what has already been completed.</p>
                  </div>
                </div>
                {appointmentNotice ? <div className="inline-notice error">{appointmentNotice}</div> : null}
                {appointmentsLoading ? (
                  <p className="muted">Loading your appointments...</p>
                ) : (
                  <div className="account-dashboard-grid">
                    <div className="auth-card">
                      <div className="eyebrow-label">Current</div>
                      <h3>Happening today</h3>
                      <AppointmentList clinics={clinics} appointments={appointments.current || []} emptyMessage="No current appointments for today." />
                    </div>
                    <div className="auth-card">
                      <div className="eyebrow-label">Upcoming</div>
                      <h3>Scheduled ahead</h3>
                      <AppointmentList clinics={clinics} appointments={appointments.upcoming || []} emptyMessage="No upcoming appointments scheduled." />
                    </div>
                  </div>
                )}
                {!appointmentsLoading ? (
                  <div className="history-toggle-block">
                    <button type="button" className="btn secondary" onClick={() => setShowHistory((current) => !current)}>
                      {showHistory ? 'Hide History' : 'See History'}
                    </button>
                    <span className="history-toggle-hint">{(appointments.past || []).length} previous appointment{(appointments.past || []).length === 1 ? '' : 's'} on record</span>
                  </div>
                ) : null}
                {!appointmentsLoading && showHistory ? (
                  <div className="auth-card history-panel-card">
                    <div className="eyebrow-label">History</div>
                    <h3>Previous visits</h3>
                    <AppointmentList clinics={clinics} appointments={appointments.past || []} emptyMessage="No appointment history yet." />
                  </div>
                ) : null}
              </section>

            </>
          ) : null}

          {currentUser.role === 'patient' && activeSection === 'profile' ? (
            <PatientProfileSection
              clinics={clinics}
              currentUser={currentUser}
              onBeginBookingJourney={onBeginBookingJourney}
              onUpdateProfile={onUpdateProfile}
              profileSaving={profileSaving}
              profileNotice={profileNotice}
            />
          ) : null}

          {(currentUser.role === 'staff' || currentUser.role === 'manager') && activeSection === 'dashboard' ? (
            <section className="panel account-panel">
              <div className="panel-heading-row">
                <div>
                  <h2 className="section-title">{isManagerDashboard ? 'Manager Appointment Dashboard' : 'Staff Dashboard'}</h2>
                  <p className="section-subtitle">{isManagerDashboard ? 'Search appointments across all clinics or narrow to one clinic using patient name, email, booking token, or appointment ID.' : "Review today's schedule and search future or past appointments for your assigned clinic."}</p>
                </div>
              </div>

              <div className="staff-kpi-strip">
                <article className="staff-kpi-card staff-kpi-card-strong">
                  <div className="staff-kpi-label">Matching appointments</div>
                  <div className="staff-kpi-value">{staffMatchCount}</div>
                  <div className="staff-kpi-note">{staffTimeBucketLabel} window</div>
                </article>
                <article className="staff-kpi-card">
                  <div className="staff-kpi-label">{isManagerDashboard ? 'Clinic scope' : 'Assigned clinic'}</div>
                  <div className="staff-kpi-text">{activeClinicLabel}</div>
                  <div className="staff-kpi-note">Live search scope</div>
                </article>
                <article className="staff-kpi-card">
                  <div className="staff-kpi-label">Selected range</div>
                  <div className="staff-kpi-text">{fromLabel} to {toLabel}</div>
                  <div className="staff-kpi-note">Filter coverage</div>
                </article>
                <article className="staff-kpi-card">
                  <div className="staff-kpi-label">Load indicator</div>
                  <div className="staff-kpi-note">Based on current matching volume</div>
                  <span className={`staff-load-pill ${staffLoadBand}`}>{staffLoadLabel}</span>
                </article>
              </div>

              <div className="compact-search-panel refined-search-panel">
                <div className="compact-search-header refined-search-header">
                  <div>
                    <div className="eyebrow-label">Search Filters</div>
                    <h3>Find appointments</h3>
                    <p className="search-panel-hint">Search by patient, email, booking token, or appointment ID with time and clinic filters.</p>
                  </div>
                  <div className="compact-search-clinic">{isManagerDashboard ? 'Clinic scope: ' + activeClinicLabel : 'Assigned clinic: ' + resolveClinicLabel(clinics, currentUser.clinic_id)}</div>
                </div>

                <div className="refined-search-layout refined-search-toolbar-layout">
                  <div className="field refined-search-field refined-search-field-query refined-search-field-card">
                    <label htmlFor="staff-patient-query">Patient, email, token, or appointment ID</label>
                    <input id="staff-patient-query" type="text" value={staffSearch.patientQuery} onChange={(event) => onStaffSearchChange('patientQuery', event.target.value)} placeholder="Search by patient, email, booking token, or appointment ID" />
                  </div>

                  <div className="field refined-search-field refined-search-field-bucket refined-search-field-card">
                    <label htmlFor="staff-time-bucket">Time range</label>
                    <select id="staff-time-bucket" value={staffSearch.timeBucket} onChange={(event) => onStaffSearchChange('timeBucket', event.target.value)}>
                      <option value="today">Today</option>
                      <option value="upcoming">Upcoming</option>
                      <option value="past">Past</option>
                    </select>
                  </div>


                  {isManagerDashboard ? (
                    <div className="field refined-search-field refined-search-field-bucket refined-search-field-card">
                      <label htmlFor="staff-clinic-filter">Clinic</label>
                      <select id="staff-clinic-filter" value={staffSearch.clinicId || ''} onChange={(event) => onStaffSearchChange('clinicId', event.target.value)}>
                        <option value="">All clinics</option>
                        {clinics.map((clinic) => (
                          <option key={clinic.id} value={clinic.id}>{clinic.name}</option>
                        ))}
                      </select>
                    </div>
                  ) : null}

                  <div className="refined-search-actions refined-search-actions-card">
                    <button className="btn" type="button" onClick={handleStaffSearchSubmitClick}>Search</button>
                    <button className="btn secondary" type="button" onClick={handleOpenOperationalDashboard}>Dashboard</button>
                    <button className="btn secondary" type="button" onClick={handleStaffSearchResetClick}>Reset</button>
                  </div>

                  <div className="field refined-search-field refined-search-field-date refined-search-field-from refined-search-field-card">
                    <label htmlFor="staff-scheduled-from">From</label>
                    <input id="staff-scheduled-from" type="datetime-local" value={staffSearch.scheduledFrom} onChange={(event) => onStaffSearchChange('scheduledFrom', event.target.value)} />
                  </div>

                  <div className="field refined-search-field refined-search-field-date refined-search-field-to refined-search-field-card">
                    <label htmlFor="staff-scheduled-to">To</label>
                    <input id="staff-scheduled-to" type="datetime-local" value={staffSearch.scheduledTo} onChange={(event) => onStaffSearchChange('scheduledTo', event.target.value)} />
                  </div>
                </div>
                {staffSearchValidationError ? <div className="field-error-text">{staffSearchValidationError}</div> : null}
              </div>

              <div className="auth-card staff-results-panel">
                <div className="eyebrow-label">Results</div>
                <h3>{activeClinicLabel} appointments</h3>
                <div className="muted small">{staffAppointments.total_results || 0} matching appointments</div>
                {staffError ? <div className="inline-notice error">{staffError}</div> : null}
                {staffLoading ? <p className="muted">Loading appointment search...</p> : <StaffResultsTable clinics={clinics} staffAppointments={staffAppointments} />}
              </div>

              <div className="queue-explorer-results-slot">
                <ClinicQueueExplorer currentUser={currentUser} />
              </div>
            </section>
          ) : null}

          {currentUser.role === 'staff' && activeSection === 'profile' ? (
            <StaffProfileSection
              clinics={clinics}
              currentUser={currentUser}
              onUpdateProfile={onUpdateProfile}
              profileSaving={profileSaving}
              profileNotice={profileNotice}
            />
          ) : null}

          {currentUser.role === 'manager' && activeSection === 'simulations' ? (
            <section className="panel account-panel">
              <div className="panel-heading-row">
                <div>
                  <h2 className="section-title">QueueControl Simulation</h2>
                  <p className="section-subtitle">Launch the simulation workspace to explore queue behavior and make better staffing and operations decisions.</p>
                </div>
              </div>
              <div className="queuecontrol-access-card">
                <div>
                  <div className="eyebrow-label">Simulation Access</div>
                  <h3>Open Manager Dashboard</h3>
                  <p className="muted">Open the manager Streamlit dashboard in a new tab.</p>
                </div>
                <div className="row">
                  <button
                    type="button"
                    className="btn"
                    onClick={() => window.open(DASHBOARD_URLS.manager, '_blank', 'noopener,noreferrer')}
                  >
                    Dashboard
                  </button>
                </div>
              </div>

              <div className="queue-explorer-results-slot">
                <ClinicQueueExplorer currentUser={currentUser} />
              </div>
            </section>
          ) : null}

          {currentUser.role === 'manager' && activeSection === 'add-member' ? (
            <section className="panel account-panel manager-dashboard-panel">
              <div className="manager-dashboard-hero">
                <div>
                  <div className="eyebrow-label">Manager Workspace</div>
                  <h2 className="section-title">Add Member Dashboard</h2>
                  <p className="section-subtitle">Manage clinic staffing with one place to search existing team members, review assignments, and create new staff accounts.</p>
                </div>
                <button type="button" className="btn manager-primary-action" onClick={onOpenAddMemberForm}>
                  Add Member
                </button>
              </div>

              <div className="manager-filter-panel">
                <div className="manager-filter-topline">
                  <div>
                    <div className="eyebrow-label">Staff Directory Filters</div>
                    <h3>Find team members</h3>
                    <p className="search-panel-hint">Search across staff names, emails, and clinic assignments.</p>
                  </div>
                  <div className="manager-results-pill">{managerStaffDirectory.total_results || 0} staff members found</div>
                </div>

                <div className="manager-search-grid manager-search-toolbar-grid">
                  <div className="field manager-search-card manager-search-card-wide">
                    <label htmlFor="member-query">Search staff</label>
                    <input id="member-query" type="text" value={managerStaffFilters.query} onChange={(event) => onManagerStaffFilterChange('query', event.target.value)} placeholder="Search by name or email" />
                  </div>
                  <div className="field manager-search-card">
                    <label htmlFor="member-clinic">Clinic</label>
                    <select id="member-clinic" value={managerStaffFilters.clinicId} onChange={(event) => onManagerStaffFilterChange('clinicId', event.target.value)}>
                      <option value="">All clinics</option>
                      {clinics.map((clinic) => (
                        <option key={clinic.id} value={clinic.id}>
                          {clinic.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="manager-search-actions manager-search-card">
                    <button type="button" className="btn secondary" onClick={onManagerStaffFilterReset}>
                      Reset Search
                    </button>
                  </div>
                </div>
              </div>

              <ManagerStaffDirectory clinics={clinics} directory={managerStaffDirectory} loading={managerStaffLoading} error={managerStaffError} />

              <AddMemberModal
                clinics={clinics}
                isOpen={isAddMemberFormOpen}
                onClose={onCloseAddMemberForm}
                onCreateStaff={onCreateStaff}
                staffCreationLoading={staffCreationLoading}
                staffCreationNotice={staffCreationNotice}
              />
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}








