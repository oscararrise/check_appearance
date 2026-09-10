import hashlib
import re
from datetime import date, datetime
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.utils.datetime import from_excel

from .models import (
    AppearanceApprovalRecord,
    DataUpload,
    HiBobEmployee,
    ImportBatch,
    ImportIssue,
    TattooRecord,
)
from .services import normalize_employee_id


TATTOO_HEADER_ALIASES = {
    "id": "employee_id",
    "name": "source_name",
    "tattoos": "tattoo_details",
    "date": "source_date",
    "shouldbecovered": "should_be_covered",
    "connotation": "connotation",
    "where": "location",
}

APPROVAL_HEADER_ALIASES = {
    "id": "employee_id",
    "name": "source_name",
    "responsable": "responsible",
    "responsible": "responsible",
    "situation": "situation",
    "testtimeframeneeded": "test_time_frame_needed",
    "medicalcondition": "medical_condition",
    "paperworksubmmited": "paperwork_submitted",
    "paperworksubmitted": "paperwork_submitted",
    "testinitialdate": "test_initial_date",
    "testfinaldate": "test_final_date",
    "status": "status",
    "coments": "comments",
    "comments": "comments",
}


class ImportServiceError(Exception):
    pass


def normalize_header(value):
    value = str(value or "").strip().lower()
    return re.sub(r"[^a-z0-9]", "", value)


def clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_yes_no(value):
    normalized = clean_text(value).lower()
    if not normalized:
        return None
    if normalized in {"yes", "y", "si", "sí", "true", "1"}:
        return True
    if normalized in {"no", "n", "false", "0"}:
        return False
    return None


def normalize_answer(value):
    normalized = clean_text(value).lower().replace(".", "")
    if normalized in {"yes", "y", "si", "sí", "true", "1"}:
        return AppearanceApprovalRecord.Answer.YES
    if normalized in {"no", "n", "false", "0"}:
        return AppearanceApprovalRecord.Answer.NO
    if normalized in {"na", "n/a", "not applicable"}:
        return AppearanceApprovalRecord.Answer.NA
    return AppearanceApprovalRecord.Answer.UNKNOWN


def normalize_approval_status(value):
    normalized = re.sub(r"\s+", " ", clean_text(value).lower())
    if normalized == "approved":
        return AppearanceApprovalRecord.ApprovalStatus.APPROVED
    if normalized == "rejected":
        return AppearanceApprovalRecord.ApprovalStatus.REJECTED
    if normalized in {"in progress", "inprogress"}:
        return AppearanceApprovalRecord.ApprovalStatus.IN_PROGRESS
    return AppearanceApprovalRecord.ApprovalStatus.UNKNOWN


def parse_optional_date(value, workbook_epoch):
    if value in {None, ""}:
        return None, ""

    if isinstance(value, datetime):
        parsed = value.date()
        return parsed, parsed.isoformat()
    if isinstance(value, date):
        return value, value.isoformat()
    if isinstance(value, (int, float)):
        try:
            converted = from_excel(value, workbook_epoch)
            parsed = converted.date() if isinstance(converted, datetime) else converted
            return parsed, parsed.isoformat()
        except (ValueError, TypeError, OverflowError):
            return None, clean_text(value)

    raw = clean_text(value)
    if raw.lower().replace(".", "") in {"na", "n/a", "not applicable"}:
        return None, raw

    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date(), raw
        except ValueError:
            continue
    return None, raw


def _find_header_sheet(workbook, aliases, required_fields):
    candidates = []
    for sheet in workbook.worksheets:
        max_search_row = min(sheet.max_row or 1, 15)
        for row_number, row in enumerate(
            sheet.iter_rows(min_row=1, max_row=max_search_row, values_only=True),
            start=1,
        ):
            normalized = [normalize_header(value) for value in row]
            header_map = {}
            for index, header in enumerate(normalized):
                mapped = aliases.get(header)
                if mapped:
                    header_map[mapped] = index

            if required_fields.issubset(header_map):
                candidates.append((sheet.max_row or 0, sheet, header_map, row_number))
                break

    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])


def find_tattoo_sheet(workbook):
    return _find_header_sheet(
        workbook,
        TATTOO_HEADER_ALIASES,
        {"employee_id", "tattoo_details", "should_be_covered"},
    )


def find_approval_sheet(workbook):
    return _find_header_sheet(
        workbook,
        APPROVAL_HEADER_ALIASES,
        {"employee_id", "situation", "status", "comments"},
    )


def detect_source_type(workbook):
    tattoo = find_tattoo_sheet(workbook)
    approval = find_approval_sheet(workbook)

    if tattoo and not approval:
        return ImportBatch.SourceType.TATTOOS
    if approval and not tattoo:
        return ImportBatch.SourceType.APPEARANCE_APPROVALS
    if tattoo and approval:
        raise ImportServiceError("Workbook matches more than one supported AP source format.")
    raise ImportServiceError(
        "Workbook format was not recognized. Expected the GP tattoo tracker or Appearance Approvals Joined Tracker."
    )


def _known_hibob_ids(employee_ids):
    if not employee_ids:
        return set()
    return set(
        HiBobEmployee.objects.using("hibob")
        .filter(employee_id__in=employee_ids)
        .values_list("employee_id", flat=True)
        .distinct()
    )


def _issue(batch, row_number, employee_id, message):
    ImportIssue.objects.create(
        batch=batch,
        row_number=row_number,
        employee_id=employee_id,
        message=message,
    )


def _finish_batch(batch, imported, rejected):
    batch.rows_imported = imported
    batch.rows_rejected = rejected
    batch.status = ImportBatch.Status.PARTIAL if rejected or batch.issues.exists() else ImportBatch.Status.SUCCESS
    batch.finished_at = timezone.now()
    batch.save(
        update_fields=[
            "rows_imported",
            "rows_rejected",
            "status",
            "finished_at",
        ]
    )
    return batch


def _read_tattoo_rows(sheet, header_map, header_row, workbook_epoch):
    records = []
    for row_number, values in enumerate(
        sheet.iter_rows(min_row=header_row + 1, values_only=True),
        start=header_row + 1,
    ):
        def get(field):
            index = header_map.get(field)
            return values[index] if index is not None and index < len(values) else None

        employee_id = normalize_employee_id(get("employee_id"))
        relevant_values = [get(field) for field in (
            "employee_id",
            "source_name",
            "tattoo_details",
            "source_date",
            "should_be_covered",
            "connotation",
            "location",
        )]
        if not employee_id and all(value in {None, ""} for value in relevant_values):
            continue

        source_date, _ = parse_optional_date(get("source_date"), workbook_epoch)
        records.append({
            "row_number": row_number,
            "employee_id": employee_id,
            "source_name": clean_text(get("source_name")),
            "tattoo_details": clean_text(get("tattoo_details")),
            "should_be_covered": normalize_yes_no(get("should_be_covered")),
            "connotation": clean_text(get("connotation")),
            "location": clean_text(get("location")),
            "source_date": source_date,
            "raw_cover_value": clean_text(get("should_be_covered")),
        })
    return records


def _import_tattoos(workbook, batch, source_file):
    candidate = find_tattoo_sheet(workbook)
    if candidate is None:
        raise ImportServiceError("Tattoo tracker sheet was not found.")

    _, sheet, header_map, header_row = candidate
    rows = _read_tattoo_rows(sheet, header_map, header_row, workbook.epoch)
    batch.rows_received = len(rows)
    batch.save(update_fields=["rows_received"])

    known_ids = _known_hibob_ids([row["employee_id"] for row in rows if row["employee_id"]])
    valid_rows = []
    rejected_rows = 0

    for row in rows:
        if not row["employee_id"]:
            rejected_rows += 1
            _issue(batch, row["row_number"], "", "Missing Employee ID.")
            continue
        if row["employee_id"] not in known_ids:
            rejected_rows += 1
            _issue(batch, row["row_number"], row["employee_id"], "Employee ID was not found in HiBob.")
            continue
        if row["raw_cover_value"] and row["should_be_covered"] is None:
            _issue(
                batch,
                row["row_number"],
                row["employee_id"],
                f"Unrecognized SHOULD BE COVERED? value: {row['raw_cover_value']!r}. Imported as not specified.",
            )
        valid_rows.append(row)

    if rows and not valid_rows:
        raise ImportServiceError("No tattoo rows matched HiBob. Import aborted; the previous active snapshot was kept.")

    with transaction.atomic(using="default"):
        TattooRecord.objects.filter(is_active=True).update(is_active=False)
        TattooRecord.objects.bulk_create([
            TattooRecord(
                employee_id=row["employee_id"],
                source_name=row["source_name"],
                tattoo_details=row["tattoo_details"],
                should_be_covered=row["should_be_covered"],
                connotation=row["connotation"],
                location=row["location"],
                source_date=row["source_date"],
                source_sheet=sheet.title,
                source_file=source_file,
                import_batch=batch,
            )
            for row in valid_rows
        ])

    return _finish_batch(batch, len(valid_rows), rejected_rows)


def _read_approval_rows(sheet, header_map, header_row, workbook_epoch):
    records = []
    for row_number, values in enumerate(
        sheet.iter_rows(min_row=header_row + 1, values_only=True),
        start=header_row + 1,
    ):
        def get(field):
            index = header_map.get(field)
            return values[index] if index is not None and index < len(values) else None

        employee_id = normalize_employee_id(get("employee_id"))
        relevant_values = [get(field) for field in set(APPROVAL_HEADER_ALIASES.values())]
        if not employee_id and all(value in {None, ""} for value in relevant_values):
            continue

        initial_date, initial_raw = parse_optional_date(get("test_initial_date"), workbook_epoch)
        final_date, final_raw = parse_optional_date(get("test_final_date"), workbook_epoch)

        records.append({
            "row_number": row_number,
            "employee_id": employee_id,
            "source_name": clean_text(get("source_name")),
            "responsible": clean_text(get("responsible")),
            "situation": clean_text(get("situation")),
            "test_time_frame_needed": normalize_answer(get("test_time_frame_needed")),
            "medical_condition": normalize_answer(get("medical_condition")),
            "paperwork_submitted": normalize_answer(get("paperwork_submitted")),
            "test_initial_date": initial_date,
            "test_initial_date_raw": initial_raw,
            "test_final_date": final_date,
            "test_final_date_raw": final_raw,
            "status": normalize_approval_status(get("status")),
            "status_raw": clean_text(get("status")),
            "comments": clean_text(get("comments")),
        })
    return records


def _import_approvals(workbook, batch, source_file):
    candidate = find_approval_sheet(workbook)
    if candidate is None:
        raise ImportServiceError("Appearance approvals tracker sheet was not found.")

    _, sheet, header_map, header_row = candidate
    rows = _read_approval_rows(sheet, header_map, header_row, workbook.epoch)
    batch.rows_received = len(rows)
    batch.save(update_fields=["rows_received"])

    known_ids = _known_hibob_ids([row["employee_id"] for row in rows if row["employee_id"]])
    valid_rows = []
    rejected_rows = 0

    for row in rows:
        if not row["employee_id"]:
            rejected_rows += 1
            _issue(batch, row["row_number"], "", "Missing Employee ID.")
            continue
        if row["employee_id"] not in known_ids:
            rejected_rows += 1
            _issue(batch, row["row_number"], row["employee_id"], "Employee ID was not found in HiBob.")
            continue
        if row["status"] == AppearanceApprovalRecord.ApprovalStatus.UNKNOWN and row["status_raw"]:
            _issue(
                batch,
                row["row_number"],
                row["employee_id"],
                f"Unrecognized Status value: {row['status_raw']!r}. Imported as not specified.",
            )
        if row["test_initial_date_raw"] and row["test_initial_date"] is None and row["test_initial_date_raw"].lower().replace(".", "") not in {"na", "n/a", "not applicable"}:
            _issue(
                batch,
                row["row_number"],
                row["employee_id"],
                f"Test initial date could not be parsed: {row['test_initial_date_raw']!r}. Raw value was preserved.",
            )
        if row["test_final_date_raw"] and row["test_final_date"] is None and row["test_final_date_raw"].lower().replace(".", "") not in {"na", "n/a", "not applicable"}:
            _issue(
                batch,
                row["row_number"],
                row["employee_id"],
                f"Test final date could not be parsed: {row['test_final_date_raw']!r}. Raw value was preserved.",
            )
        valid_rows.append(row)

    if rows and not valid_rows:
        raise ImportServiceError("No appearance approval rows matched HiBob. Import aborted; the previous active snapshot was kept.")

    with transaction.atomic(using="default"):
        AppearanceApprovalRecord.objects.filter(is_active=True).update(is_active=False)
        AppearanceApprovalRecord.objects.bulk_create([
            AppearanceApprovalRecord(
                employee_id=row["employee_id"],
                source_name=row["source_name"],
                responsible=row["responsible"],
                situation=row["situation"],
                test_time_frame_needed=row["test_time_frame_needed"],
                medical_condition=row["medical_condition"],
                paperwork_submitted=row["paperwork_submitted"],
                test_initial_date=row["test_initial_date"],
                test_initial_date_raw=row["test_initial_date_raw"],
                test_final_date=row["test_final_date"],
                test_final_date_raw=row["test_final_date_raw"],
                status=row["status"],
                comments=row["comments"],
                source_sheet=sheet.title,
                source_file=source_file,
                import_batch=batch,
            )
            for row in valid_rows
        ])

    return _finish_batch(batch, len(valid_rows), rejected_rows)


def import_workbook(path, source_type="AUTO", force=False, source_file_name=None):
    path = Path(path)
    if not path.exists():
        raise ImportServiceError(f"File not found: {path}")

    workbook = load_workbook(path, data_only=True, read_only=True)
    requested = (source_type or "AUTO").upper()
    if requested == DataUpload.SourceType.AUTO:
        detected = detect_source_type(workbook)
    elif requested in {
        ImportBatch.SourceType.TATTOOS,
        ImportBatch.SourceType.APPEARANCE_APPROVALS,
    }:
        detected = requested
    else:
        raise ImportServiceError(f"Unsupported source type: {source_type}")

    digest = file_sha256(path)
    file_name = source_file_name or path.name

    if not force and ImportBatch.objects.filter(
        file_hash=digest,
        source_type=detected,
        status__in=[ImportBatch.Status.SUCCESS, ImportBatch.Status.PARTIAL],
    ).exists():
        return ImportBatch.objects.create(
            file_name=file_name,
            file_hash=digest,
            source_type=detected,
            status=ImportBatch.Status.SKIPPED,
            finished_at=timezone.now(),
        )

    batch = ImportBatch.objects.create(
        file_name=file_name,
        file_hash=digest,
        source_type=detected,
    )

    try:
        if detected == ImportBatch.SourceType.TATTOOS:
            return _import_tattoos(workbook, batch, file_name)
        return _import_approvals(workbook, batch, file_name)
    except Exception as exc:
        batch.status = ImportBatch.Status.FAILED
        batch.finished_at = timezone.now()
        batch.save(update_fields=["status", "finished_at"])
        _issue(batch, None, "", str(exc))
        if isinstance(exc, ImportServiceError):
            raise
        raise ImportServiceError(str(exc)) from exc
    finally:
        workbook.close()


def process_data_upload(upload, force=False):
    upload.status = ImportBatch.Status.PROCESSING
    upload.error_message = ""
    upload.save(update_fields=["status", "error_message"])

    try:
        batch = import_workbook(
            upload.file.path,
            source_type=upload.source_type,
            force=force,
            source_file_name=Path(upload.file.name).name,
        )
        upload.import_batch = batch
        upload.detected_source_type = batch.source_type
        upload.status = batch.status
        upload.processed_at = timezone.now()
        upload.error_message = ""
        upload.save(
            update_fields=[
                "import_batch",
                "detected_source_type",
                "status",
                "processed_at",
                "error_message",
            ]
        )
        return batch
    except Exception as exc:
        upload.status = ImportBatch.Status.FAILED
        upload.processed_at = timezone.now()
        upload.error_message = str(exc)
        upload.save(update_fields=["status", "processed_at", "error_message"])
        raise
