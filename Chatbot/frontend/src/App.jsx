import React, { useEffect, useMemo, useState } from "react";
import { getClinics, startChat, chatTurn, endChat } from "./api.js";
import Navigation from "./components/Navigation.jsx";
import ClinicSelector from "./components/ClinicSelector.jsx";
import ChatWidget from "./components/ChatWidget.jsx";
import ChatbotModal from "./components/ChatbotModal.jsx";
import FloatingButton from "./components/FloatingButton.jsx";
import ResultsView from "./components/ResultsView.jsx";
import HomePage from "./pages/HomePage.jsx";
import AboutPage from "./pages/AboutPage.jsx";
import TeamPage from "./pages/TeamPage.jsx";
import PrivacyPage from "./pages/PrivacyPage.jsx";
import ContactPage from "./pages/ContactPage.jsx";

export default function App() {
  const [currentPage, setCurrentPage] = useState("home");
  const [clinics, setClinics] = useState([]);
  const [clinicId, setClinicId] = useState("");
  const [loading, setLoading] = useState(false);

  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState([]);
  const [disclaimers, setDisclaimers] = useState([]);
  const [progress, setProgress] = useState({ turn_count: 0, max_turns: 10 });
  const [done, setDone] = useState(false);

  const [results, setResults] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const hasSession = useMemo(() => !!sessionId, [sessionId]);

  useEffect(() => {
    (async () => {
      const data = await getClinics();
      setClinics(data);
      if (data.length) setClinicId(data[0].id);
    })().catch((e) => console.error(e));
  }, []);

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
      setMessages([{ role: "assistant", content: res.assistant_message }]);
      setProgress({ turn_count: 0, max_turns: 10 });
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(userText) {
    if (!hasSession || done) return;

    setMessages((m) => [...m, { role: "user", content: userText }]);
    setLoading(true);

    try {
      const res = await chatTurn(sessionId, userText);
      setMessages((m) => [...m, { role: "assistant", content: res.assistant_message }]);
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
      setResults(res);
      setIsModalOpen(false);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setSessionId("");
    setMessages([]);
    setDisclaimers([]);
    setProgress({ turn_count: 0, max_turns: 10 });
    setDone(false);
    setResults(null);
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
      setMessages([{ role: "assistant", content: res.assistant_message }]);
      setProgress({ turn_count: 0, max_turns: 10 });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <Navigation 
        currentPage={currentPage} 
        setCurrentPage={setCurrentPage}
        onHomeClick={() => {
          setCurrentPage("home");
          handleReset();
        }}
      />

      {/* Home/Chat Page */}
      {currentPage === "home" ? (
        <div className="container">
          <header className="header">
            <h1>QueueIQ ArrivalSignal</h1>
            <p className="subtitle">Pre-arrival intake for operational queue planning (non-diagnostic)</p>
          </header>

          <section className="panel">
            <ClinicSelector
              clinics={clinics}
              clinicId={clinicId}
              setClinicId={setClinicId}
              disabled={hasSession}
            />

            <div className="row">
              {!hasSession ? (
                <button className="btn" onClick={handleStart} disabled={!clinicId || loading}>
                  Start intake
                </button>
              ) : (
                <>
                  <button className="btn" onClick={handleFinish} disabled={loading}>
                    Finish
                  </button>
                  <button className="btn secondary" onClick={handleReset} disabled={loading}>
                    Reset
                  </button>
                </>
              )}
            </div>

            <div className="disclaimer">
              {disclaimers.map((d, idx) => (
                <div key={idx}>• {d}</div>
              ))}
            </div>
          </section>

          <section className="grid">
            <div className="panel">
              <ResultsView results={results} />
            </div>
          </section>

          {/* Floating Button */}
          <FloatingButton 
            onClick={() => setIsModalOpen(true)} 
            onStartSession={handleStart}
            isActive={isModalOpen} 
            hasSession={hasSession}
            disabled={!clinicId || loading}
          />

          {/* Chatbot Modal */}
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
          />

          {loading && <div className="toast">Working…</div>}
        </div>
      ) : currentPage === "about" ? (
        <AboutPage />
      ) : currentPage === "team" ? (
        <TeamPage />
      ) : currentPage === "privacy" ? (
        <PrivacyPage />
      ) : currentPage === "contact" ? (
        <ContactPage />
      ) : null}
    </div>
  );
}
