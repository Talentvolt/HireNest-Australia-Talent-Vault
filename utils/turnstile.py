"""
Cloudflare Turnstile server-side verification for HireNest Australia.

The client-side Turnstile widget only produces a one-time token. That token is
meaningless until it is validated here against Cloudflare's ``/siteverify``
endpoint using the site's private secret key. No form, OTP email or account is
ever actioned on the strength of the client-side widget alone.

Design notes
------------
* Secrets are read from ``django.conf.settings`` (populated from environment
  variables) and are never hardcoded or logged.
* All network and HTTP failures are converted into a :class:`TurnstileError`
  so callers can fail closed (reject the submission) while returning a friendly
  message to the user.
* ``verify_token`` performs the HTTP call through the module-level
  :func:`_siteverify` helper so tests can patch it without touching the network.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SITEVERIFY_ENDPOINT = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

# Map a selection of Cloudflare error codes to stable, caller-friendly codes.
# Unknown codes are passed through unchanged so they can still be logged.
_KNOWN_ERROR_CODES = {
    'missing-input-secret': 'missing_secret',
    'invalid-input-secret': 'invalid_secret',
    'missing-input-response': 'missing_token',
    'invalid-input-response': 'invalid_token',
    'timeout-or-duplicate': 'expired_token',
    'internal-error': 'provider_error',
}


class TurnstileError(Exception):
    """Raised when a Turnstile token cannot be verified."""

    def __init__(self, code, message=''):
        self.code = code
        self.message = message or code
        super().__init__(self.message)


def is_enabled():
    """Return True when Turnstile verification is active for this environment."""
    return bool(getattr(settings, 'TURNSTILE_ENABLED', False))


def get_site_key():
    """Return the public Turnstile site key (safe for browser templates)."""
    return (getattr(settings, 'TURNSTILE_SITE_KEY', '') or '').strip()


def _get_secret_key():
    return (getattr(settings, 'TURNSTILE_SECRET_KEY', '') or '').strip()


def _siteverify(payload, timeout):
    """Perform the siteverify HTTP POST. Patchable seam for tests."""
    response = requests.post(
        getattr(settings, 'TURNSTILE_SITEVERIFY_URL', SITEVERIFY_ENDPOINT),
        data=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _normalize_error_codes(error_codes):
    normalized = []
    for code in error_codes or []:
        normalized.append(_KNOWN_ERROR_CODES.get(code, code))
    return normalized


def verify_token(token, remote_ip='', action=None):
    """
    Verify a Turnstile token against Cloudflare's siteverify endpoint.

    Returns ``(ok, error_code)``. ``ok`` is ``True`` only when Cloudflare
    reports success. On failure ``error_code`` is a stable machine code such as
    ``invalid_token``, ``expired_token``, ``missing_token``, ``missing_secret``
    or ``network_error``.

    The caller is responsible for failing closed: a non-``True`` result means
    the submission must not be processed.
    """
    token = (token or '').strip()
    secret = _get_secret_key()

    if not secret:
        logger.error('Turnstile verification attempted with no TURNSTILE_SECRET_KEY configured')
        return False, 'missing_secret'

    if not token:
        return False, 'missing_token'

    payload = {'secret': secret, 'response': token}
    if remote_ip:
        payload['remoteip'] = remote_ip

    timeout = getattr(settings, 'TURNSTILE_TIMEOUT', 10)
    try:
        data = _siteverify(payload, timeout)
    except (requests.exceptions.RequestException, ValueError) as exc:
        # Fail closed: never accept a submission when Cloudflare is unreachable
        # or returns a malformed response.
        logger.error('Turnstile siteverify network/parse error: %s', exc)
        return False, 'network_error'

    if not isinstance(data, dict):
        logger.error('Turnstile siteverify returned a non-JSON response')
        return False, 'network_error'

    if data.get('success') is True:
        return True, ''

    error_codes = _normalize_error_codes(data.get('error-codes') or [])
    error_code = error_codes[0] if error_codes else 'invalid_token'
    logger.warning(
        'Turnstile verification failed (action=%s, codes=%s)', action, error_codes
    )
    return False, error_code
