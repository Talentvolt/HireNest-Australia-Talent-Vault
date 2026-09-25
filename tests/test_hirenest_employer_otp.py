"""
HireNest Australia employer registration email OTP verification tests.
"""
import re
import time
from datetime import timedelta

from django.core import mail
from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import User, OTPVerification
from apps.companies.models import CompanyMember

from portal.employer_service import apply_employer_action


def _otp_from_outbox():
    for message in reversed(mail.outbox):
        body = getattr(message, 'body', '') or ''
        if 'verification code' in body.lower():
            match = re.search(r'\b(\d{6})\b', body)
            if match:
                return match.group(1)
    return None


REGISTRATION_PAYLOAD = {
    'org_name': 'OTP Employer Co',
    'email': 'otp.employer@company.com.au',
    'phone_number': '+61 2 9000 0000',
    'hiring_type': 'organization',
    'industry': 'Technology',
    'location': 'Sydney NSW',
    'password': 'SecureEmployer123!',
    'confirm_password': 'SecureEmployer123!',
    'terms': 'on',
}


class HireNestEmployerOTPTests(TestCase):
    def setUp(self):
        self.client = Client()
        mail.outbox.clear()

    def register(self, payload=None):
        return self.client.post(
            '/employers/register/', data=payload or dict(REGISTRATION_PAYLOAD), follow=False
        )

    def verify(self, otp):
        return self.client.post('/employers/verify-otp/', data={'otp': otp}, follow=False)

    # 1. OTP sent + stored hashed (never plaintext)
    def test_otp_sent_and_stored_hashed(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/employers/verify-otp/')

        otp_plain = _otp_from_outbox()
        self.assertIsNotNone(otp_plain)

        record = OTPVerification.objects.filter(
            email='otp.employer@company.com.au', verified=False
        ).first()
        self.assertIsNotNone(record)
        self.assertNotEqual(record.otp, otp_plain)
        self.assertTrue(record.check_otp(otp_plain))

    # 2. Valid OTP verification creates a PENDING employer
    def test_valid_otp_verification_creates_pending_employer(self):
        self.register()
        otp = _otp_from_outbox()
        response = self.verify(otp)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/employers/registration-pending/')

        employer = User.objects.filter(email='otp.employer@company.com.au').first()
        self.assertIsNotNone(employer)
        self.assertEqual(employer.role, User.Role.RECRUITER)
        self.assertEqual(employer.recruiter_status, User.RecruiterStatus.PENDING)
        self.assertTrue(CompanyMember.objects.filter(user=employer).exists())

    # 3. Invalid OTP rejected, no employer created
    def test_invalid_otp_is_rejected(self):
        self.register()
        response = self.verify('000000')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid verification code')
        self.assertIsNone(User.objects.filter(email='otp.employer@company.com.au').first())

    # 4. Expired OTP rejected, no employer created
    def test_expired_otp_is_rejected(self):
        self.register()
        OTPVerification.objects.filter(
            email='otp.employer@company.com.au', verified=False
        ).update(expires_at=timezone.now() - timedelta(seconds=1))
        otp = _otp_from_outbox()
        response = self.verify(otp)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'expired')
        self.assertIsNone(User.objects.filter(email='otp.employer@company.com.au').first())

    # 5. Resend cooldown (60 seconds)
    def test_resend_cooldown(self):
        self.register()
        resp = self.client.post('/employers/verify-otp/resend/', follow=False)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'wait')

        session = self.client.session
        session['employer_otp_sent_at'] = time.time() - 61
        session.save()

        resp2 = self.client.post('/employers/verify-otp/resend/', follow=False)
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(resp2.url, '/employers/verify-otp/')

    # 6. Maximum verification attempts
    def test_max_verification_attempts(self):
        self.register()
        for _ in range(5):
            self.verify('000000')
        # The 6th attempt is blocked once the 5-attempt limit is reached.
        response = self.verify('000000')
        self.assertContains(response, 'Maximum verification attempts')
        self.assertIsNone(User.objects.filter(email='otp.employer@company.com.au').first())

    # 7. Unverified employer cannot proceed (no record, cannot log in)
    def test_unverified_employer_cannot_login(self):
        self.register()
        self.assertIsNone(User.objects.filter(email='otp.employer@company.com.au').first())
        login_resp = self.client.post('/employers/login/', data={
            'email': 'otp.employer@company.com.au',
            'password': 'SecureEmployer123!',
        })
        self.assertEqual(login_resp.status_code, 200)
        self.assertContains(login_resp, 'Invalid work email or password')

    # 8. Verified employer remains PENDING (not auto-approved)
    def test_verified_employer_remains_pending(self):
        self.register()
        otp = _otp_from_outbox()
        self.verify(otp)
        employer = User.objects.filter(email='otp.employer@company.com.au').first()
        self.assertEqual(employer.recruiter_status, User.RecruiterStatus.PENDING)

        login_resp = self.client.post('/employers/login/', data={
            'email': 'otp.employer@company.com.au',
            'password': 'SecureEmployer123!',
        })
        self.assertEqual(login_resp.status_code, 200)
        self.assertContains(login_resp, 'awaiting approval')

    # 9. Existing admin approval flow still works
    def test_admin_approval_flow_still_works(self):
        self.register()
        otp = _otp_from_outbox()
        self.verify(otp)
        employer = User.objects.filter(email='otp.employer@company.com.au').first()
        self.assertEqual(employer.recruiter_status, User.RecruiterStatus.PENDING)

        mail.outbox.clear()
        ok, message = apply_employer_action(employer, 'approve')
        self.assertTrue(ok)
        employer.refresh_from_db()
        self.assertEqual(employer.recruiter_status, User.RecruiterStatus.ACTIVE)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            'Your HireNest Australia Employer Account Has Been Approved',
        )
