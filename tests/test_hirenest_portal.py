import os
import json
import pytest
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, Client
from django.conf import settings
from django.utils import timezone
from apps.accounts.models import User, OTPVerification
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
    # 5. Candidate Email + OTP Authentication Flow Tests
    # --------------------------------------------------------------------------
    def test_send_otp_success_and_rate_limiting(self):
        test_email = "newcandidate.alex@gmail.com"

        # 1. First OTP request
        resp1 = self.client.post(
            '/auth/send-otp/',
            data=json.dumps({'email': test_email}),
            content_type='application/json'
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.json()
        self.assertTrue(data1.get('success'))
        self.assertEqual(data1.get('cooldown'), 60)

        # Verify record in database
        otp_rec = OTPVerification.objects.filter(email=test_email).first()
        self.assertIsNotNone(otp_rec)
        self.assertFalse(otp_rec.verified)

        # 2. Immediate second request triggers rate limit cooldown (HTTP 429)
        resp2 = self.client.post(
            '/auth/send-otp/',
            data=json.dumps({'email': test_email}),
            content_type='application/json'
        )
        self.assertEqual(resp2.status_code, 429)
        self.assertFalse(resp2.json().get('success'))

    def test_verify_otp_valid_and_creates_candidate_identity(self):
        test_email = "alex.turner@gmail.com"
        raw_code = "654321"

        otp_rec = OTPVerification(
            email=test_email,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        otp_rec.set_otp(raw_code)
        otp_rec.save()

        verify_resp = self.client.post(
            '/auth/verify-otp/',
            data=json.dumps({'email': test_email, 'otp': raw_code}),
            content_type='application/json'
        )
        self.assertEqual(verify_resp.status_code, 200)
        data = verify_resp.json()
        self.assertTrue(data.get('success'))
        self.assertTrue(data.get('is_new'))
        self.assertTrue(data.get('onboarding_required'))

        # Verify user and candidate profile created in shared DB
        created_user = User.objects.filter(email=test_email).first()
        self.assertIsNotNone(created_user)
        self.assertEqual(created_user.role, User.Role.CANDIDATE)
        self.assertTrue(created_user.is_verified)
        self.assertTrue(CandidateProfile.objects.filter(user=created_user).exists())

    def test_verify_otp_invalid_and_expired(self):
        test_email = "invalid.test@gmail.com"
        raw_code = "123456"

        otp_rec = OTPVerification(
            email=test_email,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        otp_rec.set_otp(raw_code)
        otp_rec.save()

        # 1. Wrong OTP code
        bad_resp = self.client.post(
            '/auth/verify-otp/',
            data=json.dumps({'email': test_email, 'otp': '999999'}),
            content_type='application/json'
        )
        self.assertEqual(bad_resp.status_code, 400)
        self.assertFalse(bad_resp.json().get('success'))

        # 2. Expired OTP record
        otp_rec.expires_at = timezone.now() - timedelta(minutes=5)
        otp_rec.save()

        expired_resp = self.client.post(
            '/auth/verify-otp/',
            data=json.dumps({'email': test_email, 'otp': raw_code}),
            content_type='application/json'
        )
        self.assertEqual(expired_resp.status_code, 400)
        self.assertIn("expired", expired_resp.json().get('error', '').lower())

    # --------------------------------------------------------------------------
    # 6. Social Auth (Google / Apple) Endpoint Tests
    # --------------------------------------------------------------------------
    def test_social_auth_google_and_apple(self):
        # 1. Google sign-in
        google_resp = self.client.post(
            '/auth/social/',
            data=json.dumps({
                'provider': 'google',
                'email': 'emma.watson@gmail.com',
                'name': 'Emma Watson',
            }),
            content_type='application/json'
        )
        self.assertEqual(google_resp.status_code, 200)
        self.assertTrue(google_resp.json().get('success'))

        user_emma = User.objects.filter(email='emma.watson@gmail.com').first()
        self.assertIsNotNone(user_emma)
        self.assertEqual(user_emma.role, User.Role.CANDIDATE)

        # 2. Apple sign-in linking existing user
        apple_resp = self.client.post(
            '/auth/social/',
            data=json.dumps({
                'provider': 'apple',
                'email': 'emma.watson@gmail.com',
                'name': 'Emma Watson',
            }),
            content_type='application/json'
        )
        self.assertEqual(apple_resp.status_code, 200)
        self.assertTrue(apple_resp.json().get('success'))
        # No duplicate user created
        self.assertEqual(User.objects.filter(email='emma.watson@gmail.com').count(), 1)

    # --------------------------------------------------------------------------
    # 7. 3-Question Onboarding Wizard API Tests
    # --------------------------------------------------------------------------
    def test_candidate_3_question_onboarding_wizard_api(self):
        self.client.login(email='candidate.sarah@gmail.com', password='CandidatePassword123!')

        payload = {
            'categories': ['IT & Software Development'],
            'role_title': 'Lead Cloud Engineer',
            'locations': ['Sydney NSW', 'Remote • Australia'],
            'job_types': ['FULL_TIME', 'CONTRACT']
        }

        onboard_resp = self.client.post(
            '/api/onboarding/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(onboard_resp.status_code, 200)
        self.assertTrue(onboard_resp.json().get('success'))

        # Verify saved in CandidateProfile
        self.candidate_profile.refresh_from_db()
        self.assertEqual(self.candidate_profile.department, 'IT & Software Development')
        self.assertEqual(self.candidate_profile.preferred_job_role, 'Lead Cloud Engineer')
        self.assertIn('Sydney NSW', self.candidate_profile.preferred_location)
        self.assertEqual(self.candidate_profile.employment_type, 'FULL_TIME')
        self.assertIn('onboarding_answers', self.candidate_profile.parsed_json)

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
