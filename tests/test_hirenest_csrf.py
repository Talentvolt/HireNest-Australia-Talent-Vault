"""
Regression test for the intermittent 403 Forbidden reported on HireNest
login/register/POST requests behind the Render HTTPS proxy.

The failure mode: a browser submits a form while still on ``http://`` (during
the ``http -> https`` redirect, or when the reverse proxy reports
``X-Forwarded-Proto: https`` for an ``http://`` request). Django's CSRF
``Origin`` check then saw ``http://hirenest.com.au`` / ``http://www.hirenest.com.au``
against an ``https`` request origin and rejected the request with a 403.

The fix makes the canonical HireNest origins (apex + www, HTTP + HTTPS) part of
``CSRF_TRUSTED_ORIGINS`` so these requests are accepted, without disabling CSRF
protection for genuine cross-site requests.
"""
import re

from django.test import Client, TestCase, override_settings


def _csrf_token(html):
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    return match.group(1) if match else None


@override_settings(
    SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    CSRF_COOKIE_SECURE=True,
    SESSION_COOKIE_SECURE=True,
)
class HireNestCsrfProxyRegressionTests(TestCase):
    def _post_login(self, origin, host='hirenest.com.au', proto='https'):
        client = Client(enforce_csrf_checks=True)
        resp = client.get('/employers/login/', HTTP_HOST=host)
        token = _csrf_token(resp.content.decode('utf-8'))
        self.assertIsNotNone(token, 'Login form must render a CSRF token')

        headers = {'HTTP_HOST': host}
        if proto:
            headers['HTTP_X_FORWARDED_PROTO'] = proto
        if origin:
            headers['HTTP_ORIGIN'] = origin

        return client.post(
            '/employers/login/',
            data={
                'email': 'regression@example.com',
                'password': 'NotARealPassword123!',
                'csrfmiddlewaretoken': token,
            },
            **headers,
        )

    def test_hirenest_origins_accepted_but_foreign_origin_rejected(self):
        # HireNest's own origins (apex + www, over both schemes) must be accepted
        # behind the HTTPS proxy, regardless of the browser's current scheme.
        for origin, host in [
            ('https://hirenest.com.au', 'hirenest.com.au'),
            ('http://hirenest.com.au', 'hirenest.com.au'),
            ('https://www.hirenest.com.au', 'www.hirenest.com.au'),
            ('http://www.hirenest.com.au', 'www.hirenest.com.au'),
        ]:
            resp = self._post_login(origin, host=host)
            self.assertNotEqual(
                resp.status_code,
                403,
                f"Origin {origin} was rejected with a CSRF 403",
            )

        # CSRF protection must remain intact for genuine cross-site requests.
        resp = self._post_login('https://evil.example.com')
        self.assertEqual(resp.status_code, 403)
