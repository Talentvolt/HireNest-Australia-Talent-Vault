import logging
import os
import json
from decimal import Decimal
from django.views.generic import TemplateView, ListView, DetailView, View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse, Http404
from django.db.models import Q, Count, Case, When, Value, IntegerField
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.utils.decorators import method_decorator

from apps.accounts.models import User, OTPVerification
from apps.jobs.models import Job, JobSkill
from apps.companies.models import Company, CompanyMember
from apps.candidates.models import (
    CandidateProfile, CandidateSkill, Experience, Education, SavedJob
)
from apps.applications.models import Application, ApplicationHistory
from apps.core.permissions import CandidateRequiredMixin
from utils.australia_data import (
    AUSTRALIAN_STATES,
    POPULAR_AUSTRALIAN_LOCATIONS,
    AUSTRALIAN_CLASSIFICATIONS,
    SALARY_GUIDE_DATA,
    CAREER_ADVICE_ARTICLES,
    RESOURCES_DATA
)

logger = logging.getLogger(__name__)


# ==============================================================================
# 1. HIRENEST AUSTRALIA - CANDIDATE LANDING VIEW
# ==============================================================================

class HirenestLandingView(TemplateView):
    template_name = 'hirenest/landing.html'

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.role == User.Role.CANDIDATE:
                return redirect('frontend:candidate_dashboard')
            elif request.user.role in [User.Role.RECRUITER, User.Role.COMPANY_ADMIN, User.Role.SUPER_ADMIN]:
                return redirect('frontend:recruiter_dashboard')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Featured Australian Active Jobs
        featured_jobs = Job.objects.filter(status='ACTIVE').select_related('company', 'client').prefetch_related('skills').order_by('-created_at')[:8]
        context['featured_jobs'] = featured_jobs
        
        # 2. Australian Classifications
        context['classifications'] = AUSTRALIAN_CLASSIFICATIONS
        
        # 3. Popular Search Chips
        context['popular_chips'] = [
            {"label": "Accounts", "query": "Accounts"},
            {"label": "Nursing", "query": "Nursing"},
            {"label": "Customer Service", "query": "Customer Service"},
            {"label": "Engineer", "query": "Engineer"},
            {"label": "Teacher", "query": "Teacher"},
            {"label": "Developer", "query": "Developer"},
            {"label": "Project Manager", "query": "Project Manager"},
            {"label": "Marketing", "query": "Marketing"}
        ]
        
        # 4. Top Australian Locations
        context['popular_locations'] = POPULAR_AUSTRALIAN_LOCATIONS[:8]
        
        # 5. Top Featured Companies
        context['featured_companies'] = Company.objects.filter(is_active=True).annotate(
            active_jobs_count=Count('jobs', filter=Q(jobs__status='ACTIVE'))
        ).order_by('-active_jobs_count', 'name')[:8]
        
        # 6. Career Advice preview
        context['career_articles'] = CAREER_ADVICE_ARTICLES[:3]
        
        # 7. Total active jobs count
        context['total_active_jobs'] = Job.objects.filter(status='ACTIVE').count()
        
        return context


# ==============================================================================
# 2. HIRENEST AUSTRALIA - JOB SEARCH & RESULTS VIEW
# ==============================================================================

class HirenestJobSearchView(ListView):
    model = Job
    template_name = 'hirenest/jobs_search.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        queryset = Job.objects.filter(status='ACTIVE').select_related('company', 'client').prefetch_related('skills')
        
        # 1. Keyword search (q, keyword, search)
        q = self.request.GET.get('q', '').strip() or self.request.GET.get('keyword', '').strip()
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(department__icontains=q) |
                Q(required_skills_text__icontains=q) |
                Q(preferred_skills_text__icontains=q) |
                Q(company__name__icontains=q) |
                Q(client__company_name__icontains=q) |
                Q(location__icontains=q) |
                Q(skills__skill_name__icontains=q)
            )
            
        # 2. Location search (location, suburb, city, state)
        loc = self.request.GET.get('location', '').strip() or self.request.GET.get('city', '').strip() or self.request.GET.get('state', '').strip()
        if loc:
            queryset = queryset.filter(location__icontains=loc)
            
        # 3. State/Territory Filter
        state = self.request.GET.get('state', '').strip()
        if state:
            queryset = queryset.filter(location__icontains=state)

        # 4. Classification / Department Filter
        classification = self.request.GET.get('classification', '').strip() or self.request.GET.get('category', '').strip()
        if classification:
            queryset = queryset.filter(
                Q(department__icontains=classification) |
                Q(title__icontains=classification) |
                Q(description__icontains=classification)
            )

        # 5. Job Type (FULL_TIME, PART_TIME, CONTRACT, CASUAL, TEMPORARY)
        job_types = self.request.GET.getlist('job_type')
        if job_types:
            queryset = queryset.filter(job_type__in=job_types)

        # 6. Work Mode (ONSITE, HYBRID, REMOTE)
        work_modes = self.request.GET.getlist('work_mode')
        if work_modes:
            queryset = queryset.filter(work_mode__in=work_modes)

        # 7. Salary range (AUD)
        min_sal = self.request.GET.get('min_salary', '').strip()
        if min_sal:
            try:
                min_sal_val = Decimal(min_sal)
                queryset = queryset.filter(Q(max_salary__gte=min_sal_val) | Q(min_salary__gte=min_sal_val))
            except Exception:
                pass

        # 8. Company filter
        comp = self.request.GET.get('company', '').strip()
        if comp:
            queryset = queryset.filter(
                Q(company__name__icontains=comp) | Q(client__company_name__icontains=comp)
            )

        queryset = queryset.distinct()

        # 9. Sorting
        sort_by = self.request.GET.get('sort_by', 'newest')
        if sort_by == 'relevance' and q:
            queryset = queryset.annotate(
                relevance=Case(
                    When(title__icontains=q, then=Value(3)),
                    When(description__icontains=q, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            ).order_by('-relevance', '-created_at')
        elif sort_by == 'salary_high':
            queryset = queryset.order_by('-max_salary', '-min_salary')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Active query parameters
        context['q'] = self.request.GET.get('q', '').strip()
        context['location'] = self.request.GET.get('location', '').strip()
        context['selected_job_types'] = self.request.GET.getlist('job_type')
        context['selected_work_modes'] = self.request.GET.getlist('work_mode')
        context['selected_state'] = self.request.GET.get('state', '').strip()
        context['selected_classification'] = self.request.GET.get('classification', '').strip()
        context['sort_by'] = self.request.GET.get('sort_by', 'newest')
        context['min_salary'] = self.request.GET.get('min_salary', '').strip()
        
        context['states'] = AUSTRALIAN_STATES
        context['classifications'] = AUSTRALIAN_CLASSIFICATIONS
        context['locations_list'] = POPULAR_AUSTRALIAN_LOCATIONS
        
        # Saved job IDs for current candidate
        if self.request.user.is_authenticated and getattr(self.request.user, 'role', None) == User.Role.CANDIDATE:
            profile = getattr(self.request.user, 'candidate_profile', None)
            if profile:
                context['saved_job_ids'] = list(profile.saved_jobs.values_list('job_id', flat=True))
                context['applied_job_ids'] = list(profile.job_applications.values_list('job_id', flat=True))
            else:
                context['saved_job_ids'] = []
                context['applied_job_ids'] = []
        else:
            context['saved_job_ids'] = []
            context['applied_job_ids'] = []
            
        return context


# ==============================================================================
# 3. HIRENEST AUSTRALIA - JOB DETAILS VIEW
# ==============================================================================

class HirenestJobDetailView(DetailView):
    model = Job
    template_name = 'hirenest/job_detail.html'
    context_object_name = 'job'

    def get_queryset(self):
        return Job.objects.select_related('company', 'client').prefetch_related('skills')

    def get(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
        except (Http404, Job.DoesNotExist):
            return render(request, '404.html', {'message': 'Job posting no longer available.'}, status=404)
        except Exception as e:
            logger.error(f"Error loading Hirenest job detail {kwargs.get('pk')}: {e}")
            return render(request, '404.html', {'message': 'Job posting not found.'}, status=404)

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        
        # Share URL
        try:
            context['share_url'] = self.request.build_absolute_uri(
                reverse('frontend:hirenest_job_detail', kwargs={'pk': job.pk})
            )
        except Exception:
            context['share_url'] = self.request.build_absolute_uri(self.request.path)

        # Similar Australian Jobs
        similar_jobs = Job.objects.filter(
            status='ACTIVE'
        ).exclude(id=job.id).filter(
            Q(department__icontains=job.department) |
            Q(location__icontains=job.location.split(',')[0]) |
            Q(title__icontains=job.title.split(' ')[0])
        ).select_related('company', 'client')[:4]
        
        if not similar_jobs.exists():
            similar_jobs = Job.objects.filter(status='ACTIVE').exclude(id=job.id).select_related('company', 'client')[:4]
            
        context['similar_jobs'] = similar_jobs

        # User application / saved state
        is_saved = False
        has_applied = False
        candidate_profile = None

        if self.request.user.is_authenticated and getattr(self.request.user, 'role', None) == User.Role.CANDIDATE:
            candidate_profile = getattr(self.request.user, 'candidate_profile', None)
            if candidate_profile:
                is_saved = candidate_profile.saved_jobs.filter(job=job).exists()
                has_applied = candidate_profile.job_applications.filter(job=job).exists()

        context['is_saved'] = is_saved
        context['has_applied'] = has_applied
        context['candidate_profile'] = candidate_profile

        # JD File handling
        jd_file = job.jd_file if job.jd_file else None
        context['jd_file'] = jd_file
        if jd_file:
            try:
                filename = os.path.basename(jd_file.name)
            except Exception:
                filename = str(jd_file)
            ext = os.path.splitext(filename)[1].lower() if '.' in filename else ''
            context['jd_file_name'] = filename
            context['is_pdf'] = (ext == '.pdf')
            context['is_docx'] = (ext in ['.docx', '.doc'])

        return context


# ==============================================================================
# 4. HIRENEST AUSTRALIA - JOB APPLICATION FLOW
# ==============================================================================

class HirenestJobApplyView(View):
    def get(self, request, pk, *args, **kwargs):
        job = get_object_or_404(Job, pk=pk)
        if not request.user.is_authenticated:
            return redirect(f"/login/?next=/jobs/{job.pk}/")
        
        if request.user.role != User.Role.CANDIDATE:
            messages.warning(request, "Please log in as a candidate to apply for jobs.")
            return redirect(f"/jobs/{job.pk}/")
            
        profile = getattr(request.user, 'candidate_profile', None)
        if Application.objects.filter(job=job, candidate=profile).exists():
            messages.info(request, "You have already submitted an application for this role.")
            return redirect('frontend:candidate_applications')

        return render(request, 'hirenest/job_apply.html', {'job': job, 'profile': profile})

    def post(self, request, pk, *args, **kwargs):
        job = get_object_or_404(Job, pk=pk)
        
        if not request.user.is_authenticated:
            return redirect(f"/login/?next=/jobs/{job.pk}/")
            
        if request.user.role != User.Role.CANDIDATE:
            messages.error(request, "Only registered candidates can apply for jobs.")
            return redirect(f"/jobs/{job.pk}/")

        profile = getattr(request.user, 'candidate_profile', None)
        if not profile:
            profile, _ = CandidateProfile.objects.get_or_create(user=request.user)

        # Check duplicate
        if Application.objects.filter(job=job, candidate=profile).exists():
            messages.warning(request, "You have already applied for this job.")
            return redirect('frontend:candidate_applications')

        try:
            cover_letter = request.POST.get('cover_letter', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            current_location = request.POST.get('location', '').strip() or profile.location
            total_exp_raw = request.POST.get('total_experience', '').strip()
            expected_salary_raw = request.POST.get('expected_salary', '').strip()
            notice_period_raw = request.POST.get('notice_period', '').strip()
            
            # Handle resume upload if supplied
            uploaded_resume = request.FILES.get('resume_file')
            if uploaded_resume:
                profile.resume = uploaded_resume
                profile.save()

            try:
                total_exp = float(total_exp_raw) if total_exp_raw else float(profile.total_experience or 0)
            except ValueError:
                total_exp = 0.0

            try:
                expected_salary = Decimal(expected_salary_raw) if expected_salary_raw else profile.expected_salary
            except Exception:
                expected_salary = None

            try:
                notice_period = int(notice_period_raw) if notice_period_raw else profile.notice_period
            except ValueError:
                notice_period = 30

            # Create Application
            app = Application.objects.create(
                job=job,
                candidate=profile,
                cover_letter=cover_letter,
                current_location=current_location,
                total_experience=total_exp,
                expected_ctc=expected_salary,
                notice_period=notice_period,
                stage=Application.ApplicationStage.OPEN,
                is_active=True,
                in_pipeline=True
            )

            # Record Application History
            ApplicationHistory.objects.create(
                application=app,
                from_stage=Application.ApplicationStage.OPEN,
                to_stage=Application.ApplicationStage.OPEN,
                notes="Candidate submitted application via HireNest Australia portal."
            )

            messages.success(request, f"Your application for {job.title} at {job.display_company} was successfully submitted!")
            return redirect('frontend:candidate_applications')

        except Exception as e:
            logger.error(f"Error submitting job application for job {job.pk}: {e}")
            messages.error(request, f"Application error: {str(e)}")
            return redirect(f"/jobs/{job.pk}/")


# ==============================================================================
# 5. HIRENEST AUSTRALIA - CANDIDATE AUTH (LOGIN & REGISTER)
# ==============================================================================

class HirenestCandidateLoginView(View):
    template_name = 'hirenest/candidate_login.html'

    @method_decorator(never_cache)
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(csrf_protect)
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.role == User.Role.CANDIDATE:
                next_url = request.GET.get('next') or reverse('frontend:candidate_dashboard')
                return redirect(next_url)
            else:
                return redirect('frontend:recruiter_dashboard')
        return render(request, self.template_name, {'next': request.GET.get('next', '')})

    @method_decorator(never_cache)
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me') == 'on'
        next_url = request.POST.get('next', '').strip()

        if not email or not password:
            return render(request, self.template_name, {
                'error': 'Please enter both your email address and password.',
                'email': email,
                'next': next_url
            })

        user = authenticate(request, username=email, password=password)
        if user is not None:
            if not user.is_active:
                return render(request, self.template_name, {
                    'error': 'This account has been disabled. Please contact support.',
                    'email': email,
                    'next': next_url
                })
                
            if user.role == User.Role.CANDIDATE:
                login(request, user)
                if remember_me:
                    request.session.set_expiry(1209600)  # 2 weeks
                else:
                    request.session.set_expiry(0)
                    
                target = next_url if next_url and next_url.startswith('/') else reverse('frontend:candidate_dashboard')
                return redirect(target)
            else:
                # Recruiter/Employer logged into candidate portal: redirect to recruiter workspace
                login(request, user)
                return redirect('frontend:recruiter_dashboard')
        else:
            return render(request, self.template_name, {
                'error': 'Invalid email address or password. Please try again.',
                'email': email,
                'next': next_url
            })


class HirenestCandidateRegisterView(View):
    template_name = 'hirenest/candidate_register.html'

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logout(request)
        return render(request, self.template_name, {
            'locations': POPULAR_AUSTRALIAN_LOCATIONS,
            'states': AUSTRALIAN_STATES
        })

    def post(self, request, *args, **kwargs):
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()
        location = request.POST.get('location', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        terms = request.POST.get('terms') == 'on'

        errors = []
        if not first_name: errors.append("First name is required.")
        if not last_name: errors.append("Last name is required.")
        if not email: errors.append("Email address is required.")
        if not phone_number: errors.append("Phone number is required.")
        if not location: errors.append("Location is required.")
        if not password: errors.append("Password is required.")
        if len(password) < 8: errors.append("Password must be at least 8 characters.")
        if password != confirm_password: errors.append("Passwords do not match.")
        if not terms: errors.append("You must agree to the Terms of Service & Privacy Policy.")

        if User.objects.filter(email__iexact=email).exists():
            errors.append("An account with this email address already exists. Please log in.")

        if errors:
            return render(request, self.template_name, {
                'errors': errors,
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone_number': phone_number,
                'location': location,
                'locations': POPULAR_AUSTRALIAN_LOCATIONS,
                'states': AUSTRALIAN_STATES
            })

        # Create Candidate User
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            role=User.Role.CANDIDATE,
            is_active=True,
            is_verified=True
        )

        # Create Candidate Profile
        CandidateProfile.objects.create(
            user=user,
            full_name=f"{first_name} {last_name}".strip(),
            location=location,
            candidate_status='ACTIVE'
        )

        # Authenticate and login
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f"Welcome to HireNest Australia, {first_name}! Your account has been created.")
        return redirect('frontend:candidate_dashboard')


# ==============================================================================
# 6. HIRENEST AUSTRALIA - CANDIDATE PORTAL PAGES
# ==============================================================================

class HirenestCandidateProfileView(CandidateRequiredMixin, TemplateView):
    template_name = 'hirenest/candidate_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'candidate_profile', None)
        if not profile:
            profile, _ = CandidateProfile.objects.get_or_create(user=self.request.user)
        context['profile'] = profile
        context['locations'] = POPULAR_AUSTRALIAN_LOCATIONS
        context['states'] = AUSTRALIAN_STATES
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        profile = getattr(user, 'candidate_profile', None)
        if not profile:
            profile, _ = CandidateProfile.objects.get_or_create(user=user)

        full_name = request.POST.get('full_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        current_designation = request.POST.get('current_designation', '').strip()
        current_company = request.POST.get('current_company', '').strip()
        location = request.POST.get('location', '').strip()
        total_exp_raw = request.POST.get('total_experience', '').strip()
        expected_salary_raw = request.POST.get('expected_salary', '').strip()
        notice_period_raw = request.POST.get('notice_period', '').strip()
        summary = request.POST.get('summary', '').strip()
        skills_text = request.POST.get('skills', '').strip()

        # Update User
        if full_name:
            parts = full_name.split(' ', 1)
            user.first_name = parts[0]
            user.last_name = parts[1] if len(parts) > 1 else ''
        if phone_number:
            user.phone_number = phone_number
        user.save()

        # Update Profile
        profile.full_name = full_name
        profile.current_designation = current_designation
        profile.current_company = current_company
        profile.location = location
        profile.summary = summary
        
        try:
            profile.total_experience = Decimal(total_exp_raw) if total_exp_raw else Decimal("0.0")
        except Exception:
            pass

        try:
            profile.expected_salary = Decimal(expected_salary_raw) if expected_salary_raw else None
        except Exception:
            pass

        try:
            profile.notice_period = int(notice_period_raw) if notice_period_raw else 30
        except Exception:
            pass

        # Handle resume file
        if 'resume' in request.FILES:
            profile.resume = request.FILES['resume']

        profile.save()

        # Update skills
        if skills_text:
            profile.skills.all().delete()
            for s in skills_text.split(','):
                s_clean = s.strip()
                if s_clean:
                    CandidateSkill.objects.create(profile=profile, skill_name=s_clean)

        messages.success(request, "Your HireNest candidate profile has been updated successfully!")
        return redirect('frontend:candidate_profile')


class HirenestCandidateApplicationsView(CandidateRequiredMixin, TemplateView):
    template_name = 'hirenest/candidate_applications.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'candidate_profile', None)
        if profile:
            context['applications'] = profile.job_applications.select_related('job', 'job__company').order_by('-created_at')
        else:
            context['applications'] = []
        return context


class HirenestCandidateSavedJobsView(CandidateRequiredMixin, TemplateView):
    template_name = 'hirenest/candidate_saved_jobs.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, 'candidate_profile', None)
        if profile:
            context['saved_jobs'] = profile.saved_jobs.select_related('job', 'job__company').order_by('-created_at')
            context['applied_job_ids'] = list(profile.job_applications.values_list('job_id', flat=True))
        else:
            context['saved_jobs'] = []
            context['applied_job_ids'] = []
        return context


# ==============================================================================
# 7. HIRENEST AUSTRALIA - INFORMATIONAL PAGES (COMPANIES, SALARY, ADVICE, RESOURCES)
# ==============================================================================

class HirenestCompaniesView(ListView):
    model = Company
    template_name = 'hirenest/companies.html'
    context_object_name = 'companies'
    paginate_by = 12

    def get_queryset(self):
        queryset = Company.objects.filter(is_active=True).annotate(
            active_jobs_count=Count('jobs', filter=Q(jobs__status='ACTIVE'))
        )
        q = self.request.GET.get('q', '').strip()
        if q:
            queryset = queryset.filter(
                Q(name__icontains=q) | Q(industry__icontains=q) | Q(location__icontains=q)
            )
        industry = self.request.GET.get('industry', '').strip()
        if industry:
            queryset = queryset.filter(industry__icontains=industry)
            
        return queryset.order_by('-active_jobs_count', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '').strip()
        context['industry'] = self.request.GET.get('industry', '').strip()
        context['industries'] = Company.objects.filter(is_active=True).values_list('industry', flat=True).distinct()
        return context


class HirenestCompanyDetailView(DetailView):
    model = Company
    template_name = 'hirenest/company_detail.html'
    context_object_name = 'company'
    slug_field = 'slug'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company = self.object
        context['active_jobs'] = company.jobs.filter(status='ACTIVE').order_by('-created_at')
        return context


class HirenestCareerAdviceView(TemplateView):
    template_name = 'hirenest/career_advice.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['articles'] = CAREER_ADVICE_ARTICLES
        category = self.request.GET.get('category', '').strip()
        if category:
            context['articles'] = [a for a in CAREER_ADVICE_ARTICLES if category.lower() in a['category'].lower()]
        context['selected_category'] = category
        return context


class HirenestSalaryGuideView(TemplateView):
    template_name = 'hirenest/salary_guide.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        q = self.request.GET.get('q', '').strip().lower()
        category = self.request.GET.get('category', '').strip()
        
        salaries = SALARY_GUIDE_DATA
        if q:
            salaries = [s for s in salaries if q in s['role'].lower() or q in s['category'].lower()]
        if category:
            salaries = [s for s in salaries if category.lower() in s['category'].lower()]

        context['salaries'] = salaries
        context['q'] = self.request.GET.get('q', '').strip()
        context['selected_category'] = category
        context['categories'] = list(set([s['category'] for s in SALARY_GUIDE_DATA]))
        return context


class HirenestResourcesView(TemplateView):
    template_name = 'hirenest/resources.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['resources'] = RESOURCES_DATA
        return context


# ==============================================================================
# 8. HIRENEST AUSTRALIA - EMPLOYER SUITE
# ==============================================================================

class HirenestEmployerLandingView(TemplateView):
    template_name = 'hirenest/employer_landing.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_candidates'] = CandidateProfile.objects.count() + 15000  # Indicative scale
        context['active_recruiters'] = User.objects.filter(role__in=[User.Role.RECRUITER, User.Role.COMPANY_ADMIN]).count() + 250
        return context


class HirenestEmployerLoginView(View):
    template_name = 'hirenest/employer_login.html'

    @method_decorator(never_cache)
    @method_decorator(ensure_csrf_cookie)
    @method_decorator(csrf_protect)
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.role in [User.Role.RECRUITER, User.Role.COMPANY_ADMIN, User.Role.SUPER_ADMIN]:
                return redirect('frontend:recruiter_dashboard')
            else:
                return redirect('frontend:candidate_dashboard')
        return render(request, self.template_name)

    @method_decorator(never_cache)
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me') == 'on'

        if not email or not password:
            return render(request, self.template_name, {
                'error': 'Please provide both your official work email and password.',
                'email': email
            })

        user_target = User.objects.filter(email=email).first()
        if not user_target or not user_target.check_password(password):
            return render(request, self.template_name, {
                'error': 'Invalid credentials. Please verify your work email and password.',
                'email': email
            })

        if user_target.role == User.Role.CANDIDATE:
            return render(request, self.template_name, {
                'error': 'This login is for Australian Employers & Recruiters. Candidates should sign in via the Candidate Portal.',
                'email': email
            })

        if not user_target.is_active:
            return render(request, self.template_name, {
                'error': 'Your recruiter account has been disabled. Please contact support.',
                'email': email
            })

        # Authenticate and login into existing TalentVault Recruiter Session
        login(request, user_target, backend='django.contrib.auth.backends.ModelBackend')
        if remember_me:
            request.session.set_expiry(1209600)  # 2 weeks
        else:
            request.session.set_expiry(0)

        # REDIRECT INTO THE EXISTING TALENTVAULT RECRUITER WORKSPACE
        return redirect('frontend:recruiter_dashboard')


class HirenestEmployerRegisterView(View):
    template_name = 'hirenest/employer_register.html'

    @method_decorator(never_cache)
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            logout(request)
        return render(request, self.template_name, {
            'locations': POPULAR_AUSTRALIAN_LOCATIONS,
            'states': AUSTRALIAN_STATES
        })

    def post(self, request, *args, **kwargs):
        org_name = request.POST.get('org_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()
        hiring_type = request.POST.get('hiring_type', 'organization')
        industry = request.POST.get('industry', '').strip()
        company_size = request.POST.get('company_size', '1-50')
        website = request.POST.get('website', '').strip()
        location = request.POST.get('location', '').strip() or 'Sydney NSW'
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        terms = request.POST.get('terms') == 'on'

        errors = []
        if not org_name: errors.append("Organization / Company name is required.")
        if not email: errors.append("Official work email is required.")
        if not phone_number: errors.append("Contact phone number is required.")
        if not password: errors.append("Password is required.")
        if len(password) < 8: errors.append("Password must be at least 8 characters.")
        if password != confirm_password: errors.append("Passwords do not match.")
        if not terms: errors.append("You must agree to the Terms of Service & Privacy Policy.")

        if User.objects.filter(email__iexact=email).exists():
            errors.append("An account with this work email address already exists. Please log in.")

        if errors:
            return render(request, self.template_name, {
                'errors': errors,
                'org_name': org_name,
                'email': email,
                'phone_number': phone_number,
                'hiring_type': hiring_type,
                'industry': industry,
                'company_size': company_size,
                'website': website,
                'location': location,
                'locations': POPULAR_AUSTRALIAN_LOCATIONS,
                'states': AUSTRALIAN_STATES
            })

        # 1. Create Recruiter User in existing TalentVault DB
        user = User.objects.create_user(
            email=email,
            password=password,
            phone_number=phone_number,
            role=User.Role.RECRUITER,
            recruiter_status=User.RecruiterStatus.ACTIVE,
            is_active=True,
            is_verified=True
        )

        # 2. Create or Link Company & CompanyMember in TalentVault DB
        from django.utils.text import slugify
        base_slug = slugify(org_name) or 'company'
        slug = base_slug
        idx = 1
        while Company.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{idx}"
            idx += 1

        company, _ = Company.objects.get_or_create(
            name=org_name,
            defaults={
                'slug': slug,
                'website': website,
                'industry': industry or 'Technology & Business Services',
                'location': location,
                'employee_count': company_size,
                'description': f"{org_name} - Registered Employer on HireNest Australia."
            }
        )

        CompanyMember.objects.get_or_create(
            company=company,
            user=user,
            defaults={
                'designation': 'Hiring Manager / Recruiter',
                'role': CompanyMember.MemberRole.ADMIN
            }
        )

        # 3. Log in recruiter and redirect to TalentVault Recruiter Workspace
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(request, f"Welcome to TalentVault Recruiter Workspace! Your employer account for {org_name} is active.")
        return redirect('frontend:recruiter_dashboard')
