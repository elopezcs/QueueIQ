const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function getClinics() {
  const r = await fetch(`${API_BASE}/clinics`);
  if (!r.ok) throw new Error("Failed to load clinics");
  return r.json();
}

export async function startChat(clinicId) {
  const r = await fetch(`${API_BASE}/chat/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clinic_id: clinicId })
  });
  if (!r.ok) throw new Error("Failed to start chat");
  return r.json();
}

export async function chatTurn(sessionId, userMessage) {
  const r = await fetch(`${API_BASE}/chat/turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, user_message: userMessage })
  });
  if (!r.ok) throw new Error("Failed to send message");
  return r.json();
}

export async function endChat(sessionId) {
  const r = await fetch(`${API_BASE}/chat/end`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId })
  });
  if (!r.ok) throw new Error("Failed to finalize");
  return r.json();
}
