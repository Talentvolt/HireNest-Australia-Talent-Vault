"""
HireNest candidate application service.

This module is the single source of truth for candidate applications stored in
the HireNest database. The TalentVault Admin Portal reads these records
exclusively through the authenticated API in ``portal.employer_views``; no
TalentVault data is ever imported here and the two databases stay separate.
"""
from django.db.models import Q

from apps.applications.models import Application
from .currency_data import (
    DEFAULT_CURRENCY,
    DEFAULT_SALARY_PERIOD,
    format_salary_with_currency,
)


# Display-friendly application status groups. Each maps to a set of raw
# ``Application.stage`` values so the admin API can filter by a friendly group.
APPLICATION_STATUS_GROUPS = {
    'APPLIED': ['OPEN', 'SYSTEM_SUBMITTED'],
    'UNDER_REVIEW': ['SCREENING_FEEDBACK_PENDING', 'SYSTEM_SELECTED', 'AUTOMATION_SKIPPED'],
    'SHORTLISTED': ['SCREENING_SELECT'],
    'INTERVIEW': ['INTERVIEW_SCHEDULE', 'INTERVIEW_IN_PROCESS'],
    'SELECTED': [
        'INTERVIEW_SELECT', 'ACCEPTED', 'JOINED', 'OFFER_STAGE',
        'DOCUMENTATION_STAGE', 'NEGOTIATION_STAGE',
    ],
    'REJECTED': ['SCREENING_REJECT', 'INTERVIEW_REJECT', 'SYSTEM_REJECTED', 'DROPOUT'],
}

VALID_STAGES = {choice for choice, _ in Application.ApplicationStage.choices}


def get_hirenest_applications_queryset():
    """Return all candidate applications in the HireNest database."""
    return (
        Application.objects
        .select_related('job', 'job__company', 'candidate', 'candidate__user')
        .order_by('-created_at')
    )


def _resolve_status_filter(status):
    """
    Resolve a ``status`` query parameter to a list of raw stages (or None).

    Accepts either a friendly group key (e.g. ``APPLIED``) or a raw stage value
    (e.g. ``OPEN``). Returns None when no valid filter was supplied.
    """
    status = (status or '').strip().upper()
    if not status or status == 'ALL':
        return None
    if status in APPLICATION_STATUS_GROUPS:
        return APPLICATION_STATUS_GROUPS[status]
    if status in VALID_STAGES:
        return [status]
    return None


def filter_applications(queryset, status=None, job_id=None, query=None):
    """Apply admin list filters to the applications queryset."""
    stages = _resolve_status_filter(status)
    if stages:
        queryset = queryset.filter(stage__in=stages)

    if job_id:
        queryset = queryset.filter(job_id=job_id)

    query = (query or '').strip()
    if query:
        queryset = queryset.filter(
            Q(candidate__full_name__icontains=query)
            | Q(candidate__user__email__icontains=query)
            | Q(candidate__user__first_name__icontains=query)
            | Q(candidate__user__last_name__icontains=query)
        )

    return queryset


def _resume_url(candidate, as_attachment):
    """Return a short-lived presigned URL for the candidate's resume, if any."""
    resume_field = None
    if candidate and candidate.has_resume:
        resume_field = candidate.resume
    if not resume_field:
        return ''

    from utils.s3 import get_presigned_url
    try:
        return get_presigned_url(resume_field, expires_in=900, as_attachment=as_attachment)
    except Exception:
        return ''


def serialize_application(application, include_resume_url=True):
    """Serialize a HireNest candidate application for the admin API."""
    candidate = application.candidate
    user = candidate.user if candidate else None

    expected_salary = application.expected_ctc
    if expected_salary is None and candidate is not None:
        expected_salary = candidate.expected_salary

    currency = application.expected_salary_currency or DEFAULT_CURRENCY
    salary_period = application.salary_period or DEFAULT_SALARY_PERIOD

    data = {
        'id': str(application.id),
        'candidate_id': str(candidate.id) if candidate else None,
        'candidate_name': (candidate.full_name if candidate else '') or (
            user.get_full_name() if user else '') or '',
        'email': (user.email if user else '') or '',
        'phone': application.mobile_number or (user.phone_number if user else '') or '',
        'job_id': str(application.job_id) if application.job_id else None,
        'job_title': application.job.title if application.job else '',
        'location': (candidate.location if candidate else '') or '',
        'expected_salary': str(expected_salary) if expected_salary is not None else None,
        'expected_salary_currency': currency,
        'salary_period': salary_period,
        'expected_salary_display': format_salary_with_currency(
            expected_salary, currency, salary_period
        ),
        'application_date': application.created_at.isoformat() if application.created_at else None,
        'stage': application.stage,
        'status_display': application.candidate_status_display,
        'screening_answers': application.screening_answers or [],
        'cover_letter': application.cover_letter or '',
        'linkedin_url': application.linkedin_url or '',
        'has_resume': bool(candidate and candidate.has_resume) or bool(
            application.resume and application.resume.name
        ),
    }

    if include_resume_url:
        data['resume_url'] = _resume_url(candidate, as_attachment=True)
        data['resume_preview_url'] = _resume_url(candidate, as_attachment=False)

    return data


def serialize_application_queryset(queryset):
    return [serialize_application(app) for app in queryset]
