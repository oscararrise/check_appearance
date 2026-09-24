import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def _extract_assignment_type(header_text: str) -> str:
    match = re.search(r"\b(Dedicated|Generic)\s*$", header_text, re.IGNORECASE)
    return match.group(1).title() if match else ""


def _extract_studio(header_text: str) -> str:
    match = re.match(
        r"^\s*(\d+(?:\.\d+)?(?:\s*\+\s*\d+(?:\.\d+)?)*)\b",
        header_text,
    )
    return _clean(match.group(1)) if match else ""


def _extract_game(row_text: str, employee_name: str) -> str:
    row_text = _clean(row_text)
    employee_name = _clean(employee_name)

    if employee_name and row_text.casefold().startswith(employee_name.casefold()):
        return _clean(row_text[len(employee_name):]).lstrip("-–—: ")

    # Fallback for small naming differences between HiBob and Excel.
    game_match = re.search(
        r"\b(?:BJ|SP|FBJ|RW|VIP|MW|TP|SH)\b",
        row_text,
        re.IGNORECASE,
    )
    if game_match:
        return _clean(row_text[game_match.start():])

    return ""


def parse_studio_assignment(payload: dict, employee_id: str, employee_name: str = "") -> dict:
    rows = payload.get("data")
    if not isinstance(rows, list):
        rows = []

    target = _clean(employee_id)
    employee_index = None

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        if _clean(row.get("Column1")) == target:
            employee_index = index
            break

    result = {
        "found": False,
        "studio": "",
        "assignment_type": "",
        "game": "",
        "studio_title": "",
        "source_table": _clean(payload.get("table_found")),
    }

    if employee_index is None:
        return result

    employee_row = rows[employee_index]
    header_row = None

    for index in range(employee_index - 1, -1, -1):
        candidate = rows[index]
        if not isinstance(candidate, dict):
            continue
        if _clean(candidate.get("Column1")).upper() == "ID":
            header_row = candidate
            break

    header_text = _clean(header_row.get("Column2")) if header_row else ""
    employee_text = _clean(employee_row.get("Column2"))

    result.update(
        {
            "found": True,
            "studio": _extract_studio(header_text),
            "assignment_type": _extract_assignment_type(header_text),
            "game": _extract_game(employee_text, employee_name),
            "studio_title": header_text,
        }
    )
    return result


def fetch_studio_assignment(employee_id: str, employee_name: str = "") -> dict:
    if not getattr(settings, "POWER_AUTOMATE_LOOKUP_ENABLED", False):
        return {
            "found": False,
            "studio": "",
            "assignment_type": "",
            "game": "",
            "studio_title": "",
            "source_table": "",
            "unavailable": True,
        }

    flow_url = getattr(settings, "POWER_AUTOMATE_LOOKUP_FLOW_URL", "").strip()
    if not flow_url:
        logger.warning("POWER_AUTOMATE_LOOKUP_FLOW_URL is not configured.")
        return {
            "found": False,
            "studio": "",
            "assignment_type": "",
            "game": "",
            "studio_title": "",
            "source_table": "",
            "unavailable": True,
        }

    body = json.dumps({"hibob_id": str(employee_id)}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ARRISE-Appearance/1.0",
    }

    api_key = getattr(settings, "POWER_AUTOMATE_LOOKUP_API_KEY", "").strip()
    if api_key:
        headers["X-ARRISE-API-Key"] = api_key

    request = Request(flow_url, data=body, headers=headers, method="POST")
    timeout = max(1, int(getattr(settings, "POWER_AUTOMATE_LOOKUP_TIMEOUT_SECONDS", 15)))

    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if not 200 <= response.getcode() < 300:
                raise ValueError(f"Power Automate returned HTTP {response.getcode()}.")
        payload = json.loads(raw)
        return parse_studio_assignment(payload, str(employee_id), employee_name)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Studio assignment lookup failed for employee %s: %s", employee_id, exc)
        return {
            "found": False,
            "studio": "",
            "assignment_type": "",
            "game": "",
            "studio_title": "",
            "source_table": "",
            "unavailable": True,
        }
