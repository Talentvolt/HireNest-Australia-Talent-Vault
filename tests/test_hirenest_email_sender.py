"""
Regression tests for the HireNest SMTP 555 sender-format fix.

Verifies that the SMTP envelope sender is a bare address while the visible
``From`` header keeps the display name.
"""
from django.core import mail
from django.core.mail.message import sanitize_address
from django.test import TestCase, override_settings

from apps.accounts.models import User

from portal.email_service import send_admin_new_employer_email, send_employer_otp


@override_settings(
    DEFAULT_FROM_EMAIL='HireNest Australia <otp@hirenest.com.au>',
    HIRENEST_ADMIN_NOTIFICATION_EMAIL='admin@hirenest.com.au',
)
class HireNestEmailSenderTests(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_otp_envelope_sender_is_bare_and_from_header_keeps_display_name(self):
        ok, _ = send_employer_otp('employer@example.com', '123456')
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]

        # 1. SMTP envelope MAIL FROM must be the bare address only.
        self.assertEqual(message.from_email, 'otp@hirenest.com.au')
        envelope = sanitize_address(message.from_email, 'utf-8')
        self.assertEqual(envelope, 'otp@hirenest.com.au')
        self.assertNotIn('HireNest Australia', envelope)

        # 2. Visible From header keeps the display name.
        from_header = str(message.message()['From'])
        self.assertIn('HireNest Australia', from_header)
        self.assertIn('otp@hirenest.com.au', from_header)

    def test_admin_notification_email_uses_split_sender(self):
        user = User.objects.create_user(
            email='employer@example.com',
            password='SecureEmployer123!',
            role=User.Role.RECRUITER,
            recruiter_status=User.RecruiterStatus.PENDING,
        )
        send_admin_new_employer_email(user)
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]
        self.assertEqual(message.from_email, 'otp@hirenest.com.au')
        envelope = sanitize_address(message.from_email, 'utf-8')
        self.assertEqual(envelope, 'otp@hirenest.com.au')

        from_header = str(message.message()['From'])
        self.assertIn('HireNest Australia', from_header)
        self.assertIn('otp@hirenest.com.au', from_header)
