from django.contrib import admin

from .models import AppearanceCheck, ImportBatch, ImportIssue, PreparationScan, TattooRecord


@admin.register(TattooRecord)
class TattooRecordAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "source_name", "should_be_covered", "location", "is_active", "updated_at")
    list_filter = ("should_be_covered", "is_active", "source_file")
    search_fields = ("employee_id", "source_name", "tattoo_details", "location", "connotation")
    readonly_fields = ("created_at", "updated_at")


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
        "file_name", "file_hash", "source_type", "status", "rows_received",
        "rows_imported", "rows_rejected", "started_at", "finished_at",
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


admin.site.site_header = "ARRISE Appearance Administration"
admin.site.site_title = "ARRISE Appearance Admin"
admin.site.index_title = "Appearance management"
