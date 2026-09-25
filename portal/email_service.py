import logging
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives

from apps.accounts.services.email_service import mask_email

logger = logging.getLogger(__name__)


def send_employer_otp(email, otp):
    """
    Send the 6-digit email OTP to an employer's official work email during
    registration. Reuses the shared Django email configuration; never logs the
    plaintext OTP.
    """
    target_email = email.strip().lower()
    subject = "Your HireNest Australia Employer Verification Code"
    from_email = (
        getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        or 'HireNest Australia <noreply@hirenest.com.au>'
    )

    text_content = (
        f"Your HireNest Australia employer verification code is: {otp}\n\n"
        f"Enter this 6-digit code to verify your official work email and complete "
        f"your employer registration.\n\n"
        f"This code is valid for 10 minutes. Never share this code with anyone.\n\n"
        f"If you did not request this verification code, please ignore this email.\n\n"
        f"(c) 2026 HireNest Australia. All rights reserved."
    )

    html_content = (
        '<div style="font-family: Arial, sans-serif; padding: 20px; '
        'background-color: #FAF9FF; text-align: center;">'
        '<h2 style="color: #0F172A;">Your HireNest Australia Employer Verification Code</h2>'
        '<div style="font-size: 36px; font-weight: bold; color: #0284C7; '
        'background: #F0F9FF; padding: 15px; border-radius: 12px; margin: 20px 0; '
        'letter-spacing: 8px;">{otp}</div>'
        '<p style="color: #64748B;">This code is valid for 10 minutes. '
        'Never share this code with anyone.</p>'
        '<p style="color: #64748B; font-size: 13px;">Notice: If you don\'t find this '
        'email in your Inbox, please check your Spam or Promotions folder.</p>'
        '</div>'
    ).format(otp=otp)

    try:
        email_message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[target_email],
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send(fail_silently=False)
        logger.info(f"Successfully sent employer verification code to {mask_email(target_email)}")
        return True, "Verification code sent to your email successfully."
    except Exception as exc:
        logger.error(f"Failed to send employer verification code to {mask_email(target_email)}: {exc}")
        return False, "Failed to send verification code. Please try again."


def send_admin_new_employer_email(user, company=None):
    """
    Send notification email to HIRENEST_ADMIN_NOTIFICATION_EMAIL when a new
    employer registers on HireNest Australia.
    Never fails registration; logs email sending errors safely.
    """
    admin_email = getattr(settings, 'HIRENEST_ADMIN_NOTIFICATION_EMAIL', 'admin@hirenest.com.au')
    if not admin_email:
        return

    company_name = company.name if company else (user.get_full_name() or user.email)
    contact_name = user.get_full_name() or user.email
    industry = company.industry if company else 'General Business'
    location = company.location if company else 'Sydney NSW'
    website = company.website if company else 'N/A'
    phone = user.phone_number or 'N/A'
    reg_date = user.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if user.created_at else 'N/A'
    site_url = getattr(settings, 'SITE_URL', 'https://hirenest.com.au')
    approval_url = f"{site_url.rstrip('/')}/employers/approvals/"

    subject = "New HireNest Australia Employer Registration"
    message = (
        f"A new employer has registered on HireNest Australia and is awaiting approval.\n\n"
        f"- Company / Organisation Name: {company_name}\n"
        f"- Recruiter / Contact Name: {contact_name}\n"
        f"- Official Work Email: {user.email}\n"
        f"- Phone Number: {phone}\n"
        f"- Industry: {industry}\n"
        f"- Australian HQ / Location: {location}\n"
        f"- Company Website: {website}\n"
        f"- Registration Date & Time: {reg_date}\n"
        f"- Status: PENDING\n\n"
        f"Review HireNest Employer:\n{approval_url}\n\n"
        f"--- HireNest Australia Automated Notification ---"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            fail_silently=False,
        )
    except Exception as e:
        logger.exception(f"Failed to send admin notification email for employer {user.email}: {e}")


def send_employer_status_email(user, company=None, action='approve', reason=''):
    """
    Send status update email to the employer when their account status changes
    (approve/active, reject, suspend, reactivate).
    Never raises exceptions that block approval/action execution.
    """
    if not user or not user.email:
        return

    company_name = company.name if company else (user.get_full_name() or user.email)
    site_url = getattr(settings, 'SITE_URL', 'https://hirenest.com.au')
    login_url = f"{site_url.rstrip('/')}/employers/login/"

    action = (action or '').lower()
    subject = "HireNest Australia Employer Account Update"
    message = ""

    if action in ('approve', 'reactivate'):
        subject = "Your HireNest Australia Employer Account Has Been Approved"
        action_label = "approved" if action == 'approve' else "reactivated"
        message = (
            f"Hello {user.get_full_name() or user.email},\n\n"
            f"Your employer account for {company_name} has been {action_label}.\n\n"
            f"You can now log in to your HireNest Australia employer account and start using the recruiter workspace:\n"
            f"{login_url}\n\n"
            f"- Company Name: {company_name}\n"
            f"- Registered Email: {user.email}\n"
            f"- Status: ACTIVE\n\n"
            f"Welcome to HireNest Australia!\n"
        )
    elif action == 'reject':
        subject = "HireNest Australia Employer Registration Update"
        reason_text = f"\nReason: {reason}" if reason else ""
        message = (
            f"Hello {user.get_full_name() or user.email},\n\n"
            f"Thank you for your interest in HireNest Australia. Regrettably, your employer registration for {company_name} could not be approved at this time.{reason_text}\n\n"
            f"- Company Name: {company_name}\n"
            f"- Registered Email: {user.email}\n"
            f"- Status: Rejected\n\n"
            f"If you have any questions or require assistance, please contact HireNest Support at support@hirenest.com.au.\n"
        )
    elif action == 'suspend':
        subject = "Your HireNest Australia Employer Account Has Been Suspended"
        message = (
            f"Hello {user.get_full_name() or user.email},\n\n"
            f"Your employer account for {company_name} has been suspended.\n\n"
            f"- Company Name: {company_name}\n"
            f"- Registered Email: {user.email}\n"
            f"- Status: SUSPENDED\n\n"
            f"Please contact HireNest Support at support@hirenest.com.au for further assistance.\n"
        )
    else:
        return

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.exception(f"Failed to send employer status email ({action}) to {user.email}: {e}")
