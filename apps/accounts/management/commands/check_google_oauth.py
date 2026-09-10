import os

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp


def _mask(value):
    if not value:
        return "(not set)"
    value = str(value)
    return value if len(value) <= 24 else value[:24] + "..."


class Command(BaseCommand):
    help = (
        "Diagnose the effective Google OAuth configuration. "
        "Never prints the client secret."
    )

    def handle(self, *args, **options):
        site_id = getattr(settings, "SITE_ID", None)
        site = Site.objects.filter(id=site_id).first()

        env_client_id = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
        if env_client_id.startswith("GOOGLE_CLIENT_ID="):
            env_client_id = env_client_id[len("GOOGLE_CLIENT_ID="):].strip()

        apps = SocialApp.objects.filter(provider="google").order_by("id")

        self.stdout.write("Google OAuth configuration")
        self.stdout.write(f"  SITE_ID                  : {site_id}")
        self.stdout.write(f"  SITE_URL                 : {getattr(settings, 'SITE_URL', '')}")
        self.stdout.write(f"  SITE_DOMAIN              : {getattr(settings, 'SITE_DOMAIN', '')}")
        self.stdout.write(f"  Site.domain              : {site.domain if site else '(missing)'}")
        self.stdout.write(f"  ACCOUNT_DEFAULT_PROTOCOL : {getattr(settings, 'ACCOUNT_DEFAULT_HTTP_PROTOCOL', '')}")
        self.stdout.write(f"  SECURE_PROXY_SSL_HEADER  : {getattr(settings, 'SECURE_PROXY_SSL_HEADER', None)}")
        self.stdout.write(f"  env GOOGLE_CLIENT_ID     : {_mask(env_client_id)}")
        self.stdout.write(f"  SocialApp (google) count : {apps.count()}")

        for app in apps:
            domains = list(app.sites.values_list("domain", flat=True))
            self.stdout.write(
                f"  - id={app.id} client_id={_mask(app.client_id)} sites={domains}"
            )

        self.stdout.write(
            "  Expected production callback: "
            "https://hirenest.com.au/accounts/google/login/callback/"
        )
