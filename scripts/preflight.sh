#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-.venv/bin/python}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python virtualenv not found at $PYTHON" >&2
  exit 1
fi

export DJANGO_ENV=development
export DJANGO_DEBUG=True
export DJANGO_SECRET_KEY="local-preflight-only-secret-key-2026"
export DJANGO_ALLOWED_HOSTS="testserver,localhost,127.0.0.1"
export DJANGO_TEST_SQLITE=True
export POWER_AUTOMATE_ENABLED=False
export POWER_AUTOMATE_LOOKUP_ENABLED=False
export CARD_RESOLVER_ENABLED=False

echo "== Django system check =="
"$PYTHON" manage.py check

echo "== Migration consistency =="
"$PYTHON" manage.py makemigrations --check --dry-run

echo "== Test suite =="
"$PYTHON" manage.py test --verbosity 2

echo "== Preflight passed =="
echo "Run python manage.py check --deploy separately with the real production .env loaded."
