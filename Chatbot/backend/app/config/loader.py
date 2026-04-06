import hashlib
import logging
from pathlib import Path
from typing import Any

import yaml

from app.core.settings import settings

try:
    from API.rag.db import fetch_all, rag_db_enabled
except ModuleNotFoundError:
    fetch_all = None
    rag_db_enabled = None

_cached: dict[str, Any] | None = None
_BACKEND_DIR = Path(__file__).resolve().parents[2]
logger = logging.getLogger("queueiq.config.loader")


def _config_path() -> Path:
    path = Path(settings.clinics_config_path)
    if path.is_absolute():
        return path
    return (_BACKEND_DIR / path).resolve()


def load_clinics_config() -> dict[str, Any]:
    global _cached
    if _cached is not None:
        return _cached

    raw = _config_path().read_text(encoding='utf-8')
    cfg = yaml.safe_load(raw)
    if not isinstance(cfg, dict) or 'clinics' not in cfg:
        raise ValueError('Invalid clinics config')

    _cached = cfg
    return cfg


def get_clinic_by_id(clinic_id: str) -> dict[str, Any] | None:
    if callable(rag_db_enabled) and callable(fetch_all):
        try:
            if rag_db_enabled():
                rows = fetch_all(
                    """
                    SELECT clinic_id, clinic_name, city
                    FROM rag.clinics
                    WHERE clinic_id = %s
                    LIMIT 1
                    """,
                    (clinic_id,),
                )
                if rows:
                    row = rows[0]
                    return {
                        "id": row["clinic_id"],
                        "name": row["clinic_name"],
                        "address_or_city": row.get("city") or "",
                        "hours": {},
                        "mock_capacity": {"servers_total": 3, "avg_service_minutes": 12},
                    }
        except Exception:
            logger.exception("Failed to load clinic_id=%s from rag.clinics; using YAML fallback", clinic_id)

    cfg = load_clinics_config()
    for clinic in cfg.get('clinics', []):
        if clinic.get('id') == clinic_id:
            return clinic
    return None


def clinic_config_snapshot_hash(clinic: dict[str, Any]) -> str:
    payload = yaml.safe_dump(clinic, sort_keys=True).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
