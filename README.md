# ARRISE Check Appearance

Django/PostgreSQL application for **Appearance Preparation** and **Appearance Check**.

## Architecture

- **HiBob remains the employee source of truth.** The application reads `hibob_etl.employees` and never modifies it.
- Employee lookup uses `hr_work_employeeidincompany` and displays `raw_root_fullname` plus `hr_work_title` (with `raw_work_title` as fallback).
- Tattoo data is imported manually from standardized Excel files into Appearance-owned PostgreSQL tables.
- Preparation scans and Appearance Check evaluations are stored as immutable operational records.
- Every saved Appearance Check can publish an auditable JSON event to Power Automate for downstream Excel/SharePoint updates.
- Users and permissions are managed with Django Admin.
- The operational UI is tablet-first, in English, and uses the ARRISE brand palette.

## Employee ID input

The same field supports both workflows:

- A USB/HID scanner may type the Employee ID and send Enter.
- If no scanner is available, the stylist can type the Employee ID manually and press Enter.

No Wiegand/card decoding is included in this MVP because the working assumption is that the reader returns the HiBob Employee ID directly.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The PostgreSQL user configured in `.env` needs:

1. normal read/write permissions for the Django Appearance tables;
2. **SELECT-only** access to `hibob_etl.employees`.

Create Appearance users from `/admin/`. For the MVP, use the corporate email as the Django username.

## Tattoo import

Place the workbook in:

```text
data/inbox/
```

Then run:

```bash
python manage.py import_tattoos
```

The importer:

1. finds the largest worksheet containing `ID`, `TATTOOS`, and `SHOULD BE COVERED?`;
2. normalizes Employee IDs, Yes/No values, dates and text;
3. validates Employee IDs against HiBob;
4. deactivates the previous active tattoo records only for employees included in the new valid file;
5. inserts the new records while preserving import history;
6. records rejected rows in Django Admin;
7. moves successful/partial imports to `data/processed/` and failed files to `data/rejected/`.

A previously processed identical file is skipped by SHA-256 unless `--force` is provided.

## Power Automate

The Appearance Check workflow can POST a JSON event every time an operator saves `Ready`, `Not Ready`, or `Declined`.

Configuration is environment-based:

```env
POWER_AUTOMATE_ENABLED=True
POWER_AUTOMATE_FLOW_URL="https://<generated-trigger-url>"
POWER_AUTOMATE_TIMEOUT_SECONDS=5
```

The trigger URL is a secret and must never be committed to GitHub.

Full request schema, Excel column mapping, retry behavior and Power Automate setup are documented in:

```text
docs/power_automate_appearance_check.md
```

## Production direction

The VM deployment target is:

```text
HTTPS -> Nginx -> Django/Gunicorn -> PostgreSQL
```

Real-time multi-device updates will be added after the database, importer and operational flows are validated.
