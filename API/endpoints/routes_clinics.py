import logging
from fastapi import APIRouter, HTTPException

from API.rag.db import fetch_all, rag_db_enabled
from Chatbot.backend.app.agent.queue_risk import mock_queue_snapshot
from Chatbot.backend.app.config.loader import get_clinic_by_id, load_clinics_config
from Chatbot.backend.app.models.schemas import ClinicOut, ClinicStatusOut

router = APIRouter()
logger = logging.getLogger("queueiq.endpoints.clinics")


def _clinics_from_db() -> list[ClinicOut]:
    rows = fetch_all(
        """
        SELECT clinic_id, clinic_name, city
        FROM rag.clinics
        ORDER BY clinic_name ASC
        """
    )
    return [
        ClinicOut(
            id=str(row["clinic_id"]),
            name=str(row["clinic_name"]),
            address_or_city=str(row.get("city") or ""),
        )
        for row in rows
    ]


def _clinic_exists_in_db(clinic_id: str) -> bool:
    rows = fetch_all(
        """
        SELECT clinic_id
        FROM rag.clinics
        WHERE clinic_id = %s
        LIMIT 1
        """,
        (clinic_id,),
    )
    return bool(rows)


@router.get("/clinics", response_model=list[ClinicOut])
def list_clinics():
    if rag_db_enabled():
        try:
            clinics = _clinics_from_db()
            if clinics:
                return clinics
        except Exception:
            logger.exception("Failed to load clinics from rag.clinics; falling back to YAML config")

    cfg = load_clinics_config()
    return [ClinicOut(id=c["id"], name=c["name"], address_or_city=c["address_or_city"]) for c in cfg["clinics"]]


@router.get("/clinics/{clinic_id}/status", response_model=ClinicStatusOut)
def clinic_status(clinic_id: str):
    clinic_exists = False
    if rag_db_enabled():
        try:
            clinic_exists = _clinic_exists_in_db(clinic_id)
        except Exception:
            logger.exception("Failed clinic existence lookup in rag.clinics; falling back to YAML config")

    if not clinic_exists:
        clinic_exists = bool(get_clinic_by_id(clinic_id))
    if not clinic_exists:
        raise HTTPException(status_code=404, detail="Clinic not found")

    snap = mock_queue_snapshot(
        clinic_id=clinic_id,
        servers_total=3,
    )
    return ClinicStatusOut(**snap)
