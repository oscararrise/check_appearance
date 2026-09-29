import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone

from .models import AppearanceCheck, PowerAutomateDelivery

logger = logging.getLogger(__name__)


def build_appearance_check_payload(check: AppearanceCheck) -> dict:
    local_time = timezone.localtime(check.recorded_at)
    status_label = check.get_status_display()
    not_ready_declined = (
        status_label
        if check.status in {AppearanceCheck.Status.NOT_READY, AppearanceCheck.Status.DECLINED}
        else ""
    )
    late_local_time = timezone.localtime(check.late_marked_at) if check.late_marked_at else None

    return {
        "event": "appearance_check.recorded",
        "event_version": 1,
        "record_id": check.pk,
        "request_id": str(check.request_id),
        "employee_id": str(check.employee_id),
        "employee_name": check.employee_name,
        "role": check.role or "",
        "appearance_check": status_label,
        "appearance_check_code": check.status,
        "is_ready": check.status == AppearanceCheck.Status.READY,
        "not_ready_declined": not_ready_declined,
        "late": check.is_late,
        "late_label": "Late" if check.is_late is True else "On time" if check.is_late is False else "Not recorded",
        "late_marked_at": late_local_time.isoformat() if late_local_time else "",
        "late_marked_time": late_local_time.strftime("%H:%M:%S") if late_local_time else "",
        "fs_input": "",
        "comment": check.comment or "",
        "comment_update_final_check": "",
        "shift": check.get_shift_display(),
        "recorded_date": local_time.strftime("%Y-%m-%d"),
        "recorded_time": local_time.strftime("%H:%M:%S"),
        "recorded_at": local_time.isoformat(),
        "recorded_by": check.recorded_by.get_username(),
    }


def retry_delay_seconds(attempts):
    delays = settings.POWER_AUTOMATE_RETRY_DELAYS_SECONDS
    if not delays:
        return 60
    index = min(max(0, attempts - 1), len(delays) - 1)
    return delays[index]


def attempt_power_automate_delivery(delivery: PowerAutomateDelivery) -> PowerAutomateDelivery:
    """Attempt one delivery. Persist only sanitized error codes, never remote bodies/URLs."""
    now = timezone.now()
    delivery.attempts += 1
    delivery.last_attempt_at = now
    delivery.response_status = None
    delivery.last_error = ""

    flow_url = settings.POWER_AUTOMATE_FLOW_URL.strip()
    if not flow_url:
        delivery.status = PowerAutomateDelivery.Status.FAILED
        delivery.last_error = "CONFIG_MISSING_FLOW_URL"
        delivery.save()
        return delivery

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "ARRISE-Appearance/1.0",
    }
    if settings.POWER_AUTOMATE_API_KEY:
        headers["X-ARRISE-API-Key"] = settings.POWER_AUTOMATE_API_KEY

    request = Request(
        flow_url,
        data=json.dumps(delivery.payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=settings.POWER_AUTOMATE_TIMEOUT_SECONDS) as response:
            response_status = response.getcode()
        delivery.response_status = response_status
        if 200 <= response_status < 300:
            delivery.status = PowerAutomateDelivery.Status.SENT
            delivery.sent_at = now
        else:
            delivery.status = PowerAutomateDelivery.Status.FAILED
            delivery.last_error = f"HTTP_{response_status}"
    except HTTPError as exc:
        delivery.response_status = exc.code
        delivery.status = PowerAutomateDelivery.Status.FAILED
        delivery.last_error = f"HTTP_{exc.code}"
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        delivery.status = PowerAutomateDelivery.Status.FAILED
        delivery.last_error = f"NETWORK_{exc.__class__.__name__}"

    delivery.save()

    if delivery.status == PowerAutomateDelivery.Status.FAILED:
        logger.warning(
            "POWER_AUTOMATE_DELIVERY_FAILED check_id=%s attempts=%s code=%s",
            delivery.appearance_check_id,
            delivery.attempts,
            delivery.last_error,
        )
    return delivery


def publish_appearance_check(check: AppearanceCheck) -> PowerAutomateDelivery:
    payload = build_appearance_check_payload(check)
    delivery, _ = PowerAutomateDelivery.objects.get_or_create(
        appearance_check=check,
        defaults={"payload": payload},
    )
    delivery.payload = payload

    if not settings.POWER_AUTOMATE_ENABLED:
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
