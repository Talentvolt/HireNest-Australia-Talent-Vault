import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


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
