import React, { useEffect, useRef, useState } from "react";
import { getVoiceConfig, transcribeVoiceAudio } from "../api.js";
import { useAssistantTTS } from "../features/voice/useAssistantTTS.js";

export default function ChatWidget({ messages, onSend, disabled, done, progress, onFinish, onReset, loading, hasResults = false, loginRequired = false, onLoginClick, onRegisterClick, preferredLanguage = "en" }) {
  const [text, setText] = useState("");
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [voiceOutputEnabled, setVoiceOutputEnabled] = useState(false);
  const [voiceState, setVoiceState] = useState("idle");
  const [voiceError, setVoiceError] = useState("");
  const [voiceMaxDurationSeconds, setVoiceMaxDurationSeconds] = useState(30);
  const [ttsMuted, setTtsMuted] = useState(false);
  const listRef = useRef(null);
  const inputRef = useRef(null);
  const inputPlaceholder = loginRequired
    ? "Log in to chat"
    : loading
      ? "Assistant is thinking..."
      : disabled
        ? "Start intake to chat"
        : "Type your message...";
  const mediaRecorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const chunksRef = useRef([]);
  const stopTimerRef = useRef(null);
  const previousAssistantCountRef = useRef(null);
  const {
    supported: ttsSupported,
    isSpeaking: isTtsSpeaking,
    lastError: ttsError,
    speak,
    replay,
    stop: stopSpeaking,
  } = useAssistantTTS();

  useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (!loading && !done && inputRef.current) {
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 10);
    }
  }, [loading, done]);

  useEffect(() => {
    let active = true;
    getVoiceConfig()
      .then((config) => {
        if (!active) return;
        const enabled = Boolean(config?.voice_input_enabled);
        setVoiceEnabled(enabled);
        setVoiceOutputEnabled(Boolean(config?.voice_output_enabled));
        setVoiceMaxDurationSeconds(Math.max(5, Number(config?.max_duration_seconds) || 30));
      })
      .catch(() => {
        if (!active) return;
        setVoiceEnabled(false);
        setVoiceOutputEnabled(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (stopTimerRef.current) {
        window.clearTimeout(stopTimerRef.current);
        stopTimerRef.current = null;
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
      }
      stopSpeaking();
    };
  }, [stopSpeaking]);

  useEffect(() => {
    if (previousAssistantCountRef.current !== null) {
      return;
    }
    const initialAssistantCount = messages
      .filter((message) => message.role === "assistant")
      .map((message) => String(message.content || "").trim())
      .filter(Boolean).length;
    previousAssistantCountRef.current = initialAssistantCount;
  }, [messages]);

  useEffect(() => {
    if (!voiceOutputEnabled || !ttsSupported || ttsMuted) {
      return;
    }
    const assistantMessages = messages
      .filter((message) => message.role === "assistant")
      .map((message) => String(message.content || "").trim())
      .filter(Boolean);

    if (assistantMessages.length === 0) return;

    if (assistantMessages.length <= previousAssistantCountRef.current) {
      previousAssistantCountRef.current = assistantMessages.length;
      return;
    }

    const latestContent = assistantMessages[assistantMessages.length - 1];
    const spoke = speak(latestContent, { language: preferredLanguage });
    if (spoke) previousAssistantCountRef.current = assistantMessages.length;
  }, [messages, preferredLanguage, speak, ttsMuted, ttsSupported, voiceOutputEnabled]);

  useEffect(() => {
    if (ttsMuted && isTtsSpeaking) {
      stopSpeaking();
    }
  }, [isTtsSpeaking, stopSpeaking, ttsMuted]);

  function submit(e) {
    e.preventDefault();
    const msg = text.trim();
    if (!msg) return;
    setText("");
    onSend(msg);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }

  function cleanupRecordingResources() {
    if (stopTimerRef.current) {
      window.clearTimeout(stopTimerRef.current);
      stopTimerRef.current = null;
    }
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }
    mediaRecorderRef.current = null;
  }

  async function handleStartRecording() {
    if (!voiceEnabled || voiceState === "recording" || voiceState === "transcribing" || disabled || loginRequired) {
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || typeof MediaRecorder === "undefined") {
      setVoiceError("Voice input is not supported in this browser.");
      setVoiceState("error");
      return;
    }

    setVoiceError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      chunksRef.current = [];

      let mimeType = "";
      const preferredTypes = ["audio/webm", "audio/ogg", "audio/mp4"];
      if (typeof MediaRecorder.isTypeSupported === "function") {
        mimeType = preferredTypes.find((type) => MediaRecorder.isTypeSupported(type)) || "";
      }
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setVoiceError("Could not record audio.");
        setVoiceState("error");
        cleanupRecordingResources();
      };

      recorder.onstop = async () => {
        const chunks = chunksRef.current;
        chunksRef.current = [];
        if (!chunks || chunks.length === 0) {
          setVoiceError("No audio was captured.");
          setVoiceState("error");
          cleanupRecordingResources();
          return;
        }

        setVoiceState("transcribing");
        const blobType = recorder.mimeType || "audio/webm";
        const blob = new Blob(chunks, { type: blobType });
        const extension = blobType.includes("ogg") ? "ogg" : blobType.includes("mp4") ? "m4a" : "webm";
        try {
          const response = await transcribeVoiceAudio(blob, `recording.${extension}`);
          const transcript = String(response?.transcript || "").trim();
          if (!transcript) {
            throw new Error("Could not transcribe audio.");
          }
          setText((current) => (current ? `${current.trim()} ${transcript}`.trim() : transcript));
          setVoiceState("idle");
          setVoiceError("");
          if (inputRef.current) {
            inputRef.current.focus();
          }
        } catch (error) {
          setVoiceError(error?.message || "Could not transcribe audio.");
          setVoiceState("error");
        } finally {
          cleanupRecordingResources();
        }
      };

      recorder.start();
      setVoiceState("recording");
      stopTimerRef.current = window.setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
          mediaRecorderRef.current.stop();
        }
      }, voiceMaxDurationSeconds * 1000);
    } catch (error) {
      setVoiceError(error?.name === "NotAllowedError" ? "Microphone access was denied." : "Could not start recording.");
      setVoiceState("error");
      cleanupRecordingResources();
    }
  }

  function handleStopRecording() {
    if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== "recording") {
      return;
    }
    mediaRecorderRef.current.stop();
  }

  function voiceStatusText() {
    if (!voiceEnabled) return "";
    if (voiceState === "recording") return "Recording...";
    if (voiceState === "transcribing") return "Transcribing...";
    if (voiceState === "error") return voiceError || "Could not transcribe audio.";
    return "Start recording";
  }

  function renderVoiceButtonIcon() {
    if (voiceState === "recording") {
      return (
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
          <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
        </svg>
      );
    }
    return (
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
        <rect x="9" y="4" width="6" height="11" rx="3" fill="currentColor" />
        <path d="M7 11a5 5 0 0 0 10 0h2a7 7 0 0 1-6 6.92V21h-2v-3.08A7 7 0 0 1 5 11z" fill="currentColor" />
      </svg>
    );
  }

  function renderReplayIcon() {
    return (
      <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false">
        <path
          d="M12 5a7 7 0 1 1-6.32 10H3l3.5-3.5L10 15H7.74A5 5 0 1 0 8.4 9H11V7H6V2h2v3.3A6.97 6.97 0 0 1 12 5z"
          fill="currentColor"
        />
      </svg>
    );
  }

  function replayAssistantMessage(content) {
    if (!voiceOutputEnabled || !ttsSupported || ttsMuted) {
      return;
    }
    replay(content, { language: preferredLanguage });
  }

  return (
    <div className="chat">
      <div className="chatHeader">
        <div>
          <strong>Chat</strong>
        </div>
        <div className="muted">
          Turns: {progress.turn_count}/{progress.max_turns} {done ? "(done)" : ""}
        </div>
      </div>
      {voiceOutputEnabled && (
        <div className="tts-controls">
          <button
            type="button"
            className={`btn secondary tts-toggle ${ttsMuted ? "muted" : ""}`}
            onClick={() => setTtsMuted((current) => !current)}
          >
            {ttsMuted ? "Unmute Voice" : "Mute Voice"}
          </button>
          <button
            type="button"
            className="btn secondary tts-stop"
            disabled={!isTtsSpeaking}
            onClick={stopSpeaking}
          >
            Stop Speech
          </button>
        </div>
      )}

      <div className="chatList" ref={listRef}>
        {messages.length === 0 && !loginRequired && (
          <div className="muted">Start intake to begin.</div>
        )}

        {loginRequired && (
          <div className="bubble assistant warning">
            <div className="role">assistant</div>
            <div>
              Welcome! Please log in or create a free account to start your intake.
              <div className="auth-actions" style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                <button className="btn" type="button" onClick={onLoginClick}>Log in</button>
                <button className="btn secondary" type="button" onClick={onRegisterClick}>Register</button>
              </div>
            </div>
          </div>
        )}

        {messages.map((m, idx) => (
          <div key={idx} className={`bubble ${m.role}`}>
            <div className="role">{m.role}</div>
            <div className="bubble-content-row">
              <div>{m.content}</div>
              {voiceOutputEnabled && m.role === "assistant" && (
                <button
                  type="button"
                  className="tts-replay-btn"
                  onClick={() => replayAssistantMessage(m.content)}
                  title="Replay assistant message"
                  aria-label="Replay assistant message"
                >
                  {renderReplayIcon()}
                </button>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="bubble assistant loading">
            <div className="role">assistant</div>
            <div><span className="loader-spinner" /> Thinking...</div>
          </div>
        )}
      </div>

      <div className="chatInput">
        {!done ? (
          <form onSubmit={submit} className="chat-form">
            <input
              ref={inputRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={inputPlaceholder}
              disabled={disabled || loginRequired}
              maxLength={2000}
              style={{ flex: 1 }}
            />
            {voiceEnabled && (
              <button
                type="button"
                className={`btn secondary voice-btn ${voiceState === "recording" ? "recording" : ""}`}
                onClick={voiceState === "recording" ? handleStopRecording : handleStartRecording}
                disabled={disabled || loginRequired || voiceState === "transcribing"}
                aria-label={voiceState === "recording" ? "Stop recording" : "Start recording"}
                title={voiceState === "recording" ? "Stop recording" : "Start recording"}
              >
                {renderVoiceButtonIcon()}
              </button>
            )}
            <button className="btn" disabled={disabled || loginRequired || voiceState === "recording"}>
              Send
            </button>
          </form>
        ) : (
          <div className="chat-actions">
            <button className="btn secondary" onClick={onReset} style={{ flex: 1 }}>
              Reset
            </button>
            {!hasResults && (
              <button className="btn" onClick={onFinish} style={{ flex: 1 }}>
                Finish
              </button>
            )}
          </div>
        )}
      </div>
      {voiceEnabled && !done && (
        <div className={`voice-status ${voiceState === "error" ? "error" : ""}`}>{voiceStatusText()}</div>
      )}
      {voiceOutputEnabled && !ttsSupported && (
        <div className="voice-status error">Text-to-speech is not supported in this browser.</div>
      )}
      {voiceOutputEnabled && ttsError && <div className="voice-status error">{ttsError}</div>}
    </div>
  );
}


