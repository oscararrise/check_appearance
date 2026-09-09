import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import AppearanceCheck, PowerAutomateDelivery

logger = logging.getLogger(__name__)


def build_appearance_check_payload(check: AppearanceCheck) -> dict:
    """Build the stable JSON contract consumed by the Power Automate flow."""
    local_time = timezone.localtime(check.recorded_at)
    status_label = check.get_status_display()
    not_ready_declined = (
        status_label
        if check.status in {AppearanceCheck.Status.NOT_READY, AppearanceCheck.Status.DECLINED}
        else ""
    )

    return {
        "event": "appearance_check.recorded",
        "event_version": 1,
        "record_id": check.pk,
        "employee_id": str(check.employee_id),
        "employee_name": check.employee_name,
        "role": check.role or "",
        "appearance_check": status_label,
        "appearance_check_code": check.status,
        "is_ready": check.status == AppearanceCheck.Status.READY,
        "not_ready_declined": not_ready_declined,
        "fs_input": "",
        "comment": check.comment or "",
        "comment_update_final_check": "",
        "shift": check.get_shift_display(),
        "recorded_date": local_time.strftime("%Y-%m-%d"),
        "recorded_time": local_time.strftime("%H:%M:%S"),
        "recorded_at": local_time.isoformat(),
        "recorded_by": check.recorded_by.get_username(),
    }


def _safe_http_error_body(exc: HTTPError) -> str:
    try:
        body = exc.read(500).decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    return body


def attempt_power_automate_delivery(delivery: PowerAutomateDelivery) -> PowerAutomateDelivery:
    """Attempt one webhook delivery and persist the result without raising to the UI."""
    now = timezone.now()
    delivery.attempts += 1
    delivery.last_attempt_at = now
    delivery.response_status = None
    delivery.last_error = ""

    flow_url = getattr(settings, "POWER_AUTOMATE_FLOW_URL", "").strip()
    if not flow_url:
        delivery.status = PowerAutomateDelivery.Status.FAILED
        delivery.last_error = "POWER_AUTOMATE_FLOW_URL is not configured."
        delivery.save()
        return delivery

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ARRISE-Appearance/1.0",
    }
    api_key = getattr(settings, "POWER_AUTOMATE_API_KEY", "").strip()
    if api_key:
        headers["X-ARRISE-API-Key"] = api_key

    request = Request(
        flow_url,
        data=json.dumps(delivery.payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    timeout = max(1, int(getattr(settings, "POWER_AUTOMATE_TIMEOUT_SECONDS", 5)))

    try:
        with urlopen(request, timeout=timeout) as response:
            response_status = response.getcode()
        delivery.response_status = response_status
        if 200 <= response_status < 300:
            delivery.status = PowerAutomateDelivery.Status.SENT
            delivery.sent_at = now
        else:
            delivery.status = PowerAutomateDelivery.Status.FAILED
            delivery.last_error = f"Power Automate returned HTTP {response_status}."
    except HTTPError as exc:
        delivery.response_status = exc.code
        body = _safe_http_error_body(exc)
        delivery.status = PowerAutomateDelivery.Status.FAILED
        delivery.last_error = f"HTTP {exc.code}" + (f": {body}" if body else "")
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        delivery.status = PowerAutomateDelivery.Status.FAILED
        delivery.last_error = str(exc)[:1000]

    delivery.save()

    if delivery.status == PowerAutomateDelivery.Status.FAILED:
        logger.warning(
            "Power Automate delivery failed for AppearanceCheck %s: %s",
            delivery.appearance_check_id,
            delivery.last_error,
        )

    return delivery


def publish_appearance_check(check: AppearanceCheck) -> PowerAutomateDelivery:
    """Create/update the audit record and deliver a newly saved Appearance Check."""
    payload = build_appearance_check_payload(check)
    delivery, _ = PowerAutomateDelivery.objects.get_or_create(
        appearance_check=check,
        defaults={"payload": payload},
    )
    delivery.payload = payload

    if not getattr(settings, "POWER_AUTOMATE_ENABLED", False):
        delivery.status = PowerAutomateDelivery.Status.DISABLED
        delivery.last_error = ""
        delivery.save()
        return delivery

    if delivery.status == PowerAutomateDelivery.Status.SENT:
        delivery.save(update_fields=["payload", "updated_at"])
        return delivery

    delivery.status = PowerAutomateDelivery.Status.PENDING
    delivery.save()
    return attempt_power_automate_delivery(delivery)
