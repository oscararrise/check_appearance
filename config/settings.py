import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-development-key")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [u.strip() for u in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if u.strip()]

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

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "check_appearance_db"),
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": DB_HOST,
        "PORT": DB_PORT,
        "CONN_MAX_AGE": 60,
    },
    "hibob": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("HIBOB_DB_NAME", "arrise_vm_db"),
        "USER": os.getenv("HIBOB_DB_USER", DB_USER),
        "PASSWORD": os.getenv("HIBOB_DB_PASSWORD", DB_PASSWORD),
        "HOST": os.getenv("HIBOB_DB_HOST", DB_HOST),
        "PORT": os.getenv("HIBOB_DB_PORT", DB_PORT),
        "CONN_MAX_AGE": 60,
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

STATIC_URL = "static/"
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

# Power Automate webhook for Appearance Check -> Excel/SharePoint flow.
# Keep the generated flow URL only in .env / the VM secret store; never commit it.
POWER_AUTOMATE_ENABLED = os.getenv("POWER_AUTOMATE_ENABLED", "False").lower() in {"1", "true", "yes", "on"}
POWER_AUTOMATE_FLOW_URL = os.getenv("POWER_AUTOMATE_FLOW_URL", "").strip()
POWER_AUTOMATE_API_KEY = os.getenv("POWER_AUTOMATE_API_KEY", "").strip()
POWER_AUTOMATE_TIMEOUT_SECONDS = int(os.getenv("POWER_AUTOMATE_TIMEOUT_SECONDS", "5"))
