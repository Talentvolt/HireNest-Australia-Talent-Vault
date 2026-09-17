"""
HireNest Australia job-posting service.

This module is the single source of truth for job postings created by the
TalentVault Admin Portal. Admin postings live in the HireNest database and are
tagged with ``Job.JobSource.ADMIN`` so they are never mixed with postings owned
by external employers (``Job.JobSource.EMPLOYER``).

Nothing here reads or writes TalentVault jobs: the TalentVault Admin Portal
calls the secure server-to-server API in ``portal.employer_views`` instead.
"""
from decimal import Decimal, InvalidOperation

from django.utils.text import slugify

from apps.companies.models import Company
from apps.jobs.models import Job


ADMIN_JOB_STATUSES = {choice for choice, _ in Job.JobStatus.choices}
ADMIN_JOB_TYPES = {choice for choice, _ in Job._meta.get_field('job_type').choices}
ADMIN_WORK_MODES = {choice for choice, _ in Job._meta.get_field('work_mode').choices}

DEFAULT_ADMIN_COMPANY_NAME = 'HireNest Australia'


def get_admin_jobs_queryset(status=None):
    """Return only HireNest admin-owned postings (never employer postings)."""
    qs = (
        Job.objects.filter(source=Job.JobSource.ADMIN)
        .select_related('company')
        .order_by('-created_at')
    )
    if status and status != 'ALL':
        qs = qs.filter(status=status)
    return qs


def get_or_create_company(name):
    """Resolve (or create) the company a HireNest admin job belongs to."""
    name = (name or '').strip() or DEFAULT_ADMIN_COMPANY_NAME
    company = Company.objects.filter(name__iexact=name).first()
    if company:
        return company

    base_slug = slugify(name) or 'company'
    slug = base_slug
    counter = 1
    while Company.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return Company.objects.create(
        name=name,
        slug=slug,
        industry='General',
        location='Australia',
    )


def serialize_job(job):
    """Serialize a HireNest job posting for the admin jobs API."""
    return {
        'id': str(job.id),
        'title': job.title,
        'company_name': job.display_company,
        'company_id': str(job.company_id) if job.company_id else None,
        'location': job.location or '',
        'job_type': job.job_type,
        'work_mode': job.work_mode,
        'department': job.department or '',
        'status': job.status,
        'currency': job.currency,
        'min_experience': job.min_experience,
        'max_experience': job.max_experience,
        'min_salary': str(job.min_salary) if job.min_salary is not None else None,
        'max_salary': str(job.max_salary) if job.max_salary is not None else None,
        'salary_display': job.formatted_salary_display,
        'required_skills_text': job.required_skills_text or '',
        'preferred_skills_text': job.preferred_skills_text or '',
        'description': job.description or '',
        'source': job.source,
        'posted_by_admin': job.is_admin_posted,
        'created_at': job.created_at.isoformat() if job.created_at else None,
    }


def serialize_job_queryset(queryset):
    return [serialize_job(job) for job in queryset]


def _as_int(value, default=0):
    if value in (None, ''):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None


def _validate_job_payload(payload, require_all=True):
    """
    Validate an admin job payload.

    Returns ``(cleaned, errors)``. ``require_all`` enforces the fields needed to
    create a job; updates may omit them.
    """
    errors = []
    cleaned = {}

    title = (payload.get('title') or '').strip()
    description = (payload.get('description') or '').strip()
    location = (payload.get('location') or '').strip()

    if require_all:
        if not title:
            errors.append('title is required.')
        if not description:
            errors.append('description is required.')
        if not location:
            errors.append('location is required.')

    if 'title' in payload:
        cleaned['title'] = title
    if 'description' in payload:
        cleaned['description'] = description
    if 'location' in payload:
        cleaned['location'] = location

    if 'company_name' in payload:
        cleaned['company_name'] = (payload.get('company_name') or '').strip()

    if 'department' in payload:
        cleaned['department'] = (payload.get('department') or '').strip()
    if 'required_skills_text' in payload:
        cleaned['required_skills_text'] = (payload.get('required_skills_text') or '').strip()
    if 'preferred_skills_text' in payload:
        cleaned['preferred_skills_text'] = (payload.get('preferred_skills_text') or '').strip()
    if 'education' in payload:
        cleaned['education'] = (payload.get('education') or '').strip()

    if 'job_type' in payload:
        job_type = (payload.get('job_type') or '').strip().upper()
        if job_type and job_type not in ADMIN_JOB_TYPES:
            errors.append('Invalid job_type.')
        else:
            cleaned['job_type'] = job_type or 'FULL_TIME'

    if 'work_mode' in payload:
        work_mode = (payload.get('work_mode') or '').strip().upper()
        if work_mode and work_mode not in ADMIN_WORK_MODES:
            errors.append('Invalid work_mode.')
        else:
            cleaned['work_mode'] = work_mode or 'ONSITE'

    if 'status' in payload:
        status = (payload.get('status') or '').strip().upper()
        if status and status not in ADMIN_JOB_STATUSES:
            errors.append('Invalid status.')
        else:
            cleaned['status'] = status or Job.JobStatus.ACTIVE

    if 'min_experience' in payload:
        cleaned['min_experience'] = _as_int(payload.get('min_experience'), 0)
    if 'max_experience' in payload:
        cleaned['max_experience'] = _as_int(payload.get('max_experience'), 1)
    if 'notice_period' in payload:
        cleaned['notice_period'] = _as_int(payload.get('notice_period'), 30)

    if 'min_salary' in payload:
        cleaned['min_salary'] = _as_decimal(payload.get('min_salary'))
    if 'max_salary' in payload:
        cleaned['max_salary'] = _as_decimal(payload.get('max_salary'))

    if 'is_remote' in payload:
        cleaned['is_remote'] = bool(payload.get('is_remote'))

    return cleaned, errors


def create_admin_job(payload):
    """
    Create a HireNest admin-owned job posting.

    Returns ``(job, errors)``. Admin postings are always AUD and owned by the
    admin (``source=ADMIN``); they are never attributed to an external employer.
    """
    cleaned, errors = _validate_job_payload(payload or {}, require_all=True)
    if errors:
        return None, errors

    company = get_or_create_company(cleaned.pop('company_name', ''))

    job = Job(
        company=company,
        currency='AUD',
        source=Job.JobSource.ADMIN,
        created_by=None,
        updated_by=None,
        title=cleaned['title'],
        description=cleaned['description'],
        location=cleaned['location'],
        job_type=cleaned.get('job_type', 'FULL_TIME'),
        work_mode=cleaned.get('work_mode', 'ONSITE'),
        status=cleaned.get('status', Job.JobStatus.ACTIVE),
        department=cleaned.get('department', ''),
        required_skills_text=cleaned.get('required_skills_text', ''),
        preferred_skills_text=cleaned.get('preferred_skills_text', ''),
        education=cleaned.get('education', ''),
        min_experience=cleaned.get('min_experience', 0),
        max_experience=cleaned.get('max_experience', 1),
        notice_period=cleaned.get('notice_period', 30),
        min_salary=cleaned.get('min_salary'),
        max_salary=cleaned.get('max_salary'),
        is_remote=cleaned.get('is_remote', False),
    )
    job.save()
    return job, []


def update_admin_job(job, payload):
    """Update a HireNest admin-owned job posting. Returns ``(job, errors)``."""
    if job.source != Job.JobSource.ADMIN:
        return None, ['This posting is not owned by the HireNest admin.']

    cleaned, errors = _validate_job_payload(payload or {}, require_all=False)
    if errors:
        return None, errors

    if 'company_name' in cleaned:
        job.company = get_or_create_company(cleaned.pop('company_name'))
    else:
        cleaned.pop('company_name', None)

    for field, value in cleaned.items():
        setattr(job, field, value)

    # Admin postings are always AUD and remain admin-owned.
    job.currency = 'AUD'
    job.source = Job.JobSource.ADMIN
    job.save()
    return job, []


def apply_admin_job_action(job, action):
    """
    Apply a lifecycle action to an admin-owned posting. Returns ``(ok, message)``.
    """
    if job.source != Job.JobSource.ADMIN:
        return False, 'This posting is not owned by the HireNest admin.'

    action = (action or '').strip().lower()
    if action in ('publish', 'reopen'):
        job.status = Job.JobStatus.ACTIVE
        job.closed_at = None
        job.closed_by = None
        job.save(update_fields=['status', 'closed_at', 'closed_by', 'updated_at'])
        return True, f"Job '{job.title}' published."
    if action == 'pause':
        job.status = Job.JobStatus.PAUSED
        job.save(update_fields=['status', 'updated_at'])
        return True, f"Job '{job.title}' paused."
    if action in ('on_hold', 'hold'):
        job.status = Job.JobStatus.ON_HOLD
        job.save(update_fields=['status', 'updated_at'])
        return True, f"Job '{job.title}' put on hold."
    if action == 'close':
        from django.utils import timezone
        job.status = Job.JobStatus.CLOSED
        job.closed_at = timezone.now()
        job.save(update_fields=['status', 'closed_at', 'updated_at'])
        return True, f"Job '{job.title}' closed."
    return False, f"Unsupported action: {action}"
