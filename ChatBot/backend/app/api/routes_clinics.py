from fastapi import APIRouter, HTTPException
from app.config.loader import load_clinics_config, get_clinic_by_id
from app.models.schemas import ClinicOut, ClinicStatusOut
from app.agent.queue_risk import mock_queue_snapshot

router = APIRouter()


@router.get("/clinics", response_model=list[ClinicOut])
def list_clinics():
    cfg = load_clinics_config()
    return [
        ClinicOut(id=c["id"], name=c["name"], address_or_city=c["address_or_city"])
        for c in cfg["clinics"]
    ]


@router.get("/clinics/{clinic_id}/status", response_model=ClinicStatusOut)
def clinic_status(clinic_id: str):
    clinic = get_clinic_by_id(clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    snap = mock_queue_snapshot(
        clinic_id=clinic_id,
        servers_total=int(clinic.get("mock_capacity", {}).get("servers_total", 3)),
    )
    return ClinicStatusOut(**snap)
