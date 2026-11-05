import base64
import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class CardResolverError(Exception):
    """Safe operational error returned to the Appearance workflow."""


class CardNotFoundError(CardResolverError):
    """Unknown card that may be manually registered."""


class CardMappingConflict(CardResolverError):
    """Card already belongs to a different employee."""


@dataclass(frozen=True)
class CardResolution:
    employee_id: str
    employee_name: str
    facility_code: str
    card_number: str


def resolve_card(raw):
    raw = str(raw or "").strip()
    if not raw:
        raise CardResolverError("Scan a card before continuing.")
    if len(raw) > 20:
        raise CardResolverError("The scanned card value is invalid.")
    if not settings.CARD_RESOLVER_ENABLED:
        raise CardResolverError("Card scanning is not enabled yet.")
    if not settings.CARD_RESOLVER_URL or not settings.CARD_RESOLVER_SERVICE_TOKEN:
        raise CardResolverError("Card Resolver is not configured on the server.")

    body = json.dumps({"raw": raw}).encode("utf-8")
    request = Request(
        settings.CARD_RESOLVER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {settings.CARD_RESOLVER_SERVICE_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=settings.CARD_RESOLVER_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise CardNotFoundError("Card was not found in the active Card Resolver dataset.") from exc
        if exc.code == 409:
            raise CardResolverError("Card is ambiguous in Card Resolver. Ask an administrator to review the active dataset.") from exc
        if exc.code == 422:
            raise CardResolverError("The card reader value could not be decoded.") from exc
        if exc.code in {401, 403}:
            logger.error("Card Resolver rejected Appearance authentication with HTTP %s", exc.code)
            raise CardResolverError("Card Resolver authentication failed. Contact an administrator.") from exc
        logger.error("Card Resolver returned HTTP %s", exc.code)
        raise CardResolverError("Card Resolver is temporarily unavailable.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Card Resolver request failed: %s", exc.__class__.__name__)
        raise CardResolverError("Card Resolver is temporarily unavailable.") from exc

    employee = payload.get("employee") or {}
    # Card Resolver currently calls the roster EID 'hibob_id'. In Appearance this
    # value is intentionally treated as HiBob employee.employee_id.
    employee_id = str(employee.get("hibob_id") or "").strip()
    if not employee_id:
        logger.error("Card Resolver response did not include employee.hibob_id")
        raise CardResolverError("Card Resolver returned an incomplete employee mapping.")

    decoder = payload.get("decoder") or {}
    return CardResolution(
        employee_id=employee_id,
        employee_name=str(employee.get("name") or "").strip(),
        facility_code=str(decoder.get("facility_code") or ""),
        card_number=str(decoder.get("card_number") or ""),
    )

def register_card(raw, hibob_id):
    """Create a card mapping through Card Resolver; never send secrets to the browser."""
    raw = str(raw or "").strip()
    hibob_id = str(hibob_id or "").strip()
    if not raw.isdigit() or len(raw) > 20:
        raise CardResolverError("Invalid card reader value.")
    if not hibob_id.isdigit() or len(hibob_id) > 80:
        raise CardResolverError("Enter a numeric HiBob ID.")
    if not settings.CARD_RESOLVER_ENABLED or not settings.CARD_RESOLVER_UPDATE_URL:
        raise CardResolverError("Card registration is not configured.")
    if not settings.CARD_RESOLVER_ADMIN_USER or not settings.CARD_RESOLVER_ADMIN_PASSWORD:
        raise CardResolverError("Card registration credentials are not configured.")
    credentials = f"{settings.CARD_RESOLVER_ADMIN_USER}:{settings.CARD_RESOLVER_ADMIN_PASSWORD}"
    authorization = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    request = Request(
        settings.CARD_RESOLVER_UPDATE_URL,
        data=json.dumps({"card_number_raw": raw, "hibob_id": hibob_id, "overwrite": False}).encode("utf-8"),
        headers={"Authorization": f"Basic {authorization}", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.CARD_RESOLVER_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 409:
            raise CardMappingConflict("This card is already assigned to another employee.") from exc
        if exc.code == 422:
            raise CardResolverError("Card or HiBob ID format was rejected.") from exc
        if exc.code in (401, 403):
            logger.error("Card Resolver update authentication rejected: HTTP %s", exc.code)
            raise CardResolverError("Card registration authentication failed.") from exc
        logger.error("Card Resolver update failed: HTTP %s", exc.code)
        raise CardResolverError("Card registration is temporarily unavailable.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("Card Resolver update failed: %s", exc.__class__.__name__)
        raise CardResolverError("Card registration is temporarily unavailable.") from exc
    if payload.get("status") not in ("created", "unchanged") or str(payload.get("hibob_id")) != hibob_id:
        raise CardResolverError("Card registration returned an unexpected result.")
    return payload
