"""
HireNest Australia anti-bot helpers.

Two independent layers, both applied server-side:

1. Cloudflare Turnstile verification (:func:`require_turnstile`) — validates the
   ``cf-turnstile-response`` token before any form is processed.
2. Session-based rate limiting (:func:`is_rate_limited`) — throttles repeated
   login, registration, OTP and application submissions.

Rate limits live in the DB-backed session, so they are shared across gunicorn
workers and are not tied to a single process-local cache.
"""
import time

from utils import turnstile


# ------------------------------------------------------------------------------
# Cloudflare Turnstile
# ------------------------------------------------------------------------------
def get_client_ip(request):
    """
    Best-effort client IP for the Turnstile ``remoteip`` hint.

    Uses the left-most X-Forwarded-For address (the client as seen by the proxy)
    and falls back to REMOTE_ADDR. The value is only a hint for Cloudflare; it
    is never trusted for authorization.
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def require_turnstile(request, action):
    """
    Verify the Turnstile token for a POST request.

    Returns ``None`` when verification is not required or the token is valid.
    Returns a short error code (``missing_token``, ``invalid_token``,
    ``expired_token``, ``network_error``, ...) when the submission must be
    rejected.
    """
    if not turnstile.is_enabled():
        return None

    token = (request.POST.get('cf-turnstile-response') or '').strip()
    if not token:
        return 'missing_token'

    ok, error_code = turnstile.verify_token(
        token,
        remote_ip=get_client_ip(request),
        action=action,
    )
    if ok:
        return None
    return error_code


# Human-friendly messages for Turnstile error codes surfaced to templates.
TURNSTILE_ERROR_MESSAGES = {
    'missing_token': 'Security verification is required. Please complete the "I\'m not a robot" check.',
    'invalid_token': 'Security verification failed. Please complete the challenge and try again.',
    'expired_token': 'Security verification has expired. Please complete the challenge again.',
    'network_error': 'Security verification is temporarily unavailable. Please try again in a moment.',
    'missing_secret': 'Security verification is not configured. Please contact support.',
    'invalid_secret': 'Security verification is not configured. Please contact support.',
    'provider_error': 'Security verification is temporarily unavailable. Please try again in a moment.',
}

TURNSTILE_FALLBACK_MESSAGE = (
    'Security verification failed. Please complete the challenge and try again.'
)


def turnstile_error_message(error_code):
    """Return a user-facing message for a Turnstile verification error code."""
    return TURNSTILE_ERROR_MESSAGES.get(
        error_code, TURNSTILE_FALLBACK_MESSAGE
    )


# ------------------------------------------------------------------------------
# Session-based rate limiting
# ------------------------------------------------------------------------------
def is_rate_limited(request, key, max_attempts=5, period=300):
    """
    Return ``(limited, seconds_remaining)`` for a sliding-window rate limit.

    When the limit is exceeded the key is locked out for ``period`` seconds.
    Mirrors the existing session-based throttling used elsewhere in the app so
    behaviour is consistent and the limits persist across requests.
    """
    attempts_key = f'hn_rate_attempts_{key}'
    lockout_key = f'hn_rate_lockout_{key}'

    now = time.time()
    lockout_until = request.session.get(lockout_key, 0)
    if now < lockout_until:
        return True, int(lockout_until - now)

    attempts = [
        t for t in request.session.get(attempts_key, [])
        if now - t < period
    ]

    if len(attempts) >= max_attempts:
        request.session[lockout_key] = now + period
        request.session[attempts_key] = []
        return True, period

    attempts.append(now)
    request.session[attempts_key] = attempts
    return False, 0


def reset_rate_limit(request, key):
    """Clear any tracked attempts/lockout for a key (e.g. after success)."""
    request.session.pop(f'hn_rate_attempts_{key}', None)
    request.session.pop(f'hn_rate_lockout_{key}', None)


# Sensible default limits used across the portal.
EMPLOYER_LOGIN_MAX_ATTEMPTS = 5
EMPLOYER_LOGIN_PERIOD = 300          # 5 minutes

EMPLOYER_REGISTER_MAX_ATTEMPTS = 5
EMPLOYER_REGISTER_PERIOD = 3600      # 1 hour

OTP_VERIFY_MAX_ATTEMPTS = 10
OTP_VERIFY_PERIOD = 3600             # 1 hour

OTP_RESEND_MAX_ATTEMPTS = 5
OTP_RESEND_PERIOD = 3600             # 1 hour

JOB_APPLY_MAX_ATTEMPTS = 10
JOB_APPLY_PERIOD = 3600              # 1 hour
