import re
import uuid


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_SENSITIVE_PREFIXES = ("/api/", "/admin/", "/reports/", "/login/")


class SensitiveResponseHeadersMiddleware:
    """Add safe operational headers without exposing internal implementation details."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "").strip()
        request_id = supplied if _REQUEST_ID_RE.fullmatch(supplied) else str(uuid.uuid4())
        request.request_id = request_id

        response = self.get_response(request)
        response["X-Request-ID"] = request_id
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        user = getattr(request, "user", None)
        authenticated = bool(user and user.is_authenticated)
        if authenticated or request.path.startswith(_SENSITIVE_PREFIXES):
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"

        return response
