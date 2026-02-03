CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  clinic_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  ts TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS outputs (
  session_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  urgency_band TEXT NOT NULL,
  visit_category TEXT NOT NULL,
  wait_p50_minutes INTEGER NOT NULL,
  wait_p90_minutes INTEGER NOT NULL,
  explanation TEXT NOT NULL,
  disclaimers_json TEXT NOT NULL,
  config_snapshot_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);
