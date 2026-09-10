import logging
from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)

COMPANY_RECRUITERS = [
    {"email": "snehal.2020technologies@gmail.com", "first_name": "Snehal", "last_name": "Patil", "role": "SUPER_ADMIN"},
    {"email": "chhayajoshi.2020technologies.in@gmail.com", "first_name": "Chhaya", "last_name": "Joshi", "role": "SUPER_ADMIN"},
    {"email": "rahul.2020technologies@gmail.com", "first_name": "Rahul", "last_name": "Nishad", "role": "SUPER_ADMIN"},
    {"email": "anamikashkla.2020technologies@gmail.com", "first_name": "Anamika", "last_name": "", "role": "SUPER_ADMIN"},
    {"email": "deepak.kumar@2020technologies.in", "first_name": "Deepak", "last_name": "Kumar", "role": "SUPER_ADMIN"},
    {"email": "nikhil@2020technologies.in", "first_name": "Nikhil", "last_name": "Mittal", "role": "SUPER_ADMIN"},
    {"email": "harshita.2020technologies@gmail.com", "first_name": "Harshita", "last_name": "", "role": "SUPER_ADMIN"},
    {"email": "deepanshu.verma@2020technologies.in", "first_name": "Deepanshu", "last_name": "Verma", "role": "SUPER_ADMIN"},
    {"email": "rajeevkumar9801456p@gmail.com", "first_name": "Rajeev", "last_name": "Kumar", "role": "SUPER_ADMIN"},
]

ADMIN_ACCOUNTS = [
    {"email": "admin@talentvault.in", "first_name": "System", "last_name": "Administrator", "role": "SUPER_ADMIN"},
]

def create_default_recruiter(sender, **kwargs):
    from django.db import connection
    try:
        tables = connection.introspection.table_names()
        if 'accounts_user' in tables:
            from apps.accounts.models import User
            from apps.companies.models import Company, CompanyMember
            
            company = None
            if 'companies_company' in tables:
                company, _ = Company.objects.get_or_create(
                    name="TalentVault Technologies",
                    defaults={
                        'slug': 'talentvault-technologies',
                        'industry': 'Software Product',
                        'description': 'Default organization created during database initialization.',
                        'location': 'Remote'
                    }
                )
            
            for config in COMPANY_RECRUITERS:
                email = config['email'].lower().strip()
                user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "is_staff": True,
                        "is_superuser": True,
                        "role": User.Role.SUPER_ADMIN,
                        "first_name": config['first_name'],
                        "last_name": config['last_name'],
                        "is_active": True,
                        "is_verified": True,
                        "recruiter_status": User.RecruiterStatus.ACTIVE,
                    }
                )
                if created:
                    user.set_password("TalentVault2026!")
                    user.save()
                    logger.info(f"Created company administrator account: {email}")
                else:
                    updated = False
                    if not user.first_name and config['first_name']:
                        user.first_name = config['first_name']
                        updated = True
                    if not user.last_name and config['last_name']:
                        user.last_name = config['last_name']
                        updated = True
                    if user.role != User.Role.SUPER_ADMIN or not user.is_staff or not user.is_superuser:
                        user.role = User.Role.SUPER_ADMIN
                        user.is_staff = True
                        user.is_superuser = True
                        updated = True
                    if user.recruiter_status != User.RecruiterStatus.ACTIVE:
                        user.recruiter_status = User.RecruiterStatus.ACTIVE
                        updated = True
                    if updated:
                        user.save()

                if company and 'companies_companymember' in tables:
                    CompanyMember.objects.get_or_create(
                        company=company,
                        user=user,
                        defaults={
                            'designation': 'Recruiter',
                            'role': CompanyMember.MemberRole.RECRUITER
                        }
                    )

            for config in ADMIN_ACCOUNTS:
                email = config['email'].lower().strip()
                admin_user, created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "is_staff": True,
                        "is_superuser": True,
                        "role": User.Role.SUPER_ADMIN,
                        "first_name": config['first_name'],
                        "last_name": config['last_name'],
                        "is_active": True,
                        "is_verified": True,
                        "recruiter_status": User.RecruiterStatus.ACTIVE,
                    }
                )
                if created:
                    admin_user.set_password("TalentVaultAdmin2026!")
                    admin_user.save()
                    logger.info(f"Created admin account: {email}")
    except Exception as err:
        logger.error(f"Error in create_default_recruiter: {err}")

def _clean_google_env(name):
    """Read an OAuth env var, tolerating accidental `NAME=value` copy/paste."""
    import os
    from django.conf import settings

    value = os.environ.get(name, '') or getattr(settings, name, '') or ''
    value = value.strip()
    prefix = f"{name}="
    if value.startswith(prefix):
        value = value[len(prefix):].strip()
    return value


def sync_google_social_app():
    """
    Ensure there is exactly ONE Google SocialApp, built from the production
    environment, attached only to the configured Site. This prevents a stale
    TalentVault app or a duplicate from being selected by django-allauth.

    Safe to run repeatedly (post_migrate / management command).
    """
    from django.db import connection
    from django.contrib.sites.models import Site
    from allauth.socialaccount.models import SocialApp
    from django.conf import settings

    tables = connection.introspection.table_names()
    if 'django_site' not in tables or 'socialaccount_socialapp' not in tables:
        return None

    site_id = getattr(settings, 'SITE_ID', 1)
    site_domain = getattr(settings, 'SITE_DOMAIN', 'hirenest.com.au')
    site_name = getattr(settings, 'SITE_NAME', 'HireNest Australia')

    site, _ = Site.objects.get_or_create(
        id=site_id,
        defaults={'domain': site_domain, 'name': site_name},
    )
    # Keep the Site in sync with SITE_URL/SITE_DOMAIN so allauth resolves the
    # Google SocialApp for the production domain (hirenest.com.au).
    if site.domain != site_domain or site.name != site_name:
        site.domain = site_domain
        site.name = site_name
        site.save(update_fields=['domain', 'name'])

    client_id = _clean_google_env('GOOGLE_CLIENT_ID')
    client_secret = _clean_google_env('GOOGLE_CLIENT_SECRET')

    google_apps = list(SocialApp.objects.filter(provider='google').order_by('id'))
    app = google_apps[0] if google_apps else SocialApp(provider='google', name='Google')

    app.name = 'Google'
    if client_id:
        app.client_id = client_id
    elif not app.client_id:
        app.client_id = 'placeholder-google-client-id'
    if client_secret:
        app.secret = client_secret
    elif not app.secret:
        app.secret = 'placeholder-google-client-secret'
    app.save()

    # Attach ONLY to the configured Site; allauth's on_site() filter then has a
    # single unambiguous match.
    app.sites.set([site])

    # Remove any duplicate / legacy Google apps so they can never take precedence.
    removed = 0
    for extra in google_apps[1:]:
        extra.delete()
        removed += 1

    if client_id:
        logger.info(
            "Google OAuth SocialApp synced for %s (client_id=%s..., site_id=%s, removed_duplicates=%s)",
            site_domain, client_id[:24], site.id, removed,
        )
    else:
        logger.warning(
            "GOOGLE_CLIENT_ID is not set; Google OAuth is using a placeholder client id."
        )

    return app


def setup_google_social_app(sender, **kwargs):
    try:
        sync_google_social_app()
    except Exception as e:
        logger.error(f"Error in setup_google_social_app: {e}")

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        post_migrate.connect(create_default_recruiter, sender=self)
        post_migrate.connect(setup_google_social_app)

        # Log the effective Google OAuth configuration at startup so it is visible
        # in production logs. The client secret is never logged.
        try:
            from django.conf import settings
            client_id = _clean_google_env('GOOGLE_CLIENT_ID')
            masked = (
                f"{client_id[:8]}...{client_id[-8:]}"
                if len(client_id) > 20 else (client_id or '(missing)')
            )
            logger.info(
                "HireNest Google OAuth startup: SITE_DOMAIN=%s SITE_URL=%s client_id=%s "
                "protocol=%s proxy_ssl_header=%s",
                getattr(settings, 'SITE_DOMAIN', ''),
                getattr(settings, 'SITE_URL', ''),
                masked,
                getattr(settings, 'ACCOUNT_DEFAULT_HTTP_PROTOCOL', ''),
                getattr(settings, 'SECURE_PROXY_SSL_HEADER', None),
            )
        except Exception as cfg_err:
            logger.error(f"Error logging Google OAuth startup config: {cfg_err}")

        # Enforce prompt=select_account, access_type=offline, include_granted_scopes=true on GoogleProvider
        try:
            from allauth.socialaccount.providers.google.provider import GoogleProvider
            _orig_get_auth_params = GoogleProvider.get_auth_params_from_request
            
            def custom_get_auth_params_from_request(self, request, action):
                ret = _orig_get_auth_params(self, request, action)
                ret['prompt'] = 'select_account'
                ret['access_type'] = 'offline'
                ret['include_granted_scopes'] = 'true'
                return ret

            GoogleProvider.get_auth_params_from_request = custom_get_auth_params_from_request
        except Exception as err:
            logger.error(f"Error patching GoogleProvider: {err}")


