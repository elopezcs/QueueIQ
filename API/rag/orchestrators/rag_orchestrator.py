import json
import secrets
from dataclasses import dataclass
from typing import Literal

from API.rag.db import execute
from API.rag.guardrails.rules import apply_guardrails
from API.rag.model_adapters.registry import active_adapter, active_model
from API.rag.prompts.templates import system_prompt_for_variant, user_prompt
from API.rag.retrievers.clinic_retriever import ClinicKnowledgeRetriever
from API.rag.retrievers.patient_retriever import PatientContextRetriever
from Chatbot.backend.app.core.settings import settings

RouteTarget = Literal["patient", "clinic", "mixed"]


def route_query(message: str) -> RouteTarget:
    lowered = message.lower()
    patient_terms = {"my", "i ", "medication", "allergy", "lab", "record", "history"}
    clinic_terms = {"clinic", "hours", "policy", "rule", "faq", "service", "open"}
    p = any(term in lowered for term in patient_terms)
    c = any(term in lowered for term in clinic_terms)
    if p and c:
        return "mixed"
    if c:
        return "clinic"
    return "patient"


@dataclass
class RagTurnResult:
    assistant_message: str
    done: bool
    route: RouteTarget
    trace_id: str | None
    run_id: str | None
    patient_context: list[dict]
    clinic_context: list[dict]


class RagOrchestrator:
    def __init__(self) -> None:
        self.patient_retriever = PatientContextRetriever()
        self.clinic_retriever = ClinicKnowledgeRetriever()

    def run_turn(self, *, session_id: str, patient_id: str, clinic_id: str, user_message: str) -> RagTurnResult:
        route, patient_context, clinic_context = self.retrieve_only(
            patient_id=patient_id,
            clinic_id=clinic_id,
            user_message=user_message,
        )
        guard = apply_guardrails(user_message, context_item_count=len(patient_context) + len(clinic_context))
        if guard.blocked:
            return RagTurnResult(
                assistant_message=guard.assistant_message or "I cannot answer that request safely.",
                done=guard.done,
                route=route,
                trace_id=None,
                run_id=None,
                patient_context=patient_context,
                clinic_context=clinic_context,
            )

        trace_id = f"trace_{secrets.token_hex(10)}"
        context_preview = json.dumps(
            {
                "patient": patient_context[:3],
                "clinic": clinic_context[:3],
            },
            ensure_ascii=False,
        )
        execute(
            """
            INSERT INTO rag.retrieval_traces(trace_id, session_id, patient_id, clinic_id, route, query_text, context_preview)
            VALUES(%s,%s,%s,%s,%s,%s,%s)
            """,
            (trace_id, session_id, patient_id, clinic_id, route, user_message, context_preview),
        )

        spec = active_model()
        adapter = active_adapter()
        system_prompt = system_prompt_for_variant(spec.prompt_variant)
        rendered_user_prompt = user_prompt(
            question=user_message,
            route=route,
            patient_context=patient_context,
            clinic_context=clinic_context,
        )
        parsed = adapter.generate_structured(
            model_name=spec.model_name,
            system_prompt=system_prompt,
            user_prompt=rendered_user_prompt,
        )
        assistant_message = str(parsed.get("assistant_message") or "I could not generate a safe answer.")
        done = bool(parsed.get("done", False))

        run_id = f"run_{secrets.token_hex(10)}"
        execute(
            """
            INSERT INTO rag.llm_runs(run_id, trace_id, session_id, model_key, provider, prompt_version, prompt_preview, response_preview)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                run_id,
                trace_id,
                session_id,
                spec.key,
                settings.rag_model_provider,
                f"{spec.prompt_variant}_v1",
                rendered_user_prompt[:1000],
                assistant_message[:1000],
            ),
        )

        return RagTurnResult(
            assistant_message=assistant_message,
            done=done,
            route=route,
            trace_id=trace_id,
            run_id=run_id,
            patient_context=patient_context,
            clinic_context=clinic_context,
        )

    def retrieve_only(self, *, patient_id: str, clinic_id: str, user_message: str) -> tuple[RouteTarget, list[dict], list[dict]]:
        route = route_query(user_message)
        patient_context: list[dict] = []
        clinic_context: list[dict] = []

        if route in {"patient", "mixed"}:
            patient_context = self.patient_retriever.retrieve(patient_id=patient_id, query=user_message)
        if route in {"clinic", "mixed"}:
            clinic_context = self.clinic_retriever.retrieve(clinic_id=clinic_id, query=user_message)
        return route, patient_context, clinic_context

