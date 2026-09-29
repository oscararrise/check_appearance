# Production Runbook — ARRISE Check Appearance

This runbook is the go-live gate for the Django Check Appearance service.

## 1. Release gates

Do not deploy unless all of these are true:

- Repository is private.
- `main` is protected against direct pushes and requires review/status checks.
- Production secrets are stored only in the VM secret store/`.env`, never in Git.
- `DJANGO_DEBUG=False`.
- `DJANGO_ENV=production`.
- `DJANGO_ALLOWED_HOSTS` contains only the real production hostnames.
- HTTPS terminates at Nginx and Nginx overwrites `X-Forwarded-Proto`.
- PostgreSQL and Gunicorn are not exposed publicly.
- The HiBob database account is SELECT-only. The application additionally opens the HiBob connection with `default_transaction_read_only=on`.
- Nginx does not serve `/media/`.
- A database backup has been taken immediately before the migration.
- `python manage.py check --deploy` passes after production variables are loaded.
- All automated tests pass.

Repository visibility and branch-protection are repository-level controls, not branch code changes. Apply them in GitHub before go-live.

## 2. Production environment

At minimum:

```env
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<strong-random-secret>
DJANGO_ALLOWED_HOSTS=<production-host>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<production-host>
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_TRUST_X_FORWARDED_PROTO=True
DJANGO_SECURE_HSTS_SECONDS=0

POWER_AUTOMATE_ENABLED=True
POWER_AUTOMATE_FLOW_URL=<signed-url>
POWER_AUTOMATE_MAX_ATTEMPTS=5
POWER_AUTOMATE_RETRY_DELAYS_SECONDS=60,300,900,1800

POWER_AUTOMATE_LOOKUP_ENABLED=True
POWER_AUTOMATE_LOOKUP_FLOW_URL=<signed-url>

CARD_RESOLVER_ENABLED=True
CARD_RESOLVER_URL=https://<internal-host>/card-resolver/api/v1/cards/resolve
CARD_RESOLVER_SERVICE_TOKEN=<service-token>
```

Start HSTS at `0` during final hostname validation. Once the final HTTPS hostname is confirmed and HTTP is permanently redirected, increase it deliberately (for example 86400, then 31536000). Do not preload a temporary/nip.io hostname.

## 3. Error contract

The UI distinguishes business outcomes from dependency failures.

### Card Resolver

- `CARD_NOT_FOUND`: card is absent from the active dataset.
- `CARD_AMBIGUOUS`: more than one mapping.
- `CARD_UNDECODABLE` / `CARD_INVALID`: reader input is invalid.
- `CARD_RESOLVER_UNAVAILABLE`: timeout/network/5xx; retryable.
- `CARD_RESOLVER_AUTH_ERROR`: service authentication failure.
- `CARD_RESOLVER_INVALID_RESPONSE`: dependency returned malformed/untrusted data.
- `CARD_HIBOB_MAPPING_MISMATCH`: card resolves, but the mapped employee is not in current HiBob.

### Workforce / Power Automate lookup

- `FOUND`: assignment verified.
- `NOT_FOUND`: Power Automate returned a valid dataset but the employee is absent.
- `UNAVAILABLE`: timeout/network/5xx/configuration.
- `AUTH_ERROR`: lookup authentication problem.
- `INVALID_RESPONSE`: HTTP succeeded but the response contract is invalid.

Workforce lookup failure does not delete or falsify the HiBob employee profile. Operators receive a warning and can retry Workforce independently.

### Appearance Check delivery

The operational PostgreSQL record is the source of truth. Downstream Power Automate delivery is auditable and retryable. A downstream failure must never make the saved Appearance Check disappear.

## 4. Idempotency

Preparation and Check records carry a unique UUID `request_id`.

The browser reuses the same UUID after retryable network/server errors. Replaying the same request returns the existing record rather than creating a duplicate. Reusing a UUID for different data returns `IDEMPOTENCY_CONFLICT`.

Migration `0008_operational_request_ids` is intentionally multi-step:

1. add nullable UUID fields;
2. backfill each existing row with its own UUID;
3. enforce non-null + unique.

This is safe for existing production rows.

## 5. Pre-deployment backup

From the VM, before `migrate`:

```bash
cd /home/ubuntu/apps/check_appearance
set -a
source .env
set +a

mkdir -p ~/backups/check_appearance
pg_dump   -h "$DB_HOST"   -p "$DB_PORT"   -U "$DB_USER"   -Fc "$DB_NAME"   > ~/backups/check_appearance/check_appearance_$(date +%Y%m%d_%H%M%S).dump
```

Verify the file is non-empty before proceeding.

## 6. Deployment procedure

```bash
cd /home/ubuntu/apps/check_appearance

git fetch origin
git checkout feature/production-hardening
git pull --ff-only origin feature/production-hardening

source .venv/bin/activate
pip install -r requirements.txt

python manage.py check
python manage.py check --deploy
python manage.py migrate --plan
python manage.py migrate
python manage.py bootstrap_appearance_roles
python manage.py collectstatic --noinput

sudo systemctl restart check-appearance.service
sudo systemctl status check-appearance.service --no-pager
```

Then verify:

```bash
curl -fsS https://<production-host>/health/live/
curl -fsS https://<production-host>/health/ready/
```

Both must return HTTP 200 before enabling operators.

## 7. Retry worker

Install the provided one-shot service/timer:

```bash
sudo cp deploy/check-appearance-retry.service /etc/systemd/system/
sudo cp deploy/check-appearance-retry.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now check-appearance-retry.timer
systemctl list-timers | grep check-appearance
```

The command will not retry deliveries once `POWER_AUTOMATE_MAX_ATTEMPTS` has been reached.

## 8. Upload retention

Source Excel/CSV files may contain document numbers, contact information, access-card information, medical-related data and other PII.

Nginx must return 404 for `/media/`.

Install daily cleanup:

```bash
sudo cp deploy/check-appearance-cleanup.service /etc/systemd/system/
sudo cp deploy/check-appearance-cleanup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now check-appearance-cleanup.timer
```

Preview cleanup without deleting anything:

```bash
python manage.py purge_processed_uploads --dry-run
```

## 9. Nginx

Use `deploy/nginx-check-appearance.conf.example` as a reference, not as a blind copy.

Required properties:

- only 443 reaches the application;
- redirect HTTP to HTTPS;
- set Host and overwrite `X-Forwarded-Proto`;
- rate-limit login and employee lookup;
- cap body size;
- never expose `/media/`;
- Gunicorn remains bound to localhost/private socket only.

Test before reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 10. Roles

- Operator: authenticated application user. Can lookup employees and record operational actions.
- Supervisor: member of Django group `Appearance Supervisors`. Adds report-export access.
- Administrator: Django staff/superuser. Can manage schedules/admin/imports according to Django model permissions.

Create the supervisor group with:

```bash
python manage.py bootstrap_appearance_roles
```

Then assign only users who require export access.

## 11. Mandatory failure-mode test matrix

Before go-live test all of these deliberately:

| Scenario | Expected behavior |
| --- | --- |
| Unknown card | Clear `CARD_NOT_FOUND`; no employee shown |
| Ambiguous card | Operation blocked; admin review requested |
| Card Resolver timeout | Warning; user can switch to Employee ID |
| Card Resolver auth failure | Safe service-unavailable message; technical log event |
| Card maps to absent HiBob ID | Explicit mapping mismatch |
| Unknown manual Employee ID | HiBob not-found |
| Employee absent from Workforce list | HiBob profile loads; visible Workforce not-found warning |
| Workforce timeout/5xx | HiBob profile loads; retry button |
| Workforce invalid JSON | Not treated as not-found |
| Save succeeds, downstream PA fails | Record remains saved; sync-pending warning |
| Replayed save request | Existing record returned; no duplicate |
| Same request UUID with different payload | HTTP 409 idempotency conflict |
| Session expired/403/502 HTML | Friendly frontend error, no raw JSON/HTML parser error |
| Oversized upload | Rejected before import |
| Workbook decompression bomb | Rejected before openpyxl processing |
| Non-supervisor export | HTTP 403 |
| App DB unavailable | `/health/ready/` returns 503 |
| HiBob DB unavailable | `/health/ready/` returns 503 |

## 12. Rollback

Code rollback:

```bash
cd /home/ubuntu/apps/check_appearance
git log --oneline -10
git checkout <previous-known-good-sha>
source .venv/bin/activate
pip install -r requirements.txt
python manage.py collectstatic --noinput
sudo systemctl restart check-appearance.service
```

The new migration only adds/backfills idempotency UUID columns. An application-code rollback normally does not require immediately reversing this migration; leaving additive columns in place is safer than performing destructive schema rollback during an incident.

If database restoration is required, stop the application first and restore the pre-deploy dump under the normal PostgreSQL recovery procedure.

## 13. Observability

Application logs use stable event names such as:

- `CARD_RESOLVER_AUTH_ERROR`
- `CARD_RESOLVER_NETWORK_ERROR`
- `CARD_HIBOB_MAPPING_MISMATCH`
- `WORKFORCE_EMPLOYEE_NOT_FOUND`
- `WORKFORCE_AUTH_ERROR`
- `WORKFORCE_INVALID_RESPONSE`
- `POWER_AUTOMATE_DELIVERY_FAILED`
- `HEALTH_READY_FAILED`

Do not log full card values, service tokens, signed Power Automate URLs, remote response bodies, or unnecessary medical/security payloads.
