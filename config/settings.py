import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool_env(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _int_csv_env(name, default):
    values = []
    for item in _csv_env(name, default):
        try:
            values.append(max(1, int(item)))
        except ValueError as exc:
            raise ImproperlyConfigured(f"{name} must contain comma-separated integers.") from exc
    return tuple(values)


DEBUG = _bool_env("DJANGO_DEBUG", False)
ENVIRONMENT = os.getenv(
    "DJANGO_ENV",
    "development" if DEBUG else "production",
).strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

_secret_key = os.getenv("DJANGO_SECRET_KEY", "").strip()
if IS_PRODUCTION and (not _secret_key or _secret_key in {"change-me", "unsafe-development-key"}):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set to a strong unique value in production.")
SECRET_KEY = _secret_key or "development-only-not-for-production"

ALLOWED_HOSTS = _csv_env(
    "DJANGO_ALLOWED_HOSTS",
    "127.0.0.1,localhost" if not IS_PRODUCTION else "",
)
if IS_PRODUCTION and (not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must explicitly list production hosts.")

CSRF_TRUSTED_ORIGINS = _csv_env("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "appearance",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "appearance.middleware.SensitiveResponseHeadersMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEST_WITH_SQLITE = _bool_env("DJANGO_TEST_SQLITE", False)
if TEST_WITH_SQLITE:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test.sqlite3",
        },
        "hibob": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "hibob-test.sqlite3",
        },
    }
else:
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_CONNECT_TIMEOUT = max(1, int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "5")))

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "check_appearance_db"),
            "USER": DB_USER,
            "PASSWORD": DB_PASSWORD,
            "HOST": DB_HOST,
            "PORT": DB_PORT,
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {"connect_timeout": DB_CONNECT_TIMEOUT},
        },
        "hibob": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("HIBOB_DB_NAME", "arrise_vm_db"),
            "USER": os.getenv("HIBOB_DB_USER", DB_USER),
            "PASSWORD": os.getenv("HIBOB_DB_PASSWORD", DB_PASSWORD),
            "HOST": os.getenv("HIBOB_DB_HOST", DB_HOST),
            "PORT": os.getenv("HIBOB_DB_PORT", DB_PORT),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "connect_timeout": DB_CONNECT_TIMEOUT,
                "options": "-c default_transaction_read_only=on",
            },
        },
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "data" / "uploads"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "appearance:process_selection"
LOGOUT_REDIRECT_URL = "login"

DATA_INBOX = BASE_DIR / "data" / "inbox"
DATA_PROCESSED = BASE_DIR / "data" / "processed"
DATA_REJECTED = BASE_DIR / "data" / "rejected"

# Browser/session hardening.
SESSION_COOKIE_SECURE = IS_PRODUCTION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = max(300, int(os.getenv("DJANGO_SESSION_COOKIE_AGE_SECONDS", "28800")))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

SECURE_SSL_REDIRECT = _bool_env("DJANGO_SECURE_SSL_REDIRECT", IS_PRODUCTION)
SECURE_HSTS_SECONDS = max(0, int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "0")))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _bool_env("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = _bool_env("DJANGO_SECURE_HSTS_PRELOAD", False)
if _bool_env("DJANGO_TRUST_X_FORWARDED_PROTO", IS_PRODUCTION):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Upload controls. Nginx should enforce the same or a smaller body limit.
APPEARANCE_MAX_UPLOAD_BYTES = max(
    1024 * 1024,
    int(os.getenv("APPEARANCE_MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
)
APPEARANCE_MAX_UPLOAD_ROWS = max(1000, int(os.getenv("APPEARANCE_MAX_UPLOAD_ROWS", "200000")))
UPLOAD_RETENTION_DAYS = max(1, int(os.getenv("UPLOAD_RETENTION_DAYS", "7")))
FILE_UPLOAD_MAX_MEMORY_SIZE = min(APPEARANCE_MAX_UPLOAD_BYTES, 5 * 1024 * 1024)
DATA_UPLOAD_MAX_MEMORY_SIZE = APPEARANCE_MAX_UPLOAD_BYTES + (1024 * 1024)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000

# Appearance Check -> downstream Power Automate delivery.
POWER_AUTOMATE_ENABLED = _bool_env("POWER_AUTOMATE_ENABLED", False)
POWER_AUTOMATE_FLOW_URL = os.getenv("POWER_AUTOMATE_FLOW_URL", "").strip()
POWER_AUTOMATE_API_KEY = os.getenv("POWER_AUTOMATE_API_KEY", "").strip()
POWER_AUTOMATE_TIMEOUT_SECONDS = max(1, int(os.getenv("POWER_AUTOMATE_TIMEOUT_SECONDS", "5")))
POWER_AUTOMATE_MAX_ATTEMPTS = max(1, int(os.getenv("POWER_AUTOMATE_MAX_ATTEMPTS", "5")))
POWER_AUTOMATE_RETRY_DELAYS_SECONDS = _int_csv_env(
    "POWER_AUTOMATE_RETRY_DELAYS_SECONDS",
    "60,300,900,1800",
)

# Power Automate lookup used while scanning an employee.
POWER_AUTOMATE_LOOKUP_ENABLED = _bool_env("POWER_AUTOMATE_LOOKUP_ENABLED", False)
POWER_AUTOMATE_LOOKUP_FLOW_URL = os.getenv("POWER_AUTOMATE_LOOKUP_FLOW_URL", "").strip()
POWER_AUTOMATE_LOOKUP_API_KEY = os.getenv("POWER_AUTOMATE_LOOKUP_API_KEY", "").strip()
POWER_AUTOMATE_LOOKUP_TIMEOUT_SECONDS = max(
    1,
    int(os.getenv("POWER_AUTOMATE_LOOKUP_TIMEOUT_SECONDS", "15")),
)
POWER_AUTOMATE_LOOKUP_MAX_RESPONSE_BYTES = max(
    4096,
    int(os.getenv("POWER_AUTOMATE_LOOKUP_MAX_RESPONSE_BYTES", str(2 * 1024 * 1024))),
)

# Card Resolver API used server-side for physical badge scans.
CARD_RESOLVER_ENABLED = _bool_env("CARD_RESOLVER_ENABLED", False)
CARD_RESOLVER_URL = os.getenv("CARD_RESOLVER_URL", "").strip()
CARD_RESOLVER_SERVICE_TOKEN = os.getenv("CARD_RESOLVER_SERVICE_TOKEN", "").strip()
CARD_RESOLVER_TIMEOUT_SECONDS = max(1, int(os.getenv("CARD_RESOLVER_TIMEOUT_SECONDS", "5")))
CARD_RESOLVER_MAX_RESPONSE_BYTES = max(
    4096,
    int(os.getenv("CARD_RESOLVER_MAX_RESPONSE_BYTES", str(256 * 1024))),
)

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "appearance": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
