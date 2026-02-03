import json
import secrets
from datetime import datetime, timezone
from typing import Any

from app.storage.db import get_conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionRepo:
    def create_session(self, clinic_id: str) -> str:
        session_id = secrets.token_hex(16)
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO sessions(session_id, clinic_id, created_at, done) VALUES(?,?,?,0)",
                (session_id, clinic_id, utc_now_iso()),
            )
            conn.commit()
            return session_id
        finally:
            conn.close()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT session_id, clinic_id, created_at, done FROM sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def mark_done(self, session_id: str) -> None:
        conn = get_conn()
        try:
            conn.execute("UPDATE sessions SET done=1 WHERE session_id=?", (session_id,))
            conn.commit()
        finally:
            conn.close()

    def append_message(self, session_id: str, role: str, content: str) -> None:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO messages(session_id, role, content, ts) VALUES(?,?,?,?)",
                (session_id, role, content, utc_now_iso()),
            )
            conn.commit()
        finally:
            conn.close()

    def get_transcript(self, session_id: str) -> list[dict[str, Any]]:
        conn = get_conn()
        try:
            rows = conn.execute(
                "SELECT role, content, ts FROM messages WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def store_outputs(self, session_id: str, outputs: dict[str, Any]) -> None:
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO outputs(
                  session_id, run_id, urgency_band, visit_category,
                  wait_p50_minutes, wait_p90_minutes, explanation,
                  disclaimers_json, config_snapshot_hash, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    session_id,
                    outputs["run_id"],
                    outputs["urgency_band"],
                    outputs["visit_category"],
                    int(outputs["wait_p50_minutes"]),
                    int(outputs["wait_p90_minutes"]),
                    outputs["explanation"],
                    json.dumps(outputs["disclaimers"]),
                    outputs["config_snapshot_hash"],
                    utc_now_iso(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
