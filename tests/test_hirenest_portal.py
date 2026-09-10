import os
import json
from types import SimpleNamespace
from decimal import Decimal
from django.test import TestCase, Client
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import User
from apps.accounts.adapters import CandidateAccountAdapter
from apps.accounts.services.candidate_social import get_or_create_candidate_from_social
from apps.companies.models import Company, CompanyMember
from apps.jobs.models import Job, JobSkill
from apps.candidates.models import CandidateProfile, SavedJob
from apps.applications.models import Application
from portal.services import (
    get_australian_jobs_queryset,
    normalize_australian_location,
    get_candidate_recommended_jobs,
)


class HireNestAustraliaStandaloneTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create an Australian Company in shared DB
        self.company = Company.objects.create(
            name="Atlassian Australia",
            slug="atlassian-australia",
            industry="Information Technology",
            location="Sydney NSW",
            website="https://www.atlassian.com",
            description="Leading Australian collaboration software company."
        )

        # Create an Australian Recruiter User in shared DB
        self.recruiter_user = User.objects.create_user(
            email="recruiter@atlassian.com.au",
            password="RecruiterPassword123!",
            first_name="Liam",
            last_name="Smith",
            phone_number="+61 2 9000 1234",
            role=User.Role.RECRUITER,
            recruiter_status=User.RecruiterStatus.ACTIVE,
            is_active=True,
            is_verified=True
        )

        CompanyMember.objects.create(
            company=self.company,
            user=self.recruiter_user,
            designation="Talent Lead",
            role=CompanyMember.MemberRole.ADMIN
        )

        # Create an Australian Job Posting in shared DB
        self.job = Job.objects.create(
            company=self.company,
            title="Senior Python Backend Engineer",
            location="Sydney NSW",
            job_type="FULL_TIME",
            work_mode="HYBRID",
            department="Engineering",
            min_experience=4,
            max_experience=8,
            min_salary=Decimal("150000.00"),
            max_salary=Decimal("190000.00"),
            currency="AUD",
            status="ACTIVE",
            required_skills_text="Python, Django, AWS, PostgreSQL",
            description="Join our core platform engineering team in Sydney.",
            created_by=self.recruiter_user
        )

        JobSkill.objects.create(job=self.job, skill_name="Python", is_mandatory=True)
        JobSkill.objects.create(job=self.job, skill_name="Django", is_mandatory=True)

        # Create a Candidate User & Profile in shared DB
        self.candidate_user = User.objects.create_user(
            email="candidate.sarah@gmail.com",
            password="CandidatePassword123!",
            first_name="Sarah",
            last_name="Connor",
            phone_number="+61 400 123 456",
            role=User.Role.CANDIDATE,
            is_active=True,
            is_verified=True
        )

        self.candidate_profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            full_name="Sarah Connor",
            location="Sydney NSW",
            current_designation="Software Developer",
            department="Engineering",
            preferred_job_role="Python Developer",
            preferred_location="Sydney NSW",
            employment_type="FULL_TIME",
            total_experience=Decimal("5.0"),
            expected_salary=Decimal("160000.00"),
            candidate_status="ACTIVE"
        )

    # --------------------------------------------------------------------------
    # 1. Candidate Homepage Tests
    # --------------------------------------------------------------------------
    def test_homepage_rendering_and_branding(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "HireNest")
        self.assertContains(response, "Australia")
        self.assertContains(response, "Find the right job.")
        self.assertContains(response, "Build your future.")
        self.assertContains(response, "candidate-hero")
        self.assertContains(response, "Search Jobs")
        self.assertContains(response, "Popular Job Categories")
        self.assertContains(response, "Top Cities in Australia")
        self.assertContains(response, "Sydney")
        self.assertContains(response, "Melbourne")
        self.assertContains(response, "Brisbane")
        self.assertContains(response, "Why Job Seekers Choose HireNest")
        self.assertContains(response, "Quality Jobs")
        self.assertContains(response, "Smart Matching")
        self.assertContains(response, "Easy Applications")
        self.assertContains(response, "Career Support")
        self.assertContains(response, "Senior Python Backend Engineer")
        self.assertContains(response, "Atlassian Australia")

    def test_public_navbar_always_shows_public_auth_buttons(self):
        # The public navbar always shows the same items, regardless of auth state.
        def assert_public_navbar(resp):
            self.assertContains(resp, "For Employers")
            self.assertContains(resp, "Log In")
            self.assertContains(resp, "Sign In / Register")
            self.assertNotContains(resp, "Recruiter Workspace")
            self.assertNotContains(resp, "Admin Workspace")

        assert_public_navbar(self.client.get('/'))

        self.client.force_login(self.candidate_user)
        assert_public_navbar(self.client.get('/'))

        self.client.force_login(self.recruiter_user)
        assert_public_navbar(self.client.get('/'))

        admin_user = User.objects.create_superuser(
            email="navbar.admin@hirenest.com.au", password="AdminPassword123!"
        )
        self.client.force_login(admin_user)
        assert_public_navbar(self.client.get('/'))

    # --------------------------------------------------------------------------
    # 2. Strict Backend-Enforced Australia Jobs Only Filtering Tests
    # --------------------------------------------------------------------------
    def test_strict_australia_only_marketplace_filtering(self):
        # Create non-Australian international jobs in database
        non_au_company = Company.objects.create(
            name="Bangalore Tech Ltd",
            slug="bangalore-tech",
            industry="IT",
            location="Bangalore, India",
            description="Indian development center."
        )
        indian_job = Job.objects.create(
            company=non_au_company,
            title="Java Backend Engineer (India)",
            location="Bangalore, Karnataka, India",
            job_type="FULL_TIME",
            work_mode="ONSITE",
            currency="INR",
            min_salary=Decimal("1200000.00"),
            max_salary=Decimal("2000000.00"),
            status="ACTIVE",
            description="Java role in Bangalore.",
            created_by=self.recruiter_user
        )

        us_company = Company.objects.create(
            name="US Tech Corp",
            slug="us-tech",
            industry="IT",
            location="New York, USA"
        )
        us_job = Job.objects.create(
            company=us_company,
            title="React Developer (US)",
            location="New York, USA",
            job_type="FULL_TIME",
            currency="USD",
            min_salary=Decimal("120000.00"),
            max_salary=Decimal("160000.00"),
            status="ACTIVE",
            description="US based role.",
            created_by=self.recruiter_user
        )

        # Create Melbourne AU Job
        melb_job = Job.objects.create(
            company=self.company,
            title="Clinical Nurse Specialist",
            location="Melbourne VIC",
            job_type="FULL_TIME",
            currency="AUD",
            min_salary=Decimal("95000.00"),
            max_salary=Decimal("120000.00"),
            status="ACTIVE",
            description="Healthcare role in Melbourne.",
            created_by=self.recruiter_user
        )

        # QuerySet test
        au_qs = get_australian_jobs_queryset()
        self.assertIn(self.job, au_qs)
        self.assertIn(melb_job, au_qs)
        self.assertNotIn(indian_job, au_qs)
        self.assertNotIn(us_job, au_qs)

        # Job search page check
        search_resp = self.client.get('/jobs/')
        self.assertContains(search_resp, "Senior Python Backend Engineer")
        self.assertContains(search_resp, "Clinical Nurse Specialist")
        self.assertNotContains(search_resp, "Java Backend Engineer (India)")
        self.assertNotContains(search_resp, "React Developer (US)")

    # --------------------------------------------------------------------------
    # 3. Australian Job Search & Filter Tests
    # --------------------------------------------------------------------------
    def test_job_search_page(self):
        response = self.client.get('/jobs/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senior Python Backend Engineer")
        self.assertContains(response, "$150,000 - $190,000 / year")

    def test_job_search_filters(self):
        # Keyword and location search
        response = self.client.get('/jobs/?q=Python&location=Sydney')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senior Python Backend Engineer")

        # State filter
        response_state = self.client.get('/jobs/?state=NSW')
        self.assertEqual(response_state.status_code, 200)
        self.assertContains(response_state, "Senior Python Backend Engineer")

        # Employment type filter
        response_jt = self.client.get('/jobs/?job_type=FULL_TIME')
        self.assertEqual(response_jt.status_code, 200)
        self.assertContains(response_jt, "Senior Python Backend Engineer")

        # Work arrangement filter
        response_wm = self.client.get('/jobs/?work_mode=HYBRID')
        self.assertEqual(response_wm.status_code, 200)
        self.assertContains(response_wm, "Senior Python Backend Engineer")

        # Empty state
        response_empty = self.client.get('/jobs/?q=NonExistentRoleXYZ')
        self.assertEqual(response_empty.status_code, 200)
        self.assertContains(response_empty, "No Matching Jobs Found")

    # --------------------------------------------------------------------------
    # 4. Job Details Page Tests
    # --------------------------------------------------------------------------
    def test_job_details_page(self):
        response = self.client.get(f'/jobs/{self.job.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Senior Python Backend Engineer")
        self.assertContains(response, "Atlassian Australia")
        self.assertContains(response, "$150,000 - $190,000 / year")
        self.assertContains(response, "Sydney NSW")
        self.assertContains(response, "Apply for this Role")

    # --------------------------------------------------------------------------
    # 5. Candidate "Continue with Google" Authentication Tests
    # --------------------------------------------------------------------------
    def test_candidate_auth_pages_use_google_only(self):
        login_resp = self.client.get('/login/')
        self.assertEqual(login_resp.status_code, 200)
        self.assertContains(login_resp, "Continue with Google")
        self.assertNotContains(login_resp, "verification code")
        self.assertNotContains(login_resp, "Send verification")

        register_resp = self.client.get('/register/')
        self.assertEqual(register_resp.status_code, 200)
        self.assertContains(register_resp, "Continue with Google")
        self.assertNotContains(register_resp, "Send Verification Code")
        self.assertNotContains(register_resp, "6-Digit")

    def test_google_provisioning_creates_single_candidate_account(self):
        user, created, profile_created = get_or_create_candidate_from_social(
            email='emma.watson@gmail.com',
            first_name='Emma',
            last_name='Watson',
            picture='https://example.com/emma.jpg',
        )
        self.assertTrue(created)
        self.assertTrue(profile_created)
        self.assertEqual(user.role, User.Role.CANDIDATE)
        self.assertTrue(user.is_verified)
        self.assertTrue(CandidateProfile.objects.filter(user=user).exists())
        self.assertFalse(user.candidate_profile.is_onboarding_complete)

        # A second Google sign-in for the same email must not duplicate the account.
        user2, created2, _ = get_or_create_candidate_from_social(
            email='Emma.Watson@gmail.com',
            first_name='Emma',
            last_name='Watson',
        )
        self.assertFalse(created2)
        self.assertEqual(user2.pk, user.pk)
        self.assertEqual(User.objects.filter(email__iexact='emma.watson@gmail.com').count(), 1)

    def test_google_redirect_routes_to_onboarding_or_dashboard(self):
        adapter = CandidateAccountAdapter()

        # Existing candidate with a completed profile -> dashboard.
        completed = SimpleNamespace(user=self.candidate_user)
        self.assertTrue(self.candidate_profile.is_onboarding_complete)
        self.assertEqual(adapter.get_login_redirect_url(completed), '/dashboard/')

        # Brand new candidate with an incomplete profile -> onboarding.
        new_user, _, _ = get_or_create_candidate_from_social(
            email='brand.new.candidate@gmail.com', full_name='Brand New'
        )
        incomplete = SimpleNamespace(user=new_user)
        self.assertFalse(new_user.candidate_profile.is_onboarding_complete)
        self.assertEqual(adapter.get_login_redirect_url(incomplete), '/onboarding/')

    def test_google_social_app_sync_is_single_and_uses_env(self):
        from allauth.socialaccount.models import SocialApp
        from django.contrib.sites.models import Site
        from apps.accounts.apps import sync_google_social_app, _clean_google_env

        site = Site.objects.get(id=settings.SITE_ID)

        # Simulate a stale/duplicate Google app (e.g. an old TalentVault client).
        stale = SocialApp.objects.create(
            provider='google',
            name='TalentVault Google',
            client_id='old-talentvault-client.apps.googleusercontent.com',
            secret='old-secret',
        )
        stale.sites.add(site)

        sync_google_social_app()

        apps = SocialApp.objects.filter(provider='google')
        self.assertEqual(apps.count(), 1)

        app = apps.first()
        self.assertIn(site, app.sites.all())
        self.assertNotEqual(app.client_id, 'old-talentvault-client.apps.googleusercontent.com')

        expected = _clean_google_env('GOOGLE_CLIENT_ID')
        if expected:
            self.assertEqual(app.client_id, expected)

    def test_allauth_configured_for_username_less_custom_user(self):
        from django.conf import settings as dj_settings
        from django.test import RequestFactory
        from allauth.account.adapter import get_adapter as get_account_adapter

        # allauth must know the custom User model has no username field.
        self.assertIsNone(dj_settings.ACCOUNT_USER_MODEL_USERNAME_FIELD)
        self.assertEqual(dj_settings.ACCOUNT_USER_MODEL_EMAIL_FIELD, 'email')
        self.assertIn('email', dj_settings.ACCOUNT_LOGIN_METHODS)
        self.assertNotIn('username', dj_settings.ACCOUNT_SIGNUP_FIELDS)

        # This is the exact call allauth makes during Google auto-signup; it used
        # to raise FieldDoesNotExist("User has no field named 'username'").
        user = User.objects.create_user(
            email='username.less@gmail.com',
            role=User.Role.CANDIDATE,
            is_active=True,
        )
        request = RequestFactory().get('/accounts/google/login/callback/')
        get_account_adapter().populate_username(request, user)
        self.assertEqual(user.email, 'username.less@gmail.com')

    # --------------------------------------------------------------------------
    # 6. Branded Candidate Onboarding Tests
    # --------------------------------------------------------------------------
    def test_candidate_onboarding_page_and_submission(self):
        new_user = User.objects.create_user(
            email='onboard.me@gmail.com',
            first_name='Onboard',
            last_name='Me',
            role=User.Role.CANDIDATE,
            is_active=True,
            is_verified=True,
        )
        CandidateProfile.objects.create(
            user=new_user, full_name='Onboard Me', location='Sydney NSW', candidate_status='ACTIVE'
        )
        self.client.force_login(new_user)

        page = self.client.get('/onboarding/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "set up your candidate profile")
        self.assertContains(page, "Citizenship / Work Rights")
        self.assertContains(page, "Preferred Job Category")

        resume = SimpleUploadedFile(
            "resume.pdf", b"%PDF-1.4 test resume", content_type="application/pdf"
        )
        post_resp = self.client.post('/onboarding/', data={
            'first_name': 'Onboard',
            'last_name': 'Me',
            'phone_number': '+61 400 555 666',
            'location': 'Melbourne VIC',
            'citizenship': 'Australian Citizen',
            'preferred_job_category': 'IT & Software Development',
            'work_type': 'FULL_TIME',
            'preferred_job_role': 'Backend Engineer',
            'resume': resume,
        }, follow=True)
        self.assertEqual(post_resp.status_code, 200)

        new_user.refresh_from_db()
        profile = new_user.candidate_profile
        profile.refresh_from_db()
        self.assertEqual(new_user.phone_number, '+61 400 555 666')
        self.assertEqual(profile.full_name, 'Onboard Me')
        self.assertIn('Melbourne', profile.location)
        self.assertEqual(profile.department, 'IT & Software Development')
        self.assertEqual(profile.employment_type, 'FULL_TIME')
        self.assertEqual(profile.work_permit_countries, ['Australian Citizen'])
        self.assertTrue(profile.has_resume)
        self.assertTrue(profile.is_onboarding_complete)
        self.assertIn('onboarding_answers', profile.parsed_json)

    def test_completed_candidate_is_redirected_from_onboarding(self):
        self.client.force_login(self.candidate_user)
        resp = self.client.get('/onboarding/')
        self.assertRedirects(resp, '/dashboard/')

        # Explicit edit mode still allows updating preferences.
        edit_resp = self.client.get('/onboarding/?edit=1')
        self.assertEqual(edit_resp.status_code, 200)
        self.assertContains(edit_resp, "set up your candidate profile")

    def test_onboarding_requires_authentication(self):
        resp = self.client.get('/onboarding/')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    # --------------------------------------------------------------------------
    # 7. Candidate Account Management (Profile, Resume, Deletion) Tests
    # --------------------------------------------------------------------------
    def test_candidate_profile_page_has_account_actions(self):
        self.client.force_login(self.candidate_user)
        resp = self.client.get('/profile/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My Professional Profile")
        self.assertContains(resp, "Sign Out")
        self.assertContains(resp, "Delete Account")
        self.assertContains(resp, ".pdf,.doc,.docx")

    def test_candidate_can_update_profile_and_resume(self):
        self.client.force_login(self.candidate_user)
        resume = SimpleUploadedFile(
            "updated_resume.docx",
            b"docx-bytes",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        resp = self.client.post('/profile/', data={
            'full_name': 'Sarah Connor',
            'phone_number': '+61 400 123 456',
            'location': 'Sydney NSW',
            'current_designation': 'Lead Developer',
            'current_company': 'Atlassian',
            'total_experience': '6.0',
            'expected_salary': '170000',
            'notice_period': '30',
            'summary': 'Experienced Australian software engineer.',
            'skills': 'Python, Django, AWS',
            'resume': resume,
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        self.candidate_profile.refresh_from_db()
        self.assertTrue(self.candidate_profile.has_resume)
        self.assertEqual(self.candidate_profile.current_designation, 'Lead Developer')
        self.assertEqual(
            set(self.candidate_profile.skills.values_list('skill_name', flat=True)),
            {'Python', 'Django', 'AWS'},
        )

    def test_candidate_delete_account_requires_confirmation(self):
        self.client.force_login(self.candidate_user)
        page = self.client.get('/profile/delete/')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Delete your candidate account?")

        # Posting without the explicit confirmation must not delete the account.
        self.client.post('/profile/delete/', data={}, follow=True)
        self.assertTrue(User.objects.filter(pk=self.candidate_user.pk).exists())

    def test_candidate_can_delete_own_account(self):
        user_id = self.candidate_user.pk
        self.client.force_login(self.candidate_user)

        resp = self.client.post('/profile/delete/', data={'confirm_delete': 'yes'}, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/')

        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(CandidateProfile.objects.filter(user_id=user_id).exists())

        # Session must be invalidated after deletion.
        dash = self.client.get('/dashboard/')
        self.assertEqual(dash.status_code, 302)
        self.assertIn('/login/', dash.url)

    def test_non_candidate_cannot_use_candidate_account_deletion(self):
        self.client.force_login(self.recruiter_user)
        resp = self.client.get('/profile/delete/', follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/')
        self.assertTrue(User.objects.filter(pk=self.recruiter_user.pk).exists())

    # --------------------------------------------------------------------------
    # 8. Australian Locations Autocomplete Lookup Tests
    # --------------------------------------------------------------------------
    def test_candidate_locations_lookup_api(self):
        resp_syd = self.client.get('/api/locations/?q=Syd')
        self.assertEqual(resp_syd.status_code, 200)
        data = resp_syd.json()
        labels = [l['label'] for l in data.get('locations', [])]
        self.assertTrue(any('Sydney' in l for l in labels))

        resp_rem = self.client.get('/api/locations/?q=Remote')
        self.assertEqual(resp_rem.status_code, 200)
        labels_rem = [l['label'] for l in resp_rem.json().get('locations', [])]
        self.assertTrue(any('Remote' in l for l in labels_rem))

    # --------------------------------------------------------------------------
    # 9. Candidate Recommendations Matching Engine Tests
    # --------------------------------------------------------------------------
    def test_candidate_recommendations_matching_engine(self):
        recommended = get_candidate_recommended_jobs(self.candidate_profile, limit=5)
        self.assertIn(self.job, recommended)

    # --------------------------------------------------------------------------
    # 10. Candidate Dashboard Rendering Tests
    # --------------------------------------------------------------------------
    def test_candidate_dashboard_authenticated(self):
        self.client.login(email='candidate.sarah@gmail.com', password='CandidatePassword123!')
        response = self.client.get('/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sarah Connor")
        self.assertContains(response, "Recommended Jobs for You")
        self.assertContains(response, "Target Preferences")
        self.assertContains(response, "Senior Python Backend Engineer")

    # --------------------------------------------------------------------------
    # 11. Direct Job Application Flow Tests
    # --------------------------------------------------------------------------
    def test_job_application_submission(self):
        self.client.login(email='candidate.sarah@gmail.com', password='CandidatePassword123!')

        apply_page = self.client.get(f'/jobs/{self.job.id}/apply/')
        self.assertEqual(apply_page.status_code, 200)
        self.assertContains(apply_page, "Senior Python Backend Engineer")

        apply_payload = {
            'full_name': 'Sarah Connor',
            'phone_number': '+61 400 123 456',
            'location': 'Sydney NSW',
            'total_experience': '5.0',
            'expected_salary': '165000',
            'notice_period': '30',
            'cover_letter': 'I have extensive experience with Python and AWS in Australia.'
        }
        post_response = self.client.post(f'/jobs/{self.job.id}/apply/', data=apply_payload, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # Verify application created in shared TalentVault DB
        app = Application.objects.filter(job=self.job, candidate=self.candidate_profile).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.stage, Application.ApplicationStage.OPEN)
        self.assertTrue(app.in_pipeline)

        # Check candidate applications page
        apps_page = self.client.get('/applications/')
        self.assertEqual(apps_page.status_code, 200)
        self.assertContains(apps_page, "Senior Python Backend Engineer")
        self.assertContains(apps_page, "Atlassian Australia")

    # --------------------------------------------------------------------------
    # 12. Saved Jobs AJAX Toggle Tests
    # --------------------------------------------------------------------------
    def test_save_job_toggle(self):
        self.client.login(email='candidate.sarah@gmail.com', password='CandidatePassword123!')

        # 1. Save Job
        save_resp = self.client.post(
            '/jobs/saved/toggle/',
            data={'job_id': str(self.job.id)},
            content_type='application/json'
        )
        self.assertEqual(save_resp.status_code, 200)
        self.assertEqual(save_resp.json().get('status'), 'saved')
        self.assertTrue(SavedJob.objects.filter(candidate=self.candidate_profile, job=self.job).exists())

        # Check saved jobs page
        saved_page = self.client.get('/saved-jobs/')
        self.assertEqual(saved_page.status_code, 200)
        self.assertContains(saved_page, "Senior Python Backend Engineer")

        # 2. Unsave Job
        unsave_resp = self.client.post(
            '/jobs/saved/toggle/',
            data={'job_id': str(self.job.id)},
            content_type='application/json'
        )
        self.assertEqual(unsave_resp.status_code, 200)
        self.assertEqual(unsave_resp.json().get('status'), 'removed')
        self.assertFalse(SavedJob.objects.filter(candidate=self.candidate_profile, job=self.job).exists())

    # --------------------------------------------------------------------------
    # 13. Employer Suite Tests
    # --------------------------------------------------------------------------
    def test_employer_landing_page(self):
        response = self.client.get('/employers/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find the right talent.")
        self.assertContains(response, "Build your team.")
        self.assertContains(response, "employer-hero")

    def test_employer_registration_creates_talentvault_db_records(self):
        response = self.client.get('/employers/register/')
        self.assertEqual(response.status_code, 200)

        payload = {
            'org_name': 'Qantas Airways Australia',
            'email': 'hr@qantas.com.au',
            'phone_number': '+61 2 9691 3636',
            'hiring_type': 'organization',
            'industry': 'Aviation & Travel',
            'location': 'Mascot, Sydney NSW',
            'password': 'SecureRecruiter123!',
            'confirm_password': 'SecureRecruiter123!',
            'terms': 'on'
        }
        post_response = self.client.post('/employers/register/', data=payload, follow=False)
        self.assertEqual(post_response.status_code, 302)
        expected_target = getattr(settings, 'TALENTVAULT_RECRUITER_WORKSPACE_URL', '/dashboard/recruiter/')
        self.assertIn(expected_target, post_response.url)

        new_recruiter = User.objects.filter(email='hr@qantas.com.au').first()
        self.assertIsNotNone(new_recruiter)
        self.assertEqual(new_recruiter.role, User.Role.RECRUITER)

    # --------------------------------------------------------------------------
    # 14. Informational Pages Tests
    # --------------------------------------------------------------------------
    def test_salary_guide_page(self):
        response = self.client.get('/salary-guide/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Australian Salary Guide")
        self.assertContains(response, "AUD Market Benchmarks")

    def test_career_advice_page(self):
        response = self.client.get('/career-advice/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Australian Career Advice")
        self.assertContains(response, "STAR Technique")

    def test_resources_page(self):
        response = self.client.get('/resources/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Seeker Resources")
        self.assertContains(response, "ATS Resume Template")

    # --------------------------------------------------------------------------
    # 15. Local HTTP & HTTPS Prevention Verification Tests
    # --------------------------------------------------------------------------
    def test_local_http_routes_and_security_settings(self):
        # Verify Django security settings for local development
        self.assertFalse(getattr(settings, 'SECURE_SSL_REDIRECT', False))
        self.assertEqual(getattr(settings, 'SECURE_HSTS_SECONDS', 0), 0)
        self.assertIsNone(getattr(settings, 'SECURE_PROXY_SSL_HEADER', None))

        # Verify main local development endpoints respond over HTTP without HTTPS redirects
        for path in ['/', '/jobs/', '/employers/', '/login/', '/register/']:
            resp = self.client.get(path, HTTP_HOST='127.0.0.1:8002')
            self.assertEqual(resp.status_code, 200, f"Failed for {path}")
            # Ensure no Strict-Transport-Security header is sent
            self.assertNotIn('Strict-Transport-Security', resp.headers)
            # Ensure no Location header forcing HTTPS
            if 'Location' in resp.headers:
                self.assertFalse(resp.headers['Location'].startswith('https://127.0.0.1'))
                self.assertFalse(resp.headers['Location'].startswith('https://localhost'))
