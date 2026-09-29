import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

FOUND = "FOUND"
NOT_FOUND = "NOT_FOUND"
UNAVAILABLE = "UNAVAILABLE"
AUTH_ERROR = "AUTH_ERROR"
INVALID_RESPONSE = "INVALID_RESPONSE"

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


def _masked_employee_id(value):
    value = _clean(value)
    if len(value) <= 4:
        return "*" * len(value)
    return f"***{value[-4:]}"


def _decode_excel_column_name(value: str) -> str:
    text = str(value or "")

    def replace(match):
        try:
            return chr(int(match.group(1), 16))
        except (TypeError, ValueError):
            return match.group(0)

    return _clean(re.sub(r"_x([0-9a-fA-F]{4})_", replace, text))


def _row_id(row: dict) -> str:
    if "Column1" in row:
        return _clean(row.get("Column1"))

    for key, value in row.items():
        if _normalise_key(key) == "id":
            return _clean(value)

    return ""


def _infer_text_key(rows: list[dict]) -> str:
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
    match = re.search(r"\b(Dedicated|Generic)\b", header_text, re.IGNORECASE)
    return match.group(1).title() if match else ""


def _extract_studio(header_text: str) -> str:
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

    game_match = re.search(
        r"\b(?:BJ|SP|FBJ|RW|VIP|MW|TP|SH|ONE|SPEED)\b",
        row_text,
        re.IGNORECASE,
    )
    if game_match:
        return _clean(row_text[game_match.start():])
    return ""


def _result(status, *, code="", message="", retryable=False, source_table=""):
    return {
        "status": status,
        "found": status == FOUND,
        "studio": "",
        "assignment_type": "",
        "game": "",
        "studio_title": "",
        "source_table": _clean(source_table),
        "error_code": code,
        "message": message,
        "retryable": retryable,
    }


def parse_studio_assignment(payload: dict, employee_id: str, employee_name: str = "") -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return _result(
            INVALID_RESPONSE,
            code="WORKFORCE_INVALID_RESPONSE",
            message="Workforce returned an invalid response.",
        )

    rows = payload["data"]
    target = _clean(employee_id)
    text_key = _infer_text_key(rows)
    employee_index = None

    for index, row in enumerate(rows):
        if isinstance(row, dict) and _row_id(row) == target:
            employee_index = index
            break

    if employee_index is None:
        return _result(
            NOT_FOUND,
            code="WORKFORCE_EMPLOYEE_NOT_FOUND",
            message="This employee is not present in the current Workforce assignment list.",
            source_table=payload.get("table_found"),
        )

    employee_row = rows[employee_index]
    header_row = None
    for index in range(employee_index - 1, -1, -1):
        candidate = rows[index]
        if isinstance(candidate, dict) and _row_id(candidate).upper() == "ID":
            header_row = candidate
            break

    header_text = ""
    if header_row and text_key:
        header_text = _clean(header_row.get(text_key))
    if not header_text and text_key and text_key != "Column2":
        header_text = _decode_excel_column_name(text_key)

    employee_text = _clean(employee_row.get(text_key)) if text_key else ""
    assignment_type = _extract_assignment_type(header_text)
    if not assignment_type and text_key and text_key != "Column2":
        assignment_type = _extract_assignment_type(_decode_excel_column_name(text_key))

    result = _result(FOUND, source_table=payload.get("table_found"))
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
    masked_id = _masked_employee_id(employee_id)

    if not settings.POWER_AUTOMATE_LOOKUP_ENABLED:
        return _result(
            UNAVAILABLE,
            code="WORKFORCE_LOOKUP_DISABLED",
            message="Workforce assignment lookup is currently disabled.",
        )

    flow_url = settings.POWER_AUTOMATE_LOOKUP_FLOW_URL.strip()
    if not flow_url:
        logger.error("WORKFORCE_CONFIG_ERROR employee=%s", masked_id)
        return _result(
            UNAVAILABLE,
            code="WORKFORCE_CONFIG_ERROR",
            message="Workforce assignment is temporarily unavailable.",
        )

    body = json.dumps({"hibob_id": str(employee_id)}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ARRISE-Appearance/1.0",
    }
    if settings.POWER_AUTOMATE_LOOKUP_API_KEY:
        headers["X-ARRISE-API-Key"] = settings.POWER_AUTOMATE_LOOKUP_API_KEY

    request = Request(flow_url, data=body, headers=headers, method="POST")

    try:
        with urlopen(request, timeout=settings.POWER_AUTOMATE_LOOKUP_TIMEOUT_SECONDS) as response:
            max_bytes = settings.POWER_AUTOMATE_LOOKUP_MAX_RESPONSE_BYTES
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                logger.warning("WORKFORCE_RESPONSE_TOO_LARGE employee=%s", masked_id)
                return _result(
                    INVALID_RESPONSE,
                    code="WORKFORCE_INVALID_RESPONSE",
                    message="Workforce returned an invalid response.",
                )
            payload = json.loads(raw.decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            logger.error("WORKFORCE_AUTH_ERROR http_status=%s employee=%s", exc.code, masked_id)
            return _result(
                AUTH_ERROR,
                code="WORKFORCE_AUTH_ERROR",
                message="Workforce assignment is temporarily unavailable.",
            )
        logger.warning("WORKFORCE_HTTP_ERROR http_status=%s employee=%s", exc.code, masked_id)
        return _result(
            UNAVAILABLE,
            code="WORKFORCE_UNAVAILABLE",
            message="Workforce assignment is temporarily unavailable.",
            retryable=exc.code in {408, 425, 429} or exc.code >= 500,
        )
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning("WORKFORCE_NETWORK_ERROR type=%s employee=%s", exc.__class__.__name__, masked_id)
        return _result(
            UNAVAILABLE,
            code="WORKFORCE_UNAVAILABLE",
            message="Workforce assignment is temporarily unavailable.",
            retryable=True,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        logger.warning("WORKFORCE_INVALID_JSON employee=%s", masked_id)
        return _result(
            INVALID_RESPONSE,
            code="WORKFORCE_INVALID_RESPONSE",
            message="Workforce returned an invalid response.",
        )

    result = parse_studio_assignment(payload, str(employee_id), employee_name)
    if result["status"] == NOT_FOUND:
        logger.info("WORKFORCE_EMPLOYEE_NOT_FOUND employee=%s", masked_id)
    elif result["status"] == INVALID_RESPONSE:
        logger.warning("WORKFORCE_INVALID_RESPONSE employee=%s", masked_id)
    return result
