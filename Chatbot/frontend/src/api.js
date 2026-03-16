const DEFAULT_API_BASE = `${window.location.protocol}//${window.location.hostname}:8000`;
const API_BASE = import.meta.env.VITE_API_BASE || DEFAULT_API_BASE;
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
    body: JSON.stringify({
      session_id: sessionId,
      user_message: userMessage,
    }),
  });
}

export async function endChat(sessionId) {
  return apiFetch('/chat/end', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ session_id: sessionId }),
  });
}


