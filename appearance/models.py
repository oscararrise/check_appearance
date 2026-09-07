from django.conf import settings
from django.db import models


class HiBobEmployee(models.Model):
    """Read-only projection of hibob_etl.employees.

    HiBob remains the employee source of truth. This model is unmanaged and
    must never be migrated or written to by the Appearance application.
    """

    hibob_id = models.TextField(primary_key=True, db_column="hibob_root_id")
    employee_id = models.TextField(db_column="hr_work_employeeidincompany")
    full_name = models.TextField(db_column="raw_root_fullname", blank=True, null=True)
    display_name = models.TextField(db_column="raw_root_displayname", blank=True, null=True)
    role = models.TextField(db_column="hr_work_title", blank=True, null=True)
    raw_role = models.TextField(db_column="raw_work_title", blank=True, null=True)
    lifecycle_status = models.TextField(db_column="hr_internal_lifecyclestatus", blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"hibob_etl"."employees"'
        verbose_name = "HiBob employee (read only)"
        verbose_name_plural = "HiBob employees (read only)"

    def __str__(self):
        return f"{self.employee_id} - {self.full_name or self.display_name or 'Employee'}"


class ImportBatch(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "PROCESSING", "Processing"
        SUCCESS = "SUCCESS", "Success"
        PARTIAL = "PARTIAL", "Partial"
        FAILED = "FAILED", "Failed"
        SKIPPED = "SKIPPED", "Skipped"

    file_name = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64, db_index=True)
    source_type = models.CharField(max_length=50, default="TATTOOS")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    rows_received = models.PositiveIntegerField(default=0)
    rows_imported = models.PositiveIntegerField(default=0)
    rows_rejected = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.file_name} - {self.status}"


class ImportIssue(models.Model):
    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="issues")
    row_number = models.PositiveIntegerField(blank=True, null=True)
    employee_id = models.CharField(max_length=50, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["row_number", "id"]

    def __str__(self):
        return f"{self.batch.file_name}: {self.message[:80]}"


class TattooRecord(models.Model):
    employee_id = models.CharField(max_length=50, db_index=True)
    source_name = models.CharField(max_length=255, blank=True)
    tattoo_details = models.TextField(blank=True)
    should_be_covered = models.BooleanField(blank=True, null=True)
    connotation = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True)
    source_date = models.DateField(blank=True, null=True)
    source_sheet = models.CharField(max_length=100, blank=True)
    source_file = models.CharField(max_length=255)
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="tattoos")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_id", "-created_at"]
        indexes = [models.Index(fields=["employee_id", "is_active"])]

    def __str__(self):
        return f"{self.employee_id} - {'Cover required' if self.should_be_covered else 'Tattoo record'}"


class OperationalRecord(models.Model):
    class Shift(models.TextChoices):
        MORNING = "MORNING", "Morning"
        AFTERNOON = "AFTERNOON", "Afternoon"
        NIGHT = "NIGHT", "Night"

    employee_id = models.CharField(max_length=50, db_index=True)
    employee_name = models.CharField(max_length=255)
    role = models.CharField(max_length=255, blank=True)
    shift = models.CharField(max_length=20, choices=Shift.choices, db_index=True)
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        abstract = True


class PreparationScan(OperationalRecord):
    class Meta:
        ordering = ["-recorded_at"]
        verbose_name = "Preparation scan"
        verbose_name_plural = "Preparation scans"

    def __str__(self):
        return f"{self.employee_id} - {self.recorded_at:%Y-%m-%d %H:%M}"


class AppearanceCheck(OperationalRecord):
    class Status(models.TextChoices):
        READY = "READY", "Ready"
        NOT_READY = "NOT_READY", "Not Ready"
        DECLINED = "DECLINED", "Declined"

    status = models.CharField(max_length=20, choices=Status.choices)
    comment = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name = "Appearance check"
        verbose_name_plural = "Appearance checks"

    def __str__(self):
        return f"{self.employee_id} - {self.status} - {self.recorded_at:%Y-%m-%d %H:%M}"
