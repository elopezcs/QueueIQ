from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.chdir(BACKEND_ROOT)

from app.agent.llm_client import LLMClient  # noqa: E402
from app.agent.orchestrator import format_clinic_context, transcript_to_text  # noqa: E402
from app.agent.prompts import DEFAULT_DISCLAIMERS, prompt_final_classification, prompt_next_question  # noqa: E402
from app.config.loader import clinic_config_snapshot_hash, get_clinic_by_id  # noqa: E402
from app.core.settings import settings  # noqa: E402
from app.agent.queue_risk import estimate_wait_minutes, mock_queue_snapshot  # noqa: E402

SAFE_MESSAGE = (
    "If this may be severe or an emergency, seek urgent in-person care or call local emergency services. "
    "If you can, ask someone nearby for help."
)
HIGH_RISK_KEYWORDS = [
    "chest pain",
    "trouble breathing",
    "cannot breathe",
    "severe bleeding",
    "fainted",
    "stroke",
    "suicidal",
    "overdose",
    "anaphylaxis",
]
FIRST_MESSAGE_TEMPLATE = (
    "Welcome. I can help collect intake details for {clinic_name}.\n\n"
    "I will ask a few short questions for operational queue planning. "
    "This is not a medical diagnosis.\n\n"
    "What brings you in today, in one or two sentences?"
)
DEFAULT_MODELS = ["gpt-5", "gpt-5-mini", "gpt-5-nano"]
MAX_USER_TURNS_PER_SCENARIO = 4


@dataclass(frozen=True)
class Scenario:
    user_id: str
    title: str
    clinic_id: str
    user_messages: list[str]
    fallback_answer: str


SCENARIOS = [
    Scenario(
        user_id="user-01",
        title="Mild respiratory symptoms",
        clinic_id="kitchener-downtown",
        user_messages=[
            "I have had a sore throat and cough for the last two days.",
            "It started about two days ago and feels worse at night.",
            "No injury is involved.",
            "I do not need to leave quickly and can wait if needed.",
        ],
        fallback_answer="Mostly a sore throat, cough, and mild fatigue. No emergency symptoms.",
    ),
    Scenario(
        user_id="user-02",
        title="Ankle injury after a fall",
        clinic_id="waterloo-boardwalk",
        user_messages=[
            "I twisted my ankle after stepping off a curb this morning.",
            "It happened a few hours ago and it hurts to walk on it.",
            "Yes, there was a small fall but I did not hit my head.",
            "I would like to be seen before the end of the afternoon if possible.",
        ],
        fallback_answer="The ankle is swollen and painful, but I am otherwise okay.",
    ),
    Scenario(
        user_id="user-03",
        title="Skin rash concern",
        clinic_id="cambridge-hespeler",
        user_messages=[
            "I have an itchy rash on both forearms since yesterday evening.",
            "It started yesterday and seems about the same today.",
            "There was no injury.",
            "No major time constraint, I just want to get it checked today.",
        ],
        fallback_answer="It is itchy and annoying but not severe.",
    ),
    Scenario(
        user_id="user-04",
        title="Administrative note with mild symptoms",
        clinic_id="kitchener-fairway",
        user_messages=[
            "I need a medical note for work and I also have mild cold symptoms.",
            "The cold symptoms started three days ago and have been mild.",
            "No injury involved.",
            "I would prefer to be done before 4 PM because of work.",
        ],
        fallback_answer="Mostly I need a note and the symptoms are mild.",
    ),
    Scenario(
        user_id="user-05",
        title="High-risk chest pain and breathing concern",
        clinic_id="waterloo-uptown",
        user_messages=[
            "I have chest pain and trouble breathing right now.",
            "It started suddenly a little while ago and feels serious.",
        ],
        fallback_answer="I still have chest pain and breathing trouble right now.",
    ),
]


def is_high_risk(transcript_text: str) -> bool:
    lowered = transcript_text.lower()
    return any(keyword in lowered for keyword in HIGH_RISK_KEYWORDS)


def call_model_json(llm: LLMClient, prompt: str) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    data = llm.generate_json(prompt)
    elapsed = time.perf_counter() - started
    return data, elapsed


def build_final_result(clinic: dict[str, Any], transcript: list[dict[str, Any]], llm: LLMClient) -> tuple[dict[str, Any], float]:
    transcript_text = transcript_to_text(transcript)
    clinic_context = format_clinic_context(clinic)

    if is_high_risk(transcript_text):
        urgency_band = "high"
        visit_category = "urgent"
        explanation = "High-risk indicators detected. Seek urgent in-person care."
        model_seconds = 0.0
    else:
        data, model_seconds = call_model_json(llm, prompt_final_classification(clinic_context, transcript_text))
        urgency_band = str(data.get("urgency_band", "medium")).lower()
        if urgency_band not in ["low", "medium", "high"]:
            urgency_band = "medium"
        visit_category = str(data.get("visit_category", "general")).strip() or "general"
        explanation = str(data.get("explanation", "")).strip() or "Operational summary based on your answers."

    capacity = clinic.get("mock_capacity", {})
    servers_total = int(capacity.get("servers_total", 3))
    avg_service_minutes = int(capacity.get("avg_service_minutes", 12))
    snap = mock_queue_snapshot(clinic_id=clinic.get("id", "unknown"), servers_total=servers_total)
    p50, p90 = estimate_wait_minutes(
        queue_length=int(snap["queue_length"]),
        servers_busy=int(snap["servers_busy"]),
        servers_total=int(snap["servers_total"]),
        avg_service_minutes=avg_service_minutes,
    )

    result = {
        "urgency_band": urgency_band,
        "visit_category": visit_category,
        "wait_p50_minutes": p50,
        "wait_p90_minutes": p90,
        "explanation": explanation,
        "disclaimers": DEFAULT_DISCLAIMERS,
        "config_snapshot_hash": clinic_config_snapshot_hash(clinic),
    }
    return result, model_seconds


def run_scenario(model: str, scenario: Scenario) -> tuple[dict[str, Any], list[dict[str, str]]]:
    settings.openai_model = model
    clinic = get_clinic_by_id(scenario.clinic_id)
    if not clinic:
        raise ValueError(f"Clinic not found: {scenario.clinic_id}")

    llm = LLMClient()
    clinic_context = format_clinic_context(clinic)
    transcript: list[dict[str, Any]] = []
    messages: list[dict[str, str]] = []
    llm_questions_asked = 0
    llm_call_seconds = 0.0
    first_message = FIRST_MESSAGE_TEMPLATE.format(clinic_name=clinic.get("name", "the clinic"))

    transcript.append({"role": "assistant", "content": first_message})
    messages.append({"role": "assistant", "content": first_message})

    done = False
    for idx in range(MAX_USER_TURNS_PER_SCENARIO):
        user_message = scenario.user_messages[idx] if idx < len(scenario.user_messages) else scenario.fallback_answer
        transcript.append({"role": "user", "content": user_message})
        messages.append({"role": "user", "content": user_message})

        transcript_text = transcript_to_text(transcript)
        if is_high_risk(transcript_text):
            assistant_message = SAFE_MESSAGE
            transcript.append({"role": "assistant", "content": assistant_message})
            messages.append({"role": "assistant", "content": assistant_message})
            done = True
            break

        data, elapsed = call_model_json(
            llm,
            prompt_next_question(
                clinic_context=clinic_context,
                transcript=transcript_text,
                turn_count=sum(1 for item in transcript if item["role"] == "user"),
                max_turns=MAX_USER_TURNS_PER_SCENARIO,
            ),
        )
        llm_call_seconds += elapsed

        decision = str(data.get("decision", "ASK")).upper()
        if decision == "SAFETY":
            assistant_message = SAFE_MESSAGE
            done = True
        elif decision == "STOP":
            assistant_message = "Thanks. I have enough information to generate operational results. Please tap Finish to see them."
            done = True
        else:
            assistant_message = str(data.get("next_question") or "Could you share a bit more detail about what you need help with today?").strip()
            llm_questions_asked += 1

        transcript.append({"role": "assistant", "content": assistant_message})
        messages.append({"role": "assistant", "content": assistant_message})

        if done:
            break

    result, final_call_seconds = build_final_result(clinic, transcript, llm)
    llm_call_seconds += final_call_seconds
    summary = {
        "model": model,
        "user_id": scenario.user_id,
        "scenario": scenario.title,
        "clinic_id": scenario.clinic_id,
        "llm_questions_asked": llm_questions_asked,
        "user_turns_used": sum(1 for item in transcript if item["role"] == "user"),
        "conversation_completed": done,
        "llm_call_seconds": round(llm_call_seconds, 2),
        "result": result,
        "status": "success",
        "error_message": "",
    }
    return summary, messages


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def _xml_cell(value: Any) -> str:
    return f'<Cell><Data ss:Type="String">{escape(_stringify(value))}</Data></Cell>'


def _sheet_xml(name: str, headers: list[str], rows: list[list[Any]]) -> str:
    lines = [f'<Worksheet ss:Name="{escape(name[:31])}">', '<Table>']
    for _ in headers:
        lines.append('<Column ss:Width="180"/>')
    lines.append('<Row>' + ''.join(_xml_cell(header) for header in headers) + '</Row>')
    for row in rows:
        lines.append('<Row>' + ''.join(_xml_cell(value) for value in row) + '</Row>')
    lines.extend(['</Table>', '</Worksheet>'])
    return '\n'.join(lines)


def build_workbook_xml(summary_rows: list[list[Any]], model_rows: list[list[Any]], detail_rows: list[list[Any]]) -> str:
    sheets = [
        _sheet_xml(
            'Summary',
            ['run_id', 'model', 'user_id', 'scenario', 'clinic_id', 'llm_questions_asked', 'user_turns_used', 'conversation_completed', 'llm_call_seconds', 'urgency_band', 'visit_category', 'wait_p50_minutes', 'wait_p90_minutes', 'status', 'error_message'],
            summary_rows,
        ),
        _sheet_xml(
            'Model Summary',
            ['model', 'scenario_runs', 'successful_runs', 'avg_llm_questions', 'avg_llm_call_seconds'],
            model_rows,
        ),
        _sheet_xml(
            'Conversations',
            ['run_id', 'model', 'user_id', 'scenario', 'message_index', 'role', 'content', 'urgency_band', 'visit_category', 'wait_p50_minutes', 'wait_p90_minutes', 'explanation', 'status', 'error_message'],
            detail_rows,
        ),
    ]
    return '\n'.join([
        '<?xml version="1.0"?>',
        '<?mso-application progid="Excel.Sheet"?>',
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:o="urn:schemas-microsoft-com:office:office"',
        ' xmlns:x="urn:schemas-microsoft-com:office:excel"',
        ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"',
        ' xmlns:html="http://www.w3.org/TR/REC-html40">',
        *sheets,
        '</Workbook>',
    ])


def write_reports(json_path: Path, xml_path: Path, raw_results: list[dict[str, Any]], summary_rows: list[list[Any]], detail_rows: list[list[Any]]) -> None:
    grouped: dict[str, dict[str, float]] = {}
    for item in raw_results:
        model = item['model']
        grouped.setdefault(model, {'scenario_runs': 0, 'successful_runs': 0, 'questions': 0.0, 'seconds': 0.0})
        grouped[model]['scenario_runs'] += 1
        if item.get('status') == 'success':
            grouped[model]['successful_runs'] += 1
            grouped[model]['questions'] += float(item.get('llm_questions_asked', 0) or 0)
            grouped[model]['seconds'] += float(item.get('llm_call_seconds', 0) or 0)

    model_rows: list[list[Any]] = []
    for model, data in grouped.items():
        successful = int(data['successful_runs'])
        avg_questions = round(data['questions'] / successful, 2) if successful else ''
        avg_seconds = round(data['seconds'] / successful, 2) if successful else ''
        model_rows.append([model, int(data['scenario_runs']), successful, avg_questions, avg_seconds])

    json_path.write_text(json.dumps(raw_results, ensure_ascii=False, indent=2), encoding='utf-8')
    xml_path.write_text(build_workbook_xml(summary_rows, model_rows, detail_rows), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(description='Run Chatbot conversation evaluations across multiple OpenAI models.')
    parser.add_argument('--models', nargs='*', default=DEFAULT_MODELS, help='List of model names to evaluate.')
    args = parser.parse_args()

    report_dir = BACKEND_ROOT / 'reports'
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = report_dir / f'chatbot_model_eval_{timestamp}.json'
    xml_path = report_dir / f'chatbot_model_eval_{timestamp}.xml'

    summary_rows: list[list[Any]] = []
    detail_rows: list[list[Any]] = []
    raw_results: list[dict[str, Any]] = []

    for model in args.models:
        for scenario in SCENARIOS:
            run_id = f'{model}__{scenario.user_id}'
            try:
                summary, messages = run_scenario(model, scenario)
                result = summary['result']
                run_payload = {'run_id': run_id, **summary, 'messages': messages}
                raw_results.append(run_payload)
                summary_rows.append([
                    run_id,
                    model,
                    scenario.user_id,
                    scenario.title,
                    scenario.clinic_id,
                    summary['llm_questions_asked'],
                    summary['user_turns_used'],
                    summary['conversation_completed'],
                    summary['llm_call_seconds'],
                    result.get('urgency_band', ''),
                    result.get('visit_category', ''),
                    result.get('wait_p50_minutes', ''),
                    result.get('wait_p90_minutes', ''),
                    summary['status'],
                    summary['error_message'],
                ])
                for idx, message in enumerate(messages, start=1):
                    detail_rows.append([
                        run_id,
                        model,
                        scenario.user_id,
                        scenario.title,
                        idx,
                        message['role'],
                        message['content'],
                        result.get('urgency_band', ''),
                        result.get('visit_category', ''),
                        result.get('wait_p50_minutes', ''),
                        result.get('wait_p90_minutes', ''),
                        result.get('explanation', ''),
                        summary['status'],
                        summary['error_message'],
                    ])
            except Exception as exc:
                error_message = str(exc)
                raw_results.append({
                    'run_id': run_id,
                    'model': model,
                    'user_id': scenario.user_id,
                    'scenario': scenario.title,
                    'clinic_id': scenario.clinic_id,
                    'status': 'error',
                    'error_message': error_message,
                })
                summary_rows.append([
                    run_id,
                    model,
                    scenario.user_id,
                    scenario.title,
                    scenario.clinic_id,
                    '',
                    '',
                    False,
                    '',
                    '',
                    '',
                    '',
                    '',
                    'error',
                    error_message,
                ])
                detail_rows.append([
                    run_id,
                    model,
                    scenario.user_id,
                    scenario.title,
                    1,
                    'system',
                    '',
                    '',
                    '',
                    '',
                    '',
                    '',
                    'error',
                    error_message,
                ])

            write_reports(json_path, xml_path, raw_results, summary_rows, detail_rows)
            print(json.dumps({'run_id': run_id, 'status': raw_results[-1].get('status', 'unknown')}, ensure_ascii=False), flush=True)

    print(json.dumps({'json_report': str(json_path), 'xml_report': str(xml_path), 'runs': len(summary_rows)}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

