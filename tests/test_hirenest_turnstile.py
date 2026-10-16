"""
Regression tests for HireNest Australia Cloudflare Turnstile anti-bot protection.

Covers:
* ``utils.turnstile.verify_token`` for valid / invalid / expired / missing-secret /
  network-error cases (no live network: the siteverify HTTP call is patched).
* View-level enforcement for employer register/login, OTP verify/resend and job
  applications (missing, invalid, expired and valid tokens).
* Candidate Google-OAuth gate (missing token rejected, valid token redirects).
* Existing registration and application workflows still work when Turnstile is
  disabled (the local-development / test default).
"""
import re
from unittest import mock

import requests
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User, OTPVerification
from apps.applications.models import Application
from apps.candidates.models import CandidateProfile
from apps.companies.models import Company, CompanyMember
from apps.jobs.models import Job

from utils import turnstile


def _otp_from_outbox():
    for message in reversed(mail.outbox):
        body = getattr(message, 'body', '') or ''
        if 'verification code' in body.lower():
            match = re.search(r'\b(\d{6})\b', body)
            if match:
                return match.group(1)
    return None


ENABLED_SETTINGS = dict(
    TURNSTILE_ENABLED=True,
    TURNSTILE_SITE_KEY='1x00000000000000000000AA',
    TURNSTILE_SECRET_KEY='1x0000000000000000000000000000000AA',
)


class TurnstileVerifyTokenTests(TestCase):
    """Unit tests for the Cloudflare siteverify client."""

    @override_settings(TURNSTILE_SECRET_KEY='test-secret')
    def test_valid_token_is_accepted(self):
        with mock.patch.object(turnstile, '_siteverify', return_value={'success': True}):
            ok, code = turnstile.verify_token('valid-token', remote_ip='127.0.0.1')
        self.assertTrue(ok)
        self.assertEqual(code, '')

    @override_settings(TURNSTILE_SECRET_KEY='test-secret')
    def test_invalid_token_is_rejected(self):
        with mock.patch.object(
            turnstile, '_siteverify',
            return_value={'success': False, 'error-codes': ['invalid-input-response']},
        ):
            ok, code = turnstile.verify_token('bad-token')
        self.assertFalse(ok)
        self.assertEqual(code, 'invalid_token')

    @override_settings(TURNSTILE_SECRET_KEY='test-secret')
    def test_expired_token_is_rejected(self):
        with mock.patch.object(
            turnstile, '_siteverify',
            return_value={'success': False, 'error-codes': ['timeout-or-duplicate']},
        ):
            ok, code = turnstile.verify_token('stale-token')
        self.assertFalse(ok)
        self.assertEqual(code, 'expired_token')

    @override_settings(TURNSTILE_SECRET_KEY='')
    def test_missing_secret_fails_closed(self):
        ok, code = turnstile.verify_token('any-token')
        self.assertFalse(ok)
        self.assertEqual(code, 'missing_secret')

    @override_settings(TURNSTILE_SECRET_KEY='test-secret')
    def test_network_error_fails_closed(self):
        with mock.patch.object(
            turnstile, '_siteverify',
            side_effect=requests.exceptions.ConnectionError('boom'),
        ):
            ok, code = turnstile.verify_token('token')
        self.assertFalse(ok)
        self.assertEqual(code, 'network_error')

    @override_settings(TURNSTILE_SECRET_KEY='test-secret')
    def test_malformed_response_fails_closed(self):
        with mock.patch.object(turnstile, '_siteverify', return_value='not-json'):
            ok, code = turnstile.verify_token('token')
        self.assertFalse(ok)
        self.assertEqual(code, 'network_error')

    @override_settings(TURNSTILE_SECRET_KEY='test-secret')
    def test_missing_token_is_rejected(self):
        ok, code = turnstile.verify_token('')
        self.assertFalse(ok)
        self.assertEqual(code, 'missing_token')


class TurnstileProtectedViewsTests(TestCase):
    """View-level enforcement of Turnstile + rate limits."""

    def setUp(self):
        self.client = Client()
        mail.outbox.clear()

        self.company = Company.objects.create(
            name='Turnstile Pty Ltd', slug='turnstile-pty-ltd',
            industry='Technology', location='Sydney NSW',
        )
        self.recruiter = User.objects.create_user(
            email='boss@turnstile.com.au', password='SecureEmployer123!',
            role=User.Role.RECRUITER, recruiter_status=User.RecruiterStatus.ACTIVE,
            is_active=True, is_verified=True,
        )
        CompanyMember.objects.create(
            company=self.company, user=self.recruiter,
            designation='Hiring Lead', role=CompanyMember.MemberRole.ADMIN,
        )
        self.job = Job.objects.create(
            company=self.company, title='Backend Engineer', location='Sydney NSW',
            job_type='FULL_TIME', work_mode='HYBRID', currency='AUD',
            status='ACTIVE', description='Build things.', created_by=self.recruiter,
        )
        self.candidate = User.objects.create_user(
            email='cand@example.com', password='CandidatePassword123!',
            role=User.Role.CANDIDATE, is_active=True, is_verified=True,
        )
        self.profile = CandidateProfile.objects.create(
            user=self.candidate, full_name='Cand Date', location='Sydney NSW',
            candidate_status='ACTIVE',
        )

    def _register_payload(self):
        return {
            'org_name': 'Turnstile Pty Ltd',
            'email': 'hr@turnstile.com.au',
            'phone_number': '+61 2 9000 0000',
            'hiring_type': 'organization',
            'industry': 'Technology',
            'location': 'Sydney NSW',
            'password': 'SecureEmployer123!',
            'confirm_password': 'SecureEmployer123!',
            'terms': 'on',
        }

    # ------------------------------------------------------------------
    # Employer registration
    # ------------------------------------------------------------------
    @override_settings(**ENABLED_SETTINGS)
    def test_employer_register_missing_token_rejected(self):
        resp = self.client.post('/employers/register/', data=self._register_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Security verification is required')
        self.assertIsNone(User.objects.filter(email='hr@turnstile.com.au').first())

    @override_settings(**ENABLED_SETTINGS)
    def test_employer_register_invalid_token_rejected(self):
        payload = self._register_payload()
        payload['cf-turnstile-response'] = 'bad'
        with mock.patch.object(
            turnstile, '_siteverify',
            return_value={'success': False, 'error-codes': ['invalid-input-response']},
        ):
            resp = self.client.post('/employers/register/', data=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Security verification failed')
        self.assertIsNone(User.objects.filter(email='hr@turnstile.com.au').first())

    @override_settings(**ENABLED_SETTINGS)
    def test_employer_register_expired_token_rejected(self):
        payload = self._register_payload()
        payload['cf-turnstile-response'] = 'stale'
        with mock.patch.object(
            turnstile, '_siteverify',
            return_value={'success': False, 'error-codes': ['timeout-or-duplicate']},
        ):
            resp = self.client.post('/employers/register/', data=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Security verification has expired')
        self.assertIsNone(User.objects.filter(email='hr@turnstile.com.au').first())

    @override_settings(**ENABLED_SETTINGS)
    def test_employer_register_valid_token_proceeds(self):
        payload = self._register_payload()
        payload['cf-turnstile-response'] = 'valid'
        with mock.patch.object(turnstile, '_siteverify', return_value={'success': True}):
            resp = self.client.post('/employers/register/', data=payload, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/employers/verify-otp/')
        self.assertTrue(
            OTPVerification.objects.filter(email='hr@turnstile.com.au').exists()
        )

    def test_employer_register_works_when_turnstile_disabled(self):
        # Default test environment has no Turnstile keys, so the flow must be
        # unchanged and must not require a token.
        resp = self.client.post('/employers/register/', data=self._register_payload(), follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/employers/verify-otp/')

    # ------------------------------------------------------------------
    # Employer login
    # ------------------------------------------------------------------
    @override_settings(**ENABLED_SETTINGS)
    def test_employer_login_missing_token_rejected(self):
        resp = self.client.post('/employers/login/', data={
            'email': 'boss@turnstile.com.au', 'password': 'SecureEmployer123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Security verification is required')

    @override_settings(**ENABLED_SETTINGS)
    def test_employer_login_valid_token_proceeds_to_auth(self):
        payload = {
            'email': 'boss@turnstile.com.au',
            'password': 'SecureEmployer123!',
            'cf-turnstile-response': 'valid',
        }
        with mock.patch.object(turnstile, '_siteverify', return_value={'success': True}):
            resp = self.client.post('/employers/login/', data=payload, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/employers/dashboard/')

    # ------------------------------------------------------------------
    # Employer OTP verify + resend
    # ------------------------------------------------------------------
    def _register_with_valid_turnstile(self):
        payload = self._register_payload()
        payload['cf-turnstile-response'] = 'valid'
        with mock.patch.object(turnstile, '_siteverify', return_value={'success': True}):
            return self.client.post('/employers/register/', data=payload, follow=False)

    @override_settings(**ENABLED_SETTINGS)
    def test_otp_verify_missing_token_rejected(self):
        self._register_with_valid_turnstile()
        resp = self.client.post('/employers/verify-otp/', data={'otp': '000000'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Security verification is required')

    @override_settings(**ENABLED_SETTINGS)
    def test_otp_verify_valid_token_proceeds(self):
        self._register_with_valid_turnstile()
        otp = _otp_from_outbox()
        self.assertIsNotNone(otp)
        payload = {'otp': otp, 'cf-turnstile-response': 'valid'}
        with mock.patch.object(turnstile, '_siteverify', return_value={'success': True}):
            resp = self.client.post('/employers/verify-otp/', data=payload, follow=False)
        self.assertEqual(resp.status_code, 302)
        # Non-gmail domain stays PENDING.
        self.assertEqual(resp.url, '/employers/registration-pending/')

    @override_settings(**ENABLED_SETTINGS)
    def test_otp_resend_missing_token_rejected(self):
        self._register_with_valid_turnstile()
        resp = self.client.post('/employers/verify-otp/resend/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Security verification is required')

    # ------------------------------------------------------------------
    # Job application
    # ------------------------------------------------------------------
    @override_settings(**ENABLED_SETTINGS)
    def test_job_apply_missing_token_rejected(self):
        self.client.force_login(self.candidate)
        resp = self.client.post(
            f'/jobs/{self.job.id}/apply/',
            data={'first_name': 'Cand', 'last_name': 'Date', 'phone_number': '0400000000',
                  'location': 'Sydney NSW'},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, f'/jobs/{self.job.id}/apply/')
        self.assertFalse(
            Application.objects.filter(job=self.job, candidate=self.profile).exists()
        )

    @override_settings(**ENABLED_SETTINGS)
    def test_job_apply_valid_token_proceeds(self):
        self.client.force_login(self.candidate)
        payload = {
            'first_name': 'Cand', 'last_name': 'Date', 'phone_number': '0400000000',
            'location': 'Sydney NSW', 'cf-turnstile-response': 'valid',
        }
        with mock.patch.object(turnstile, '_siteverify', return_value={'success': True}):
            resp = self.client.post(f'/jobs/{self.job.id}/apply/', data=payload, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/applications/')
        self.assertTrue(
            Application.objects.filter(job=self.job, candidate=self.profile).exists()
        )

    def test_job_apply_works_when_turnstile_disabled(self):
        self.client.force_login(self.candidate)
        resp = self.client.post(
            f'/jobs/{self.job.id}/apply/',
            data={'first_name': 'Cand', 'last_name': 'Date', 'phone_number': '0400000000',
                  'location': 'Sydney NSW'},
            follow=False,
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            Application.objects.filter(job=self.job, candidate=self.profile).exists()
        )

    # ------------------------------------------------------------------
    # Candidate Google OAuth gate
    # ------------------------------------------------------------------
    @override_settings(**ENABLED_SETTINGS)
    def test_candidate_login_missing_token_rejected(self):
        resp = self.client.post('/login/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Security verification is required')

    @override_settings(**ENABLED_SETTINGS)
    def test_candidate_login_valid_token_redirects_to_google(self):
        with mock.patch.object(turnstile, '_siteverify', return_value={'success': True}):
            resp = self.client.post('/login/', data={'cf-turnstile-response': 'valid'}, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/accounts/google/login/')

    @override_settings(**ENABLED_SETTINGS)
    def test_candidate_register_valid_token_preserves_next(self):
        with mock.patch.object(turnstile, '_siteverify', return_value={'success': True}):
            resp = self.client.post(
                '/register/',
                data={'cf-turnstile-response': 'valid', 'next': '/jobs/'},
                follow=False,
            )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/google/login/', resp.url)
        self.assertIn('next=', resp.url)


class TurnstileRateLimitTests(TestCase):
    """Session rate limits applied to public anti-abuse endpoints."""

    def setUp(self):
        self.client = Client()
        mail.outbox.clear()

    def _register_payload(self):
        return {
            'org_name': 'Rate Ltd Co',
            'email': 'rl@example.com',
            'phone_number': '+61 2 9000 1111',
            'hiring_type': 'organization',
            'industry': 'Tech',
            'location': 'Sydney NSW',
            'password': 'SecureEmployer123!',
            'confirm_password': 'SecureEmployer123!',
            'terms': 'on',
        }

    def test_employer_login_rate_limited_after_repeated_attempts(self):
        for _ in range(5):
            self.client.post('/employers/login/', data={
                'email': 'nobody@example.com', 'password': 'WrongPassword123!',
            })
        resp = self.client.post('/employers/login/', data={
            'email': 'nobody@example.com', 'password': 'WrongPassword123!',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Too many login attempts')

    def test_employer_registration_rate_limited(self):
        for _ in range(5):
            self.client.post('/employers/register/', data=self._register_payload())
        resp = self.client.post('/employers/register/', data=self._register_payload())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Too many registration attempts')
