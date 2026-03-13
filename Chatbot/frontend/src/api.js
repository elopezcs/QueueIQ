const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
const AUTH_TOKEN_KEY = 'queueiq_auth_token';

function getErrorMessage(payload, fallback) {
  if (payload && typeof payload === 'object' && typeof payload.detail === 'string') {
    return payload.detail;
  }
  return fallback;
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

export async function createAppointment(clinicId, scheduledFor, sessionId) {
  return apiFetch('/appointments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({
      clinic_id: clinicId,
      scheduled_for: scheduledFor,
      session_id: sessionId || null,
    }),
  });
}

export async function getAdminResults(filters = {}) {
  const queryParams = new URLSearchParams();
  const entries = {
    clinic_id: filters.clinicId || '',
    urgency_band: filters.urgencyBand || '',
    visit_category: filters.visitCategory || '',
    patient_query: filters.patientQuery || '',
    created_from: filters.createdFrom || '',
    created_to: filters.createdTo || '',
  };

  Object.entries(entries).forEach(([key, value]) => {
    if (value) queryParams.set(key, value);
  });

  const query = queryParams.toString() ? `?${queryParams.toString()}` : '';
  return apiFetch(`/admin/results${query}`, {
    headers: { ...authHeaders() },
  });
}

export async function startChat(clinicId) {
  return apiFetch('/chat/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ clinic_id: clinicId }),
  });
}

export async function chatTurn(sessionId, userMessage) {
  return apiFetch('/chat/turn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ session_id: sessionId, user_message: userMessage }),
  });
}

export async function endChat(sessionId) {
  return apiFetch('/chat/end', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ session_id: sessionId }),
  });
}
