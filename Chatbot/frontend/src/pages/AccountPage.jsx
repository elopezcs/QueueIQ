import React, { useEffect, useState } from 'react';

const QUEUECONTROL_DASHBOARD_URL = 'http://127.0.0.1:8501';

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
                <div className="muted small">{formatDateTime(appointment.scheduled_for)}</div>
              </div>
              <span className={`status-pill ${appointment.status === 'scheduled' ? 'scheduled' : 'completed'}`}>{appointment.status}</span>
            </div>
            <div className="history-entry-details">
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
  if (!demoUsers.length) {
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
        {demoUsers.map((user) => (
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
            <th>Email</th>
            <th>Clinic</th>
            <th>Scheduled</th>
            <th>Status</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {staffAppointments.results.map((appointment) => (
            <tr key={appointment.appointment_id}>
              <td>{appointment.full_name}</td>
              <td>{appointment.email}</td>
              <td>{resolveClinicLabel(clinics, appointment.clinic_id)}</td>
              <td>{formatDateTime(appointment.scheduled_for)}</td>
              <td>{appointment.status}</td>
              <td>{appointment.description || 'No description added.'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProfileSection({ clinics, currentUser, onBeginBookingJourney, showBookingButton }) {
  return (
    <section className="panel account-panel">
      <div className="panel-heading-row">
        <div>
          <h2 className="section-title">Profile</h2>
          <p className="section-subtitle">This summary reflects the account and clinic access you are currently using.</p>
          {showBookingButton ? <div className="muted small">Book Appointment takes you back to the home page and opens the chatbot intake flow.</div> : null}
        </div>
        {showBookingButton ? (
          <button type="button" className="btn" onClick={onBeginBookingJourney}>
            Book Appointment
          </button>
        ) : null}
      </div>
      <div className="profile-grid">
        <article className="auth-card">
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

  useEffect(() => {
    if (clinics.length && !staffForm.clinicId) {
      setStaffForm((current) => ({ ...current, clinicId: clinics[0].id }));
    }
  }, [clinics, staffForm.clinicId]);

  useEffect(() => {
    if (!isOpen) {
      setStaffForm((current) => ({ ...current, fullName: '', email: '', password: '' }));
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const success = await onCreateStaff(staffForm);
    if (success) {
      setStaffForm((current) => ({ ...current, fullName: '', email: '', password: '' }));
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

        <form className="auth-card add-member-form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="modal-staff-name">Full name</label>
            <input id="modal-staff-name" type="text" value={staffForm.fullName} onChange={(event) => setStaffForm((current) => ({ ...current, fullName: event.target.value }))} />
          </div>
          <div className="field">
            <label htmlFor="modal-staff-email">Email</label>
            <input id="modal-staff-email" type="email" value={staffForm.email} onChange={(event) => setStaffForm((current) => ({ ...current, email: event.target.value }))} />
          </div>
          <div className="field">
            <label htmlFor="modal-staff-password">Temporary password</label>
            <input id="modal-staff-password" type="password" value={staffForm.password} onChange={(event) => setStaffForm((current) => ({ ...current, password: event.target.value }))} />
          </div>
          <div className="field">
            <label htmlFor="modal-staff-clinic">Clinic assignment</label>
            <select id="modal-staff-clinic" value={staffForm.clinicId} onChange={(event) => setStaffForm((current) => ({ ...current, clinicId: event.target.value }))}>
              {clinics.map((clinic) => (
                <option key={clinic.id} value={clinic.id}>
                  {clinic.name}
                </option>
              ))}
            </select>
          </div>
          {staffCreationNotice ? <div className={`inline-notice ${staffCreationNotice.toLowerCase().includes('added') ? '' : 'error'}`}>{staffCreationNotice}</div> : null}
          <button className="btn" type="submit" disabled={staffCreationLoading}>{staffCreationLoading ? 'Creating...' : 'Create Staff Account'}</button>
        </form>
      </div>
    </div>
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
  isAddMemberFormOpen,
  onOpenAddMemberForm,
  onCloseAddMemberForm,
}) {
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  const [registerForm, setRegisterForm] = useState({ fullName: '', email: '', password: '' });
  const heroCopy = sectionCopy(currentUser, activeSection);

  async function handleLoginSubmit(event) {
    event.preventDefault();
    const success = await onLogin(loginForm);
    if (success) {
      setLoginForm({ email: '', password: '' });
    }
  }

  async function handleRegisterSubmit(event) {
    event.preventDefault();
    const success = await onRegister(registerForm);
    if (success) {
      setRegisterForm({ fullName: '', email: '', password: '' });
    }
  }

  return (
    <div className="page-container login-demo-page">
      <header className="page-header login-demo-header">
        <h1>{heroCopy.title}</h1>
        <p>{heroCopy.description}</p>
      </header>

      {!currentUser ? (
        <>
          <section className="panel account-panel">
            <div className="panel-heading-row">
              <div>
                <h2 className="section-title">Access Portal</h2>
                <p className="section-subtitle">Patients can register here directly. Staff and manager access starts from login.</p>
              </div>
            </div>
            {bookingIntentActive ? <div className="inline-notice">Sign in or register as a patient to finish booking the appointment you just assessed in the chatbot.</div> : null}
            <div className="auth-entry-grid">
              <form className="auth-card" onSubmit={handleLoginSubmit}>
                <div>
                  <div className="eyebrow-label">Login</div>
                  <h3>Sign in to an existing account</h3>
                </div>
                <div className="field">
                  <label htmlFor="login-email">Email</label>
                  <input id="login-email" type="email" value={loginForm.email} onChange={(event) => setLoginForm((current) => ({ ...current, email: event.target.value }))} />
                </div>
                <div className="field">
                  <label htmlFor="login-password">Password</label>
                  <input id="login-password" type="password" value={loginForm.password} onChange={(event) => setLoginForm((current) => ({ ...current, password: event.target.value }))} />
                </div>
                <button className="btn" type="submit" disabled={authLoading}>Log In</button>
              </form>

              <form className="auth-card" onSubmit={handleRegisterSubmit}>
                <div>
                  <div className="eyebrow-label">Register</div>
                  <h3>Create a new patient account</h3>
                </div>
                <div className="field">
                  <label htmlFor="register-name">Full name</label>
                  <input id="register-name" type="text" value={registerForm.fullName} onChange={(event) => setRegisterForm((current) => ({ ...current, fullName: event.target.value }))} />
                </div>
                <div className="field">
                  <label htmlFor="register-email">Email</label>
                  <input id="register-email" type="email" value={registerForm.email} onChange={(event) => setRegisterForm((current) => ({ ...current, email: event.target.value }))} />
                </div>
                <div className="field">
                  <label htmlFor="register-password">Password</label>
                  <input id="register-password" type="password" value={registerForm.password} onChange={(event) => setRegisterForm((current) => ({ ...current, password: event.target.value }))} />
                </div>
                <div className="inline-notice">Managers create staff accounts from the Add Member dashboard, so public registration stays patient-only.</div>
                <button className="btn" type="submit" disabled={authLoading}>Register As Patient</button>
              </form>
            </div>
            {authError ? <div className="inline-notice error">{authError}</div> : null}
          </section>

          <DemoAccessCards clinics={clinics} demoUsers={demoUsers} authLoading={authLoading} onDemoLogin={onDemoLogin} />
        </>
      ) : (
        <>
          <section className="panel account-panel">
            <div className="account-summary enhanced-account-summary">
              <div>
                <div className="eyebrow-label">Signed In As</div>
                <strong>{currentUser.full_name}</strong>
                <div className="muted small">{currentUser.email}</div>
                <div className="muted small">Role: {formatRoleLabel(currentUser.role)}</div>
                <div className="muted small">Clinic: {resolveClinicLabel(clinics, currentUser.clinic_id)}</div>
              </div>
              <span className={`role-badge ${currentUser.role}`}>{formatRoleLabel(currentUser.role)}</span>
            </div>
          </section>

          {currentUser.role === 'patient' && activeSection === 'my-appointments' ? (
            <>
              <section className="panel account-panel">
                <div className="panel-heading-row">
                  <div>
                    <h2 className="section-title">Book A New Appointment</h2>
                    <p className="section-subtitle">Start the same chatbot intake used on the home page. Once the final wait-time result is ready, you can book directly from that result.</p>
                  </div>
                  <button type="button" className="btn" onClick={onBeginBookingJourney} disabled={bookingLoading}>
                    Book Appointment
                  </button>
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
                    <div className="auth-card">
                      <div className="eyebrow-label">History</div>
                      <h3>Previous visits</h3>
                      <AppointmentList clinics={clinics} appointments={appointments.past || []} emptyMessage="No appointment history yet." />
                    </div>
                  </div>
                )}
              </section>
            </>
          ) : null}

          {currentUser.role === 'patient' && activeSection === 'profile' ? <ProfileSection clinics={clinics} currentUser={currentUser} onBeginBookingJourney={onBeginBookingJourney} showBookingButton /> : null}

          {currentUser.role === 'staff' && activeSection === 'dashboard' ? (
            <section className="panel account-panel">
              <div className="panel-heading-row">
                <div>
                  <h2 className="section-title">Staff Dashboard</h2>
                  <p className="section-subtitle">Review today's schedule and search future or past appointments for your assigned clinic.</p>
                </div>
              </div>

              <div className="compact-search-panel refined-search-panel">
                <div className="compact-search-header refined-search-header">
                  <div>
                    <div className="eyebrow-label">Search Filters</div>
                    <h3>Find appointments</h3>
                  </div>
                  <div className="compact-search-clinic">Assigned clinic: {resolveClinicLabel(clinics, currentUser.clinic_id)}</div>
                </div>

                <div className="refined-search-layout">
                  <div className="refined-search-row refined-search-row-primary">
                    <div className="field refined-search-field refined-search-field-query">
                      <label htmlFor="staff-patient-query">Patient name or email</label>
                      <input id="staff-patient-query" type="text" value={staffSearch.patientQuery} onChange={(event) => onStaffSearchChange('patientQuery', event.target.value)} placeholder="Search by patient name or email" />
                    </div>
                    <div className="field refined-search-field refined-search-field-bucket">
                      <label htmlFor="staff-time-bucket">Time range</label>
                      <select id="staff-time-bucket" value={staffSearch.timeBucket} onChange={(event) => onStaffSearchChange('timeBucket', event.target.value)}>
                        <option value="today">Today</option>
                        <option value="upcoming">Upcoming</option>
                        <option value="past">Past</option>
                      </select>
                    </div>
                    <div className="refined-search-actions">
                      <button className="btn" type="button" onClick={onStaffSearchSubmit}>Search</button>
                      <button className="btn secondary" type="button" onClick={onStaffSearchReset}>Reset</button>
                    </div>
                  </div>

                  <div className="refined-search-row refined-search-row-secondary">
                    <div className="field refined-search-field refined-search-field-date">
                      <label htmlFor="staff-scheduled-from">From</label>
                      <input id="staff-scheduled-from" type="datetime-local" value={staffSearch.scheduledFrom} onChange={(event) => onStaffSearchChange('scheduledFrom', event.target.value)} />
                    </div>
                    <div className="field refined-search-field refined-search-field-date">
                      <label htmlFor="staff-scheduled-to">To</label>
                      <input id="staff-scheduled-to" type="datetime-local" value={staffSearch.scheduledTo} onChange={(event) => onStaffSearchChange('scheduledTo', event.target.value)} />
                    </div>
                  </div>
                </div>
              </div>

              <div className="auth-card staff-results-panel">
                <div className="eyebrow-label">Results</div>
                <h3>{resolveClinicLabel(clinics, staffAppointments.clinic_id || currentUser.clinic_id)} appointments</h3>
                <div className="muted small">{staffAppointments.total_results || 0} matching appointments</div>
                {staffError ? <div className="inline-notice error">{staffError}</div> : null}
                {staffLoading ? <p className="muted">Loading appointment search...</p> : <StaffResultsTable clinics={clinics} staffAppointments={staffAppointments} />}
              </div>
            </section>
          ) : null}

          {currentUser.role === 'staff' && activeSection === 'profile' ? <ProfileSection clinics={clinics} currentUser={currentUser} /> : null}

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
                  <h3>Open QueueControl Dashboard</h3>
                  <p className="muted">Open the live simulation dashboard in a new tab and compare different queue scenarios.</p>
                </div>
                <a className="queuecontrol-link" href={QUEUECONTROL_DASHBOARD_URL} target="_blank" rel="noreferrer">
                  Open Simulation
                </a>
              </div>
            </section>
          ) : null}

          {currentUser.role === 'manager' && activeSection === 'add-member' ? (
            <section className="panel account-panel">
              <div className="panel-heading-row">
                <div>
                  <h2 className="section-title">Add Member Dashboard</h2>
                  <p className="section-subtitle">Search existing staff members, filter by clinic, and open the add-member form whenever a new staff account is needed.</p>
                </div>
                <button type="button" className="btn" onClick={onOpenAddMemberForm}>
                  Add Member
                </button>
              </div>

              <div className="manager-search-grid">
                <div className="field">
                  <label htmlFor="member-query">Search staff</label>
                  <input id="member-query" type="text" value={managerStaffFilters.query} onChange={(event) => onManagerStaffFilterChange('query', event.target.value)} placeholder="Search by name or email" />
                </div>
                <div className="field">
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
                <div className="manager-search-actions">
                  <button type="button" className="btn secondary" onClick={onManagerStaffFilterReset}>
                    Reset Search
                  </button>
                </div>
              </div>

              <div className="muted small">{managerStaffDirectory.total_results || 0} staff members found</div>
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


