import csv

from API.rag import prompt_logging


def test_prompt_logging_writes_csv_only_when_configured(tmp_path, monkeypatch):
    original_enable = prompt_logging.settings.enable_prompt_logging
    original_format = getattr(prompt_logging.settings, "prompt_log_format", "both")
    try:
        monkeypatch.setattr(prompt_logging, "_PROMPT_LOG_DIR", tmp_path)
        prompt_logging.settings.enable_prompt_logging = True
        prompt_logging.settings.prompt_log_format = "csv"

        prompt_logging.log_constructed_prompt(
            session_id="rag_sess_csv_1",
            user_query="I have a headache.",
            constructed_prompt="Prompt body",
            clinic_id="clinic_1",
            patient_id="pat_1",
            model_name="gemma3:4b",
            provider="ollama",
            endpoint="/rag/chat/turn",
            retrieval_mode="patient",
        )
        prompt_logging.log_llm_inference(
            session_id="rag_sess_csv_1",
            user_query="I have a headache.",
            clinic_id="clinic_1",
            patient_id="pat_1",
            model_name="gemma3:4b",
            provider="ollama",
            endpoint="/rag/chat/turn",
            retrieval_mode="patient",
            inference_json={"decision": "ASK", "next_question": "When did this begin?"},
        )

        csv_path = tmp_path / "prompt_session_rag_sess_csv_1.csv"
        log_path = tmp_path / "prompt_session_rag_sess_csv_1.log"
        assert csv_path.exists()
        assert not log_path.exists()

        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

        assert len(rows) == 2
        assert rows[0]["event_type"] == "prompt"
        assert rows[0]["constructed_prompt"] == "Prompt body"
        assert rows[0]["llm_inference"] == ""
        assert rows[1]["event_type"] == "inference"
        assert rows[1]["llm_inference"] == '{"decision":"ASK","next_question":"When did this begin?"}'
    finally:
        prompt_logging.settings.enable_prompt_logging = original_enable
        prompt_logging.settings.prompt_log_format = original_format


def test_prompt_logging_writes_both_by_default(tmp_path, monkeypatch):
    original_enable = prompt_logging.settings.enable_prompt_logging
    original_format = getattr(prompt_logging.settings, "prompt_log_format", "both")
    try:
        monkeypatch.setattr(prompt_logging, "_PROMPT_LOG_DIR", tmp_path)
        prompt_logging.settings.enable_prompt_logging = True
        prompt_logging.settings.prompt_log_format = "both"

        prompt_logging.log_constructed_prompt(
            session_id="rag_sess_both_1",
            user_query="I have a headache.",
            constructed_prompt="Prompt body",
            clinic_id="clinic_1",
            patient_id="pat_1",
            model_name="gemma3:4b",
            provider="ollama",
            endpoint="/rag/chat/turn",
            retrieval_mode="patient",
            inference_source="adapter_error",
        )

        assert (tmp_path / "prompt_session_rag_sess_both_1.log").exists()
        assert (tmp_path / "prompt_session_rag_sess_both_1.csv").exists()
    finally:
        prompt_logging.settings.enable_prompt_logging = original_enable
        prompt_logging.settings.prompt_log_format = original_format
