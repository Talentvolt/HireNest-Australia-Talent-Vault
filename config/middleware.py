from django.shortcuts import redirect
from apps.accounts.models import User

PUBLIC_EXACT_PATHS = frozenset({
    '/', '/employers/', '/employers',
    '/login/', '/login', '/register/', '/register',
    '/employers/login/', '/employers/login',
    '/employers/register/', '/employers/register',
    '/companies/', '/companies',
    '/career-advice/', '/career-advice',
    '/salary-guide/', '/salary-guide',
    '/resources/', '/resources',
    '/sitemap.xml', '/robots.txt'
})

PUBLIC_PREFIXES = (
    '/jobs/',
    '/companies/',
    '/career-advice/',
    '/salary-guide/',
    '/resources/',
    '/employers/',
    '/login/',
    '/register/',
    '/location-search/',
    '/static/',
    '/media/',
)

CANDIDATE_PROTECTED_PREFIXES = (
    '/profile/',
    '/applications/',
    '/saved-jobs/',
)

class HirenestAccessMiddleware:
    """
    Middleware for HireNest Australia portal.
    Ensures public routes are easily accessible to all guests,
    candidate portal pages require authenticated CANDIDATE users,
    and responses have standard security/cache headers.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def _add_no_cache_headers(self, response):
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def __call__(self, request):
        path = request.path

        # Bypass static and media files
        if path.startswith('/static/') or path.startswith('/media/'):
            return self.get_response(request)

        # Unauthenticated access control
        if not request.user.is_authenticated:
            is_protected = any(path.startswith(prefix) for prefix in CANDIDATE_PROTECTED_PREFIXES)
            if is_protected or path.endswith('/apply/'):
                res = redirect(f'/login/?next={path}')
                return self._add_no_cache_headers(res)

        response = self.get_response(request)
        return self._add_no_cache_headers(response)
