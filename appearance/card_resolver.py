import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class CardResolverError(Exception):
    """Typed, operator-safe failure from the Card Resolver dependency."""

    def __init__(self, code, message, http_status=400, retryable=False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.retryable = retryable

    def as_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class CardResolution:
    employee_id: str
    employee_name: str
    facility_code: str
    card_number: str


def _read_json_response(response):
    max_bytes = settings.CARD_RESOLVER_MAX_RESPONSE_BYTES
    raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise CardResolverError(
            "CARD_RESOLVER_INVALID_RESPONSE",
            "Card Resolver returned an invalid response.",
            http_status=502,
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CardResolverError(
            "CARD_RESOLVER_INVALID_RESPONSE",
            "Card Resolver returned an invalid response.",
            http_status=502,
        ) from exc

    if not isinstance(payload, dict):
        raise CardResolverError(
            "CARD_RESOLVER_INVALID_RESPONSE",
            "Card Resolver returned an invalid response.",
            http_status=502,
        )
    return payload


def resolve_card(raw):
    raw = str(raw or "").strip()
    if not raw:
        raise CardResolverError("CARD_REQUIRED", "Scan a card before continuing.", 400)
    if len(raw) > 20:
        raise CardResolverError("CARD_INVALID", "The scanned card value is invalid.", 422)
    if not settings.CARD_RESOLVER_ENABLED:
        raise CardResolverError(
            "CARD_RESOLVER_DISABLED",
            "Card scanning is temporarily unavailable. Use Employee ID lookup.",
            503,
        )
    if not settings.CARD_RESOLVER_URL or not settings.CARD_RESOLVER_SERVICE_TOKEN:
        logger.error("CARD_RESOLVER_CONFIG_ERROR")
        raise CardResolverError(
            "CARD_RESOLVER_CONFIG_ERROR",
            "Card scanning is temporarily unavailable. Use Employee ID lookup.",
            503,
        )

    body = json.dumps({"raw": raw}).encode("utf-8")
    request = Request(
        settings.CARD_RESOLVER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.CARD_RESOLVER_SERVICE_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ARRISE-Appearance/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=settings.CARD_RESOLVER_TIMEOUT_SECONDS) as response:
            payload = _read_json_response(response)
    except CardResolverError:
        raise
    except HTTPError as exc:
        if exc.code == 404:
            raise CardResolverError(
                "CARD_NOT_FOUND",
                "This card was not found in the active Card Resolver dataset.",
                404,
            ) from exc
        if exc.code == 409:
            raise CardResolverError(
                "CARD_AMBIGUOUS",
                "This card matches more than one employee. Ask an administrator to review the active dataset.",
                409,
            ) from exc
        if exc.code == 422:
            raise CardResolverError(
                "CARD_UNDECODABLE",
                "The card reader value could not be decoded.",
                422,
            ) from exc
        if exc.code in {401, 403}:
            logger.error("CARD_RESOLVER_AUTH_ERROR http_status=%s", exc.code)
            raise CardResolverError(
                "CARD_RESOLVER_AUTH_ERROR",
                "Card scanning is temporarily unavailable. Use Employee ID lookup.",
                503,
            ) from exc
        logger.warning("CARD_RESOLVER_HTTP_ERROR http_status=%s", exc.code)
        raise CardResolverError(
            "CARD_RESOLVER_UNAVAILABLE",
            "Card Resolver is temporarily unavailable. Use Employee ID lookup.",
            503,
            retryable=True,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning("CARD_RESOLVER_NETWORK_ERROR type=%s", exc.__class__.__name__)
        raise CardResolverError(
            "CARD_RESOLVER_UNAVAILABLE",
            "Card Resolver is temporarily unavailable. Use Employee ID lookup.",
            503,
            retryable=True,
        ) from exc

    employee = payload.get("employee")
    if not isinstance(employee, dict):
        logger.error("CARD_RESOLVER_INVALID_EMPLOYEE_PAYLOAD")
        raise CardResolverError(
            "CARD_RESOLVER_INVALID_RESPONSE",
            "Card Resolver returned an incomplete employee mapping.",
            502,
        )

    employee_id = str(employee.get("hibob_id") or "").strip()
    if not employee_id:
        logger.error("CARD_RESOLVER_MISSING_HIBOB_ID")
        raise CardResolverError(
            "CARD_RESOLVER_INVALID_RESPONSE",
            "Card Resolver returned an incomplete employee mapping.",
            502,
        )

    decoder = payload.get("decoder")
    if not isinstance(decoder, dict):
        decoder = {}

    return CardResolution(
        employee_id=employee_id,
        employee_name=str(employee.get("name") or "").strip(),
        facility_code=str(decoder.get("facility_code") or ""),
        card_number=str(decoder.get("card_number") or ""),
    )
