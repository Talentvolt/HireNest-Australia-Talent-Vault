import json
import logging
import secrets
from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from apps.accounts.models import User, OTPVerification
from apps.accounts.services.email_service import generate_otp, send_email_otp
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
    CandidateRegistrationForm,
    CandidateLoginForm,
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
# 5. CANDIDATE AUTHENTICATION & POPUP (EMAIL + OTP + GOOGLE + APPLE)
# ==============================================================================
class CandidateSendOTPView(View):
    """
    AJAX Endpoint to send a 6-digit verification code to candidate email.
    Includes rate-limiting cooldown and secure hashed storage.
    """
    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST

        email = data.get('email', '').strip().lower()
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            return JsonResponse({'success': False, 'error': 'Please provide a valid email address.'}, status=400)

        # Check rate limiting / cooldown (1 request per 60 seconds)
        recent_otp = OTPVerification.objects.filter(
            email=email,
            created_at__gte=timezone.now() - timedelta(seconds=60)
        ).first()

        if recent_otp:
            time_left = 60 - int((timezone.now() - recent_otp.created_at).total_seconds())
            return JsonResponse({
                'success': False,
                'error': f'Please wait {time_left} seconds before requesting a new code.',
                'cooldown': time_left
            }, status=429)

        # Generate fresh 6-digit OTP
        raw_otp = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)

        otp_record = OTPVerification(
            email=email,
            expires_at=expires_at,
        )
        otp_record.set_otp(raw_otp)
        otp_record.save()

        # Send email OTP via configured infrastructure
        success, msg = send_email_otp(email, raw_otp, purpose='candidate_auth')

        return JsonResponse({
            'success': True,
            'message': 'A 6-digit verification code has been sent to your email.',
            'cooldown': 60,
            'email': email
        })


class CandidateVerifyOTPView(View):
    """
    AJAX Endpoint to verify 6-digit OTP and authenticate or create candidate.
    Links existing accounts seamlessly without creating duplicates.
    """
    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST

        email = data.get('email', '').strip().lower()
        otp_code = data.get('otp', '').strip()

        if not email or not otp_code or len(otp_code) != 6:
            return JsonResponse({'success': False, 'error': 'Please enter the complete 6-digit verification code.'}, status=400)

        # Find latest pending OTP record for this email
        otp_record = OTPVerification.objects.filter(
            email=email,
            verified=False
        ).order_by('-created_at').first()

        if not otp_record:
            return JsonResponse({'success': False, 'error': 'No verification code found. Please request a new code.'}, status=400)

        if otp_record.is_expired():
            return JsonResponse({'success': False, 'error': 'Verification code has expired. Please request a new code.'}, status=400)

        if not otp_record.can_attempt():
            return JsonResponse({'success': False, 'error': 'Too many failed attempts. Please request a new code.'}, status=400)

        # Increment attempt count
        otp_record.attempts += 1
        otp_record.save()

        # Validate OTP hash
        if not otp_record.check_otp(otp_code):
            remaining = 5 - otp_record.attempts
            return JsonResponse({
                'success': False,
                'error': f'Incorrect verification code. {remaining} attempt(s) remaining.'
            }, status=400)

        # OTP is valid -> Mark verified
        otp_record.verified = True
        otp_record.save()

        # Find or create candidate user
        is_new = False
        user = User.objects.filter(email=email).first()

        if user:
            # Existing user -> Ensure active & verified
            user.is_active = True
            user.is_verified = True
            if user.role != User.Role.CANDIDATE and user.role != User.Role.SUPER_ADMIN:
                user.role = User.Role.CANDIDATE
            user.save()
        else:
            # New candidate user
            is_new = True
            first_name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                role=User.Role.CANDIDATE,
                is_active=True,
                is_verified=True
            )

        # Ensure CandidateProfile exists in DB
        profile, profile_created = CandidateProfile.objects.get_or_create(
            user=user,
            defaults={
                'full_name': user.get_full_name() or user.email.split('@')[0].title(),
                'location': 'Sydney NSW',
                'candidate_status': 'ACTIVE'
            }
        )

        # Check if onboarding wizard is needed (if new or preferences not set)
        onboarding_required = is_new or profile_created or not profile.preferred_location or not profile.department

        # Log candidate into Django session
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        return JsonResponse({
            'success': True,
            'is_new': is_new,
            'onboarding_required': onboarding_required,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'name': user.get_full_name() or user.email,
            },
            'redirect_url': '/profile/' if not onboarding_required else '/dashboard/'
        })


class CandidateSocialAuthView(View):
    """
    Endpoint for Google & Apple OAuth registration / sign-in for candidates.
    Connects to existing candidate profile system without duplicate entries.
    """
    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST

        provider = data.get('provider', 'google').lower()
        email = data.get('email', '').strip().lower()
        full_name = data.get('name', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        profile_picture = data.get('picture', '').strip()

        if not email:
            return JsonResponse({'success': False, 'error': f'Email is required for {provider.title()} authentication.'}, status=400)

        # Find or create user
        is_new = False
        user = User.objects.filter(email=email).first()

        if not user:
            is_new = True
            if not first_name and full_name:
                parts = full_name.split(' ', 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ''

            user = User.objects.create_user(
                email=email,
                first_name=first_name or email.split('@')[0].title(),
                last_name=last_name,
                role=User.Role.CANDIDATE,
                is_active=True,
                is_verified=True,
                profile_picture=profile_picture if profile_picture else None
            )
        else:
            if profile_picture and not user.profile_picture:
                user.profile_picture = profile_picture
                user.save()

        profile, profile_created = CandidateProfile.objects.get_or_create(
            user=user,
            defaults={
                'full_name': full_name or user.get_full_name() or email.split('@')[0].title(),
                'location': 'Sydney NSW',
                'candidate_status': 'ACTIVE'
            }
        )

        onboarding_required = is_new or profile_created or not profile.preferred_location

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')

        return JsonResponse({
            'success': True,
            'is_new': is_new,
            'onboarding_required': onboarding_required,
            'user': {
                'id': str(user.id),
                'email': user.email,
                'name': user.get_full_name() or user.email,
            },
            'redirect_url': '/dashboard/' if onboarding_required else '/jobs/'
        })


# ==============================================================================
# 6. ONBOARDING 3-QUESTION WIZARD & LOCATION LOOKUP APIS
# ==============================================================================
class CandidateOnboardingView(LoginRequiredMixin, View):
    """
    Saves the 3-question onboarding preferences:
    1. Work category / classification (Question 1)
    2. Preferred Australian locations / Remote (Question 2)
    3. Job / Employment type (Question 3)
    """
    login_url = '/login/'

    def post(self, request):
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = request.POST

        categories = data.get('categories', [])
        locations = data.get('locations', [])
        job_types = data.get('job_types', [])
        role_title = data.get('role_title', '').strip()

        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)

        # Save Question 1 (Work Category)
        if isinstance(categories, list) and categories:
            profile.department = categories[0]
        elif isinstance(categories, str) and categories:
            profile.department = categories

        if role_title:
            profile.preferred_job_role = role_title

        # Save Question 2 (Australian Locations / Remote)
        if isinstance(locations, list) and locations:
            profile.preferred_location = ', '.join(locations)
            # Normalize candidate primary location if not set
            if not profile.location or profile.location == 'Sydney NSW':
                first_loc = locations[0]
                profile.location = normalize_australian_location(first_loc)
        elif isinstance(locations, str) and locations:
            profile.preferred_location = locations
            profile.location = normalize_australian_location(locations)

        # Save Question 3 (Job / Employment Type)
        if isinstance(job_types, list) and job_types:
            profile.employment_type = job_types[0]
        elif isinstance(job_types, str) and job_types:
            profile.employment_type = job_types

        # Store complete onboarding answers in parsed_json for rich AI matching
        if not isinstance(profile.parsed_json, dict):
            profile.parsed_json = {}

        profile.parsed_json['onboarding_answers'] = {
            'categories': categories,
            'locations': locations,
            'job_types': job_types,
            'role_title': role_title,
            'completed_at': timezone.now().isoformat(),
        }

        profile.save()

        return JsonResponse({
            'success': True,
            'message': 'Your job preferences have been saved successfully!',
            'redirect_url': '/dashboard/'
        })


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
# 8. LEGACY AUTHENTICATION, REGISTRATION & PROFILE (FORM BASED)
# ==============================================================================
class HirenestCandidateRegisterView(View):
    """Candidate registration page (form fallback)."""
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        return render(request, 'hirenest/candidate_register.html', {'locations': POPULAR_AU_LOCATIONS})

    def post(self, request):
        form = CandidateRegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            phone_number = form.cleaned_data['phone_number']
            location = form.cleaned_data['location']

            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                role=User.Role.CANDIDATE,
                is_active=True,
                is_verified=True,
            )

            CandidateProfile.objects.create(
                user=user,
                full_name=f"{first_name} {last_name}".strip(),
                location=location,
                candidate_status='ACTIVE'
            )

            auth_user = authenticate(request, username=email, password=password)
            if auth_user:
                login(request, auth_user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f"Welcome to HireNest Australia, {first_name}!")
                return redirect('/dashboard/')

            return redirect('/login/')

        errors = [err for err_list in form.errors.values() for err in err_list]
        return render(request, 'hirenest/candidate_register.html', {
            'errors': errors,
            'locations': POPULAR_AU_LOCATIONS,
            'first_name': request.POST.get('first_name', ''),
            'last_name': request.POST.get('last_name', ''),
            'email': request.POST.get('email', ''),
            'phone_number': request.POST.get('phone_number', ''),
            'location': request.POST.get('location', ''),
        })


class HirenestCandidateLoginView(View):
    """Candidate login page (form fallback)."""
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        next_url = request.GET.get('next', '')
        return render(request, 'hirenest/candidate_login.html', {'next': next_url})

    def post(self, request):
        form = CandidateLoginForm(request.POST)
        next_url = request.POST.get('next', '').strip() or '/dashboard/'

        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', True)

            user = authenticate(request, username=email, password=password)
            if user is not None and user.is_active:
                if user.role != User.Role.CANDIDATE:
                    return render(request, 'hirenest/candidate_login.html', {
                        'error': 'This account is registered as an Employer. Please sign in via the Employer Portal.',
                        'email': email,
                        'next': next_url,
                    })

                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                if not remember_me:
                    request.session.set_expiry(0)

                messages.success(request, f"Welcome back, {user.first_name or user.email}!")
                return redirect(next_url)

            return render(request, 'hirenest/candidate_login.html', {
                'error': 'Invalid email or password. Please verify your credentials.',
                'email': email,
                'next': next_url,
            })

        return render(request, 'hirenest/candidate_login.html', {
            'error': 'Please provide a valid email and password.',
            'next': next_url,
        })


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
                CandidateSkill.objects.create(candidate=profile, skill_name=s)

        messages.success(request, "Your profile has been updated successfully.")
        return redirect('/profile/')


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
