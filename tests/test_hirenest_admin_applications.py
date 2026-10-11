"""
HireNest candidate applications admin API tests.

Verifies the secure server-to-server applications endpoint consumed by the
TalentVault Admin Portal, plus the worldwide fields on the candidate
application form (single location, currency, salary period and international
work authorisation).
"""
import json
from decimal import Decimal

from django.test import Client, TestCase, override_settings

from apps.accounts.models import User
from apps.applications.models import Application
from apps.candidates.models import CandidateProfile
from apps.companies.models import Company
from apps.jobs.models import Job

from portal.forms import JobApplicationForm


ADMIN_API_KEY = 'test-hirenest-admin-key-applications-123'
APPLICATIONS_URL = '/api/admin/applications/'


@override_settings(HIRENEST_ADMIN_API_KEY=ADMIN_API_KEY, USE_LOCAL_STORAGE='1')
class HireNestAdminApplicationsAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.company = Company.objects.create(
            name='Aussie Data Co', slug='aussie-data-co', industry='IT', location='Sydney NSW'
        )
        self.job = Job.objects.create(
            company=self.company,
            title='Data Engineer',
            location='Sydney NSW',
            currency='AUD',
            status='ACTIVE',
            description='Build the data platform.',
        )
        self.candidate_user = User.objects.create_user(
            email='candidate@example.com',
            password='CandidatePassword123!',
            first_name='Jane',
            last_name='Doe',
            phone_number='+61 400 111 222',
            role=User.Role.CANDIDATE,
            is_active=True,
            is_verified=True,
        )
        self.profile = CandidateProfile.objects.create(
            user=self.candidate_user,
            full_name='Jane Doe',
            location='Sydney NSW',
            expected_salary=Decimal('160000.00'),
        )
        self.admin = User.objects.create_superuser(
            email='admin@hirenest.com.au', password='AdminPassword123!'
        )

    def _make_application(self, **kwargs):
        defaults = {
            'job': self.job,
            'candidate': self.profile,
            'stage': Application.ApplicationStage.OPEN,
            'in_pipeline': True,
            'expected_ctc': Decimal('150000.00'),
            'expected_salary_currency': 'AUD',
            'salary_period': 'ANNUALLY',
            'screening_answers': [
                {'question': 'Are you eligible to work?', 'answer': 'Yes', 'type': 'YES_NO', 'required': True}
            ],
        }
        defaults.update(kwargs)
        return Application.objects.create(**defaults)

    def _get(self, url=None):
        return self.client.get(url or APPLICATIONS_URL, HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY)

    # ------------------------------------------------------------------
    # Access control
    # ------------------------------------------------------------------
    def test_applications_api_requires_admin(self):
        self.assertEqual(self.client.get(APPLICATIONS_URL).status_code, 403)

    # ------------------------------------------------------------------
    # List + detail
    # ------------------------------------------------------------------
    def test_list_applications_returns_worldwide_fields(self):
        self._make_application()
        response = self._get()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['count'], 1)
        app = body['applications'][0]
        self.assertEqual(app['candidate_name'], 'Jane Doe')
        self.assertEqual(app['email'], 'candidate@example.com')
        self.assertEqual(app['job_title'], 'Data Engineer')
        self.assertEqual(app['location'], 'Sydney NSW')
        self.assertEqual(app['expected_salary_currency'], 'AUD')
        self.assertEqual(app['salary_period'], 'ANNUALLY')
        self.assertEqual(app['status_display'], 'Applied')

    def test_application_detail_includes_screening_answers(self):
        application = self._make_application()
        response = self._get(f'{APPLICATIONS_URL}{application.id}/')
        self.assertEqual(response.status_code, 200)
        app = response.json()['application']
        self.assertEqual(app['screening_answers'][0]['answer'], 'Yes')
        self.assertIn('resume_url', app)
        self.assertIn('resume_preview_url', app)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    def test_filter_by_status(self):
        self._make_application()
        self.assertEqual(self._get(APPLICATIONS_URL + '?status=APPLIED').json()['count'], 1)
        self.assertEqual(self._get(APPLICATIONS_URL + '?status=REJECTED').json()['count'], 0)

    def test_filter_by_candidate_name(self):
        self._make_application()
        self.assertEqual(self._get(APPLICATIONS_URL + '?q=Jane').json()['count'], 1)
        self.assertEqual(self._get(APPLICATIONS_URL + '?q=nobody').json()['count'], 0)

    def test_filter_by_job(self):
        self._make_application()
        self.assertEqual(self._get(APPLICATIONS_URL + f'?job={self.job.id}').json()['count'], 1)
        other_job = Job.objects.create(
            company=self.company, title='Other Role', location='Melbourne VIC',
            currency='AUD', status='ACTIVE', description='Other.'
        )
        self.assertEqual(self._get(APPLICATIONS_URL + f'?job={other_job.id}').json()['count'], 0)

    # ------------------------------------------------------------------
    # Legacy defaults
    # ------------------------------------------------------------------
    def test_legacy_application_defaults_currency_and_period(self):
        self._make_application(expected_salary_currency='', salary_period='')
        app = self._get().json()['applications'][0]
        self.assertEqual(app['expected_salary_currency'], 'AUD')
        self.assertEqual(app['salary_period'], 'ANNUALLY')

    # ------------------------------------------------------------------
    # Worldwide application form
    # ------------------------------------------------------------------
    def test_application_form_has_worldwide_fields(self):
        form = JobApplicationForm()
        self.assertNotIn('suburb', form.fields)
        self.assertNotIn('state', form.fields)
        self.assertIn('location', form.fields)
        self.assertIn('expected_salary_currency', form.fields)
        self.assertIn('salary_period', form.fields)
        work_rights_choices = [c[0] for c in form.fields['work_rights'].choices]
        self.assertNotIn('Australian Citizen', work_rights_choices)
        self.assertIn('Work Visa / Permit', work_rights_choices)

    def test_apply_persists_currency_and_period(self):
        self.client.force_login(self.candidate_user)
        response = self.client.post(
            f'/jobs/{self.job.id}/apply/',
            data={
                'full_name': 'Jane Doe',
                'phone_number': '+61 400 111 222',
                'location': 'Sydney NSW',
                'expected_salary': '150000',
                'expected_salary_currency': 'INR',
                'salary_period': 'MONTHLY',
                'work_rights': 'Work Visa / Permit',
                'notice_period': '30',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        application = Application.objects.get(job=self.job, candidate=self.profile)
        self.assertEqual(application.expected_salary_currency, 'INR')
        self.assertEqual(application.salary_period, 'MONTHLY')
        self.assertEqual(application.expected_ctc, Decimal('150000.00'))
