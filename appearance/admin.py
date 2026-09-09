from django.contrib import admin, messages

from .import_services import process_data_upload
from .models import (
    AppearanceApprovalRecord,
    AppearanceCheck,
    DataUpload,
    ImportBatch,
    ImportIssue,
    PowerAutomateDelivery,
    PreparationScan,
    ProcessSchedule,
    TattooRecord,
)
from .power_automate import publish_appearance_check


@admin.register(DataUpload)
class DataUploadAdmin(admin.ModelAdmin):
    list_display = (
        "file",
        "source_type",
        "detected_source_type",
        "status",
        "uploaded_by",
        "uploaded_at",
        "processed_at",
    )
    list_filter = ("source_type", "detected_source_type", "status", "uploaded_at")
    search_fields = ("file", "error_message")
    readonly_fields = (
        "detected_source_type",
        "status",
        "import_batch",
        "uploaded_by",
        "uploaded_at",
        "processed_at",
        "error_message",
    )

    def save_model(self, request, obj, form, change):
        is_new = not change
        if is_new:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

        if is_new and obj.file:
            try:
                batch = process_data_upload(obj)
                if batch.status == ImportBatch.Status.SKIPPED:
                    self.message_user(
                        request,
                        "This exact workbook was already imported. No database snapshot was changed.",
                        level=messages.WARNING,
                    )
                else:
                    self.message_user(
                        request,
                        f"Workbook processed: {batch.rows_imported} rows imported, "
                        f"{batch.rows_rejected} rows rejected ({batch.get_status_display()}).",
                        level=messages.SUCCESS if batch.status == ImportBatch.Status.SUCCESS else messages.WARNING,
                    )
            except Exception as exc:
                self.message_user(request, f"Import failed: {exc}", level=messages.ERROR)


@admin.register(TattooRecord)
class TattooRecordAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "source_name", "should_be_covered", "location", "is_active", "updated_at")
    list_filter = ("should_be_covered", "is_active", "source_file")
    search_fields = ("employee_id", "source_name", "tattoo_details", "location", "connotation")
    readonly_fields = ("created_at", "updated_at")


@admin.register(AppearanceApprovalRecord)
class AppearanceApprovalRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "source_name",
        "situation",
        "status",
        "medical_condition",
        "is_active",
        "updated_at",
    )
    list_filter = ("status", "medical_condition", "test_time_frame_needed", "is_active", "source_file")
    search_fields = ("employee_id", "source_name", "responsible", "situation", "comments")
    readonly_fields = ("created_at", "updated_at")
    exclude = ("test_final_date", "test_final_date_raw")


@admin.register(ProcessSchedule)
class ProcessScheduleAdmin(admin.ModelAdmin):
    list_display = ("process", "shift", "start_time", "end_time", "updated_by", "updated_at")
    list_filter = ("process", "shift")
    readonly_fields = ("updated_by", "updated_at")

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class ImportIssueInline(admin.TabularInline):
    model = ImportIssue
    extra = 0
    readonly_fields = ("row_number", "employee_id", "message", "created_at")
    can_delete = False


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("file_name", "source_type", "status", "rows_received", "rows_imported", "rows_rejected", "started_at")
    list_filter = ("status", "source_type")
    search_fields = ("file_name", "file_hash")
    readonly_fields = (
        "file_name",
        "file_hash",
        "source_type",
        "status",
        "rows_received",
        "rows_imported",
        "rows_rejected",
        "started_at",
        "finished_at",
    )
    inlines = [ImportIssueInline]


@admin.register(PreparationScan)
class PreparationScanAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "employee_name", "role", "shift", "recorded_at", "recorded_by")
    list_filter = ("shift", "recorded_at")
    search_fields = ("employee_id", "employee_name", "role")
    readonly_fields = ("employee_id", "employee_name", "role", "shift", "recorded_at", "recorded_by")


@admin.register(AppearanceCheck)
class AppearanceCheckAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "employee_name", "status", "shift", "recorded_at", "recorded_by")
    list_filter = ("status", "shift", "recorded_at")
    search_fields = ("employee_id", "employee_name", "role", "comment")
    readonly_fields = ("employee_id", "employee_name", "role", "shift", "status", "comment", "recorded_at", "recorded_by")


@admin.register(PowerAutomateDelivery)
class PowerAutomateDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "appearance_check",
        "employee_id",
        "status",
        "attempts",
        "response_status",
        "last_attempt_at",
        "sent_at",
    )
    list_filter = ("status", "response_status", "created_at")
    search_fields = (
        "appearance_check__employee_id",
        "appearance_check__employee_name",
        "last_error",
    )
    readonly_fields = (
        "appearance_check",
        "status",
        "payload",
        "attempts",
        "response_status",
        "last_error",
        "last_attempt_at",
        "sent_at",
        "created_at",
        "updated_at",
    )
    actions = ("retry_delivery",)

    @admin.display(description="Employee ID")
    def employee_id(self, obj):
        return obj.appearance_check.employee_id

    @admin.action(description="Retry selected Power Automate deliveries")
    def retry_delivery(self, request, queryset):
        sent = 0
        failed = 0
        disabled = 0
        for delivery in queryset.select_related("appearance_check", "appearance_check__recorded_by"):
            result = publish_appearance_check(delivery.appearance_check)
            if result.status == PowerAutomateDelivery.Status.SENT:
                sent += 1
            elif result.status == PowerAutomateDelivery.Status.DISABLED:
                disabled += 1
            else:
                failed += 1
        self.message_user(
            request,
            f"Power Automate retry finished: {sent} sent, {failed} failed, {disabled} disabled.",
            level=messages.SUCCESS if failed == 0 else messages.WARNING,
        )


admin.site.site_header = "ARRISE Appearance Administration"
admin.site.site_title = "ARRISE Appearance Admin"
admin.site.index_title = "Appearance management"
