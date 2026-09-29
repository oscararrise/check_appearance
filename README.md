# ARRISE Check Appearance

Django/PostgreSQL application for **Appearance Preparation** and **Appearance Check**.

## Architecture

The production request path is:

```text
HTTPS -> Nginx -> Django/Gunicorn -> Appearance PostgreSQL
                              \-> HiBob PostgreSQL (read only)
                              \-> Card Resolver API
                              \-> Power Automate / Workforce lookup
```

Key design rules:

- **HiBob remains the employee source of truth.** Appearance reads `hibob_etl.employees` and never writes to it.
- Card scans are resolved server-side by Card Resolver before the returned HiBob Employee ID is verified against HiBob.
- Manual Employee ID lookup searches HiBob directly.
- Studio/workforce assignment is retrieved through a separate Power Automate lookup and is treated as a degradable dependency: a lookup outage never becomes a false "employee not found".
- Tattoo, appearance approval and Security source data are imported into Appearance-owned PostgreSQL tables.
- Preparation scans and Appearance Check evaluations are immutable operational records with idempotency UUIDs to prevent accidental duplicate saves.
- PostgreSQL is the operational source of truth. A saved Appearance Check can publish downstream to Power Automate, but a Power Automate outage does not roll back the operational record.
- Users and permissions are managed with Django authentication/Admin. Report exports are limited to staff or members of the `Appearance Supervisors` group.
- The operational UI is tablet-first and supports both card scanning and manual Employee ID lookup.

## Lookup behavior

### Card mode

```text
reader RAW value
    -> Card Resolver
    -> HiBob Employee ID
    -> HiBob verification
    -> Workforce/studio lookup
    -> Appearance guidance
```

Important failure states are explicit:

- card not found;
- card ambiguous;
- card value cannot be decoded;
- Card Resolver unavailable/authentication failure;
- Card Resolver -> HiBob mapping mismatch;
- HiBob employee not found;
- employee absent from the current Workforce list;
- Workforce unavailable/authentication failure/invalid response.

### Employee ID mode

Manual mode bypasses Card Resolver and verifies the Employee ID directly in HiBob.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py bootstrap_appearance_roles
python manage.py runserver
```

The PostgreSQL users configured in `.env` should have:

1. normal read/write permissions for the Django Appearance database;
2. a separate **SELECT-only** account for the HiBob source database.

The application also opens the HiBob connection using PostgreSQL `default_transaction_read_only=on` as defense in depth.

## Data imports

Supported upload formats are CSV and supported Office Open XML workbooks. Upload processing applies file-size, row-count and workbook-expansion limits before importing.

Source uploads may contain sensitive employee/security information. Production Nginx must **never serve `/media/`**, and retained source files should be removed with:

```bash
python manage.py purge_processed_uploads
```

A systemd cleanup timer example is included under `deploy/`.

Imports preserve batch/audit metadata and rejected-row issues. Identical files can be skipped by SHA-256 unless a forced import is explicitly requested.

## Power Automate delivery

Every saved Appearance Check can publish an auditable JSON event downstream.

```env
POWER_AUTOMATE_ENABLED=True
POWER_AUTOMATE_FLOW_URL="https://<generated-trigger-url>"
POWER_AUTOMATE_TIMEOUT_SECONDS=5
POWER_AUTOMATE_MAX_ATTEMPTS=5
POWER_AUTOMATE_RETRY_DELAYS_SECONDS=60,300,900,1800
```

The signed trigger URL is a secret and must never be committed.

Failed deliveries retain only sanitized error metadata and can be retried from Django Admin or with:

```bash
python manage.py retry_power_automate
```

See `docs/power_automate_appearance_check.md` for the event contract.

## Production safety

Production configuration fails closed when critical Django configuration is missing. Before go-live:

```bash
python manage.py check
python manage.py check --deploy
python manage.py migrate --plan
python manage.py test
```

Health endpoints:

```text
/health/live/
/health/ready/
```

`ready` checks both the Appearance database and HiBob database. External degradable dependencies do not make the whole application unready.

Deployment examples are under `deploy/`:

- hardened Nginx configuration;
- Power Automate retry service/timer;
- source-upload cleanup service/timer.

The full production checklist, failure-mode matrix, backup procedure and rollback procedure are in:

```text
docs/production_runbook.md
```

## Repository governance

This application processes internal employee data. Before production, the repository should be **private**, direct pushes to `main` should be blocked, and merges should require review plus passing automated checks.

Those controls are GitHub repository settings and are intentionally separate from application code.
