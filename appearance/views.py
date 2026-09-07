import json
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from openpyxl import Workbook

from .models import AppearanceCheck, PreparationScan
from .services import get_employee_profile, resolve_operational_shift, tattoo_payload


@login_required
def process_selection(request):
    return render(request, "appearance/process_selection.html")


@login_required
def workspace(request, process):
    process = process.upper()
    if process not in {"PREPARATION", "CHECK"}:
        return JsonResponse({"error": "Invalid process."}, status=404)

    if process == "PREPARATION":
        recent = PreparationScan.objects.select_related("recorded_by")[:25]
        title = "Appearance Preparation"
    else:
        recent = AppearanceCheck.objects.select_related("recorded_by")[:25]
        title = "Appearance Check"

    return render(
        request,
        "appearance/workspace.html",
        {"process": process, "process_title": title, "recent": recent},
    )


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


@login_required
@require_POST
def lookup_employee(request):
    payload = _json_body(request)
    employee_id = str(payload.get("employee_id", "")).strip()
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
    return JsonResponse(
        {
            "ok": True,
            "record": {
                "id": record.id,
                "employee_id": record.employee_id,
                "employee_name": record.employee_name,
                "role": record.role,
                "shift": record.get_shift_display(),
                "recorded_at": timezone.localtime(record.recorded_at).strftime("%H:%M:%S"),
            },
        }
    )


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
    return JsonResponse(
        {
            "ok": True,
            "record": {
                "id": record.id,
                "employee_id": record.employee_id,
                "employee_name": record.employee_name,
                "status": record.get_status_display(),
                "comment": record.comment,
                "shift": record.get_shift_display(),
                "recorded_at": timezone.localtime(record.recorded_at).strftime("%H:%M:%S"),
            },
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
