from pathlib import Path

_SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def schema_sql() -> str:
    return _SCHEMA_FILE.read_text(encoding="utf-8")
