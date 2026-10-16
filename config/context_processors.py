"""Shared template context processors for the HireNest Australia portal."""
from utils import turnstile as turnstile_module


def turnstile(request):
    """
    Expose Turnstile configuration to templates.

    The site key is public (safe for the browser); the secret key is never
    exposed. Templates gate the widget behind ``turnstile_enabled`` so pages
    without the keys (local dev / tests) render no Cloudflare assets.
    """
    return {
        'turnstile_site_key': turnstile_module.get_site_key(),
        'turnstile_enabled': turnstile_module.is_enabled(),
    }
