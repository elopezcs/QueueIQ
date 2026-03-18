from __future__ import annotations

from dataclasses import dataclass
import requests

from queueiq_common.catalog import ProductModule


@dataclass(frozen=True)
class ServiceStatus:
    module_name: str
    service_name: str
    url: str
    reachable: bool
    detail: str


def _probe(url: str, timeout: float = 1.5) -> tuple[bool, str]:
    try:
        response = requests.get(url, timeout=timeout)
        return response.ok, f"HTTP {response.status_code}"
    except requests.RequestException as exc:
        return False, exc.__class__.__name__


def collect_statuses(modules: tuple[ProductModule, ...]) -> list[ServiceStatus]:
    statuses: list[ServiceStatus] = []
    for module in modules:
        for service in module.services:
            target = service.health_url or service.url
            reachable, detail = _probe(target)
            statuses.append(
                ServiceStatus(
                    module_name=module.name,
                    service_name=service.name,
                    url=service.url,
                    reachable=reachable,
                    detail=detail,
                )
            )
    return statuses
