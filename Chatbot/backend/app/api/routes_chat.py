from fastapi import APIRouter, HTTPException
from app.models.schemas import (
    ChatStartIn,
    ChatStartOut,
    ChatTurnIn,
    ChatTurnOut,
    ChatEndIn,
    ChatEndOut,
)
from app.storage.repo import SessionRepo
from app.agent.orchestrator import ChatOrchestrator
from app.config.loader import get_clinic_by_id

router = APIRouter()


@router.post("/chat/start", response_model=ChatStartOut)
def chat_start(payload: ChatStartIn):
    clinic = get_clinic_by_id(payload.clinic_id)
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    repo = SessionRepo()
    session_id = repo.create_session(clinic_id=payload.clinic_id)

    orchestrator = ChatOrchestrator()
    assistant_message, disclaimers = orchestrator.first_message(clinic=clinic)

    repo.append_message(session_id, role="assistant", content=assistant_message)
    return ChatStartOut(
        session_id=session_id,
        assistant_message=assistant_message,
        disclaimers=disclaimers,
    )


@router.post("/chat/turn", response_model=ChatTurnOut)
def chat_turn(payload: ChatTurnIn):
    repo = SessionRepo()
    session = repo.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    clinic = get_clinic_by_id(session["clinic_id"])
    if not clinic:
        raise HTTPException(status_code=500, detail="Clinic config missing")

    repo.append_message(payload.session_id, role="user", content=payload.user_message)

    orchestrator = ChatOrchestrator()
    assistant_message, done, progress = orchestrator.next_turn(
        clinic=clinic,
        transcript=repo.get_transcript(payload.session_id),
    )

    repo.append_message(payload.session_id, role="assistant", content=assistant_message)

    if done:
        repo.mark_done(payload.session_id)

    return ChatTurnOut(
        assistant_message=assistant_message,
        done=done,
        progress=progress,
    )


@router.post("/chat/end", response_model=ChatEndOut)
def chat_end(payload: ChatEndIn):
    repo = SessionRepo()
    session = repo.get_session(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    clinic = get_clinic_by_id(session["clinic_id"])
    if not clinic:
        raise HTTPException(status_code=500, detail="Clinic config missing")

    transcript = repo.get_transcript(payload.session_id)

    orchestrator = ChatOrchestrator()
    result = orchestrator.finalize(
        clinic=clinic,
        transcript=transcript,
    )
    result["session_id"] = payload.session_id  # ensure correct

    repo.store_outputs(
        session_id=payload.session_id,
        outputs=result,
    )

    return ChatEndOut(**result)
