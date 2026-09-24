import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


_OPERATIONAL_COLUMN_NAMES = {
    "team",
    "appereance check",
    "appearance check",
    "fs imput",
    "fs input",
    "not ready/declined",
    "comment",
    "comment update (final check)",
    "tattoo policy",
}


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def _normalise_key(value) -> str:
    return _clean(value).casefold()


def _decode_excel_column_name(value: str) -> str:
    """Decode Excel/Power Automate names such as 7_x002e_1 -> 7.1."""
    text = str(value or "")

    def replace(match):
        try:
            return chr(int(match.group(1), 16))
        except (TypeError, ValueError):
            return match.group(0)

    return _clean(re.sub(r"_x([0-9a-fA-F]{4})_", replace, text))


def _row_id(row: dict) -> str:
    """Support both Power Automate shapes: Column1/Column2 and ID/dynamic-name."""
    if "Column1" in row:
        return _clean(row.get("Column1"))

    for key, value in row.items():
        if _normalise_key(key) == "id":
            return _clean(value)

    return ""


def _infer_text_key(rows: list[dict]) -> str:
    """
    Return the column containing the employee name/game and studio section title.

    Table4-style responses expose it as Column2.
    Other Excel tables expose the first Excel header as the JSON property name,
    e.g. "7_x002e_1 Spanish (LIVE) Generic".
    """
    if any(isinstance(row, dict) and "Column2" in row for row in rows):
        return "Column2"

    candidate_scores: dict[str, int] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        for key, value in row.items():
            normalised = _normalise_key(key)

            if (
                normalised == "id"
                or normalised in _OPERATIONAL_COLUMN_NAMES
                or normalised == "iteminternalid"
                or key.startswith("@")
            ):
                continue

            # Prefer a real Excel data column: rows with names/section titles
            # will repeatedly contain non-empty values here.
            score = 1
            if _clean(value):
                score += 3
            if re.search(r"_x[0-9a-fA-F]{4}_", key):
                score += 2

            candidate_scores[key] = candidate_scores.get(key, 0) + score

    if not candidate_scores:
        return ""

    return max(candidate_scores, key=candidate_scores.get)


def _extract_assignment_type(header_text: str) -> str:
    # Generic/Dedicated is not always the final text; some headers append
    # "(NO VISIBLE TATTOOS)" afterwards.
    match = re.search(r"\b(Dedicated|Generic)\b", header_text, re.IGNORECASE)
    return match.group(1).title() if match else ""


def _extract_studio(header_text: str) -> str:
    # Accept 7.3, S7.4, "S 7.4", 8.1 + 8.8 and 9.1.3 + 9.5.1.
    match = re.match(
        r"^\s*S?\s*(\d+(?:\.\d+)+(?:\s*\+\s*\d+(?:\.\d+)+)*)\b",
        header_text,
        re.IGNORECASE,
    )
    return _clean(match.group(1)) if match else ""


def _extract_game(row_text: str, employee_name: str) -> str:
    row_text = _clean(row_text)
    employee_name = _clean(employee_name)

    if employee_name and row_text.casefold().startswith(employee_name.casefold()):
        return _clean(row_text[len(employee_name):]).lstrip("-–—: ")

    # Fallback for small naming differences between HiBob and Excel.
    game_match = re.search(
        r"\b(?:BJ|SP|FBJ|RW|VIP|MW|TP|SH|ONE|SPEED)\b",
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
    text_key = _infer_text_key(rows)
    employee_index = None

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        if _row_id(row) == target:
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
        if _row_id(candidate).upper() == "ID":
            header_row = candidate
            break

    header_text = ""
    if header_row and text_key:
        header_text = _clean(header_row.get(text_key))

    # In some Power Automate Excel responses the first studio title is the
    # JSON property name itself rather than a data row.
    if not header_text and text_key and text_key != "Column2":
        header_text = _decode_excel_column_name(text_key)

    employee_text = _clean(employee_row.get(text_key)) if text_key else ""

    assignment_type = _extract_assignment_type(header_text)

    # Some Power Automate Excel tables keep Generic/Dedicated in the
    # original Excel column name rather than in every section title.
    # Use that only as a fallback so a row-level section title always wins.
    if not assignment_type and text_key and text_key != "Column2":
        assignment_type = _extract_assignment_type(
            _decode_excel_column_name(text_key)
        )

    result.update(
        {
            "found": True,
            "studio": _extract_studio(header_text),
            "assignment_type": assignment_type,
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
