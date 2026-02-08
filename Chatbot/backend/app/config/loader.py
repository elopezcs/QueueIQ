import hashlib
import yaml
from pathlib import Path
from typing import Any

from app.core.settings import settings

_cached: dict[str, Any] | None = None


def load_clinics_config() -> dict[str, Any]:
    global _cached
    if _cached is not None:
        return _cached

    path = Path(settings.clinics_config_path)
    raw = path.read_text(encoding="utf-8")
    cfg = yaml.safe_load(raw)
    if not isinstance(cfg, dict) or "clinics" not in cfg:
        raise ValueError("Invalid clinics config")

    _cached = cfg
    return cfg


def get_clinic_by_id(clinic_id: str) -> dict[str, Any] | None:
    cfg = load_clinics_config()
    for c in cfg.get("clinics", []):
        if c.get("id") == clinic_id:
            return c
    return None


def clinic_config_snapshot_hash(clinic: dict[str, Any]) -> str:
    payload = yaml.safe_dump(clinic, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
