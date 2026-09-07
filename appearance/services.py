from dataclasses import dataclass
from datetime import time

from .models import HiBobEmployee, TattooRecord


@dataclass(frozen=True)
class EmployeeProfile:
    employee_id: str
    full_name: str
    role: str
    tattoo_records: list

    @property
    def has_tattoo_record(self):
        return bool(self.tattoo_records)

    @property
    def cover_required(self):
        return any(record.should_be_covered is True for record in self.tattoo_records)


def normalize_employee_id(value):
    if value is None:
        return ""
    value = str(value).strip()
    if value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]
    return value


def get_hibob_employee(employee_id):
    employee_id = normalize_employee_id(employee_id)
    if not employee_id:
        return None

    employees = HiBobEmployee.objects.filter(employee_id=employee_id)
    active = employees.filter(lifecycle_status__iexact="active").first()
    return active or employees.first()


def get_employee_profile(employee_id):
    employee = get_hibob_employee(employee_id)
    if employee is None:
        return None

    name = (employee.full_name or employee.display_name or "Employee").strip()
    role = (employee.role or employee.raw_role or "Role not available").strip()
    tattoos = list(TattooRecord.objects.filter(employee_id=employee.employee_id, is_active=True))

    return EmployeeProfile(
        employee_id=employee.employee_id,
        full_name=name,
        role=role,
        tattoo_records=tattoos,
    )


def resolve_operational_shift(local_dt):
    """Assign a stable operational shift without blocking off-schedule testing.

    Morning: 04:00-11:59, Afternoon: 12:00-19:59, Night: 20:00-03:59.
    Official process windows are displayed in the UI separately.
    """
    current = local_dt.time()
    if time(4, 0) <= current < time(12, 0):
        return "MORNING"
    if time(12, 0) <= current < time(20, 0):
        return "AFTERNOON"
    return "NIGHT"


def tattoo_payload(profile):
    records = profile.tattoo_records
    return {
        "has_record": bool(records),
        "cover_required": profile.cover_required,
        "records": [
            {
                "details": item.tattoo_details,
                "location": item.location,
                "connotation": item.connotation,
                "should_be_covered": item.should_be_covered,
            }
            for item in records
        ],
    }
