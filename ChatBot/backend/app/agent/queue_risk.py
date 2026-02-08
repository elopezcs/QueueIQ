from datetime import datetime, timezone
from typing import Any
import hashlib


def mock_queue_snapshot(clinic_id: str, servers_total: int) -> dict[str, Any]:
    """
    Deterministic snapshot based on clinic_id and current date-hour bucket.
    This is mock logic for demo purposes.
    """
    now = datetime.now(timezone.utc)
    bucket = now.strftime("%Y%m%d%H")
    seed = int(hashlib.sha256(f"{clinic_id}:{bucket}".encode("utf-8")).hexdigest(), 16)

    queue_length = (seed % 18)  # 0..17
    servers_busy = min(servers_total, 1 + (seed % (servers_total + 1)))

    return {
        "queue_length": int(queue_length),
        "servers_busy": int(servers_busy),
        "servers_total": int(servers_total),
        "updated_at": now.isoformat(),
    }


def estimate_wait_minutes(
    queue_length: int,
    servers_busy: int,
    servers_total: int,
    avg_service_minutes: int
) -> tuple[int, int]:
    """
    Simple heuristic:
    - effective_servers = max(1, servers_total - max(0, servers_busy - 1))
    - p50 ~ (queue_length / effective_servers) * avg_service_minutes
    - p90 ~ p50 * 1.7, with a minimum spread
    """
    effective_servers = max(1, servers_total - max(0, servers_busy - 1))
    base = (queue_length / effective_servers) * max(5, avg_service_minutes)
    p50 = int(round(base))
    p90 = int(round(max(p50 + 10, base * 1.7)))
    return max(0, p50), max(0, p90)
