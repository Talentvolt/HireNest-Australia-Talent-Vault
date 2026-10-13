"""
HireNest Australia job sharing feature tests.

These verify:
- Public share URLs always use the production domain (never localhost).
- Public job cards and the job detail page expose Share / Copy Link controls.
- The employer Manage Jobs workspace exposes Share / Copy Link only for active
  (published) jobs.
- Draft / paused / closed postings stay protected from the public website.
"""
from decimal import Decimal

from django.test import TestCase, Client

from apps.accounts.models import User
from apps.companies.models import Company, CompanyMember
from apps.jobs.models import Job


class JobShareFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.company = Company.objects.create(
            name="Atlassian Australia",
            slug="atlassian-australia",
            industry="Information Technology",
            location="Sydney NSW",
            website="https://www.atlassian.com",
        )

        self.recruiter_user = User.objects.create_user(
            email="recruiter@atlassian.com.au",
            password="RecruiterPassword123!",
            first_name="Liam",
            last_name="Smith",
            phone_number="+61 2 9000 1234",
            role=User.Role.RECRUITER,
            recruiter_status=User.RecruiterStatus.ACTIVE,
            is_active=True,
            is_verified=True,
        )
        CompanyMember.objects.create(
            company=self.company,
            user=self.recruiter_user,
            designation="Talent Lead",
            role=CompanyMember.MemberRole.ADMIN,
        )

        self.active_job = Job.objects.create(
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
            status=Job.JobStatus.ACTIVE,
            description="Join our core platform engineering team in Sydney.",
            created_by=self.recruiter_user,
        )

        self.draft_job = Job.objects.create(
            company=self.company,
            title="Draft Backend Role",
            location="Sydney NSW",
            job_type="FULL_TIME",
            work_mode="ONSITE",
            department="Engineering",
            min_experience=2,
            max_experience=5,
            currency="AUD",
            status=Job.JobStatus.DRAFT,
            description="Still being written.",
            created_by=self.recruiter_user,
        )

    def test_public_share_url_uses_production_domain(self):
        url = self.active_job.public_share_url
        self.assertEqual(url, f"https://hirenest.com.au/jobs/{self.active_job.id}/")
        self.assertNotIn("localhost", url)
        self.assertNotIn("127.0.0.1", url)
        self.assertNotIn("testserver", url)

    def test_job_detail_page_exposes_share_controls_and_production_url(self):
        response = self.client.get(f"/jobs/{self.active_job.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hn-copy-job-link")
        self.assertContains(response, f"https://hirenest.com.au/jobs/{self.active_job.id}/")

    def test_job_search_cards_expose_share_controls(self):
        response = self.client.get("/jobs/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hn-copy-job-link")
        self.assertContains(response, f"https://hirenest.com.au/jobs/{self.active_job.id}/")

    def test_landing_cards_expose_share_controls(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hn-copy-job-link")

    def test_employer_manage_jobs_exposes_share_for_active_job(self):
        self.client.force_login(self.recruiter_user)
        response = self.client.get("/employers/jobs/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"data-share-url=\"{self.active_job.public_share_url}\"")

    def test_employer_manage_jobs_hides_share_for_draft_job(self):
        self.client.force_login(self.recruiter_user)
        response = self.client.get("/employers/jobs/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.draft_job.title)
        self.assertNotContains(response, self.draft_job.public_share_url)

    def test_draft_job_is_not_publicly_accessible(self):
        response = self.client.get(f"/jobs/{self.draft_job.id}/")
        self.assertEqual(response.status_code, 404)

    def test_closed_job_is_not_publicly_accessible(self):
        closed_job = Job.objects.create(
            company=self.company,
            title="Closed Role",
            location="Melbourne VIC",
            job_type="FULL_TIME",
            work_mode="ONSITE",
            department="Engineering",
            min_experience=2,
            max_experience=5,
            currency="AUD",
            status=Job.JobStatus.CLOSED,
            description="No longer hiring.",
            created_by=self.recruiter_user,
        )
        response = self.client.get(f"/jobs/{closed_job.id}/")
        self.assertEqual(response.status_code, 404)
