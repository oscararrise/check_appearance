import json
from datetime import datetime, time
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from openpyxl import Workbook

from .models import AppearanceCheck, PreparationScan, ProcessSchedule
from .services import (
    appearance_approval_payload,
    get_employee_profile,
    resolve_operational_shift,
    tattoo_payload,
)


SCHEDULE_DEFAULTS = {
    "PREPARATION": {
        "MORNING": (time(6, 0), time(8, 0)),
        "AFTERNOON": (time(14, 0), time(16, 0)),
        "NIGHT": (time(22, 0), time(0, 0)),
    },
    "CHECK": {
        "MORNING": (time(6, 50), time(7, 30)),
        "AFTERNOON": (time(14, 50), time(15, 30)),
        "NIGHT": (time(22, 50), time(23, 30)),
    },
}
SHIFT_ORDER = ("MORNING", "AFTERNOON", "NIGHT")


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _record_timestamp_payload(record):
    local_time = timezone.localtime(record.recorded_at)
    return {
        "recorded_date": local_time.strftime("%Y-%m-%d"),
        "recorded_at": local_time.strftime("%H:%M:%S"),
        "recorded_by": record.recorded_by.get_username(),
    }


def _operational_record_payload(record, process):
    if record is None:
        return None
    is_check = process == "CHECK"
    return {
        "id": record.id,
        "employee_id": record.employee_id,
        "employee_name": record.employee_name,
        "role": record.role,
        "shift": record.get_shift_display(),
        "status": record.get_status_display() if is_check else "Registered",
        "comment": record.comment if is_check else "",
        "process": process,
        **_record_timestamp_payload(record),
    }


def _latest_employee_record(employee_id, process):
    if process == "CHECK":
        record = (
            AppearanceCheck.objects.filter(employee_id=employee_id)
            .select_related("recorded_by")
            .order_by("-recorded_at")
            .first()
        )
    else:
        record = (
            PreparationScan.objects.filter(employee_id=employee_id)
            .select_related("recorded_by")
            .order_by("-recorded_at")
            .first()
        )
    return _operational_record_payload(record, process)


def _schedule_rows(process):
    existing = {
        row.shift: row
        for row in ProcessSchedule.objects.filter(process=process).select_related("updated_by")
    }
    rows = []
    for shift in SHIFT_ORDER:
        row = existing.get(shift)
        if row is None:
            start_time, end_time = SCHEDULE_DEFAULTS[process][shift]
            row, _ = ProcessSchedule.objects.get_or_create(
                process=process,
                shift=shift,
                defaults={"start_time": start_time, "end_time": end_time},
            )
        rows.append(row)
    return rows


@login_required
def process_selection(request):
    return render(
        request,
        "appearance/process_selection.html",
        {
            "preparation_schedule": _schedule_rows("PREPARATION"),
            "check_schedule": _schedule_rows("CHECK"),
        },
    )


@login_required
def schedule_settings(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Only administrators can manage schedule settings.")

    return render(
        request,
        "appearance/schedule_settings.html",
        {
            "preparation_schedule": _schedule_rows("PREPARATION"),
            "check_schedule": _schedule_rows("CHECK"),
        },
    )


def _history_filters(request, process):
    date_from_raw = request.GET.get("date_from", "").strip()
    date_to_raw = request.GET.get("date_to", "").strip()
    employee_id = request.GET.get("employee_id", "").strip()
    status = request.GET.get("status", "").strip().upper()

    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None

    if process == "CHECK":
        allowed_statuses = {choice for choice, _ in AppearanceCheck.Status.choices}
        if status not in allowed_statuses:
            status = ""
    elif status != "REGISTERED":
        status = ""

    return {
        "date_from_raw": date_from_raw if date_from else "",
        "date_to_raw": date_to_raw if date_to else "",
        "date_from": date_from,
        "date_to": date_to,
        "employee_id": employee_id,
        "status": status,
    }


def _apply_history_filters(records, process, filters):
    if filters["date_from"]:
        records = records.filter(recorded_at__date__gte=filters["date_from"])
    if filters["date_to"]:
        records = records.filter(recorded_at__date__lte=filters["date_to"])
    if filters["employee_id"]:
        records = records.filter(employee_id__icontains=filters["employee_id"])
    if process == "CHECK" and filters["status"]:
        records = records.filter(status=filters["status"])
    return records


@login_required
def workspace(request, process):
    process = process.upper()
    if process not in {"PREPARATION", "CHECK"}:
        return JsonResponse({"error": "Invalid process."}, status=404)

    if process == "PREPARATION":
        records = PreparationScan.objects.select_related("recorded_by")
        title = "Appearance Preparation"
        status_options = [("REGISTERED", "Registered")]
    else:
        records = AppearanceCheck.objects.select_related("recorded_by")
        title = "Appearance Check"
        status_options = list(AppearanceCheck.Status.choices)

    filters = _history_filters(request, process)
    filtered_records = _apply_history_filters(records, process, filters)
    matched_count = filtered_records.count()
    history = filtered_records[:500]

    return render(
        request,
        "appearance/workspace.html",
        {
            "process": process,
            "process_title": title,
            "history": history,
            "history_count": matched_count,
            "history_loaded_count": len(history),
            "history_filters": filters,
            "history_has_filters": any(
                [
                    filters["date_from"],
                    filters["date_to"],
                    filters["employee_id"],
                    filters["status"],
                ]
            ),
            "status_options": status_options,
            "schedule_rows": _schedule_rows(process),
        },
    )


@login_required
@require_POST
def lookup_employee(request):
    payload = _json_body(request)
    employee_id = str(payload.get("employee_id", "")).strip()
    process = str(payload.get("process", "CHECK")).upper()
    if process not in {"PREPARATION", "CHECK"}:
        process = "CHECK"

    profile = get_employee_profile(employee_id)
    if profile is None:
        return JsonResponse(
            {"ok": False, "error": "Employee ID was not found in HiBob."},
            status=404,
        )

    return JsonResponse(
        {
            "ok": True,
            "employee": {
                "employee_id": profile.employee_id,
                "full_name": profile.full_name,
                "role": profile.role,
                "tattoos": tattoo_payload(profile),
                "appearance_approvals": appearance_approval_payload(profile),
                "latest_process_record": _latest_employee_record(profile.employee_id, process),
            },
        }
    )


@login_required
@require_POST
def record_preparation(request):
    payload = _json_body(request)
    profile = get_employee_profile(payload.get("employee_id"))
    if profile is None:
        return JsonResponse({"ok": False, "error": "Employee ID was not found in HiBob."}, status=404)

    now = timezone.localtime()
    record = PreparationScan.objects.create(
        employee_id=profile.employee_id,
        employee_name=profile.full_name,
        role=profile.role,
        shift=resolve_operational_shift(now),
        recorded_by=request.user,
    )
    return JsonResponse({"ok": True, "record": _operational_record_payload(record, "PREPARATION")})


@login_required
@require_POST
def record_check(request):
    payload = _json_body(request)
    profile = get_employee_profile(payload.get("employee_id"))
    if profile is None:
        return JsonResponse({"ok": False, "error": "Employee ID was not found in HiBob."}, status=404)

    status = str(payload.get("status", "")).upper()
    allowed = {choice for choice, _ in AppearanceCheck.Status.choices}
    if status not in allowed:
        return JsonResponse({"ok": False, "error": "Select Ready, Not Ready or Declined."}, status=400)

    comment = str(payload.get("comment", "")).strip()[:500]
    now = timezone.localtime()
    record = AppearanceCheck.objects.create(
        employee_id=profile.employee_id,
        employee_name=profile.full_name,
        role=profile.role,
        shift=resolve_operational_shift(now),
        status=status,
        comment=comment,
        recorded_by=request.user,
    )
    return JsonResponse({"ok": True, "record": _operational_record_payload(record, "CHECK")})


def _parse_clock(value):
    try:
        return datetime.strptime(str(value), "%H:%M").time()
    except (TypeError, ValueError):
        return None


@login_required
@require_POST
def update_schedule(request, process):
    process = process.upper()
    if process not in SCHEDULE_DEFAULTS:
        return JsonResponse({"ok": False, "error": "Invalid process."}, status=404)
    if not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "Only administrators can update the operating schedule."}, status=403)

    payload = _json_body(request)
    schedule = payload.get("schedule")
    if not isinstance(schedule, list):
        return JsonResponse({"ok": False, "error": "Schedule data is required."}, status=400)

    normalized = {}
    for item in schedule:
        shift = str(item.get("shift", "")).upper()
        start_time = _parse_clock(item.get("start_time"))
        end_time = _parse_clock(item.get("end_time"))
        if shift not in SHIFT_ORDER or start_time is None or end_time is None:
            return JsonResponse({"ok": False, "error": "Each shift requires a valid start and end time."}, status=400)
        normalized[shift] = (start_time, end_time)

    if set(normalized) != set(SHIFT_ORDER):
        return JsonResponse({"ok": False, "error": "Morning, Afternoon and Night schedules are required."}, status=400)

    with transaction.atomic():
        for shift in SHIFT_ORDER:
            start_time, end_time = normalized[shift]
            ProcessSchedule.objects.update_or_create(
                process=process,
                shift=shift,
                defaults={
                    "start_time": start_time,
                    "end_time": end_time,
                    "updated_by": request.user,
                },
            )

    rows = _schedule_rows(process)
    return JsonResponse(
        {
            "ok": True,
            "schedule": [
                {
                    "shift": row.shift,
                    "shift_label": row.get_shift_display(),
                    "start_time": row.start_time.strftime("%H:%M"),
                    "end_time": row.end_time.strftime("%H:%M"),
                }
                for row in rows
            ],
        }
    )


@login_required
@require_GET
def export_report(request):
    process = request.GET.get("process", "CHECK").upper()
    today = timezone.localdate()

    wb = Workbook()
    ws = wb.active

    if process == "PREPARATION":
        ws.title = "Appearance Preparation"
        ws.append(["Employee ID", "Name", "Role", "Date", "Time", "Shift", "Recorded by"])
        records = PreparationScan.objects.filter(recorded_at__date=today).select_related("recorded_by")
        for item in records:
            local_time = timezone.localtime(item.recorded_at)
            ws.append([
                item.employee_id,
                item.employee_name,
                item.role,
                local_time.date().isoformat(),
                local_time.strftime("%H:%M:%S"),
                item.get_shift_display(),
                item.recorded_by.get_username(),
            ])
    else:
        ws.title = "Appearance Check"
        ws.append(["Employee ID", "Name", "Role", "Date", "Time", "Shift", "Status", "Comment", "Recorded by"])
        records = AppearanceCheck.objects.filter(recorded_at__date=today).select_related("recorded_by")
        for item in records:
            local_time = timezone.localtime(item.recorded_at)
            ws.append([
                item.employee_id,
                item.employee_name,
                item.role,
                local_time.date().isoformat(),
                local_time.strftime("%H:%M:%S"),
                item.get_shift_display(),
                item.get_status_display(),
                item.comment,
                item.recorded_by.get_username(),
            ])

    for column in ws.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 45)
        ws.column_dimensions[column[0].column_letter].width = width

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"appearance_{process.lower()}_{today.isoformat()}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
