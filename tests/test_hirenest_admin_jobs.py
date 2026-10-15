"""
HireNest Australia job-posting flow tests.

These verify:
- The TalentVault Admin Portal (shared admin key) can post HireNest jobs and
  they appear in the HireNest Australia marketplace.
- External employers post their own jobs through the employer workspace and
  those jobs stay associated with the correct employer company.
- Admin-owned and employer-owned postings are never mixed.
- TalentVault India (INR / Indian location) jobs never surface in HireNest.
"""
import json
from decimal import Decimal

from django.test import Client, TestCase, override_settings

from apps.accounts.models import User
from apps.companies.models import Company, CompanyMember
from apps.jobs.models import Job

from portal.job_service import get_admin_jobs_queryset
from portal.services import get_australian_jobs_queryset


ADMIN_API_KEY = 'test-hirenest-admin-key-12345'
ADMIN_JOBS_URL = '/api/admin/jobs/'


def make_employer(email, company_name, status=User.RecruiterStatus.ACTIVE):
    company = Company.objects.create(
        name=company_name,
        slug=company_name.lower().replace(' ', '-'),
        industry='Information Technology',
        location='Sydney NSW',
    )
    user = User.objects.create_user(
        email=email,
        password='EmployerPassword123!',
        phone_number='+61 2 9000 0000',
        role=User.Role.RECRUITER,
        recruiter_status=status,
        is_active=True,
        is_verified=True,
    )
    CompanyMember.objects.create(
        company=company,
        user=user,
        role=CompanyMember.MemberRole.ADMIN,
        designation='Hiring Lead',
    )
    return company, user


@override_settings(HIRENEST_ADMIN_API_KEY=ADMIN_API_KEY)
class HireNestAdminJobPostingTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.employer_company, self.employer_user = make_employer(
            'employer@aussieco.com.au', 'Aussie Co Pty Ltd'
        )
        self.candidate = User.objects.create_user(
            email='candidate@example.com',
            password='CandidatePassword123!',
            role=User.Role.CANDIDATE,
            is_active=True,
            is_verified=True,
        )
        self.admin = User.objects.create_superuser(
            email='admin@hirenest.com.au', password='AdminPassword123!'
        )

        self.payload = {
            'title': 'Senior Data Engineer',
            'company_name': 'Sydney Analytics Group',
            'location': 'Sydney NSW',
            'job_type': 'FULL_TIME',
            'work_mode': 'HYBRID',
            'department': 'Engineering',
            'min_experience': 5,
            'max_experience': 10,
            'min_salary': '150000',
            'max_salary': '190000',
            'required_skills_text': 'Python, Spark, AWS',
            'description': 'Build the Australian data platform.',
            'status': 'ACTIVE',
        }

    # ------------------------------------------------------------------
    # 1. Admin posts a HireNest job -> it appears in HireNest Australia
    # ------------------------------------------------------------------
    def test_admin_can_post_job_that_appears_in_hirenest(self):
        response = self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps(self.payload),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body['job']['source'], 'ADMIN')
        self.assertEqual(body['job']['currency'], 'AUD')
        self.assertEqual(body['job']['company_name'], 'Sydney Analytics Group')

        job = Job.objects.get(pk=body['job']['id'])
        self.assertEqual(job.source, Job.JobSource.ADMIN)
        self.assertEqual(job.currency, 'AUD')
        self.assertIsNone(job.created_by)
        self.assertEqual(job.company.name, 'Sydney Analytics Group')

        # The job is part of the Australia marketplace and the public search.
        self.assertIn(job, get_australian_jobs_queryset())
        search = self.client.get('/jobs/')
        self.assertContains(search, 'Senior Data Engineer')

    # ------------------------------------------------------------------
    # 2. Admin list returns only admin-owned postings
    # ------------------------------------------------------------------
    def test_admin_job_list_only_returns_admin_postings(self):
        self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps(self.payload),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        employer_job = Job.objects.create(
            company=self.employer_company,
            title='Employer Owned Role',
            location='Melbourne VIC',
            currency='AUD',
            status='ACTIVE',
            description='Owned by the employer.',
            created_by=self.employer_user,
            source=Job.JobSource.EMPLOYER,
        )

        response = self.client.get(ADMIN_JOBS_URL, HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY)
        self.assertEqual(response.status_code, 200)
        titles = {j['title'] for j in response.json()['jobs']}
        self.assertIn('Senior Data Engineer', titles)
        self.assertNotIn(employer_job.title, titles)

    # ------------------------------------------------------------------
    # 3. Admin can manage (update / action / delete) admin postings
    # ------------------------------------------------------------------
    def test_admin_can_manage_own_job(self):
        created = self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps(self.payload),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        ).json()['job']
        job_id = created['id']
        detail_url = f'{ADMIN_JOBS_URL}{job_id}/'

        update = self.client.put(
            detail_url,
            data=json.dumps({'title': 'Principal Data Engineer'}),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()['job']['title'], 'Principal Data Engineer')

        paused = self.client.post(
            detail_url,
            data=json.dumps({'action': 'pause'}),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json()['job']['status'], 'PAUSED')

        deleted = self.client.delete(detail_url, HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY)
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(Job.objects.filter(pk=job_id).exists())

    # ------------------------------------------------------------------
    # 4. Admin API cannot touch an employer-owned posting
    # ------------------------------------------------------------------
    def test_admin_api_cannot_manage_employer_job(self):
        employer_job = Job.objects.create(
            company=self.employer_company,
            title='Employer Private Role',
            location='Brisbane QLD',
            currency='AUD',
            status='ACTIVE',
            description='Owned by the employer.',
            created_by=self.employer_user,
            source=Job.JobSource.EMPLOYER,
        )
        detail_url = f'{ADMIN_JOBS_URL}{employer_job.id}/'
        response = self.client.put(
            detail_url,
            data=json.dumps({'title': 'Hijacked'}),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(response.status_code, 404)
        employer_job.refresh_from_db()
        self.assertEqual(employer_job.title, 'Employer Private Role')

    # ------------------------------------------------------------------
    # 5. External employer posts a job -> owned by the correct employer
    # ------------------------------------------------------------------
    def test_external_employer_job_is_owned_by_employer(self):
        self.client.force_login(self.employer_user)
        response = self.client.post('/employers/jobs/new/', data={
            'title': 'Registered Nurse',
            'department': 'Healthcare',
            'location': 'Melbourne VIC',
            'job_type': 'FULL_TIME',
            'work_mode': 'ONSITE',
            'min_experience': 2,
            'max_experience': 6,
            'min_salary': '90000',
            'max_salary': '110000',
            'required_skills_text': 'Patient Care, Triage',
            'description': 'Join our Melbourne clinic.',
            'status': 'ACTIVE',
        }, follow=False)
        self.assertEqual(response.status_code, 302)

        job = Job.objects.get(title='Registered Nurse')
        self.assertEqual(job.source, Job.JobSource.EMPLOYER)
        self.assertEqual(job.company, self.employer_company)
        self.assertEqual(job.created_by, self.employer_user)
        self.assertEqual(job.currency, 'AUD')

        # It appears in the public Australia marketplace.
        self.assertIn(job, get_australian_jobs_queryset())
        search = self.client.get('/jobs/')
        self.assertContains(search, 'Registered Nurse')

    # ------------------------------------------------------------------
    # 6. Admin postings never leak into the employer workspace
    # ------------------------------------------------------------------
    def test_admin_postings_do_not_leak_into_employer_workspace(self):
        # Admin job assigned to the SAME company as the employer.
        Job.objects.create(
            company=self.employer_company,
            title='Admin Managed Role',
            location='Sydney NSW',
            currency='AUD',
            status='ACTIVE',
            description='Created by the admin portal.',
            source=Job.JobSource.ADMIN,
        )
        Job.objects.create(
            company=self.employer_company,
            title='Employer Own Role',
            location='Sydney NSW',
            currency='AUD',
            status='ACTIVE',
            description='Created by the employer.',
            created_by=self.employer_user,
            source=Job.JobSource.EMPLOYER,
        )

        self.client.force_login(self.employer_user)
        jobs_page = self.client.get('/employers/jobs/')
        self.assertEqual(jobs_page.status_code, 200)
        self.assertContains(jobs_page, 'Employer Own Role')
        self.assertNotContains(jobs_page, 'Admin Managed Role')

    # ------------------------------------------------------------------
    # 7. TalentVault India jobs never appear in HireNest
    # ------------------------------------------------------------------
    def test_talentvault_india_jobs_do_not_appear_in_hirenest(self):
        india_company = Company.objects.create(
            name='Bangalore Tech Ltd',
            slug='bangalore-tech-ltd',
            industry='IT',
            location='Bangalore, India',
        )
        india_job = Job.objects.create(
            company=india_company,
            title='Java Engineer (India)',
            location='Bangalore, India',
            currency='INR',
            min_salary=Decimal('1200000.00'),
            max_salary=Decimal('2000000.00'),
            status='ACTIVE',
            description='India role.',
        )
        self.assertNotIn(india_job, get_australian_jobs_queryset())
        search = self.client.get('/jobs/')
        self.assertNotContains(search, 'Java Engineer (India)')

    # ------------------------------------------------------------------
    # 8. Only admins (shared key or super-admin session) can use the API
    # ------------------------------------------------------------------
    def test_admin_jobs_api_requires_admin(self):
        # Anonymous
        self.assertEqual(self.client.get(ADMIN_JOBS_URL).status_code, 403)
        # Candidate session
        self.client.force_login(self.candidate)
        self.assertEqual(self.client.get(ADMIN_JOBS_URL).status_code, 403)
        # Employer session
        self.client.force_login(self.employer_user)
        self.assertEqual(self.client.get(ADMIN_JOBS_URL).status_code, 403)
        # Super-admin session
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(ADMIN_JOBS_URL).status_code, 200)

    # ------------------------------------------------------------------
    # 9. Invalid payloads are rejected without creating a job
    # ------------------------------------------------------------------
    def test_admin_create_requires_required_fields(self):
        response = self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps({'title': 'Missing fields'}),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Job.objects.filter(title='Missing fields').exists())

    # ------------------------------------------------------------------
    # 10. Admin-created jobs are returned by the admin queryset
    # ------------------------------------------------------------------
    def test_admin_jobs_queryset_excludes_employer_jobs(self):
        admin_job = Job.objects.create(
            company=self.employer_company,
            title='Admin Queryset Role',
            location='Perth WA',
            currency='AUD',
            status='ACTIVE',
            description='Admin role.',
            source=Job.JobSource.ADMIN,
        )
        employer_job = Job.objects.create(
            company=self.employer_company,
            title='Employer Queryset Role',
            location='Perth WA',
            currency='AUD',
            status='ACTIVE',
            description='Employer role.',
            source=Job.JobSource.EMPLOYER,
        )
        qs = get_admin_jobs_queryset()
        self.assertIn(admin_job, qs)
        self.assertNotIn(employer_job, qs)

    # ------------------------------------------------------------------
    # 11. Currency regression tests: USD / AUD creation, update & reload
    # ------------------------------------------------------------------
    def test_admin_can_create_usd_job_and_persists_in_db_and_api(self):
        payload = dict(self.payload)
        payload['currency'] = 'USD'
        payload['country'] = 'United States'
        payload['location'] = 'San Francisco, CA, United States'
        payload['min_salary'] = '140000'
        payload['max_salary'] = '180000'

        response = self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body['job']['currency'], 'USD')

        job = Job.objects.get(pk=body['job']['id'])
        self.assertEqual(job.currency, 'USD')

        # Verify currency survives a reload via GET
        detail_resp = self.client.get(
            f"{ADMIN_JOBS_URL}{job.id}/",
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()['job']['currency'], 'USD')

        # Verify jobs list also returns USD
        list_resp = self.client.get(
            ADMIN_JOBS_URL,
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(list_resp.status_code, 200)
        usd_jobs = [j for j in list_resp.json()['jobs'] if j['id'] == str(job.id)]
        self.assertEqual(len(usd_jobs), 1)
        self.assertEqual(usd_jobs[0]['currency'], 'USD')

    def test_admin_can_update_job_currency_from_aud_to_usd_and_reload(self):
        # 1. Create job with AUD
        created = self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps(self.payload),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        ).json()['job']
        job_id = created['id']
        detail_url = f'{ADMIN_JOBS_URL}{job_id}/'

        job = Job.objects.get(pk=job_id)
        self.assertEqual(job.currency, 'AUD')

        # 2. Update to USD
        update_resp = self.client.put(
            detail_url,
            data=json.dumps({'currency': 'USD'}),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()['job']['currency'], 'USD')

        # 3. Verify in DB
        job.refresh_from_db()
        self.assertEqual(job.currency, 'USD')

        # 4. Partial update of another field must NOT silently revert USD to AUD
        partial_resp = self.client.put(
            detail_url,
            data=json.dumps({'title': 'Senior Staff Data Engineer'}),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(partial_resp.status_code, 200)
        self.assertEqual(partial_resp.json()['job']['currency'], 'USD')
        job.refresh_from_db()
        self.assertEqual(job.currency, 'USD')

        # 5. Reloading via GET still returns USD
        reload_resp = self.client.get(detail_url, HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY)
        self.assertEqual(reload_resp.status_code, 200)
        self.assertEqual(reload_resp.json()['job']['currency'], 'USD')

    def test_create_job_defaults_currency_by_country_usa_and_australia(self):
        # USA country defaults to USD
        usa_payload = dict(self.payload)
        usa_payload.pop('currency', None)
        usa_payload['country'] = 'United States'
        usa_payload['location'] = 'New York, NY, USA'
        usa_resp = self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps(usa_payload),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(usa_resp.status_code, 201)
        self.assertEqual(usa_resp.json()['job']['currency'], 'USD')

        # Australia country defaults to AUD
        au_payload = dict(self.payload)
        au_payload.pop('currency', None)
        au_payload['country'] = 'Australia'
        au_payload['location'] = 'Melbourne, VIC, Australia'
        au_resp = self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps(au_payload),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(au_resp.status_code, 201)
        self.assertEqual(au_resp.json()['job']['currency'], 'AUD')

    def test_negotiable_salary_does_not_show_misleading_currency_label(self):
        # Admin creates job with no min/max salary
        negotiable_payload = dict(self.payload)
        negotiable_payload.pop('min_salary', None)
        negotiable_payload.pop('max_salary', None)
        negotiable_payload['currency'] = 'USD'
        response = self.client.post(
            ADMIN_JOBS_URL,
            data=json.dumps(negotiable_payload),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(response.status_code, 201)
        job_id = response.json()['job']['id']
        job = Job.objects.get(pk=job_id)
        self.assertEqual(job.formatted_salary_display, 'Salary negotiable')

        # Public detail view should show "Salary" and not "Annual Salary (AUD)"
        detail_view = self.client.get(f'/jobs/{job_id}/')
        self.assertEqual(detail_view.status_code, 200)
        self.assertContains(detail_view, 'Salary negotiable')
        self.assertNotContains(detail_view, 'Annual Salary (AUD)')
