import os
import pytest
from decimal import Decimal
from django.test import TestCase, Client
from django.conf import settings
from apps.accounts.models import User
from apps.companies.models import Company, CompanyMember
from apps.jobs.models import Job, JobSkill
from apps.candidates.models import CandidateProfile, SavedJob
from apps.applications.models import Application


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
    # 2. Australian Job Search & Filter Tests
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
    # 3. Job Details Page Tests
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
    # 4. Candidate Registration & Login Tests
    # --------------------------------------------------------------------------
    def test_candidate_registration(self):
        response = self.client.get('/register/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Candidate Account")

        payload = {
            'first_name': 'David',
            'last_name': 'Warner',
            'email': 'david.warner@cricket.com.au',
            'phone_number': '+61 411 999 888',
            'location': 'Sydney NSW',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!',
            'terms': 'on'
        }
        post_response = self.client.post('/register/', data=payload, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # Verify candidate created in shared TalentVault DB
        new_user = User.objects.filter(email='david.warner@cricket.com.au').first()
        self.assertIsNotNone(new_user)
        self.assertEqual(new_user.role, User.Role.CANDIDATE)
        self.assertTrue(CandidateProfile.objects.filter(user=new_user).exists())

    def test_candidate_login(self):
        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Candidate Log In")

        login_payload = {
            'email': 'candidate.sarah@gmail.com',
            'password': 'CandidatePassword123!',
            'remember_me': 'on'
        }
        post_response = self.client.post('/login/', data=login_payload, follow=True)
        self.assertEqual(post_response.status_code, 200)
        self.assertTrue(post_response.context['user'].is_authenticated)
        self.assertEqual(post_response.context['user'].email, 'candidate.sarah@gmail.com')

    # --------------------------------------------------------------------------
    # 5. Direct Job Application Flow Tests
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
    # 6. Saved Jobs AJAX Toggle Tests
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
    # 7. Employer Suite & TalentVault Recruiter Workspace Redirection Tests
    # --------------------------------------------------------------------------
    def test_employer_landing_page(self):
        response = self.client.get('/employers/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Find the right talent.")
        self.assertContains(response, "Build your team.")
        self.assertContains(response, "employer-hero")
        self.assertContains(response, "AI Candidate Matching")
        self.assertContains(response, "Register as Employer")
        self.assertContains(response, "Employer Login")

    def test_employer_registration_creates_talentvault_db_records(self):
        response = self.client.get('/employers/register/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register Employer Account")

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
        # Should redirect into the TalentVault Recruiter Workspace URL
        self.assertEqual(post_response.status_code, 302)
        expected_target = getattr(settings, 'TALENTVAULT_RECRUITER_WORKSPACE_URL', '/dashboard/recruiter/')
        self.assertIn(expected_target, post_response.url)

        # Verify employer account created in shared TalentVault database
        new_recruiter = User.objects.filter(email='hr@qantas.com.au').first()
        self.assertIsNotNone(new_recruiter)
        self.assertEqual(new_recruiter.role, User.Role.RECRUITER)
        company = Company.objects.filter(name='Qantas Airways Australia').first()
        self.assertIsNotNone(company)
        self.assertTrue(CompanyMember.objects.filter(company=company, user=new_recruiter).exists())

    def test_employer_login_redirects_to_talentvault_recruiter_workspace(self):
        response = self.client.get('/employers/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employer Sign In")

        login_payload = {
            'email': 'recruiter@atlassian.com.au',
            'password': 'RecruiterPassword123!',
            'remember_me': 'on'
        }
        post_response = self.client.post('/employers/login/', data=login_payload, follow=False)
        # Verify redirect to TalentVault Recruiter Workspace
        self.assertEqual(post_response.status_code, 302)
        expected_target = getattr(settings, 'TALENTVAULT_RECRUITER_WORKSPACE_URL', '/dashboard/recruiter/')
        self.assertIn(expected_target, post_response.url)

    # --------------------------------------------------------------------------
    # 8. Informational Pages Tests
    # --------------------------------------------------------------------------
    def test_companies_directory(self):
        response = self.client.get('/companies/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Atlassian Australia")

        detail_response = self.client.get('/companies/atlassian-australia/')
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Atlassian Australia")
        self.assertContains(detail_response, "Senior Python Backend Engineer")

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
