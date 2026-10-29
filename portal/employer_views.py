"""
HireNest Australia Employer Suite views.

Contains:
- The HireNest recruiter workspace (dashboard, jobs, candidates, profile).
- The employer registration "pending approval" confirmation page.
- An admin-only HireNest employer approvals page.
- The secure server-to-server admin API consumed by the TalentVault Admin
  Portal.

Every queryset in this module targets the HireNest database only. TalentVault
jobs, candidates and recruiters are never read, written or imported here.
"""
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView

from apps.accounts.models import User
from apps.applications.models import Application
from apps.jobs.models import Job

from .forms import EmployerJobForm
from .employer_service import (
    apply_employer_action,
    employer_status_counts,
    employer_status_message,
    get_hirenest_employers_queryset,
    serialize_employer,
    serialize_employer_queryset,
)
from .job_service import (
    apply_admin_job_action,
    create_admin_job,
    get_admin_jobs_queryset,
    serialize_job,
    serialize_job_queryset,
    update_admin_job,
)
from .application_service import (
    filter_applications,
    get_hirenest_applications_queryset,
    serialize_application,
    serialize_application_queryset,
)


EMPLOYER_ROLES = (User.Role.RECRUITER, User.Role.COMPANY_ADMIN)


class HirenestEmployerRequiredMixin(LoginRequiredMixin):
    """Allow only approved HireNest employer accounts into the workspace."""
    login_url = '/employers/login/'
    redirect_field_name = 'next'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        user = request.user
        if getattr(user, 'role', None) not in EMPLOYER_ROLES:
            messages.error(request, "This workspace is only available to HireNest employer accounts.")
            return redirect('/employers/login/')

        if getattr(user, 'recruiter_status', None) != User.RecruiterStatus.ACTIVE:
            logout(request)
            messages.warning(request, employer_status_message(user.recruiter_status))
            return redirect('/employers/login/')

        return super().dispatch(request, *args, **kwargs)


class HirenestSuperAdminRequiredMixin(LoginRequiredMixin):
    """Admin-only access for the HireNest employer approvals screen."""
    login_url = '/login/'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        user = request.user
        is_admin = (
            getattr(user, 'role', None) == User.Role.SUPER_ADMIN
            or getattr(user, 'is_superuser', False)
            or getattr(user, 'is_staff', False)
        )
        if not is_admin:
            return HttpResponseForbidden(
                "You do not have permission to access HireNest employer approvals."
            )
        return super().dispatch(request, *args, **kwargs)


def _get_company_for_user(user):
    membership = (
        user.company_affiliations.select_related('company').first()
        if hasattr(user, 'company_affiliations')
        else None
    )
    return membership.company if membership else None


MAX_SCREENING_QUESTIONS = 5


def _parse_screening_questions(post):
    """Parse screening questions from the job posting form submission."""
    try:
        count = int(post.get('screening_count', '0') or 0)
    except (TypeError, ValueError):
        count = 0
    count = max(0, min(count, MAX_SCREENING_QUESTIONS))

    questions = []
    for i in range(count):
        text = (post.get(f'question_text_{i}') or '').strip()
        if not text:
            continue
        q_type = post.get(f'question_type_{i}', 'TEXT')
        if q_type not in ('TEXT', 'YES_NO'):
            q_type = 'TEXT'
        required = post.get(f'question_required_{i}') == '1'
        questions.append({
            'question': text,
            'type': q_type,
            'required': required,
        })
    return questions


# ==============================================================================
# EMPLOYER REGISTRATION PENDING CONFIRMATION
# ==============================================================================
class HirenestEmployerRegistrationPendingView(View):
    """Confirmation page shown immediately after employer registration."""

    def get(self, request):
        return render(request, 'hirenest/employer_registration_pending.html')


# ==============================================================================
# HIRENEST RECRUITER WORKSPACE
# ==============================================================================
class HirenestEmployerDashboardView(HirenestEmployerRequiredMixin, View):
    """HireNest-only recruiter dashboard."""

    def get(self, request):
        company = _get_company_for_user(request.user)
        jobs = (
            Job.objects.filter(company=company, source=Job.JobSource.EMPLOYER)
            if company
            else Job.objects.none()
        )

        applications = (
            Application.objects.filter(job__company=company)
            .select_related('candidate', 'job')
            .order_by('-created_at')
            if company
            else Application.objects.none()
        )

        context = {
            'company': company,
            'total_jobs': jobs.count(),
            'active_jobs': jobs.filter(status=Job.JobStatus.ACTIVE).count(),
            'total_applications': applications.count(),
            'recent_jobs': jobs.order_by('-created_at')[:5],
            'recent_applications': applications[:5],
        }
        return render(request, 'hirenest/employer_dashboard.html', context)


class HirenestEmployerJobsView(HirenestEmployerRequiredMixin, ListView):
    """List the employer's own HireNest job postings."""
    template_name = 'hirenest/employer_jobs.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        company = _get_company_for_user(self.request.user)
        if not company:
            return Job.objects.none()
        return Job.objects.filter(
            company=company, source=Job.JobSource.EMPLOYER
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company'] = _get_company_for_user(self.request.user)
        return context


class HirenestEmployerJobCreateView(HirenestEmployerRequiredMixin, View):
    """Create a HireNest-only job posting for the employer's company."""

    def get(self, request):
        return render(request, 'hirenest/employer_job_form.html', {
            'form': EmployerJobForm(),
            'company': _get_company_for_user(request.user),
            'screening_questions': [],
        })

    def post(self, request):
        company = _get_company_for_user(request.user)
        if not company:
            messages.error(request, "Your employer account is not linked to a company yet.")
            return redirect('/employers/dashboard/')

        screening_questions = _parse_screening_questions(request.POST)
        form = EmployerJobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            benefits = (form.cleaned_data.get('benefits') or '').strip()
            if benefits:
                job.description = f"{job.description.rstrip()}\n\nBenefits\n{benefits}"
            job.company = company
            job.currency = 'AUD'
            # External employers always own their own postings.
            job.source = Job.JobSource.EMPLOYER
            job.created_by = request.user
            job.updated_by = request.user
            job.screening_questions = screening_questions
            job.save()
            messages.success(request, f"Job '{job.title}' was created successfully.")
            return redirect('/employers/jobs/')

        return render(request, 'hirenest/employer_job_form.html', {
            'form': form,
            'company': company,
            'screening_questions': screening_questions,
        })


class HirenestEmployerProfileView(HirenestEmployerRequiredMixin, View):
    """Employer / company profile for the HireNest workspace."""

    def get(self, request):
        return render(request, 'hirenest/employer_profile.html', {
            'company': _get_company_for_user(request.user),
        })

    def post(self, request):
        company = _get_company_for_user(request.user)
        if not company:
            messages.error(request, "Your employer account is not linked to a company yet.")
            return redirect('/employers/dashboard/')

        company.name = request.POST.get('name', company.name).strip() or company.name
        company.industry = request.POST.get('industry', company.industry).strip()
        company.website = request.POST.get('website', company.website).strip()
        company.location = request.POST.get('location', company.location).strip()
        description = request.POST.get('description', '').strip()
        if description:
            company.description = description
        company.save()

        messages.success(request, "Company profile updated successfully.")
        return redirect('/employers/profile/')


# ==============================================================================
# ADMIN-ONLY APPROVALS PAGE (HireNest side)
# ==============================================================================
class HirenestEmployerApprovalsView(HirenestSuperAdminRequiredMixin, View):
    """Admin-only list of HireNest employer registrations with actions."""

    template_name = 'hirenest/employer_approvals.html'

    def get(self, request):
        status_filter = request.GET.get('status', 'PENDING').upper()
        if status_filter not in ('PENDING', 'ACTIVE', 'REJECTED', 'SUSPENDED', 'ALL'):
            status_filter = 'PENDING'

        employers = serialize_employer_queryset(
            get_hirenest_employers_queryset(status_filter)
        )
        return render(request, self.template_name, {
            'employers': employers,
            'status_filter': status_filter,
            'counts': employer_status_counts(),
        })

    def post(self, request):
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        if not user_id or not action:
            messages.error(request, "Invalid request parameters.")
            return redirect('/employers/approvals/')

        target = get_object_or_404(
            get_hirenest_employers_queryset(), pk=user_id
        )
        ok, message = apply_employer_action(target, action)
        if ok:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect('/employers/approvals/')


# ==============================================================================
# SECURE SERVER-TO-SERVER ADMIN API (consumed by the TalentVault Admin Portal)
# ==============================================================================
def _is_hirenest_admin(request):
    """
    Authorize an admin API request.

    Accepts either the shared server-side secret (TalentVault Admin Portal) or
    an authenticated HireNest super-admin session. The secret is compared in
    constant time and is never logged or returned to clients.
    """
    expected = getattr(settings, 'HIRENEST_ADMIN_API_KEY', '') or ''
    provided = request.META.get('HTTP_X_HIRENEST_ADMIN_KEY', '') or ''
    if expected and provided and constant_time_compare(provided, expected):
        return True

    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return bool(
            getattr(user, 'role', None) == User.Role.SUPER_ADMIN
            or getattr(user, 'is_superuser', False)
            or getattr(user, 'is_staff', False)
        )
    return False


@method_decorator(csrf_exempt, name='dispatch')
class HirenestEmployerApprovalsAPIView(View):
    """
    Secure JSON API for HireNest employer approvals.

    GET  /api/admin/employer-approvals/?status=PENDING  -> list employers
    POST /api/admin/employer-approvals/<uuid>/          -> approve/reject
    """

    def get(self, request):
        if not _is_hirenest_admin(request):
            return JsonResponse({'error': 'Forbidden'}, status=403)

        status_filter = request.GET.get('status', 'ALL').upper()
        if status_filter not in ('PENDING', 'ACTIVE', 'REJECTED', 'SUSPENDED', 'ALL'):
            status_filter = 'ALL'

        employers = serialize_employer_queryset(
            get_hirenest_employers_queryset(status_filter)
        )
        return JsonResponse({
            'source': 'hirenest',
            'status_filter': status_filter,
            'count': len(employers),
            'employers': employers,
        })

    def post(self, request, user_id=None):
        if not _is_hirenest_admin(request):
            return JsonResponse({'error': 'Forbidden'}, status=403)

        if user_id is None:
            user_id = request.POST.get('user_id')

        payload = {}
        if request.body:
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                payload = {}

        action = payload.get('action') or request.POST.get('action')
        reason = payload.get('reason') or request.POST.get('reason', '')

        if not user_id or not action:
            return JsonResponse({'error': 'user_id and action are required.'}, status=400)

        target = get_object_or_404(get_hirenest_employers_queryset(), pk=user_id)
        ok, message = apply_employer_action(target, action, reason)
        if not ok:
            return JsonResponse({'error': message}, status=400)

        return JsonResponse({
            'status': 'ok',
            'message': message,
            'employer': serialize_employer(target),
        })


# ==============================================================================
# SECURE SERVER-TO-SERVER ADMIN JOBS API (TalentVault Admin Portal integration)
# ==============================================================================
def _parse_json_body(request):
    """Best-effort JSON (or form) body parsing for the admin jobs API."""
    if request.body:
        try:
            return json.loads(request.body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return {}
    return request.POST.dict()


@method_decorator(csrf_exempt, name='dispatch')
class HirenestAdminJobsAPIView(View):
    """
    Secure JSON API for HireNest admin-owned job postings.

    Only postings with ``source=ADMIN`` can be read or changed here, so admin
    management never touches an external employer's postings.

    GET    /api/admin/jobs/?status=ACTIVE   -> list admin jobs
    GET    /api/admin/jobs/<uuid>/          -> admin job detail
    POST   /api/admin/jobs/                 -> create an admin job
    POST   /api/admin/jobs/<uuid>/          -> lifecycle action (publish/pause/...)
    PUT    /api/admin/jobs/<uuid>/          -> update an admin job
    DELETE /api/admin/jobs/<uuid>/          -> delete an admin job
    """

    def _forbidden(self):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    def get(self, request, job_id=None):
        if not _is_hirenest_admin(request):
            return self._forbidden()

        if job_id is not None:
            job = get_object_or_404(get_admin_jobs_queryset(), pk=job_id)
            return JsonResponse({'source': 'hirenest', 'job': serialize_job(job)})

        status_filter = request.GET.get('status', 'ALL').upper()
        jobs = get_admin_jobs_queryset(status_filter)
        return JsonResponse({
            'source': 'hirenest',
            'status_filter': status_filter,
            'count': jobs.count(),
            'jobs': serialize_job_queryset(jobs),
        })

    def post(self, request, job_id=None):
        if not _is_hirenest_admin(request):
            return self._forbidden()

        payload = _parse_json_body(request)

        if job_id is not None:
            job = get_object_or_404(get_admin_jobs_queryset(), pk=job_id)
            ok, message = apply_admin_job_action(job, payload.get('action'))
            if not ok:
                return JsonResponse({'error': message}, status=400)
            return JsonResponse({'status': 'ok', 'message': message, 'job': serialize_job(job)})

        job, errors = create_admin_job(payload)
        if errors:
            return JsonResponse({'error': ' '.join(errors), 'errors': errors}, status=400)
        return JsonResponse({
            'status': 'ok',
            'message': f"Job '{job.title}' posted to HireNest Australia.",
            'job': serialize_job(job),
        }, status=201)

    def put(self, request, job_id=None):
        return self._update(request, job_id)

    def patch(self, request, job_id=None):
        return self._update(request, job_id)

    def _update(self, request, job_id):
        if not _is_hirenest_admin(request):
            return self._forbidden()
        if job_id is None:
            return JsonResponse({'error': 'job_id is required.'}, status=400)

        job = get_object_or_404(get_admin_jobs_queryset(), pk=job_id)
        payload = _parse_json_body(request)
        job, errors = update_admin_job(job, payload)
        if errors:
            return JsonResponse({'error': ' '.join(errors), 'errors': errors}, status=400)
        return JsonResponse({
            'status': 'ok',
            'message': f"Job '{job.title}' updated.",
            'job': serialize_job(job),
        })

    def delete(self, request, job_id=None):
        if not _is_hirenest_admin(request):
            return self._forbidden()
        if job_id is None:
            return JsonResponse({'error': 'job_id is required.'}, status=400)

        job = get_object_or_404(get_admin_jobs_queryset(), pk=job_id)
        title = job.title
        job.delete()
        return JsonResponse({'status': 'ok', 'message': f"Job '{title}' deleted."})


# ==============================================================================
# SECURE SERVER-TO-SERVER ADMIN APPLICATIONS API (TalentVault Admin Portal)
# ==============================================================================
@method_decorator(csrf_exempt, name='dispatch')
class HirenestAdminApplicationsAPIView(View):
    """
    Secure JSON API for HireNest candidate applications.

    GET /api/admin/applications/?status=&job=&q=  -> list applications
    GET /api/admin/applications/<uuid>/           -> application detail

    Only the shared server-side secret or an authenticated HireNest super-admin
    session can read these records. The resume URL is a short-lived presigned
    URL generated server-side; no secret is ever returned to the browser.
    """

    def _forbidden(self):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    def get(self, request, application_id=None):
        if not _is_hirenest_admin(request):
            return self._forbidden()

        if application_id is not None:
            application = get_object_or_404(
                get_hirenest_applications_queryset(), pk=application_id
            )
            return JsonResponse({
                'source': 'hirenest',
                'application': serialize_application(application, include_resume_url=True),
            })

        queryset = filter_applications(
            get_hirenest_applications_queryset(),
            status=request.GET.get('status'),
            job_id=request.GET.get('job'),
            query=request.GET.get('q'),
        )

        return JsonResponse({
            'source': 'hirenest',
            'count': queryset.count(),
            'applications': serialize_application_queryset(queryset),
        })


@method_decorator(csrf_exempt, name='dispatch')
class HirenestAdminCandidatesCreateAPIView(View):
    """
    Secure JSON API for creating candidate profiles in the HireNest database only
    (consumed by TalentVault Admin Portal via HireNest Candidate Parser).

    POST /api/admin/candidates/ -> create candidate profile
    """
    def _forbidden(self):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    def post(self, request):
        if not _is_hirenest_admin(request):
            return self._forbidden()

        try:
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST
        except Exception:
            data = request.POST

        email = (data.get('email') or '').strip().lower()
        phone = (data.get('phone_number') or data.get('phone') or '').strip()
        full_name = (data.get('full_name') or 'Candidate').strip()
        ignore_duplicate = str(data.get('ignore_duplicate', 'false')).lower() in ('true', '1', 'yes')

        if not email:
            return JsonResponse({'success': False, 'message': 'Email address is required.'}, status=400)

        # Duplicate check in HireNest DB
        from apps.candidates.models import CandidateProfile, CandidateSkill
        existing_user = None
        if phone:
            existing_user = User.objects.filter(Q(email=email) | Q(phone_number=phone)).first()
        else:
            existing_user = User.objects.filter(email=email).first()

        if existing_user and not ignore_duplicate:
            existing_profile = getattr(existing_user, 'candidate_profile', None)
            return JsonResponse({
                "success": False,
                "stage": "duplicate",
                "message": "Candidate profile with this email or phone number already exists in HireNest database.",
                "duplicate_candidate": {
                    "candidate_id": str(existing_profile.id) if existing_profile else "",
                    "name": existing_profile.full_name if existing_profile else "Unknown",
                    "email": existing_user.email,
                    "phone": existing_user.phone_number or "Not specified",
                    "current_company": existing_profile.current_company if existing_profile else "Not specified"
                }
            }, status=400)

        if existing_user and ignore_duplicate:
            import time
            if '@' in email:
                parts = email.split('@')
                email = f"{parts[0]}+anyway{int(time.time())}@{parts[1]}"
            else:
                email = f"{email}+anyway{int(time.time())}"

        try:
            with transaction.atomic():
                user = User.objects.create(
                    email=email,
                    role=User.Role.CANDIDATE,
                    phone_number=phone if phone else None,
                    first_name=full_name.split()[0] if full_name else '',
                    last_name=" ".join(full_name.split()[1:]) if len(full_name.split()) > 1 else ''
                )
                user.set_unusable_password()
                user.save()

                profile = CandidateProfile.objects.create(
                    user=user,
                    full_name=full_name,
                    current_company=(data.get('current_company') or '').strip(),
                    current_designation=(data.get('current_designation') or '').strip(),
                    total_experience=float(data.get('total_experience') or 0.0),
                    location=(data.get('location') or 'Australia').strip(),
                    summary=(data.get('summary') or '').strip(),
                    linkedin_url=(data.get('linkedin_url') or '').strip() or None,
                    portfolio_url=(data.get('portfolio_url') or '').strip() or None,
                    notice_period=int(data.get('notice_period') or 30),
                )

                curr_sal = data.get('current_salary')
                if curr_sal not in (None, ''):
                    try:
                        profile.current_salary = float(curr_sal)
                    except ValueError:
                        pass

                exp_sal = data.get('expected_salary')
                if exp_sal not in (None, ''):
                    try:
                        profile.expected_salary = float(exp_sal)
                    except ValueError:
                        pass
                profile.save()

                skills = data.get('skills')
                if skills:
                    if isinstance(skills, str):
                        skill_list = [s.strip() for s in skills.split(',') if s.strip()]
                    elif isinstance(skills, list):
                        skill_list = [str(s).strip() for s in skills if str(s).strip()]
                    else:
                        skill_list = []
                    for s in skill_list:
                        CandidateSkill.objects.get_or_create(profile=profile, skill_name=s[:100])

                return JsonResponse({
                    "success": True,
                    "candidate_id": str(profile.id),
                    "message": "Candidate profile successfully created in HireNest database."
                })
        except Exception as exc:
            return JsonResponse({
                "success": False,
                "message": f"Failed to create candidate in HireNest database: {str(exc)}"
            }, status=500)
