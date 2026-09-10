import json
import logging
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.jobs.models import Job, JobSkill
from apps.companies.models import Company, CompanyMember
from apps.candidates.models import CandidateProfile, CandidateSkill, SavedJob
from apps.applications.models import Application, ApplicationHistory

from .services import (
    AUSTRALIAN_STATES,
    POPULAR_CITIES,
    POPULAR_SEARCH_CHIPS,
    POPULAR_AU_LOCATIONS,
    ALL_AUSTRALIAN_LOCATIONS,
    AUSTRALIAN_CLASSIFICATIONS,
    AU_EMPLOYMENT_TYPES,
    AU_SALARY_BENCHMARKS,
    AU_CAREER_ARTICLES,
    AU_RESOURCES,
    get_australian_jobs_queryset,
    normalize_australian_location,
    get_candidate_recommended_jobs,
)
from .forms import (
    CandidateOnboardingForm,
    CandidateProfileForm,
    EmployerRegistrationForm,
    EmployerLoginForm,
    JobApplicationForm,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. HOMEPAGE / CANDIDATE LANDING VIEW (AUSTRALIA MARKETPLACE ONLY)
# ==============================================================================
class HirenestLandingView(View):
    """
    Public Homepage for HireNest Australia (hirenest.com.au).
    Strictly filters to the Australia Job Marketplace.
    Features hero search, popular categories with real counts, Australian city cards,
    featured jobs, top employers, and career insights.
    """
    def get(self, request):
        active_jobs = get_australian_jobs_queryset().order_by('-created_at')

        # Compute dynamic job counts per classification
        classifications_with_counts = []
        for cat in AUSTRALIAN_CLASSIFICATIONS:
            count = active_jobs.filter(
                Q(department__icontains=cat['name']) |
                Q(title__icontains=cat['name'].split('&')[0].strip()) |
                Q(company__industry__icontains=cat['name'].split('&')[0].strip())
            ).count()
            cat_copy = dict(cat)
            cat_copy['live_count'] = count if count > 0 else cat['roles_count']
            classifications_with_counts.append(cat_copy)

        # Compute dynamic job counts per city
        cities_with_counts = []
        for city in POPULAR_CITIES:
            c_count = active_jobs.filter(
                Q(location__icontains=city['name']) |
                Q(location__icontains=city['state'])
            ).count()
            city_copy = dict(city)
            city_copy['live_count'] = f"{c_count} jobs" if c_count > 0 else "500+ jobs"
            cities_with_counts.append(city_copy)

        # Candidate personalized recommendations if authenticated
        recommended_jobs = []
        saved_job_ids = set()
        applied_job_ids = set()
        candidate_profile = None

        if request.user.is_authenticated and request.user.role == User.Role.CANDIDATE:
            try:
                candidate_profile = request.user.candidate_profile
                recommended_jobs = get_candidate_recommended_jobs(candidate_profile, limit=6)
                saved_job_ids = set(SavedJob.objects.filter(candidate=candidate_profile).values_list('job_id', flat=True))
                applied_job_ids = set(Application.objects.filter(candidate=candidate_profile).values_list('job_id', flat=True))
            except Exception as e:
                logger.error(f"Error fetching candidate profile: {e}")

        featured_jobs = recommended_jobs if recommended_jobs else list(active_jobs[:6])
        featured_companies = Company.objects.filter(jobs__in=active_jobs).annotate(
            active_jobs_count=Count('jobs', filter=Q(jobs__status='ACTIVE'))
        ).order_by('-active_jobs_count')[:8]

        context = {
            'popular_chips': POPULAR_SEARCH_CHIPS,
            'popular_locations': POPULAR_AU_LOCATIONS,
            'all_locations': ALL_AUSTRALIAN_LOCATIONS,
            'classifications': classifications_with_counts,
            'employment_types': AU_EMPLOYMENT_TYPES,
            'cities': cities_with_counts,
            'featured_jobs': featured_jobs,
            'featured_companies': featured_companies,
            'total_active_jobs': active_jobs.count(),
            'career_articles': AU_CAREER_ARTICLES[:3],
            'salaries': AU_SALARY_BENCHMARKS[:4],
            'saved_job_ids': saved_job_ids,
            'applied_job_ids': applied_job_ids,
            'candidate_profile': candidate_profile,
        }
        return render(request, 'hirenest/landing.html', context)


# ==============================================================================
# 2. AUSTRALIAN JOB SEARCH & ADVANCED FILTER VIEW
# ==============================================================================
class HirenestJobSearchView(ListView):
    """
    Search and filter active Australian jobs with state, work arrangement,
    job type, classification, and salary filters.
    Strictly enforced at the database level for the Australia marketplace only.
    """
    model = Job
    template_name = 'hirenest/jobs_search.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        qs = get_australian_jobs_queryset().order_by('-created_at')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(company__name__icontains=q) |
                Q(required_skills_text__icontains=q) |
                Q(department__icontains=q)
            )

        location = self.request.GET.get('location', '').strip()
        if location:
            if 'REMOTE' in location.upper():
                qs = qs.filter(Q(work_mode='REMOTE') | Q(is_remote=True) | Q(location__icontains='Remote'))
            else:
                qs = qs.filter(location__icontains=location)

        state = self.request.GET.get('state', '').strip()
        if state:
            qs = qs.filter(
                Q(location__icontains=f" {state}") |
                Q(location__icontains=f",{state}") |
                Q(location__icontains=state)
            )

        job_types = self.request.GET.getlist('job_type')
        if job_types:
            qs = qs.filter(job_type__in=job_types)

        work_modes = self.request.GET.getlist('work_mode')
        if work_modes:
            if 'REMOTE' in work_modes:
                qs = qs.filter(Q(work_mode__in=work_modes) | Q(is_remote=True))
            else:
                qs = qs.filter(work_mode__in=work_modes)

        classification = self.request.GET.get('classification', '').strip()
        if classification:
            qs = qs.filter(
                Q(department__icontains=classification) |
                Q(company__industry__icontains=classification)
            )

        min_salary = self.request.GET.get('min_salary', '').strip()
        if min_salary:
            try:
                val = Decimal(min_salary)
                qs = qs.filter(Q(max_salary__gte=val) | Q(min_salary__gte=val))
            except Exception:
                pass

        max_salary = self.request.GET.get('max_salary', '').strip()
        if max_salary:
            try:
                val = Decimal(max_salary)
                qs = qs.filter(min_salary__lte=val)
            except Exception:
                pass

        sort_by = self.request.GET.get('sort_by', 'newest')
        if sort_by == 'salary_high':
            qs = qs.order_by('-max_salary', '-min_salary')
        elif sort_by == 'salary_low':
            qs = qs.order_by('min_salary', 'max_salary')
        elif sort_by == 'relevance' and q:
            qs = qs.order_by('-created_at')
        else:
            qs = qs.order_by('-created_at')

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context['location'] = self.request.GET.get('location', '')
        context['selected_state'] = self.request.GET.get('state', '')
        context['selected_job_types'] = self.request.GET.getlist('job_type')
        context['selected_work_modes'] = self.request.GET.getlist('work_mode')
        context['selected_classification'] = self.request.GET.get('classification', '')
        context['min_salary'] = self.request.GET.get('min_salary', '')
        context['max_salary'] = self.request.GET.get('max_salary', '')
        context['sort_by'] = self.request.GET.get('sort_by', 'newest')

        context['states'] = AUSTRALIAN_STATES
        context['classifications'] = AUSTRALIAN_CLASSIFICATIONS
        context['locations_list'] = POPULAR_AU_LOCATIONS
        context['all_locations'] = ALL_AUSTRALIAN_LOCATIONS
        context['employment_types'] = AU_EMPLOYMENT_TYPES

        # Dynamic live total count
        context['total_filtered_jobs'] = self.get_queryset().count()

        saved_job_ids = set()
        applied_job_ids = set()
        recommended_job_ids = set()

        if self.request.user.is_authenticated and self.request.user.role == User.Role.CANDIDATE:
            try:
                profile = self.request.user.candidate_profile
                saved_job_ids = set(SavedJob.objects.filter(candidate=profile).values_list('job_id', flat=True))
                applied_job_ids = set(Application.objects.filter(candidate=profile).values_list('job_id', flat=True))
                rec_jobs = get_candidate_recommended_jobs(profile, limit=20)
                recommended_job_ids = {j.id for j in rec_jobs}
            except Exception:
                pass

        context['saved_job_ids'] = saved_job_ids
        context['applied_job_ids'] = applied_job_ids
        context['recommended_job_ids'] = recommended_job_ids
        return context


# ==============================================================================
# 3. JOB DETAIL & PREVIEW VIEW
# ==============================================================================
class HirenestJobDetailView(View):
    """
    Detailed view for an Australian job posting with full description,
    AUD remuneration, skills chips, JD file preview/download, and actions.
    """
    def get(self, request, pk):
        job = get_object_or_404(get_australian_jobs_queryset(), pk=pk)

        is_saved = False
        has_applied = False
        if request.user.is_authenticated and request.user.role == User.Role.CANDIDATE:
            try:
                profile = request.user.candidate_profile
                is_saved = SavedJob.objects.filter(candidate=profile, job=job).exists()
                has_applied = Application.objects.filter(candidate=profile, job=job).exists()
            except Exception:
                pass

        similar_jobs = get_australian_jobs_queryset().exclude(pk=job.pk).filter(
            Q(department=job.department) |
            Q(company__industry=job.company.industry) |
            Q(location__icontains=job.location.split()[-1] if job.location else '')
        )[:4]

        jd_file = getattr(job, 'jd_file', None)
        jd_file_name = jd_file.name.split('/')[-1] if jd_file else None
        is_pdf = jd_file_name.lower().endswith('.pdf') if jd_file_name else False

        context = {
            'job': job,
            'is_saved': is_saved,
            'has_applied': has_applied,
            'similar_jobs': similar_jobs,
            'jd_file': jd_file,
            'jd_file_name': jd_file_name,
            'is_pdf': is_pdf,
            'share_url': request.build_absolute_uri(),
        }
        return render(request, 'hirenest/job_detail.html', context)


# ==============================================================================
# 4. DIRECT JOB APPLICATION VIEW
# ==============================================================================
class HirenestJobApplyView(LoginRequiredMixin, View):
    """
    Candidate direct application submission for a specific Australian job.
    """
    login_url = '/login/'

    def get(self, request, pk):
        job = get_object_or_404(get_australian_jobs_queryset(), pk=pk)
        profile, _ = CandidateProfile.objects.get_or_create(
            user=request.user,
            defaults={'full_name': request.user.get_full_name() or request.user.email}
        )

        has_applied = Application.objects.filter(job=job, candidate=profile).exists()
        if has_applied:
            messages.info(request, f"You have already applied for '{job.title}'. Check status in your applications.")
            return redirect('/applications/')

        context = {
            'job': job,
            'profile': profile,
            'locations': POPULAR_AU_LOCATIONS,
        }
        return render(request, 'hirenest/job_apply.html', context)

    def post(self, request, pk):
        job = get_object_or_404(get_australian_jobs_queryset(), pk=pk)
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)

        form = JobApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            full_name = form.cleaned_data['full_name']
            phone_number = form.cleaned_data['phone_number']
            location = form.cleaned_data['location']
            total_experience = form.cleaned_data.get('total_experience') or Decimal('0.0')
            expected_salary = form.cleaned_data.get('expected_salary')
            notice_period = form.cleaned_data.get('notice_period') or 30
            cover_letter = form.cleaned_data.get('cover_letter', '')
            resume_file = form.cleaned_data.get('resume_file')

            # Update Candidate User & Profile
            if ' ' in full_name:
                request.user.first_name, request.user.last_name = full_name.split(' ', 1)
            else:
                request.user.first_name = full_name
            request.user.phone_number = phone_number
            request.user.save()

            profile.full_name = full_name
            profile.location = location
            profile.total_experience = total_experience
            if expected_salary:
                profile.expected_salary = expected_salary
            profile.notice_period = notice_period
            if resume_file:
                profile.resume = resume_file
            profile.save()

            # Create or get Application in existing TalentVault DB
            app, created = Application.objects.get_or_create(
                job=job,
                candidate=profile,
                defaults={
                    'cover_letter': cover_letter,
                    'stage': Application.ApplicationStage.OPEN,
                    'in_pipeline': True,
                }
            )

            if created:
                ApplicationHistory.objects.create(
                    application=app,
                    from_stage=Application.ApplicationStage.OPEN,
                    to_stage=Application.ApplicationStage.OPEN,
                    notes="Application submitted directly via HireNest Australia portal."
                )
                messages.success(request, f"Your application for '{job.title}' was submitted successfully!")
            else:
                messages.info(request, f"You have already applied for '{job.title}'.")

            return redirect('/applications/')

        context = {
            'job': job,
            'profile': profile,
            'form': form,
            'locations': POPULAR_AU_LOCATIONS,
        }
        return render(request, 'hirenest/job_apply.html', context)


# ==============================================================================
# 5. CANDIDATE ONBOARDING (HIRENEST AUSTRALIA BRANDED PROFILE FLOW)
# ==============================================================================
class HirenestCandidateOnboardingView(LoginRequiredMixin, View):
    """
    Branded HireNest Australia candidate onboarding.

    Collects the candidate's core profile details and work preferences after a
    successful "Continue with Google" sign-in. Candidates whose profile is
    already complete are sent straight to their dashboard.
    """
    login_url = '/login/'

    def _form_context(self, request, profile, form):
        return {
            'form': form,
            'profile': profile,
            'locations': POPULAR_AU_LOCATIONS,
            'all_locations': ALL_AUSTRALIAN_LOCATIONS,
            'classifications': AUSTRALIAN_CLASSIFICATIONS,
            'employment_types': AU_EMPLOYMENT_TYPES,
        }

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(
            user=request.user,
            defaults={'full_name': request.user.get_full_name() or request.user.email}
        )
        if profile.is_onboarding_complete and request.GET.get('edit') != '1':
            return redirect('/dashboard/')

        form = CandidateOnboardingForm(initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'phone_number': request.user.phone_number or '',
            'location': profile.location or '',
            'citizenship': profile.citizenship,
            'preferred_job_category': profile.department or '',
            'work_type': profile.employment_type or '',
            'preferred_job_role': profile.preferred_job_role or '',
        })
        return render(request, 'hirenest/candidate_onboarding.html', self._form_context(request, profile, form))

    def post(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(
            user=request.user,
            defaults={'full_name': request.user.get_full_name() or request.user.email}
        )
        form = CandidateOnboardingForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            first_name = cd['first_name'].strip()
            last_name = cd['last_name'].strip()
            phone_number = cd['phone_number'].strip()
            location = normalize_australian_location(cd['location'].strip()) or 'Sydney NSW'
            citizenship = cd['citizenship']
            category = cd['preferred_job_category']
            work_type = cd['work_type']
            role_title = (cd.get('preferred_job_role') or '').strip()

            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.phone_number = phone_number
            request.user.save(update_fields=['first_name', 'last_name', 'phone_number'])

            profile.full_name = f"{first_name} {last_name}".strip()
            profile.location = location
            profile.department = category
            profile.employment_type = work_type
            profile.preferred_location = location
            profile.work_permit_countries = [citizenship] if citizenship else []
            if role_title:
                profile.preferred_job_role = role_title
            if cd.get('resume'):
                profile.resume = cd['resume']

            if not isinstance(profile.parsed_json, dict):
                profile.parsed_json = {}
            profile.parsed_json['onboarding_answers'] = {
                'citizenship': citizenship,
                'preferred_job_category': category,
                'work_type': work_type,
                'role_title': role_title,
                'location': location,
                'completed_at': timezone.now().isoformat(),
            }
            profile.save()

            messages.success(request, "Your HireNest Australia profile is complete. Start exploring jobs matched to you!")
            return redirect('/dashboard/')

        messages.error(request, "Please review the highlighted fields and try again.")
        return render(request, 'hirenest/candidate_onboarding.html', self._form_context(request, profile, form))


# ==============================================================================
# 6. AUSTRALIAN LOCATION LOOKUP API
# ==============================================================================


class AustralianLocationsLookupView(View):
    """
    Autocomplete/Search endpoint for Australian locations and cities.
    """
    def get(self, request):
        q = request.GET.get('q', '').strip().lower()
        if not q:
            return JsonResponse({'locations': ALL_AUSTRALIAN_LOCATIONS[:15]})

        matched = [
            loc for loc in ALL_AUSTRALIAN_LOCATIONS
            if q in loc['name'].lower() or q in loc['state'].lower() or q in loc['label'].lower()
        ]
        return JsonResponse({'locations': matched[:20]})


# ==============================================================================
# 7. CANDIDATE DASHBOARD & WORKSPACE
# ==============================================================================
class HirenestCandidateDashboardView(LoginRequiredMixin, View):
    """
    Personalized Candidate Dashboard on HireNest Australia.
    Sections:
    - Recommended Jobs for You (scored from preferences)
    - Recent Australian Jobs
    - Saved Jobs
    - My Applications
    - Profile Completion & Preference Editor
    """
    login_url = '/login/'

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(
            user=request.user,
            defaults={'full_name': request.user.get_full_name() or request.user.email}
        )

        recommended_jobs = get_candidate_recommended_jobs(profile, limit=8)
        applications = Application.objects.filter(candidate=profile).select_related('job', 'job__company').order_by('-created_at')
        saved_jobs = SavedJob.objects.filter(candidate=profile).select_related('job', 'job__company').order_by('-created_at')

        saved_job_ids = set(saved_jobs.values_list('job_id', flat=True))
        applied_job_ids = set(applications.values_list('job_id', flat=True))

        context = {
            'profile': profile,
            'recommended_jobs': recommended_jobs,
            'applications': applications[:5],
            'saved_jobs': saved_jobs[:5],
            'total_applications_count': applications.count(),
            'total_saved_count': saved_jobs.count(),
            'saved_job_ids': saved_job_ids,
            'applied_job_ids': applied_job_ids,
            'all_locations': ALL_AUSTRALIAN_LOCATIONS,
            'classifications': AUSTRALIAN_CLASSIFICATIONS,
            'employment_types': AU_EMPLOYMENT_TYPES,
        }
        return render(request, 'hirenest/candidate_dashboard.html', context)


# ==============================================================================
# 8. CANDIDATE AUTHENTICATION PAGES (CONTINUE WITH GOOGLE)
# ==============================================================================
class HirenestCandidateRegisterView(View):
    """
    Candidate registration landing page.

    Registration happens exclusively through "Continue with Google" OAuth. A new
    candidate account is created automatically and the candidate is taken into
    the branded onboarding flow. Email/password and OTP registration are removed.
    """
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        return render(request, 'hirenest/candidate_register.html', {
            'locations': POPULAR_AU_LOCATIONS,
            'next': request.GET.get('next', ''),
        })

    def post(self, request):
        # No email/password or OTP registration. Always start Google OAuth.
        return redirect('/accounts/google/login/')


class HirenestCandidateLoginView(View):
    """
    Candidate login page. Sign-in happens exclusively through Google OAuth.
    """
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        next_url = request.GET.get('next', '')
        return render(request, 'hirenest/candidate_login.html', {'next': next_url})

    def post(self, request):
        return redirect('/accounts/google/login/')


class HirenestCandidateLogoutView(View):
    """Logs out candidate and redirects to homepage."""
    def get(self, request):
        logout(request)
        messages.info(request, "You have been logged out of HireNest Australia.")
        return redirect('/')


class HirenestCandidateProfileView(LoginRequiredMixin, View):
    """Candidate profile & resume management."""
    login_url = '/login/'

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(
            user=request.user,
            defaults={'full_name': request.user.get_full_name() or request.user.email}
        )
        context = {
            'profile': profile,
            'locations': POPULAR_AU_LOCATIONS,
            'all_locations': ALL_AUSTRALIAN_LOCATIONS,
            'classifications': AUSTRALIAN_CLASSIFICATIONS,
            'employment_types': AU_EMPLOYMENT_TYPES,
        }
        return render(request, 'hirenest/candidate_profile.html', context)

    def post(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)

        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        location = request.POST.get('location', '').strip()
        current_designation = request.POST.get('current_designation', '').strip()
        current_company = request.POST.get('current_company', '').strip()
        total_exp = request.POST.get('total_experience', '').strip()
        expected_sal = request.POST.get('expected_salary', '').strip()
        notice_period = request.POST.get('notice_period', '').strip()
        summary = request.POST.get('summary', '').strip()
        skills_text = request.POST.get('skills', '').strip()

        # Update User
        if full_name:
            if ' ' in full_name:
                request.user.first_name, request.user.last_name = full_name.split(' ', 1)
            else:
                request.user.first_name = full_name
        request.user.phone_number = phone_number
        request.user.save()

        # Update Profile
        profile.full_name = full_name
        profile.location = location
        profile.current_designation = current_designation
        profile.current_company = current_company
        profile.summary = summary

        if total_exp:
            try:
                profile.total_experience = Decimal(total_exp)
            except Exception:
                pass
        if expected_sal:
            try:
                profile.expected_salary = Decimal(expected_sal)
            except Exception:
                pass
        if notice_period:
            try:
                profile.notice_period = int(notice_period)
            except Exception:
                pass

        if 'resume' in request.FILES:
            profile.resume = request.FILES['resume']

        profile.save()

        # Update skills
        if skills_text:
            profile.skills.all().delete()
            for s in [x.strip() for x in skills_text.split(',') if x.strip()]:
                CandidateSkill.objects.create(profile=profile, skill_name=s)

        messages.success(request, "Your profile has been updated successfully.")
        return redirect('/profile/')


class HirenestCandidateDeleteAccountView(LoginRequiredMixin, View):
    """
    Confirmation + secure deletion of the authenticated candidate's own account.

    Only the logged-in candidate can act on their own account (there is no user
    identifier in the URL), so candidates can never delete or modify another
    user's account. Deletion cascades through the existing CandidateProfile
    relationships (skills, experience, education, projects, certifications,
    saved jobs, applications, tags, notifications).
    """
    login_url = '/login/'

    def _block_non_candidate(self, request):
        if request.user.role != User.Role.CANDIDATE:
            messages.error(request, "Only candidate accounts can be deleted from this page.")
            return redirect('/')
        return None

    def get(self, request):
        blocked = self._block_non_candidate(request)
        if blocked:
            return blocked
        profile = getattr(request.user, 'candidate_profile', None)
        return render(request, 'hirenest/candidate_delete_account.html', {'profile': profile})

    def post(self, request):
        blocked = self._block_non_candidate(request)
        if blocked:
            return blocked

        if request.POST.get('confirm_delete') != 'yes':
            messages.error(request, "Please confirm the deletion before continuing.")
            return redirect('/profile/delete/')

        user = request.user
        profile = getattr(user, 'candidate_profile', None)

        # Best-effort removal of uploaded files before the DB rows are deleted.
        if profile is not None:
            for field_name in ('resume', 'original_file', 'generated_resume', 'profile_photo'):
                file_field = getattr(profile, field_name, None)
                if file_field and getattr(file_field, 'name', ''):
                    try:
                        file_field.storage.delete(file_field.name)
                    except Exception:
                        logger.warning("Could not delete %s for candidate %s", field_name, user.pk)

        with transaction.atomic():
            user.delete()

        logout(request)
        messages.success(request, "Your HireNest Australia candidate account has been permanently deleted.")
        return redirect('/')


class HirenestCandidateApplicationsView(LoginRequiredMixin, View):
    """Candidate applications tracking."""
    login_url = '/login/'

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        applications = Application.objects.filter(candidate=profile).select_related('job', 'job__company').order_by('-created_at')

        context = {
            'applications': applications,
        }
        return render(request, 'hirenest/candidate_applications.html', context)


class HirenestCandidateSavedJobsView(LoginRequiredMixin, View):
    """Candidate saved / bookmarked jobs."""
    login_url = '/login/'

    def get(self, request):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        saved_jobs = SavedJob.objects.filter(candidate=profile).select_related('job', 'job__company').order_by('-created_at')

        context = {
            'saved_jobs': saved_jobs,
        }
        return render(request, 'hirenest/candidate_saved_jobs.html', context)


class HirenestToggleSaveJobView(LoginRequiredMixin, View):
    """AJAX endpoint to save/unsave a job."""
    login_url = '/login/'

    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST

        job_id = data.get('job_id')
        if not job_id:
            return JsonResponse({'error': 'Job ID required'}, status=400)

        job = get_object_or_404(Job, pk=job_id)
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)

        saved = SavedJob.objects.filter(candidate=profile, job=job).first()
        if saved:
            saved.delete()
            return JsonResponse({'status': 'removed', 'is_saved': False})
        else:
            SavedJob.objects.create(candidate=profile, job=job)
            return JsonResponse({'status': 'saved', 'is_saved': True})


# ==============================================================================
# 9. EMPLOYER SUITE & TALENTVAULT WORKSPACE REDIRECTION VIEWS
# ==============================================================================
class HirenestEmployerLandingView(View):
    """Public Employer Landing page for HireNest Australia."""
    def get(self, request):
        return render(request, 'hirenest/employer_landing.html')


class HirenestEmployerRegisterView(View):
    """Employer registration on HireNest Australia."""
    def get(self, request):
        if request.user.is_authenticated and request.user.role in [User.Role.RECRUITER, User.Role.COMPANY_ADMIN]:
            target_url = getattr(settings, 'TALENTVAULT_RECRUITER_WORKSPACE_URL', '/dashboard/recruiter/')
            return redirect(target_url)
        return render(request, 'hirenest/employer_register.html', {'locations': POPULAR_AU_LOCATIONS})

    def post(self, request):
        form = EmployerRegistrationForm(request.POST)
        if form.is_valid():
            org_name = form.cleaned_data['org_name']
            email = form.cleaned_data['email']
            phone_number = form.cleaned_data['phone_number']
            hiring_type = form.cleaned_data.get('hiring_type', 'organization')
            industry = form.cleaned_data.get('industry', 'General Business')
            website = form.cleaned_data.get('website', '')
            location = form.cleaned_data.get('location', 'Sydney NSW')
            password = form.cleaned_data['password']

            # Create or get Company in shared DB
            slug = slugify(org_name)
            company, _ = Company.objects.get_or_create(
                name=org_name,
                defaults={
                    'slug': slug,
                    'industry': industry,
                    'website': website,
                    'location': location,
                    'description': f"{org_name} is an Australian employer.",
                    'is_active': True,
                }
            )

            # Create Recruiter User in shared DB
            user = User.objects.create_user(
                email=email,
                password=password,
                phone_number=phone_number,
                role=User.Role.RECRUITER,
                recruiter_status=User.RecruiterStatus.ACTIVE,
                is_active=True,
                is_verified=True,
            )

            CompanyMember.objects.create(
                company=company,
                user=user,
                role=CompanyMember.MemberRole.ADMIN,
                designation="Hiring Lead"
            )

            auth_user = authenticate(request, username=email, password=password)
            if auth_user:
                login(request, auth_user, backend='django.contrib.auth.backends.ModelBackend')
                target_url = getattr(settings, 'TALENTVAULT_RECRUITER_WORKSPACE_URL', '/dashboard/recruiter/')
                return redirect(target_url)

            return redirect('/employers/login/')

        errors = [err for err_list in form.errors.values() for err in err_list]
        return render(request, 'hirenest/employer_register.html', {
            'errors': errors,
            'locations': POPULAR_AU_LOCATIONS,
            'org_name': request.POST.get('org_name', ''),
            'email': request.POST.get('email', ''),
            'phone_number': request.POST.get('phone_number', ''),
            'hiring_type': request.POST.get('hiring_type', 'organization'),
            'industry': request.POST.get('industry', ''),
            'website': request.POST.get('website', ''),
            'location': request.POST.get('location', 'Sydney NSW'),
        })


class HirenestEmployerLoginView(View):
    """Employer login on HireNest Australia."""
    def get(self, request):
        if request.user.is_authenticated and request.user.role in [User.Role.RECRUITER, User.Role.COMPANY_ADMIN]:
            target_url = getattr(settings, 'TALENTVAULT_RECRUITER_WORKSPACE_URL', '/dashboard/recruiter/')
            return redirect(target_url)
        return render(request, 'hirenest/employer_login.html')

    def post(self, request):
        form = EmployerLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', True)

            user = authenticate(request, username=email, password=password)
            if user is not None and user.is_active:
                if user.role not in [User.Role.RECRUITER, User.Role.COMPANY_ADMIN, User.Role.SUPER_ADMIN]:
                    return render(request, 'hirenest/employer_login.html', {
                        'error': 'This account is registered as a Candidate. Please sign in via the Candidate Portal.',
                        'email': email,
                    })

                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                if not remember_me:
                    request.session.set_expiry(0)

                target_url = getattr(settings, 'TALENTVAULT_RECRUITER_WORKSPACE_URL', '/dashboard/recruiter/')
                return redirect(target_url)

            return render(request, 'hirenest/employer_login.html', {
                'error': 'Invalid work email or password. Please try again.',
                'email': email,
            })

        return render(request, 'hirenest/employer_login.html', {
            'error': 'Please provide a valid work email and password.',
        })


# ==============================================================================
# 10. INFORMATIONAL & DIRECTORY VIEWS
# ==============================================================================
class HirenestCompaniesView(ListView):
    """Australian companies directory."""
    model = Company
    template_name = 'hirenest/companies.html'
    context_object_name = 'companies'
    paginate_by = 12

    def get_queryset(self):
        au_jobs = get_australian_jobs_queryset()
        qs = Company.objects.filter(jobs__in=au_jobs).annotate(
            active_jobs_count=Count('jobs', filter=Q(jobs__status='ACTIVE'))
        ).order_by('-active_jobs_count', 'name')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(industry__icontains=q) | Q(location__icontains=q))
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        return context


class HirenestCompanyDetailView(View):
    """Company detail & active Australian job openings."""
    def get(self, request, slug):
        company = get_object_or_404(Company, slug=slug)
        active_jobs = get_australian_jobs_queryset().filter(company=company).order_by('-created_at')
        context = {
            'company': company,
            'active_jobs': active_jobs,
        }
        return render(request, 'hirenest/company_detail.html', context)


class HirenestSalaryGuideView(View):
    """Australian salary benchmark guide in AUD."""
    def get(self, request):
        q = request.GET.get('q', '').strip()
        salaries = AU_SALARY_BENCHMARKS
        if q:
            salaries = [s for s in salaries if q.lower() in s['role'].lower() or q.lower() in s['category'].lower()]
        context = {
            'salaries': salaries,
            'q': q,
        }
        return render(request, 'hirenest/salary_guide.html', context)


class HirenestCareerAdviceView(View):
    """Australian career advice and interview guides."""
    def get(self, request):
        context = {
            'articles': AU_CAREER_ARTICLES,
        }
        return render(request, 'hirenest/career_advice.html', context)


class HirenestResourcesView(View):
    """Job seeker Australian resources and templates."""
    def get(self, request):
        context = {
            'resources': AU_RESOURCES,
        }
        return render(request, 'hirenest/resources.html', context)
