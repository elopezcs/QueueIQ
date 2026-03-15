import React, { useEffect, useMemo, useState } from 'react';
import {
  chatTurn,
  clearStoredToken,
  demoLogin,
  endChat,
  getAdminResults,
  getClinics,
  getDemoUsers,
  getMe,
  getMyAppointments,
  getStoredToken,
  logout,
  setStoredToken,
  startChat,
} from './api.js';
import Navigation from './components/Navigation.jsx';
import ClinicSelector from './components/ClinicSelector.jsx';
import ChatbotModal from './components/ChatbotModal.jsx';
import FloatingButton from './components/FloatingButton.jsx';
import ResultsView from './components/ResultsView.jsx';
import AboutPage from './pages/AboutPage.jsx';
import ContactPage from './pages/ContactPage.jsx';
import LoginDemosPage from './pages/LoginDemosPage.jsx';
import PrivacyPage from './pages/PrivacyPage.jsx';
import TeamPage from './pages/TeamPage.jsx';

const DEFAULT_ADMIN_FILTERS = {
  clinicId: '',
  urgencyBand: '',
  visitCategory: '',
  patientQuery: '',
  createdFrom: '',
  createdTo: '',
};

export default function App() {
  const [currentPage, setCurrentPage] = useState('home');
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

  const [appointments, setAppointments] = useState({ upcoming: [], past: [] });
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentNotice, setAppointmentNotice] = useState('');

  const [adminFilters, setAdminFilters] = useState(DEFAULT_ADMIN_FILTERS);
  const [adminResults, setAdminResults] = useState({ clinic_id: null, total_results: 0, results: [] });
  const [adminLoading, setAdminLoading] = useState(false);
  const [adminError, setAdminError] = useState('');

  const hasSession = useMemo(() => !!sessionId, [sessionId]);
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

  useEffect(() => {
    (async () => {
      const [clinicData, demoData] = await Promise.all([getClinics(), getDemoUsers()]);
      setClinics(clinicData);
      setDemoUsers(demoData);
      if (clinicData.length) {
        setClinicId((current) => current || clinicData[0].id);
      }

      const token = getStoredToken();
      if (!token) return;
      try {
        const me = await getMe();
        setCurrentUser(me);
      } catch {
        clearStoredToken();
      }
    })().catch((error) => {
      console.error(error);
      setAuthError(error.message || 'Unable to load startup data');
    });
  }, []);

  useEffect(() => {
    if (currentPage !== 'login-demos' || !currentUser || currentUser.is_admin) {
      if (!currentUser || currentUser.is_admin) {
        setAppointments({ upcoming: [], past: [] });
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
  }, [currentUser, currentPage]);

  useEffect(() => {
    if (currentPage !== 'login-demos' || !currentUser || !currentUser.is_admin) {
      if (!currentUser || !currentUser.is_admin) {
        setAdminResults({ clinic_id: null, total_results: 0, results: [] });
        setAdminError('');
      }
      return;
    }

    (async () => {
      setAdminLoading(true);
      setAdminError('');
      try {
        setAdminResults(await getAdminResults(adminFilters));
      } catch (error) {
        setAdminError(error.message || 'Unable to load admin results');
      } finally {
        setAdminLoading(false);
      }
    })();
  }, [currentUser, currentPage, adminFilters]);

  async function handleDemoLogin(email) {
    setAuthLoading(true);
    setAuthError('');
    try {
      const res = await demoLogin(email);
      setStoredToken(res.token);
      setCurrentUser(res.patient);
      setCurrentPage('login-demos');
    } catch (error) {
      setAuthError(error.message || 'Unable to log in');
    } finally {
      setAuthLoading(false);
    }
  }

  async function handleLogout() {
    setAuthLoading(true);
    try {
      await logout();
    } catch (error) {
      console.error(error);
    } finally {
      clearStoredToken();
      setCurrentUser(null);
      setAppointments({ upcoming: [], past: [] });
      setAdminResults({ clinic_id: null, total_results: 0, results: [] });
      setAdminFilters(DEFAULT_ADMIN_FILTERS);
      setAuthLoading(false);
    }
  }

  function handleAdminFilterChange(field, value) {
    setAdminFilters((current) => ({ ...current, [field]: value }));
  }

  function handleAdminFilterReset() {
    setAdminFilters(DEFAULT_ADMIN_FILTERS);
  }

  async function handleStart() {
    setLoading(true);
    setResults(null);
    setMessages([]);
    setDone(false);
    setIsModalOpen(true);

    try {
      const res = await startChat(clinicId);
      setSessionId(res.session_id);
      setDisclaimers(res.disclaimers || []);
      setMessages([{ role: 'assistant', content: res.assistant_message }]);
      setProgress({ turn_count: 0, max_turns: 10 });
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(userText) {
    if (!hasSession || done) return;

    setMessages((m) => [...m, { role: 'user', content: userText }]);
    setLoading(true);

    try {
      const res = await chatTurn(sessionId, userText);
      setMessages((m) => [...m, { role: 'assistant', content: res.assistant_message }]);
      setDone(!!res.done);
      setProgress(res.progress || progress);
    } finally {
      setLoading(false);
    }
  }

  async function handleFinish() {
    if (!hasSession) return;
    setLoading(true);
    try {
      const res = await endChat(sessionId);
      const isEmergencyResult =
        String(res?.urgency_band || '').toLowerCase() === 'high' &&
        String(res?.visit_category || '').toLowerCase() === 'urgent';

      if (isEmergencyResult) {
        setIsModalOpen(false);
        handleReset();
        return;
      }

      setResults(res);
      setIsModalOpen(false);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setSessionId('');
    setMessages([]);
    setDisclaimers([]);
    setProgress({ turn_count: 0, max_turns: 10 });
    setDone(false);
    setResults(null);
    setAppointmentNotice('');
  }

  async function handleResetAndRestart() {
    setLoading(true);
    setResults(null);
    setMessages([]);
    setDone(false);
    setDisclaimers([]);
    setProgress({ turn_count: 0, max_turns: 10 });

    try {
      const res = await startChat(clinicId);
      setSessionId(res.session_id);
      setDisclaimers(res.disclaimers || []);
      setMessages([{ role: 'assistant', content: res.assistant_message }]);
      setProgress({ turn_count: 0, max_turns: 10 });
    } finally {
      setLoading(false);
    }
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
                  <button className="btn" onClick={handleStart} disabled={!clinicId || loading}>
                    Start intake
                  </button>
                ) : (
                  <>
                    {!results && (
                      <button className="btn" onClick={handleFinish} disabled={loading}>
                        Finish
                      </button>
                    )}
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
                  {activeDisclaimers.map((item, idx) => (
                    <div key={idx}>- {item}</div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {results ? (
          <section className="grid">
            <div className="panel">
              <ResultsView results={results} clinic={selectedClinic} />
            </div>
          </section>
        ) : null}

        <FloatingButton
          onClick={() => setIsModalOpen(true)}
          onStartSession={handleStart}
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
          hasResults={!!results}
        />

        {loading && <div className="toast">Working...</div>}
      </div>
    );
  }

  return (
    <div className="app">
      <Navigation
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        onHomeClick={() => {
          setCurrentPage('home');
          handleReset();
        }}
      />

      {currentPage === 'home' ? renderHomePage() : null}
      {currentPage === 'login-demos' ? (
        <LoginDemosPage
          currentUser={currentUser}
          demoUsers={demoUsers}
          authLoading={authLoading}
          authError={authError}
          onDemoLogin={handleDemoLogin}
          onLogout={handleLogout}
          appointments={appointments}
          appointmentsLoading={appointmentsLoading}
          appointmentNotice={appointmentNotice}
          adminFilters={adminFilters}
          clinics={clinics}
          onAdminFilterChange={handleAdminFilterChange}
          onAdminFilterReset={handleAdminFilterReset}
          adminResults={adminResults}
          adminLoading={adminLoading}
          adminError={adminError}
        />
      ) : null}
      {currentPage === 'about' ? <AboutPage /> : null}
      {currentPage === 'team' ? <TeamPage /> : null}
      {currentPage === 'privacy' ? <PrivacyPage /> : null}
      {currentPage === 'contact' ? <ContactPage /> : null}
    </div>
  );
}
