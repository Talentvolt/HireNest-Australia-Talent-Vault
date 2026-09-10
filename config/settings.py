import os
import sys
from pathlib import Path
from urllib.parse import urlparse
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent
TALENTVAULT_DIR = BASE_DIR.parent / '2020Tech'

# Load environment variables from .env if present
load_dotenv(BASE_DIR / '.env', override=True)

# Ensure BASE_DIR and fallback paths are on sys.path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if TALENTVAULT_DIR.exists() and str(TALENTVAULT_DIR) not in sys.path:
    sys.path.insert(1, str(TALENTVAULT_DIR))

# ==============================================================================
# Security & Environment-Aware Configuration
# ==============================================================================
SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get(
    'HIRENEST_SECRET_KEY',
    'django-insecure-hirenest-australia-key-2026-production-ready'
)

# Detect environment runtime
IS_RENDER = bool(os.environ.get('RENDER') or os.environ.get('RENDER_EXTERNAL_HOSTNAME'))
IS_RUNSERVER = 'runserver' in sys.argv
IS_TESTING = (
    'test' in sys.argv
    or 'pytest' in sys.modules
    or any('pytest' in arg for arg in sys.argv)
)

# DEBUG:
# 1. If explicitly specified in environment, respect it.
# 2. Otherwise default to True for local development / runserver, and False on Render / Production.
debug_env = os.environ.get('DEBUG')
if debug_env is not None:
    DEBUG = debug_env.strip().lower() in ('true', '1', 't', 'yes')
else:
    DEBUG = not IS_RENDER and not os.environ.get('ENVIRONMENT', '').lower().startswith('prod')

# Host configuration
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '')
if allowed_hosts_env:
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]
else:
    ALLOWED_HOSTS = [
        'hirenest.com.au',
        'www.hirenest.com.au',
        '.hirenest.com.au',
        'localhost',
        '127.0.0.1',
        '0.0.0.0',
        'testserver',
    ]

# Automatically support Render external hostnames
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

# Always allow local hosts and wildcard in DEBUG or local dev
if DEBUG and '*' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('*')

# CSRF Trusted Origins
csrf_origins_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins_env.split(',') if origin.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        'https://hirenest.com.au',
        'https://www.hirenest.com.au',
        'https://*.onrender.com',
        'https://*.render.com',
        # Local development origins (HireNest Australia runs on port 8002 locally)
        'http://localhost',
        'http://127.0.0.1',
        'http://0.0.0.0',
        'http://localhost:8002',
        'http://127.0.0.1:8002',
        'http://localhost:8080',
        'http://127.0.0.1:8080',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
        'http://localhost:5000',
        'http://127.0.0.1:5000',
    ]

if render_hostname:
    render_origin = f"https://{render_hostname}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

# HTTPS & Security Redirect Settings
# ONLY enable SSL redirects, secure proxy headers, and secure-only cookies in actual production environments (Render / Live production).
# NEVER force SSL redirection on local development, runserver, testing, or when DEBUG is True.
is_production = not DEBUG and not IS_TESTING and (IS_RENDER or os.environ.get('ENVIRONMENT', '').lower().startswith('prod'))

if is_production:
    # Reverse proxy SSL header for Render HTTPS termination
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', '1').strip().lower() in ('1', 'true', 'yes')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'SAMEORIGIN'
    hsts_seconds = os.environ.get('SECURE_HSTS_SECONDS', '0').strip()
    if hsts_seconds.isdigit() and int(hsts_seconds) > 0:
        SECURE_HSTS_SECONDS = int(hsts_seconds)
        SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', '1').strip().lower() in ('1', 'true', 'yes')
        SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', '0').strip().lower() in ('1', 'true', 'yes')
    else:
        SECURE_HSTS_SECONDS = 0
else:
    # Local Development & Testing: strictly disable HTTPS redirects, headers, and secure-only cookies
    SECURE_PROXY_SSL_HEADER = None
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# TalentVault Recruiter Workspace Target URL
TALENTVAULT_RECRUITER_WORKSPACE_URL = os.environ.get(
    'TALENTVAULT_RECRUITER_WORKSPACE_URL',
    'https://talent-vault.in/dashboard/recruiter/'
)

# ==============================================================================
# Application Definition
# ==============================================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',

    # Third Party
    'crispy_forms',
    'crispy_bootstrap5',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Shared TalentVault Core & Database Models
    'apps.core',
    'apps.accounts',
    'apps.companies',
    'apps.jobs',
    'apps.candidates',
    'apps.applications',
    'apps.taxonomy',
    'apps.clients',
    'apps.notifications',

    # HireNest Australia Dedicated App
    'portal',
]

SITE_ID = 1

# ==============================================================================
# Public Site URL / Domain (used by django.contrib.sites and django-allauth)
# Local:      http://127.0.0.1:8002
# Production: https://hirenest.com.au
# The OAuth callback itself is always derived from the current request host,
# so absolute redirects never fall back to a hard-coded port.
# ==============================================================================
SITE_URL = os.environ.get('SITE_URL', 'https://hirenest.com.au').rstrip('/')
SITE_DOMAIN = urlparse(SITE_URL).netloc or 'hirenest.com.au'
SITE_NAME = os.environ.get('SITE_NAME', 'HireNest Australia')

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

AUTH_USER_MODEL = 'accounts.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.HirenestAccessMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ==============================================================================
# Database Configuration — HireNest Australia uses its OWN database ONLY.
#
# HireNest and TalentVault are data-isolated and MUST NOT share a database.
# HireNest reads ONLY HIRENEST_DATABASE_URL (or the HIRENEST_DB_* variables).
# It deliberately does NOT read TalentVault's DATABASE_URL or DB_* variables,
# and it does NOT fall back to them.
# ==============================================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('HIRENEST_DB_NAME', 'hirenest_australia'),
        'USER': os.environ.get('HIRENEST_DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('HIRENEST_DB_PASSWORD', ''),
        'HOST': os.environ.get('HIRENEST_DB_HOST', 'localhost'),
        'PORT': os.environ.get('HIRENEST_DB_PORT', '5432'),
    }
}

HIRENEST_DATABASE_URL = os.environ.get('HIRENEST_DATABASE_URL')

# Local development / tests use HireNest's OWN SQLite file.
use_sqlite = (
    'test' in sys.argv
    or 'pytest' in sys.modules
    or os.environ.get('USE_SQLITE') == '1'
)

if use_sqlite:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
elif HIRENEST_DATABASE_URL:
    # Production: use HireNest's dedicated database only.
    DATABASES['default'] = dj_database_url.parse(
        HIRENEST_DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
elif is_production and not os.environ.get('HIRENEST_DB_HOST'):
    # Fail fast instead of silently connecting to TalentVault's database.
    raise ImproperlyConfigured(
        "HIRENEST_DATABASE_URL is required in production. HireNest must use its "
        "own database and will not fall back to TalentVault's DATABASE_URL."
    )
# else: individual HIRENEST_DB_* variables (defined above) are used.

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization / Australian Localization
LANGUAGE_CODE = 'en-au'
TIME_ZONE = 'Australia/Sydney'
USE_I18N = True
USE_TZ = True

# ==============================================================================
# Static & Media Storage Configuration (WhiteNoise + AWS S3)
# ==============================================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

WHITENOISE_MAX_AGE = 31536000

# AWS S3 Settings for Media Uploads (Resumes, Profile Pictures, Documents)
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_KEY')
AWS_STORAGE_BUCKET_NAME = (
    os.environ.get('AWS_STORAGE_BUCKET_NAME')
    or os.environ.get('AWS_S3_BUCKET_NAME')
    or os.environ.get('AWS_S3_BUCKET')
    or os.environ.get('S3_BUCKET_NAME')
    or os.environ.get('AWS_BUCKET_NAME')
    or os.environ.get('AWS_BUCKET')
)
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME') or os.environ.get('AWS_REGION') or 'ap-south-1'
AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN')
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False
AWS_S3_FILE_OVERWRITE = False
AWS_S3_SIGNATURE_VERSION = 's3v4'

use_s3 = bool(
    AWS_ACCESS_KEY_ID and
    AWS_SECRET_ACCESS_KEY and
    AWS_STORAGE_BUCKET_NAME and
    os.environ.get('USE_LOCAL_STORAGE') != '1'
)

if use_s3:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
    else:
        MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/"
    MEDIA_ROOT = BASE_DIR / 'media'
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    MEDIA_URL = '/media/'
    # HireNest's own media directory — never TalentVault's.
    MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session Configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_NAME = 'hirenest_sessionid'
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = False

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# ==============================================================================
# HireNest Australia Candidate "Continue with Google" (django-allauth)
# Reuses the Google SocialApp configured from environment variables.
# Never hardcode OAuth client secrets here.
# ==============================================================================
SOCIALACCOUNT_ADAPTER = 'apps.accounts.adapters.CandidateSocialAccountAdapter'
ACCOUNT_ADAPTER = 'apps.accounts.adapters.CandidateAccountAdapter'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'none'

# The custom User model (apps.accounts.User) has NO username field; email is
# the USERNAME_FIELD. Tell django-allauth this explicitly, otherwise its
# populate_username()/generate_unique_username() look up a "username" field and
# raise FieldDoesNotExist during the Google callback.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = 'email'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_UNIQUE_EMAIL = True

# Force the OAuth callback protocol from SITE_URL. In production SITE_URL is
# https://hirenest.com.au, so allauth always builds:
#   https://hirenest.com.au/accounts/google/login/callback/
# even if a proxy header is missing. Locally SITE_URL is http, so it stays http.
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https' if SITE_URL.startswith('https://') else 'http'

# ==============================================================================
# SMTP & Email Delivery Configuration (HireNest Australia OTP Engine)
# ==============================================================================
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 't')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '').strip()
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '').strip()
DEFAULT_FROM_EMAIL = (
    os.environ.get('DEFAULT_FROM_EMAIL') or
    (f"HireNest Australia <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else 'HireNest Australia <noreply@hirenest.com.au>')
)
EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', 10))

if os.environ.get('EMAIL_BACKEND'):
    EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND')
elif EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

