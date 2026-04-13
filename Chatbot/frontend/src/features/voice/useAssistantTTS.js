import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { synthesizeAssistantSpeech } from "../../api.js";

function getSpeechSynthesis() {
  if (typeof window === "undefined") return null;
  return window.speechSynthesis || null;
}

function normalizeSpeakableText(text) {
  return String(text || "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .replace(/[#>*_~-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeProvider(provider) {
  const candidate = String(provider || "").trim().toLowerCase();
  return candidate === "openai" ? "openai" : "system";
}

function waitForAudioReady(audio, signal) {
  if (!audio) {
    return Promise.reject(new Error("Audio element is not available."));
  }
  if (signal?.aborted) {
    return Promise.reject(new Error("Playback aborted."));
  }
  if (audio.readyState >= 2) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      audio.removeEventListener("loadeddata", onReady);
      audio.removeEventListener("canplay", onReady);
      audio.removeEventListener("error", onError);
      if (signal) {
        signal.removeEventListener("abort", onAbort);
      }
    };
    const onReady = () => {
      cleanup();
      resolve();
    };
    const onError = () => {
      cleanup();
      reject(new Error("Speech audio could not be loaded."));
    };
    const onAbort = () => {
      cleanup();
      reject(new Error("Playback aborted."));
    };
    audio.addEventListener("loadeddata", onReady, { once: true });
    audio.addEventListener("canplay", onReady, { once: true });
    audio.addEventListener("error", onError, { once: true });
    if (signal) {
      signal.addEventListener("abort", onAbort, { once: true });
    }
  });
}

export function useAssistantTTS({ provider = "system" } = {}) {
  const speechRef = useRef(null);
  const audioRef = useRef(null);
  const audioUrlRef = useRef("");
  const abortRef = useRef(null);
  const providerRef = useRef(normalizeProvider(provider));
  const [supported, setSupported] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [lastError, setLastError] = useState("");
  const resolvedProvider = useMemo(() => normalizeProvider(provider), [provider]);

  const cleanupAudio = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (audioUrlRef.current && typeof URL !== "undefined" && typeof URL.revokeObjectURL === "function") {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = "";
    }
  }, []);

  useEffect(() => {
    const synth = getSpeechSynthesis();
    speechRef.current = synth;
    return () => {
      if (synth) {
        synth.cancel();
      }
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
      cleanupAudio();
    };
  }, [cleanupAudio]);

  useEffect(() => {
    providerRef.current = resolvedProvider;
    if (resolvedProvider === "openai") {
      setSupported(
        typeof window !== "undefined" &&
          typeof window.fetch === "function" &&
          typeof window.Audio !== "undefined",
      );
    } else {
      setSupported(Boolean(speechRef.current));
    }
  }, [resolvedProvider]);

  const stop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    cleanupAudio();
    const synth = speechRef.current;
    if (synth) {
      synth.cancel();
    }
    setIsSpeaking(false);
  }, [cleanupAudio]);

  const speak = useCallback(
    (rawText, options = {}) => {
      const text = normalizeSpeakableText(rawText);
      if (!text) return false;

      const activeProvider = providerRef.current;

      try {
        stop();
        setLastError("");
        if (activeProvider === "openai") {
          const supportsOpenAIPlayback = typeof window !== "undefined" && typeof window.Audio !== "undefined";
          if (!supportsOpenAIPlayback) {
            setLastError("Audio playback is not supported in this browser.");
            return false;
          }

          const controller = new AbortController();
          abortRef.current = controller;
          setIsSpeaking(true);
          const normalizedLanguage = String(options?.language || "").trim().toLowerCase();
          void synthesizeAssistantSpeech(text, normalizedLanguage)
            .then((audioBlob) => {
              if (controller.signal.aborted) return;
              const audioType = String(audioBlob?.type || "").toLowerCase();
              if (!audioBlob || audioBlob.size === 0 || !audioType.startsWith("audio/")) {
                throw new Error("Text-to-speech audio was invalid.");
              }
              const audioUrl = URL.createObjectURL(audioBlob);
              audioUrlRef.current = audioUrl;
              const audio = new Audio(audioUrl);
              audio.preload = "auto";
              audioRef.current = audio;
              audio.onended = () => {
                cleanupAudio();
                setIsSpeaking(false);
              };
              audio.onerror = () => {
                cleanupAudio();
                setIsSpeaking(false);
                setLastError("Speech playback failed.");
              };
              return waitForAudioReady(audio, controller.signal)
                .then(() => audio.play())
                .catch(() => {
                throw new Error("Unable to play generated speech audio.");
                });
            })
            .catch((error) => {
              if (controller.signal.aborted) return;
              setIsSpeaking(false);
              setLastError(error?.message || "Speech playback failed.");
            })
            .finally(() => {
              if (abortRef.current === controller) {
                abortRef.current = null;
              }
            });
          return true;
        }

        const synth = speechRef.current;
        if (!synth) return false;
        const utterance = new SpeechSynthesisUtterance(text);
        const normalizedLanguage = String(options?.language || "").trim().toLowerCase();
        if (normalizedLanguage === "fr") {
          utterance.lang = "fr-FR";
        } else if (normalizedLanguage === "es") {
          utterance.lang = "es-US";
        } else {
          utterance.lang = "en-CA";
        }
        utterance.onstart = () => {
          setIsSpeaking(true);
          setLastError("");
        };
        utterance.onend = () => {
          setIsSpeaking(false);
        };
        utterance.onerror = () => {
          setIsSpeaking(false);
          setLastError("Speech playback failed.");
        };
        synth.speak(utterance);
        return true;
      } catch {
        setIsSpeaking(false);
        setLastError("Speech synthesis is not available.");
        return false;
      }
    },
    [cleanupAudio, stop],
  );

  return useMemo(
    () => ({
      supported,
      isSpeaking,
      lastError,
      speak,
      replay: speak,
      stop,
      toSpeakableText: normalizeSpeakableText,
    }),
    [isSpeaking, lastError, speak, stop, supported],
  );
}
