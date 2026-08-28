"""Standard security headers applied to every response."""

from app.config import settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # style-src/font-src allow the Google Fonts families used by the /ui web
    # interface. Self-host both families and drop the two hosts here if the
    # deployment must make no third-party requests.
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    ),
}


def apply_security_headers(headers) -> None:
    for name, value in SECURITY_HEADERS.items():
        headers.setdefault(name, value)
    if settings.enable_hsts:
        headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
