import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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

export function useAssistantTTS() {
  const speechRef = useRef(null);
  const [supported, setSupported] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [lastError, setLastError] = useState("");

  useEffect(() => {
    const synth = getSpeechSynthesis();
    speechRef.current = synth;
    setSupported(Boolean(synth));
    return () => {
      if (synth) {
        synth.cancel();
      }
    };
  }, []);

  const stop = useCallback(() => {
    const synth = speechRef.current;
    if (!synth) return;
    synth.cancel();
    setIsSpeaking(false);
  }, []);

  const speak = useCallback(
    (rawText, options = {}) => {
      const synth = speechRef.current;
      if (!synth) return false;

      const text = normalizeSpeakableText(rawText);
      if (!text) return false;

      try {
        synth.cancel();
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
    [],
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
