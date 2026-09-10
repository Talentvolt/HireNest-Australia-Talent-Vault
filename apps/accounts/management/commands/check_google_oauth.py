import os
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.test import Client, RequestFactory
from allauth.socialaccount.adapter import get_adapter
from allauth.socialaccount.models import SocialApp

from apps.accounts.apps import (
    HIRENEST_GOOGLE_CLIENT_PREFIX,
    LEGACY_TALENTVAULT_CLIENT_PREFIXES,
)


def _mask(value):
    """Show enough of the client id to identify the GCP project, hide the rest."""
    if not value:
        return "(not set)"
    value = str(value)
    if len(value) <= 28:
        return value
    return f"{value[:16]}...{value[-8:]}"


def _clean(name):
    value = (os.environ.get(name) or "").strip()
    if value.startswith(f"{name}="):
        value = value[len(f"{name}="):].strip()
    return value


# Known legacy Google OAuth clients that must NOT be used for HireNest Australia.
# Using one of these produces redirect_uri_mismatch for hirenest.com.au.
LEGACY_CLIENT_PREFIXES = {
    prefix: "old TalentVault OAuth client"
    for prefix in LEGACY_TALENTVAULT_CLIENT_PREFIXES
}


def _legacy_warning(value):
    for prefix, label in LEGACY_CLIENT_PREFIXES.items():
        if value and value.startswith(prefix):
            return (
                f"WARNING: this is the {label} (project {prefix.rstrip('-')}), "
                "not the HireNest Australia client -> redirect_uri_mismatch"
            )
    return None


def _hirenest_note(value):
    if value and value.startswith(HIRENEST_GOOGLE_CLIENT_PREFIX):
        return f"OK: HireNest Australia client (project {HIRENEST_GOOGLE_CLIENT_PREFIX.rstrip('-')})"
    return None


class Command(BaseCommand):
    help = (
        "Diagnose the effective Google OAuth configuration and print the actual "
        "Google authorization URL django-allauth generates (client_id + redirect_uri). "
        "Never prints the client secret."
    )

    def handle(self, *args, **options):
        site_id = getattr(settings, "SITE_ID", None)
        site_domain = getattr(settings, "SITE_DOMAIN", "")
        host = site_domain or "hirenest.com.au"
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

        self.stdout.write("=== Environment / settings ===")
        self.stdout.write(f"  SITE_URL                 : {getattr(settings, 'SITE_URL', '')}")
        self.stdout.write(f"  SITE_DOMAIN              : {site_domain}")
        self.stdout.write(f"  SITE_ID                  : {site_id}")
        self.stdout.write(f"  ACCOUNT_DEFAULT_PROTOCOL : {getattr(settings, 'ACCOUNT_DEFAULT_HTTP_PROTOCOL', '')}")
        self.stdout.write(f"  SECURE_PROXY_SSL_HEADER  : {getattr(settings, 'SECURE_PROXY_SSL_HEADER', None)}")
        self.stdout.write(f"  GOOGLE_CLIENT_ID (env)   : {_mask(env_client_id)}")
        self.stdout.write(f"  GOOGLE_CLIENT_SECRET set : {bool(env_client_secret)}")
        env_note = _hirenest_note(env_client_id)
        if env_note:
            self.stdout.write(self.style.SUCCESS(f"  {env_note}"))

        self.stdout.write("=== Runtime app selection (adapter.get_app) ===")
        request = RequestFactory().get("/accounts/google/login/", HTTP_HOST=host, secure=True)
        try:
            selected = get_adapter().get_app(request, provider="google")
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"  get_app() failed: {type(exc).__name__}: {exc}"))
        else:
            match = "MATCH" if env_client_id and selected.client_id == env_client_id else "MISMATCH"
            self.stdout.write(
                f"  selected id={selected.id} provider={selected.provider!r} "
                f"client_id={_mask(selected.client_id)} "
                f"sites={list(selected.sites.values_list('domain', flat=True))}"
            )
            self.stdout.write(f"  env GOOGLE_CLIENT_ID vs selected : {match}")
            self.stdout.write(
                "  env GOOGLE_CLIENT_SECRET vs selected : "
                f"{'MATCH' if env_client_secret and selected.secret == env_client_secret else 'MISMATCH/unknown'}"
            )
            for value in (selected.client_id, env_client_id):
                warning = _legacy_warning(value)
                if warning:
                    self.stdout.write(self.style.ERROR(f"  {warning}"))
            sel_note = _hirenest_note(selected.client_id)
            if sel_note:
                self.stdout.write(self.style.SUCCESS(f"  {sel_note}"))

        self.stdout.write("=== Actual generated Google authorization URL ===")
        try:
            response = Client().get("/accounts/google/login/", HTTP_HOST=host, secure=True)
            location = response.headers.get("Location", "")
        except Exception as exc:
            location = ""
            self.stdout.write(self.style.ERROR(f"  could not build auth URL: {type(exc).__name__}: {exc}"))

        if location.startswith("https://accounts.google.com"):
            params = parse_qs(urlsplit(location).query)
            client_id = params.get("client_id", [""])[0]
            redirect_uri = params.get("redirect_uri", [""])[0]
            self.stdout.write(f"  auth endpoint            : https://accounts.google.com/o/oauth2/v2/auth")
            self.stdout.write(f"  client_id sent to Google : {_mask(client_id)}")
            self.stdout.write(f"  redirect_uri sent        : {redirect_uri}")
            self.stdout.write(f"  scope                    : {params.get('scope', [''])[0]}")
            self.stdout.write(
                f"  client_id matches env    : "
                f"{'YES' if env_client_id and client_id == env_client_id else 'NO'}"
            )
            warning = _legacy_warning(client_id)
            if warning:
                self.stdout.write(self.style.ERROR(f"  {warning}"))
        else:
            self.stdout.write(f"  unexpected Location: {location or '(none)'}")

        self.stdout.write(
            "  Expected production callback: "
            "https://hirenest.com.au/accounts/google/login/callback/"
        )
