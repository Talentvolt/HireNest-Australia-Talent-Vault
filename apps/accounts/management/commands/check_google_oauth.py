import os

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialApp


def _mask(value):
    if not value:
        return "(not set)"
    value = str(value)
    return value if len(value) <= 24 else value[:24] + "..."


def _clean(name):
    value = (os.environ.get(name) or "").strip()
    if value.startswith(f"{name}="):
        value = value[len(f"{name}="):].strip()
    return value


class Command(BaseCommand):
    help = (
        "Diagnose the effective Google OAuth configuration and show exactly which "
        "SocialApp django-allauth selects at runtime. Never prints the client secret."
    )

    def handle(self, *args, **options):
        site_id = getattr(settings, "SITE_ID", None)
        site_domain = getattr(settings, "SITE_DOMAIN", "")
        env_client_id = _clean("GOOGLE_CLIENT_ID")
        env_client_secret = _clean("GOOGLE_CLIENT_SECRET")

        self.stdout.write("=== Sites ===")
        for s in Site.objects.all().order_by("id"):
            marker = " (SITE_ID)" if s.id == site_id else ""
            self.stdout.write(f"  id={s.id} domain={s.domain!r} name={s.name!r}{marker}")

        self.stdout.write("=== Google SocialApps (DB) ===")
        google_apps = list(SocialApp.objects.filter(provider="google").order_by("id"))
        if not google_apps:
            self.stdout.write("  (none)")
        for app in google_apps:
            domains = list(app.sites.values_list("domain", flat=True))
            self.stdout.write(
                f"  id={app.id} provider={app.provider!r} "
                f"client_id={_mask(app.client_id)} secret_set={bool(app.secret)} sites={domains}"
            )

        self.stdout.write("=== Environment ===")
        self.stdout.write(f"  SITE_URL                 : {getattr(settings, 'SITE_URL', '')}")
        self.stdout.write(f"  SITE_DOMAIN              : {site_domain}")
        self.stdout.write(f"  SITE_ID                  : {site_id}")
        self.stdout.write(f"  ACCOUNT_DEFAULT_PROTOCOL : {getattr(settings, 'ACCOUNT_DEFAULT_HTTP_PROTOCOL', '')}")
        self.stdout.write(f"  SECURE_PROXY_SSL_HEADER  : {getattr(settings, 'SECURE_PROXY_SSL_HEADER', None)}")
        self.stdout.write(f"  GOOGLE_CLIENT_ID (env)   : {_mask(env_client_id)}")
        self.stdout.write(f"  GOOGLE_CLIENT_SECRET set : {bool(env_client_secret)}")

        self.stdout.write("=== Runtime selection (what allauth would use) ===")
        host = site_domain or "hirenest.com.au"
        request = RequestFactory().get("/accounts/google/login/", HTTP_HOST=host)
        try:
            selected = get_adapter().get_app(request, provider="google")
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  get_app() failed: {type(exc).__name__}: {exc}"))
        else:
            match = "MATCH" if env_client_id and selected.client_id == env_client_id else "MISMATCH"
            self.stdout.write(
                f"  selected id={selected.id} client_id={_mask(selected.client_id)} "
                f"sites={list(selected.sites.values_list('domain', flat=True))}"
            )
            self.stdout.write(
                f"  env GOOGLE_CLIENT_ID vs selected: {match}"
            )
            self.stdout.write(
                f"  env secret vs selected secret   : "
                f"{'MATCH' if env_client_secret and selected.secret == env_client_secret else 'MISMATCH/unknown'}"
            )

        self.stdout.write(
            "  Expected production callback: "
            "https://hirenest.com.au/accounts/google/login/callback/"
        )
