const DEFAULT_API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API_BASE;
const AUTH_TOKEN_KEY = 'queueiq_auth_token';

function getErrorMessage(payload, fallback) {
  if (payload && typeof payload === 'object' && typeof payload.detail === 'string') {
    return payload.detail;
  }
  if (payload && typeof payload === 'object' && Array.isArray(payload.detail) && payload.detail.length) {
    const firstError = payload.detail[0];
    if (firstError && typeof firstError === 'object' && typeof firstError.msg === 'string') {
      return firstError.msg;
    }
  }
  return fallback;
}

function normalizeQueuePredictionRecords(queueRecords = []) {
  return queueRecords.map((record) => {
    const recordId = Number(record.record_id ?? record.recordId);
    const priority = Number(record.priority);
    const estDuration = Number(record.est_duration ?? record.estDuration);

    return {
      record_id: Number.isFinite(recordId) ? recordId : null,
      clinic_name: String(record.clinic_name ?? record.clinicName ?? ''),
      patient_id: String(record.patient_id ?? record.patientId ?? ''),
      arrival_time: record.arrival_time ?? record.arrivalTime ?? null,
      priority: Number.isFinite(priority) ? priority : 5,
      est_duration: Number.isFinite(estDuration) ? estDuration : 5,
      seen_by_doctor_time: record.seen_by_doctor_time ?? record.seenByDoctorTime ?? null,
    };
  });
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new Error(getErrorMessage(payload, 'Request failed'));
  }
  return response.json();
}

async function apiFetchBlob(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new Error(getErrorMessage(payload, 'Request failed'));
  }
  return response.blob();
}

function authHeaders() {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getStoredToken() {
  return window.localStorage.getItem(AUTH_TOKEN_KEY) || '';
}

export function setStoredToken(token) {
  if (token) {
    window.localStorage.setItem(AUTH_TOKEN_KEY, token);
  }
}

export function clearStoredToken() {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

export async function getClinics() {
  return apiFetch('/clinics');
}

export async function getDemoUsers() {
  return apiFetch('/auth/demo-users');
}

export async function registerAccount(payload) {
  return apiFetch('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      full_name: payload.fullName,
      email: payload.email,
      password: payload.password,
    }),
  });
}

export async function createStaffAccount(payload) {
  return apiFetch('/auth/staff', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      full_name: payload.fullName,
      email: payload.email,
      password: payload.password,
      clinic_id: payload.clinicId,
    }),
  });
}

export async function getStaffMembers(filters = {}) {
  const queryParams = new URLSearchParams();
  const entries = {
    query: filters.query || '',
    clinic_id: filters.clinicId || '',
  };

  Object.entries(entries).forEach(([key, value]) => {
    if (value) {
      queryParams.set(key, value);
    }
  });

  const query = queryParams.toString() ? `?${queryParams.toString()}` : '';
  return apiFetch(`/auth/staff-members${query}`, {
    headers: { ...authHeaders() },
  });
}

export async function loginAccount(payload) {
  return apiFetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: payload.email,
      password: payload.password,
    }),
  });
}

export async function demoLogin(email) {
  return apiFetch('/auth/demo-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
}

export async function getMe() {
  return apiFetch('/auth/me', {
    headers: { ...authHeaders() },
  });
}

export async function updateMyProfile(payload) {
  return apiFetch('/auth/me', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
}

export async function logout() {
  return apiFetch('/auth/logout', {
    method: 'POST',
    headers: { ...authHeaders() },
  });
}

export async function getMyAppointments() {
  return apiFetch('/me/appointments', {
    headers: { ...authHeaders() },
  });
}

export async function getStaffAppointments(filters = {}) {
  const queryParams = new URLSearchParams();
  const entries = {
    time_bucket: filters.timeBucket || 'today',
    patient_query: filters.patientQuery || '',
    scheduled_from: filters.scheduledFrom || '',
    scheduled_to: filters.scheduledTo || '',
    clinic_id: filters.clinicId || '',
  };

  Object.entries(entries).forEach(([key, value]) => {
    if (value) {
      queryParams.set(key, value);
    }
  });

  return apiFetch(`/staff/appointments?${queryParams.toString()}`, {
    headers: { ...authHeaders() },
  });
}

export async function createAppointment(clinicId, scheduledFor, description, sessionId) {
  return apiFetch('/appointments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      clinic_id: clinicId,
      scheduled_for: scheduledFor,
      description: description || null,
      session_id: sessionId || null,
    }),
  });
}

export async function createQueuePatientRecord(payload) {
  return apiFetch('/queuecontrol/create-queue-patient-record', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      clinic_name: payload.clinicName,
      patient_id: payload.patientId,
      arrival_time: payload.arrivalTime,
      priority: payload.priority,
      est_duration: payload.estDuration ?? null,
      chat_session_id: payload.chatSessionId ?? null,
    }),
  });
}

export async function getQueueControlClinics() {
  return apiFetch('/queuecontrol/list-registered-clinics', {
    headers: { ...authHeaders() },
  });
}

export async function getActiveQueueRecords() {
  return apiFetch('/queuecontrol/list-active-queue-records', {
    headers: { ...authHeaders() },
  });
}

export async function updateQueuePatientTriage(recordId, payload) {
  return apiFetch(`/queuecontrol/queue-patient-records/${encodeURIComponent(String(recordId))}/update-triage`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      priority: payload.priority,
      est_duration: payload.estDuration ?? null,
    }),
  });
}

export async function deleteQueuePatientRecord(recordId) {
  return apiFetch(`/queuecontrol/queue-patient-records/${encodeURIComponent(String(recordId))}/remove`, {
    method: 'DELETE',
    headers: { ...authHeaders() },
  });
}

export async function getPublicTraceabilityDetail(sessionId) {
  return apiFetch(`/traceability/${encodeURIComponent(String(sessionId))}/detail`, {
    headers: { ...authHeaders() },
  });
}

export async function predictQueueSurge(payload = {}) {
  return apiFetch('/queuecontrol/predict-rush-hour-predictor-model-surge', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      queue_records: normalizeQueuePredictionRecords(payload.queueRecords || []),
      current_time: payload.currentTime || null,
    }),
  });
}

export async function predictQueueWaitTime(payload) {
  const body = {
    clinic_name: payload.clinicName,
    queue_records: normalizeQueuePredictionRecords(payload.queueRecords || []),
    current_time: payload.currentTime || null,
  };
  if (payload.doctorCount) {
    body.doctor_count = payload.doctorCount;
  }
  return apiFetch('/queuecontrol/predict-wait-time-predictor-model-estimate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
  });
}

export async function startChat(clinicId, preferredLanguage = '') {
  const payload = { clinic_id: clinicId };
  const normalizedLanguage = String(preferredLanguage || '').trim().toLowerCase();
  if (normalizedLanguage === 'en' || normalizedLanguage === 'fr' || normalizedLanguage === 'es') {
    payload.preferred_language = normalizedLanguage;
  }
  return apiFetch('/rag/chat/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
}

export async function chatTurn(sessionId, userMessage) {
  return apiFetch('/rag/chat/turn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      session_id: sessionId,
      user_message: userMessage,
    }),
  });
}

export async function endChat(sessionId) {
  return apiFetch('/rag/chat/end', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function getVoiceConfig() {
  return apiFetch('/rag/voice/config', {
    headers: { ...authHeaders() },
  });
}

export async function transcribeVoiceAudio(blob, filename = 'recording.webm') {
  const formData = new FormData();
  formData.append('file', blob, filename);
  return apiFetch('/rag/chat/transcribe', {
    method: 'POST',
    headers: { ...authHeaders() },
    body: formData,
  });
}

export async function synthesizeAssistantSpeech(text, preferredLanguage = "") {
  const payload = { text };
  const normalizedLanguage = String(preferredLanguage || "").trim().toLowerCase();
  if (normalizedLanguage === "en" || normalizedLanguage === "fr" || normalizedLanguage === "es") {
    payload.preferred_language = normalizedLanguage;
  }
  return apiFetchBlob('/rag/chat/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  });
}

export async function getRagAuditSessions({ patientId = '', limit = 50, offset = 0 } = {}) {
  const queryParams = new URLSearchParams();
  if (patientId) {
    queryParams.set('patient_id', String(patientId));
  }
  queryParams.set('limit', String(limit));
  queryParams.set('offset', String(offset));
  return apiFetch(`/rag/audit/sessions?${queryParams.toString()}`, {
    headers: { ...authHeaders() },
  });
}

export async function getRagAuditSessionTurns(sessionId) {
  return apiFetch(`/rag/audit/session/${encodeURIComponent(String(sessionId))}/turns`, {
    headers: { ...authHeaders() },
  });
}

export async function getRagAuditRuns({ patientId = '', sessionId = '', modelKey = '', limit = 100, offset = 0 } = {}) {
  const queryParams = new URLSearchParams();
  if (patientId) {
    queryParams.set('patient_id', String(patientId));
  }
  if (sessionId) {
    queryParams.set('session_id', String(sessionId));
  }
  if (modelKey) {
    queryParams.set('model_key', String(modelKey));
  }
  queryParams.set('limit', String(limit));
  queryParams.set('offset', String(offset));
  return apiFetch(`/rag/audit/runs?${queryParams.toString()}`, {
    headers: { ...authHeaders() },
  });
}

export async function getRagAuditTimeline(sessionId) {
  return apiFetch(`/rag/audit/session/${encodeURIComponent(String(sessionId))}/timeline`, {
    headers: { ...authHeaders() },
  });
}

export async function getRagTrace(traceId) {
  return apiFetch(`/rag/trace/${encodeURIComponent(String(traceId))}`, {
    headers: { ...authHeaders() },
  });
}

