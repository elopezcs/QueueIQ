import React, { useEffect, useMemo, useState } from 'react';
import {
  chatTurn,
  clearStoredToken,
  createAppointment,
  createStaffAccount,
  demoLogin,
  endChat,
  getClinics,
  getDemoUsers,
  getMe,
  getMyAppointments,
  getStaffAppointments,
  getStaffMembers,
  getStoredToken,
  loginAccount,
  logout,
  registerAccount,
  setStoredToken,
  startChat,
  updateMyProfile,
} from './api.js';
import Navigation from './components/Navigation.jsx';
import ClinicSelector from './components/ClinicSelector.jsx';
import ChatbotModal from './components/ChatbotModal.jsx';
import FloatingButton from './components/FloatingButton.jsx';
import ResultsView from './components/ResultsView.jsx';
import AboutPage from './pages/AboutPage.jsx';
import ContactPage from './pages/ContactPage.jsx';
import AccountPage from './pages/AccountPage.jsx';
import PrivacyPage from './pages/PrivacyPage.jsx';
import TeamPage from './pages/TeamPage.jsx';

const EMPTY_APPOINTMENTS = {
  current: [],
  upcoming: [],
  past: [],
};

const DEFAULT_STAFF_SEARCH = {
  timeBucket: 'today',
  patientQuery: '',
  scheduledFrom: '',
  scheduledTo: '',
};

const EMPTY_STAFF_APPOINTMENTS = {
  clinic_id: null,
  time_bucket: 'today',
  total_results: 0,
  results: [],
};

const DEFAULT_MANAGER_STAFF_FILTERS = {
  query: '',
  clinicId: '',
};

const EMPTY_MANAGER_STAFF_DIRECTORY = {
  clinic_id: null,
  query: null,
  total_results: 0,
  results: [],
};

function defaultAccountSectionForUser(user) {
  const role = String(user?.role || '').toLowerCase();
  if (role === 'staff') {
    return 'dashboard';
  }
  if (role === 'manager') {
    return 'simulations';
  }
  if (role === 'patient') {
    return 'my-appointments';
  }
  return 'auth';
}

function toAppointmentDescription(results) {
  const explanation = String(results?.explanation || '')
    .replace(/\s+/g, ' ')
    .trim();
  const firstSentence = explanation.split(/(?<=[.!?])\s+/)[0] || explanation;
  const urgency = String(results?.urgency_band || '').trim();
  const category = String(results?.visit_category || '').trim();
  const prefix = [category, urgency ? `${urgency} urgency` : '']
    .filter(Boolean)
    .join(' - ');
  const combined = [prefix, firstSentence]
    .filter(Boolean)
    .join(': ')
    .trim();
  return combined ? combined.slice(0, 280) : null;
}

export default function App() {
  const [currentPage, setCurrentPage] = useState('home');
  const [accountSection, setAccountSection] = useState('auth');
  const [clinics, setClinics] = useState([]);
  const [clinicId, setClinicId] = useState('');
  const [loading, setLoading] = useState(false);

  const [sessionId, setSessionId] = useState('');
  const [messages, setMessages] = useState([]);
  const [disclaimers, setDisclaimers] = useState([]);
  const [progress, setProgress] = useState({ turn_count: 0, max_turns: 10 });
  const [done, setDone] = useState(false);
  const [results, setResults] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [demoUsers, setDemoUsers] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  const [appointments, setAppointments] = useState(EMPTY_APPOINTMENTS);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentNotice, setAppointmentNotice] = useState('');
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingNotice, setBookingNotice] = useState('');
  const [pendingBooking, setPendingBooking] = useState(null);

  const [staffSearch, setStaffSearch] = useState(DEFAULT_STAFF_SEARCH);
  const [appliedStaffSearch, setAppliedStaffSearch] = useState(DEFAULT_STAFF_SEARCH);
  const [staffAppointments, setStaffAppointments] = useState(EMPTY_STAFF_APPOINTMENTS);
  const [staffLoading, setStaffLoading] = useState(false);
  const [staffError, setStaffError] = useState('');

  const [managerStaffFilters, setManagerStaffFilters] = useState(DEFAULT_MANAGER_STAFF_FILTERS);
  const [managerStaffDirectory, setManagerStaffDirectory] = useState(EMPTY_MANAGER_STAFF_DIRECTORY);
  const [managerStaffLoading, setManagerStaffLoading] = useState(false);
  const [managerStaffError, setManagerStaffError] = useState('');
  const [isAddMemberFormOpen, setIsAddMemberFormOpen] = useState(false);

  const [staffCreationLoading, setStaffCreationLoading] = useState(false);
  const [staffCreationNotice, setStaffCreationNotice] = useState('');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileNotice, setProfileNotice] = useState('');

  const hasSession = useMemo(() => Boolean(sessionId), [sessionId]);
  const isStaffUser = useMemo(() => String(currentUser?.role || '').toLowerCase() === 'staff', [currentUser]);
  const selectedClinic = useMemo(() => clinics.find((clinic) => clinic.id === clinicId) || null, [clinics, clinicId]);
  const activeDisclaimers = useMemo(
    () =>
      disclaimers.length > 0
        ? disclaimers
        : [
            'This tool provides operational guidance only. It is not a medical diagnosis.',
            'If you think this is an emergency or severe, seek urgent in-person care or call local emergency services.',
            'Wait-time estimates are not guaranteed and may change.',
          ],
    [disclaimers],
  );

  const userTurnCount = useMemo(
    () => messages.filter((message) => message.role === 'user').length,
    [messages],
  );
  const canFinishAssessment = useMemo(
    () => hasSession && !results && done && userTurnCount > 0 && !loading,
    [done, hasSession, loading, results, userTurnCount],
  );

  function handleReset() {
    setSessionId('');
    setMessages([]);
    setDisclaimers([]);
    setProgress({ turn_count: 0, max_turns: 10 });
    setDone(false);
    setResults(null);
  }

  function applyAuthenticatedUser(user) {
    setCurrentUser(user);
    setAccountSection(defaultAccountSectionForUser(user));
    setAuthError('');
    setAppointments(EMPTY_APPOINTMENTS);
    setAppointmentNotice('');
    setStaffSearch(DEFAULT_STAFF_SEARCH);
    setAppliedStaffSearch(DEFAULT_STAFF_SEARCH);
    setStaffAppointments(EMPTY_STAFF_APPOINTMENTS);
    setStaffError('');
    setManagerStaffFilters(DEFAULT_MANAGER_STAFF_FILTERS);
    setManagerStaffDirectory(EMPTY_MANAGER_STAFF_DIRECTORY);
    setManagerStaffError('');
    setIsAddMemberFormOpen(false);
    setStaffCreationNotice('');
    setProfileNotice('');
  }

  async function refreshManagerStaffDirectory(filters = managerStaffFilters) {
    setManagerStaffLoading(true);
    setManagerStaffError('');
    try {
      setManagerStaffDirectory(await getStaffMembers(filters));
    } catch (error) {
      setManagerStaffError(error.message || 'Unable to load staff members');
    } finally {
      setManagerStaffLoading(false);
    }
  }

  async function bookAppointmentFromAssessment(assessment) {
    if (!assessment?.clinicId || !assessment?.results) {
      setBookingNotice('Complete the chatbot flow first to book an appointment.');
      return false;
    }

    setBookingLoading(true);
    setBookingNotice('');

    try {
      await createAppointment(
        assessment.clinicId,
        new Date().toISOString(),
        toAppointmentDescription(assessment.results),
        assessment.sessionId || null,
      );
      setAppointments(await getMyAppointments());
      setBookingNotice('Appointment booked successfully from your chatbot assessment.');
      setPendingBooking(null);
      handleReset();
      setCurrentPage('account');
      setAccountSection('my-appointments');
      return true;
    } catch (error) {
      setBookingNotice(error.message || 'Unable to book appointment');
      return false;
    } finally {
      setBookingLoading(false);
    }
  }

  useEffect(() => {
    (async () => {
      const clinicData = await getClinics();
      const demoData = await getDemoUsers().catch(() => []);
      setClinics(clinicData);
      setDemoUsers(demoData);
      if (clinicData.length) {
        setClinicId((current) => current || clinicData[0].id);
      }

      const token = getStoredToken();
      if (!token) {
        return;
      }

      try {
        const me = await getMe();
        applyAuthenticatedUser(me);
      } catch {
        clearStoredToken();
      }
    })().catch((error) => {
      console.error(error);
      setAuthError(error.message || 'Unable to load startup data');
    });
  }, []);

  useEffect(() => {
    if (currentPage !== 'account' || !currentUser || currentUser.role !== 'patient' || accountSection !== 'my-appointments') {
      if (!currentUser || currentUser.role !== 'patient') {
        setAppointments(EMPTY_APPOINTMENTS);
        setAppointmentNotice('');
      }
      return;
    }

    (async () => {
      setAppointmentsLoading(true);
      setAppointmentNotice('');
      try {
        setAppointments(await getMyAppointments());
      } catch (error) {
        setAppointmentNotice(error.message || 'Unable to load appointments');
      } finally {
        setAppointmentsLoading(false);
      }
    })();
  }, [accountSection, currentPage, currentUser]);

  useEffect(() => {
    if (currentPage !== 'account' || !currentUser || currentUser.role !== 'staff' || accountSection !== 'dashboard') {
      if (!currentUser || currentUser.role !== 'staff') {
        setStaffAppointments(EMPTY_STAFF_APPOINTMENTS);
        setStaffError('');
      }
      return;
    }

    (async () => {
      setStaffLoading(true);
      setStaffError('');
      try {
        setStaffAppointments(await getStaffAppointments(appliedStaffSearch));
      } catch (error) {
        setStaffError(error.message || 'Unable to load staff appointments');
      } finally {
        setStaffLoading(false);
      }
    })();
  }, [accountSection, appliedStaffSearch, currentPage, currentUser]);

  useEffect(() => {
    if (currentPage !== 'account' || !currentUser || currentUser.role !== 'manager' || accountSection !== 'add-member') {
      if (!currentUser || currentUser.role !== 'manager') {
        setManagerStaffDirectory(EMPTY_MANAGER_STAFF_DIRECTORY);
        setManagerStaffError('');
      }
      return;
    }

    refreshManagerStaffDirectory(managerStaffFilters);
  }, [accountSection, currentPage, currentUser, managerStaffFilters]);

  useEffect(() => {
    if (!isStaffUser) {
      return;
    }

    if (currentPage !== 'account') {
      setCurrentPage('account');
    }

    if (accountSection !== 'dashboard' && accountSection !== 'profile') {
      setAccountSection('dashboard');
    }
  }, [accountSection, currentPage, isStaffUser]);

  async function completeAuth(authPromise) {
    setAuthLoading(true);
    setAuthError('');
    try {
      const response = await authPromise;
      setStoredToken(response.token);
      applyAuthenticatedUser(response.patient);

      if (response.patient.role === 'patient' && pendingBooking) {
        await bookAppointmentFromAssessment(pendingBooking);
      } else {
        setCurrentPage('account');
      }

      return true;
    } catch (error) {
      setAuthError(error.message || 'Unable to authenticate');
      return false;
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleDemoLogin(email) {
    return completeAuth(demoLogin(email));
  }

  async function handleLogin(credentials) {
    return completeAuth(loginAccount(credentials));
  }

  async function handleRegister(details) {
    return completeAuth(registerAccount(details));
  }

  async function handleLogout() {
    setAuthLoading(true);
    try {
      await logout();
    } catch (error) {
      console.error(error);
    } finally {
      clearStoredToken();
      applyAuthenticatedUser(null);
      setCurrentUser(null);
      setAuthLoading(false);
      setCurrentPage('account');
    }
  }

  function handleStaffSearchChange(field, value) {
    setStaffSearch((current) => ({ ...current, [field]: value }));
  }

  function handleStaffSearchSubmit() {
    setAppliedStaffSearch({ ...staffSearch });
  }

  function handleStaffSearchReset() {
    setStaffSearch(DEFAULT_STAFF_SEARCH);
    setAppliedStaffSearch(DEFAULT_STAFF_SEARCH);
  }

  function handleManagerStaffFilterChange(field, value) {
    setManagerStaffFilters((current) => ({ ...current, [field]: value }));
  }

  function handleManagerStaffFilterReset() {
    setManagerStaffFilters(DEFAULT_MANAGER_STAFF_FILTERS);
  }

  async function handleCreateStaff(form) {
    setStaffCreationLoading(true);
    setStaffCreationNotice('');

    try {
      const created = await createStaffAccount(form);
      const clinicLabel = created.clinic_id || form.clinicId;
      setStaffCreationNotice(`${created.full_name} was added for ${clinicLabel}.`);
      if (currentUser?.role === 'manager') {
        await refreshManagerStaffDirectory(managerStaffFilters);
      }
      return true;
    } catch (error) {
      setStaffCreationNotice(error.message || 'Unable to create staff account');
      return false;
    } finally {
      setStaffCreationLoading(false);
    }
  }

  async function handleUpdateProfile(payload) {
    setProfileSaving(true);
    setProfileNotice('');
    try {
      const updated = await updateMyProfile(payload);
      setCurrentUser(updated);
      setProfileNotice('Profile updated successfully.');
      return { ok: true, patient: updated };
    } catch (error) {
      const message = error.message || 'Unable to update profile';
      setProfileNotice(message);
      return { ok: false, message };
    } finally {
      setProfileSaving(false);
    }
  }

  function handleNavigateToAccountSection(section) {
    setCurrentPage('account');
    setAccountSection(section || defaultAccountSectionForUser(currentUser));
  }

  async function handleStart(targetClinicId = clinicId) {
    if (!targetClinicId) {
      return;
    }

    setLoading(true);
    setResults(null);
    setMessages([]);
    setDone(false);
    setBookingNotice('');
    setIsModalOpen(true);

    try {
      const response = await startChat(targetClinicId);
      setSessionId(response.session_id);
      setDisclaimers(response.disclaimers || []);
      setMessages([{ role: 'assistant', content: response.assistant_message }]);
      setProgress({ turn_count: 0, max_turns: 10 });
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(userText) {
    if (!hasSession || done) {
      return;
    }

    setMessages((current) => [...current, { role: 'user', content: userText }]);
    setLoading(true);

    try {
      const response = await chatTurn(sessionId, userText);
      setMessages((current) => [...current, { role: 'assistant', content: response.assistant_message }]);
      setDone(Boolean(response.done));
      setProgress(response.progress || progress);
    } finally {
      setLoading(false);
    }
  }

  async function handleFinish() {
    if (!canFinishAssessment) {
      return;
    }

    setLoading(true);
    try {
      const response = await endChat(sessionId);
      const isEmergencyResult =
        String(response?.urgency_band || '').toLowerCase() === 'high' &&
        String(response?.visit_category || '').toLowerCase() === 'urgent';

      if (isEmergencyResult) {
        setIsModalOpen(false);
        handleReset();
        return;
      }

      setResults(response);
      setIsModalOpen(false);
    } finally {
      setLoading(false);
    }
  }

  async function handleResetAndRestart() {
    setLoading(true);
    setResults(null);
    setMessages([]);
    setDone(false);
    setDisclaimers([]);
    setProgress({ turn_count: 0, max_turns: 10 });
    setBookingNotice('');

    try {
      const response = await startChat(clinicId);
      setSessionId(response.session_id);
      setDisclaimers(response.disclaimers || []);
      setMessages([{ role: 'assistant', content: response.assistant_message }]);
      setProgress({ turn_count: 0, max_turns: 10 });
    } finally {
      setLoading(false);
    }
  }

  async function handleBookAppointmentFromResults() {
    const targetClinicId = selectedClinic?.id || clinicId || clinics[0]?.id || '';
    if (!results || !targetClinicId) {
      setBookingNotice('Complete the chatbot assessment first.');
      return;
    }

    const assessment = {
      sessionId,
      clinicId: targetClinicId,
      results,
    };

    if (!currentUser) {
      setPendingBooking(assessment);
      setAuthError('Sign in or register as a patient to complete this booking.');
      setCurrentPage('account');
      setAccountSection('auth');
      return;
    }

    if (currentUser.role !== 'patient') {
      setBookingNotice('Please use a patient account to book an appointment.');
      return;
    }

    await bookAppointmentFromAssessment(assessment);
  }

  async function handleBeginBookingJourney() {
    const targetClinicId = clinicId || clinics[0]?.id || '';
    if (!targetClinicId) {
      return;
    }

    setCurrentPage('home');
    if (!clinicId) {
      setClinicId(targetClinicId);
    }
    handleReset();
    await handleStart(targetClinicId);
  }

  function renderHomePage() {
    return (
      <div className="container">
        <header className="header content-header">
          <h1>QueueIQ ArrivalSignal</h1>
          <p className="subtitle">Pre-arrival intake for operational queue planning and chatbot-guided queue estimates.</p>
        </header>

        <section className="panel intake-intro-panel">
          <div className="intake-intro-copy">
            <h2 className="section-title">Clinic Intake</h2>
            <p className="section-subtitle">
              Select a clinic, review the operational guidance, and start the chatbot when you are ready to collect intake details.
            </p>
          </div>
        </section>

        <section className="panel intake-layout-panel">
          <div className="intake-layout">
            <div className="intake-column intake-form-column">
              <ClinicSelector clinics={clinics} clinicId={clinicId} setClinicId={setClinicId} disabled={hasSession} />

              <div className="row">
                {!hasSession ? (
                  <button className="btn" onClick={() => handleStart(clinicId)} disabled={!clinicId || loading}>
                    Start intake
                  </button>
                ) : (
                  <>
                    {!results ? (
                      <button className="btn" onClick={() => setIsModalOpen(true)} disabled={loading}>
                        {done ? 'Review chat' : 'Resume intake'}
                      </button>
                    ) : null}
                    <button className="btn secondary" onClick={handleReset} disabled={loading}>
                      Reset
                    </button>
                  </>
                )}
              </div>
            </div>

            <div className="intake-column disclaimer-column">
              <div className="disclaimer-box intake-disclaimer-box">
                <div className="disclaimer-title">Important</div>
                <div className="disclaimer-subtitle">This is not a diagnosis. Wait-time estimates are not guaranteed.</div>
                <div className="disclaimer-list">
                  {activeDisclaimers.map((item, index) => (
                    <div key={index}>- {item}</div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {results ? (
          <section className="grid">
            <div className="panel">
              <ResultsView
                results={results}
                clinic={selectedClinic}
                onBookNow={handleBookAppointmentFromResults}
                bookingLoading={bookingLoading}
                bookingNotice={bookingNotice}
              />
            </div>
          </section>
        ) : null}

        <FloatingButton
          onClick={() => setIsModalOpen(true)}
          onStartSession={() => handleStart(clinicId)}
          isActive={isModalOpen}
          hasSession={hasSession}
          disabled={!clinicId || loading}
        />

        <ChatbotModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          messages={messages}
          onSend={handleSend}
          disabled={!hasSession || loading}
          done={done}
          progress={progress}
          onFinish={handleFinish}
          onReset={handleResetAndRestart}
          loading={loading}
          hasResults={Boolean(results)}
        />

        {loading ? <div className="toast">Working...</div> : null}
      </div>
    );
  }

  return (
    <div className={`app ${isStaffUser ? 'staff-focus-mode' : ''}`}>
      <Navigation
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        onHomeClick={() => {
          if (isStaffUser) {
            setCurrentPage('account');
            setAccountSection('dashboard');
            return;
          }
          setCurrentPage('home');
          handleReset();
        }}
        currentUser={currentUser}
        clinics={clinics}
        accountSection={accountSection}
        onNavigateToAccountSection={handleNavigateToAccountSection}
        onLogout={handleLogout}
      />

      {currentPage === 'home' ? renderHomePage() : null}
      {currentPage === 'account' ? (
        <AccountPage
          currentUser={currentUser}
          activeSection={accountSection}
          demoUsers={demoUsers}
          authLoading={authLoading}
          authError={authError}
          bookingIntentActive={Boolean(pendingBooking)}
          onLogin={handleLogin}
          onRegister={handleRegister}
          onDemoLogin={handleDemoLogin}
          clinics={clinics}
          appointments={appointments}
          appointmentsLoading={appointmentsLoading}
          appointmentNotice={appointmentNotice}
          onBeginBookingJourney={handleBeginBookingJourney}
          bookingLoading={bookingLoading}
          bookingNotice={bookingNotice}
          staffSearch={staffSearch}
          appliedStaffSearch={appliedStaffSearch}
          onStaffSearchChange={handleStaffSearchChange}
          onStaffSearchSubmit={handleStaffSearchSubmit}
          onStaffSearchReset={handleStaffSearchReset}
          staffAppointments={staffAppointments}
          staffLoading={staffLoading}
          staffError={staffError}
          managerStaffFilters={managerStaffFilters}
          onManagerStaffFilterChange={handleManagerStaffFilterChange}
          onManagerStaffFilterReset={handleManagerStaffFilterReset}
          managerStaffDirectory={managerStaffDirectory}
          managerStaffLoading={managerStaffLoading}
          managerStaffError={managerStaffError}
          onCreateStaff={handleCreateStaff}
          staffCreationLoading={staffCreationLoading}
          staffCreationNotice={staffCreationNotice}
          profileSaving={profileSaving}
          profileNotice={profileNotice}
          onUpdateProfile={handleUpdateProfile}
          isAddMemberFormOpen={isAddMemberFormOpen}
          onOpenAddMemberForm={() => setIsAddMemberFormOpen(true)}
          onCloseAddMemberForm={() => setIsAddMemberFormOpen(false)}
        />
      ) : null}
      {currentPage === 'about' ? <AboutPage /> : null}
      {currentPage === 'team' ? <TeamPage /> : null}
      {currentPage === 'privacy' ? <PrivacyPage /> : null}
      {currentPage === 'contact' ? <ContactPage /> : null}
    </div>
  );
}



