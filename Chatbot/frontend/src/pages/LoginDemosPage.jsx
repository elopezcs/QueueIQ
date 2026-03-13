import React from 'react';

function formatDateTime(value) {
  return new Date(value).toLocaleString([], {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatDate(value) {
  return new Date(value).toLocaleDateString([], {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatTime(value) {
  return new Date(value).toLocaleTimeString([], {
    hour: 'numeric',
    minute: '2-digit',
  });
}

function formatClinicLabel(value) {
  return String(value || '')
    .split('-')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function relativeLabel(value) {
  const now = new Date();
  const target = new Date(value);
  const diffDays = Math.round((target.getTime() - now.getTime()) / 86400000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Tomorrow';
  if (diffDays > 1) return `In ${diffDays} days`;
  if (diffDays === -1) return 'Yesterday';
  return `${Math.abs(diffDays)} days ago`;
}

function countActiveFilters(filters) {
  return Object.values(filters || {}).filter((value) => String(value || '').trim() !== '').length;
}

export default function LoginDemosPage({
  currentUser,
  demoUsers,
  authLoading,
  authError,
  onDemoLogin,
  onLogout,
  appointments,
  appointmentsLoading,
  appointmentNotice,
  adminFilters,
  clinics,
  onAdminFilterChange,
  onAdminFilterReset,
  adminResults,
  adminLoading,
  adminError,
}) {
  const upcomingAppointments = appointments.upcoming.slice(0, 2);
  const historyAppointments = appointments.past.slice(0, 10);
  const lastVisit = historyAppointments[0] || null;
  const activeFilterCount = countActiveFilters(adminFilters);

  return (
    <div className="page-container login-demo-page">
      <header className="page-header login-demo-header">
        <h1>Login Demo Center</h1>
        <p>Use seeded local patient and admin accounts to showcase appointment visibility and clinic-level admin results.</p>
      </header>

      <section className="panel account-panel">
        <div className="panel-heading-row">
          <div>
            <h2 className="section-title">Local Demo Access</h2>
            <p className="section-subtitle">These demo accounts are seeded locally for patient and admin walkthroughs. No OTP is required for them.</p>
          </div>
          {currentUser ? (
            <button className="btn secondary" onClick={onLogout} disabled={authLoading}>
              Logout
            </button>
          ) : null}
        </div>

        {currentUser ? (
          <div className="account-summary enhanced-account-summary">
            <div>
              <div className="eyebrow-label">Signed In As</div>
              <strong>{currentUser.full_name}</strong>
              <div className="muted small">{currentUser.email}</div>
            </div>
            <span className={`role-badge ${currentUser.is_admin ? 'admin' : 'patient'}`}>
              {currentUser.is_admin ? 'Admin' : 'Patient'}
            </span>
          </div>
        ) : (
          <div className="demo-user-grid">
            {demoUsers.map((user) => (
              <button
                key={user.email}
                className="demo-user-card"
                onClick={() => onDemoLogin(user.email)}
                disabled={authLoading}
              >
                <div className="eyebrow-label">Demo Account</div>
                <strong>{user.full_name}</strong>
                <span>{user.email}</span>
                <span className={`role-badge ${user.is_admin ? 'admin' : 'patient'}`}>
                  {user.is_admin ? 'Admin' : 'Patient'}
                </span>
              </button>
            ))}
          </div>
        )}

        {authError ? <div className="inline-notice error">{authError}</div> : null}
      </section>

      {!currentUser ? (
        <section className="panel demo-guide-panel">
          <h2 className="section-title">What This Demo Shows</h2>
          <div className="demo-guide-grid">
            <div className="demo-guide-card">
              <strong>Patient demo</strong>
              <p>View upcoming appointments in a polished summary view, then browse a fuller appointment history below.</p>
            </div>
            <div className="demo-guide-card">
              <strong>Admin demo</strong>
              <p>Filter completed intake outputs by clinic, urgency, category, patient identity, and date range.</p>
            </div>
          </div>
        </section>
      ) : null}

      {currentUser && !currentUser.is_admin ? (
        <section className="panel appointments-panel portal-panel">
          <div className="panel-heading-row portal-heading-row">
            <div>
              <h2 className="section-title">My Appointments</h2>
              <p className="section-subtitle">A patient-style view of the next scheduled visits and recent clinic history for this demo user.</p>
            </div>
          </div>

          {appointmentNotice ? <div className="inline-notice error">{appointmentNotice}</div> : null}
          {appointmentsLoading ? <p className="muted">Loading appointments...</p> : null}

          {!appointmentsLoading ? (
            <>
              <div className="appointment-summary-strip">
                <div className="appointment-summary-card primary">
                  <span className="eyebrow-label">Upcoming Visits</span>
                  <strong>{appointments.upcoming.length}</strong>
                  <span className="muted">Currently scheduled</span>
                </div>
                <div className="appointment-summary-card">
                  <span className="eyebrow-label">History</span>
                  <strong>{historyAppointments.length}</strong>
                  <span className="muted">Recent visits shown</span>
                </div>
                <div className="appointment-summary-card">
                  <span className="eyebrow-label">Last Visit</span>
                  <strong>{lastVisit ? formatDate(lastVisit.scheduled_for) : 'No visits yet'}</strong>
                  <span className="muted">{lastVisit ? formatClinicLabel(lastVisit.clinic_id) : 'History will appear here'}</span>
                </div>
              </div>

              <div className="portal-section-header">
                <div>
                  <div className="eyebrow-label">Current and Upcoming</div>
                  <h3>Next Scheduled Appointments</h3>
                </div>
              </div>

              <div className="upcoming-highlight-grid professional-upcoming-grid">
                {upcomingAppointments.length > 0 ? (
                  upcomingAppointments.map((appointment, index) => (
                    <article key={appointment.appointment_id} className={`upcoming-highlight-card professional-upcoming-card ${index === 0 ? 'featured' : ''}`}>
                      <div className="upcoming-card-topline">
                        <span className="eyebrow-label">{index === 0 ? 'Primary Upcoming' : 'Also Scheduled'}</span>
                        <span className="status-pill scheduled">{appointment.status}</span>
                      </div>
                      <h4>{formatClinicLabel(appointment.clinic_id)}</h4>
                      <div className="appointment-date-block">
                        <strong>{formatDate(appointment.scheduled_for)}</strong>
                        <span>{formatTime(appointment.scheduled_for)}</span>
                      </div>
                      <div className="appointment-meta-grid">
                        <div>
                          <span className="meta-label">Timing</span>
                          <span>{relativeLabel(appointment.scheduled_for)}</span>
                        </div>
                        <div>
                          <span className="meta-label">Clinic</span>
                          <span>{appointment.clinic_id}</span>
                        </div>
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="upcoming-highlight-card professional-upcoming-card empty">
                    <span className="eyebrow-label">No upcoming appointment</span>
                    <strong>Nothing scheduled right now</strong>
                    <span className="muted">This demo user will receive fresh seeded appointments on the next demo login.</span>
                  </div>
                )}
              </div>

              <div className="portal-section-header history-section-header">
                <div>
                  <div className="eyebrow-label">Past Visits</div>
                  <h3>Appointment History</h3>
                </div>
                <span className="history-count-pill">{historyAppointments.length} records</span>
              </div>

              <div className="appointment-history-card professional-history-card">
                {!appointmentsLoading && historyAppointments.length === 0 ? <p className="muted">No appointment history found yet.</p> : null}
                <div className="appointment-history-list professional-history-list">
                  {historyAppointments.map((appointment, index) => (
                    <article key={appointment.appointment_id} className="history-entry-card">
                      <div className="history-entry-rail">
                        <span className="history-entry-dot" />
                        {index !== historyAppointments.length - 1 ? <span className="history-entry-line" /> : null}
                      </div>
                      <div className="history-entry-content">
                        <div className="history-entry-topline">
                          <div>
                            <h4>{formatClinicLabel(appointment.clinic_id)}</h4>
                            <div className="muted small">{appointment.clinic_id}</div>
                          </div>
                          <span className="status-pill completed">{appointment.status}</span>
                        </div>
                        <div className="history-entry-details">
                          <div>
                            <span className="meta-label">Visit Date</span>
                            <span>{formatDateTime(appointment.scheduled_for)}</span>
                          </div>
                          <div>
                            <span className="meta-label">Relative</span>
                            <span>{relativeLabel(appointment.scheduled_for)}</span>
                          </div>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {currentUser && currentUser.is_admin ? (
        <section className="panel admin-panel admin-portal-panel">
          <div className="panel-heading-row">
            <div>
              <h2 className="section-title">Admin Clinic Results</h2>
              <p className="section-subtitle">Filter intake outputs by clinic, urgency, visit category, patient identity, and created date.</p>
            </div>
          </div>

          <div className="admin-filter-panel">
            <div className="admin-filter-panel-topline">
              <div>
                <div className="eyebrow-label">Admin Filters</div>
                <h3>Refine Results</h3>
              </div>
              <div className="admin-filter-actions">
                <span className="history-count-pill">{activeFilterCount} active</span>
                <button className="btn secondary" onClick={onAdminFilterReset} disabled={adminLoading || activeFilterCount === 0}>
                  Clear filters
                </button>
              </div>
            </div>

            <div className="admin-filter-grid">
              <div className="field">
                <label htmlFor="admin-clinic">Clinic</label>
                <select id="admin-clinic" value={adminFilters.clinicId} onChange={(event) => onAdminFilterChange('clinicId', event.target.value)}>
                  <option value="">All clinics</option>
                  {clinics.map((clinic) => (
                    <option key={clinic.id} value={clinic.id}>
                      {clinic.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="admin-urgency">Urgency band</label>
                <select id="admin-urgency" value={adminFilters.urgencyBand} onChange={(event) => onAdminFilterChange('urgencyBand', event.target.value)}>
                  <option value="">All urgency levels</option>
                  <option value="low">Low</option>
                  <option value="medium">Medium</option>
                  <option value="high">High</option>
                </select>
              </div>

              <div className="field">
                <label htmlFor="admin-category">Visit category</label>
                <select id="admin-category" value={adminFilters.visitCategory} onChange={(event) => onAdminFilterChange('visitCategory', event.target.value)}>
                  <option value="">All categories</option>
                  <option value="general">General</option>
                  <option value="respiratory">Respiratory</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>

              <div className="field admin-search-field">
                <label htmlFor="admin-patient-search">Patient name or email</label>
                <input
                  id="admin-patient-search"
                  type="text"
                  placeholder="Search linked patient results"
                  value={adminFilters.patientQuery}
                  onChange={(event) => onAdminFilterChange('patientQuery', event.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="admin-created-from">Created from</label>
                <input
                  id="admin-created-from"
                  type="date"
                  value={adminFilters.createdFrom}
                  onChange={(event) => onAdminFilterChange('createdFrom', event.target.value)}
                />
              </div>

              <div className="field">
                <label htmlFor="admin-created-to">Created to</label>
                <input
                  id="admin-created-to"
                  type="date"
                  value={adminFilters.createdTo}
                  onChange={(event) => onAdminFilterChange('createdTo', event.target.value)}
                />
              </div>
            </div>
          </div>

          <div className="admin-dashboard-strip">
            <div className="admin-summary-card enhanced-admin-summary-card">
              <span className="muted small">Visible results</span>
              <strong>{adminResults.total_results}</strong>
            </div>
          </div>

          {adminError ? <div className="inline-notice error">{adminError}</div> : null}
          {adminLoading ? <p className="muted">Loading clinic results...</p> : null}
          {!adminLoading && adminResults.results.length === 0 ? <p className="muted">No results available for the selected filters yet.</p> : null}

          {adminResults.results.length > 0 ? (
            <div className="admin-results-table-wrapper">
              <table className="admin-results-table">
                <thead>
                  <tr>
                    <th>Clinic</th>
                    <th>Patient</th>
                    <th>Urgency</th>
                    <th>Category</th>
                    <th>Wait P50</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {adminResults.results.map((result) => (
                    <tr key={result.session_id}>
                      <td>{result.clinic_id}</td>
                      <td>{result.full_name || result.email || 'Guest user'}</td>
                      <td>{result.urgency_band}</td>
                      <td>{result.visit_category}</td>
                      <td>{result.wait_p50_minutes} min</td>
                      <td>{new Date(result.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
