from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from allauth.socialaccount.models import SocialApp

from apps.accounts.apps import sync_google_social_app


def _mask(value):
    if not value:
        return "(not set)"
    value = str(value)
    return value if len(value) <= 24 else value[:24] + "..."


class Command(BaseCommand):
    help = (
        "Verify/configure the Site and the single Google SocialApp used by "
        "django-allauth, using GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET from the "
        "environment. Removes stale/duplicate Google apps. Never prints the secret."
    )

    def handle(self, *args, **options):
        sync_google_social_app()

        site_id = getattr(settings, "SITE_ID", 1)
        site = Site.objects.filter(id=site_id).first()
        self.stdout.write(
            self.style.SUCCESS(
                f"Site ID {site_id} -> domain={site.domain if site else '(missing)'!r} "
                f"name={site.name if site else '(missing)'!r}"
            )
        )

        google_apps = SocialApp.objects.filter(provider="google").order_by("id")
        self.stdout.write(f"Google SocialApp count: {google_apps.count()}")
        for app in google_apps:
            domains = list(app.sites.values_list("domain", flat=True))
            self.stdout.write(
                self.style.SUCCESS(
                    f"  id={app.id} provider={app.provider!r} "
                    f"client_id={_mask(app.client_id)} sites={domains}"
                )
            )
