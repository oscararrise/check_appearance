from urllib.parse import urlparse

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


def _https_error(name, url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return Error(
            f"{name} must use a valid HTTPS URL.",
            id="appearance.E001",
        )
    return None


@register(Tags.security)
def production_integration_checks(app_configs, **kwargs):
    issues = []

    if not getattr(settings, "IS_PRODUCTION", False):
        return issues

    integrations = (
        (
            "POWER_AUTOMATE",
            settings.POWER_AUTOMATE_ENABLED,
            settings.POWER_AUTOMATE_FLOW_URL,
            False,
        ),
        (
            "POWER_AUTOMATE_LOOKUP",
            settings.POWER_AUTOMATE_LOOKUP_ENABLED,
            settings.POWER_AUTOMATE_LOOKUP_FLOW_URL,
            False,
        ),
        (
            "CARD_RESOLVER",
            settings.CARD_RESOLVER_ENABLED,
            settings.CARD_RESOLVER_URL,
            True,
        ),
    )

    for name, enabled, url, token_required in integrations:
        if not enabled:
            continue
        if not url:
            issues.append(
                Error(
                    f"{name} is enabled but its URL is not configured.",
                    id="appearance.E002",
                )
            )
            continue
        url_error = _https_error(f"{name} URL", url)
        if url_error:
            issues.append(url_error)
        if token_required and not settings.CARD_RESOLVER_SERVICE_TOKEN:
            issues.append(
                Error(
                    "CARD_RESOLVER is enabled but CARD_RESOLVER_SERVICE_TOKEN is missing.",
                    id="appearance.E003",
                )
            )

    if settings.SECURE_HSTS_SECONDS == 0:
        issues.append(
            Warning(
                "HSTS is disabled. Enable it after the production hostname and HTTPS path are validated.",
                id="appearance.W001",
            )
        )

    return issues
