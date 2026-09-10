import os
import sys

from django.conf import settings
from django.core.management.base import BaseCommand


def _mask(value):
    if not value:
        return "(not set)"
    value = str(value)
    return value if len(value) <= 24 else f"{value[:16]}...{value[-8:]}"


class Command(BaseCommand):
    help = (
        "Show exactly which database and Site HireNest Australia is using at "
        "runtime. Never prints passwords or client secrets."
    )

    def handle(self, *args, **options):
        db = settings.DATABASES.get("default", {})
        engine = db.get("ENGINE", "")
        name = db.get("NAME", "")
        host = db.get("HOST", "")
        port = db.get("PORT", "")
        user = db.get("USER", "")

        if os.environ.get("HIRENEST_DATABASE_URL"):
            source = "HIRENEST_DATABASE_URL"
        elif os.environ.get("USE_SQLITE") == "1" or "test" in sys.argv:
            source = "USE_SQLITE=1 (local SQLite)"
        else:
            source = "HIRENEST_DB_* variables"

        self.stdout.write("HireNest Australia active configuration")
        self.stdout.write(f"  source env var : {source}")
        self.stdout.write(f"  ENGINE         : {engine}")
        self.stdout.write(f"  NAME           : {name}")
        if "sqlite" in engine:
            self.stdout.write(f"  SQLite file    : {name}")
        else:
            self.stdout.write(f"  HOST           : {host}")
            self.stdout.write(f"  PORT           : {port}")
            self.stdout.write(f"  USER           : {user}")

        # Active Site domain, read from the database HireNest is actually on.
        try:
            from django.contrib.sites.models import Site
            site = Site.objects.filter(id=getattr(settings, "SITE_ID", 1)).first()
            self.stdout.write(f"  Site.domain    : {site.domain if site else '(missing)'}")
            self.stdout.write(f"  Site.name      : {site.name if site else '(missing)'}")
        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(f"  Site lookup failed: {type(exc).__name__}: {exc}")
            )

        # Active Google SocialApp(s), masked (never prints the secret).
        try:
            from allauth.socialaccount.models import SocialApp
            apps = list(SocialApp.objects.filter(provider="google"))
            self.stdout.write(f"  Google apps    : {len(apps)}")
            for app in apps:
                domains = list(app.sites.values_list("domain", flat=True))
                self.stdout.write(
                    f"    id={app.id} client_id={_mask(app.client_id)} sites={domains}"
                )
        except Exception as exc:
            self.stdout.write(
                self.style.WARNING(f"  SocialApp lookup failed: {type(exc).__name__}: {exc}")
            )

        blob = f"{name} {host} {user}".lower()
        if any(marker in blob for marker in ("talentvault", "talent_vault", "talent-vault")):
            self.stdout.write(
                self.style.ERROR(
                    "  WARNING: this database looks like TalentVault's. HireNest must "
                    "use its own separate database."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("  OK: no TalentVault marker in database name/host/user.")
            )
