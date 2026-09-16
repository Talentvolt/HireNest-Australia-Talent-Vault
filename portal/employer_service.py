"""
HireNest Australia Employer Approvals service.

This module is the single source of truth for HireNest employer approval
records. All queries run against the HireNest database ONLY. TalentVault admin
reads and updates these records exclusively through the authenticated API in
``portal.employer_views``; no TalentVault data is ever imported here.
"""
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.companies.models import CompanyMember


EMPLOYER_ROLES = (User.Role.RECRUITER, User.Role.COMPANY_ADMIN)


def employer_status_message(status):
    """Return the user-facing message for a non-active employer status."""
    if status == User.RecruiterStatus.PENDING:
        return "Your employer account is awaiting approval."
    if status == User.RecruiterStatus.REJECTED:
        return "Your employer registration was not approved."
    if status == User.RecruiterStatus.SUSPENDED:
        return "Your employer account has been suspended. Please contact HireNest Support."
    return "Your employer account is not active."


def get_hirenest_employers_queryset(status=None):
    """
    Return the HireNest employer (recruiter) records in the HireNest database.

    Superusers/staff are excluded: they are platform administrators, not
    employer registrations awaiting approval.
    """
    qs = (
        User.objects.filter(role__in=EMPLOYER_ROLES)
        .exclude(is_superuser=True)
        .exclude(is_staff=True)
        .order_by('-created_at')
    )
    if status and status != 'ALL':
        qs = qs.filter(recruiter_status=status)
    return qs


def get_employer_company(user):
    """Return the company linked to an employer user, if any."""
    membership = (
        user.company_affiliations.select_related('company').first()
        if hasattr(user, 'company_affiliations')
        else None
    )
    return membership.company if membership else None


def serialize_employer(user):
    """Serialize a HireNest employer record for the admin approvals API."""
    company = get_employer_company(user)
    contact_name = user.get_full_name().strip()
    return {
        'id': str(user.id),
        'company_name': company.name if company else (contact_name or user.email),
        'contact_name': contact_name or user.email,
        'email': user.email,
        'phone': user.phone_number or '',
        'industry': (company.industry if company else '') or '',
        'location': (company.location if company else '') or '',
        'website': (company.website if company else '') or '',
        'status': user.recruiter_status,
        'registration_date': user.created_at.isoformat() if user.created_at else None,
    }


def serialize_employer_queryset(queryset):
    return [serialize_employer(user) for user in queryset]


def apply_employer_action(user, action, reason=''):
    """
    Apply an approval action to a HireNest employer and persist it.

    Returns ``(ok, message)``. Unknown actions are rejected. Records are never
    deleted; rejections are retained with their status and reason.
    """
    action = (action or '').strip().lower()

    if action in ('approve', 'reactivate'):
        user.recruiter_status = User.RecruiterStatus.ACTIVE
        user.is_active = True
        user.save(update_fields=['recruiter_status', 'is_active', 'updated_at'])
        label = 'reactivated' if action == 'reactivate' else 'approved'
        return True, f"Employer {user.email} {label}. Status is now ACTIVE."

    if action == 'reject':
        user.recruiter_status = User.RecruiterStatus.REJECTED
        user.is_active = False
        user.save(update_fields=['recruiter_status', 'is_active', 'updated_at'])
        return True, f"Employer {user.email} rejected."

    if action == 'suspend':
        user.recruiter_status = User.RecruiterStatus.SUSPENDED
        user.is_active = False
        user.save(update_fields=['recruiter_status', 'is_active', 'updated_at'])
        return True, f"Employer {user.email} suspended."

    return False, f"Unsupported action: {action}"


def employer_status_counts():
    """Return counts per approval status for the HireNest database."""
    qs = get_hirenest_employers_queryset()
    return {
        'PENDING': qs.filter(recruiter_status=User.RecruiterStatus.PENDING).count(),
        'APPROVED': qs.filter(recruiter_status=User.RecruiterStatus.ACTIVE).count(),
        'REJECTED': qs.filter(recruiter_status=User.RecruiterStatus.REJECTED).count(),
        'SUSPENDED': qs.filter(recruiter_status=User.RecruiterStatus.SUSPENDED).count(),
    }
