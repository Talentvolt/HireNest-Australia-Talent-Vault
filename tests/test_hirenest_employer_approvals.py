"""
HireNest Australia employer registration + approval workflow tests.

These tests verify:
- HireNest employer registration stays inside HireNest (never TalentVault).
- New employers are created PENDING and cannot access the workspace.
- The secure admin API (used by the TalentVault Admin Portal) can list,
  approve and reject HireNest employers.
- Only admins can approve/reject; recruiters and candidates cannot.
- HireNest jobs/candidates remain isolated from TalentVault.
"""
import json
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile
from apps.companies.models import Company, CompanyMember
from apps.jobs.models import Job

from portal.services import get_australian_jobs_queryset
from portal.employer_service import apply_employer_action


ADMIN_API_KEY = 'test-hirenest-admin-key-12345'
API_LIST_URL = '/api/admin/employer-approvals/'
APPROVALS_PAGE_URL = '/employers/approvals/'


def make_employer(email, company_name, status, is_active=True):
    company = Company.objects.create(
        name=company_name,
        slug=company_name.lower().replace(' ', '-'),
        industry='Information Technology',
        location='Sydney NSW',
        website='https://example.com',
        description=f"{company_name} is an Australian employer.",
    )
    user = User.objects.create_user(
        email=email,
        password='EmployerPassword123!',
        phone_number='+61 2 9000 0000',
        role=User.Role.RECRUITER,
        recruiter_status=status,
        is_active=is_active,
        is_verified=status == User.RecruiterStatus.ACTIVE,
    )
    CompanyMember.objects.create(
        company=company,
        user=user,
        role=CompanyMember.MemberRole.ADMIN,
        designation='Hiring Lead',
    )
    return company, user


@override_settings(HIRENEST_ADMIN_API_KEY=ADMIN_API_KEY)
class HireNestEmployerApprovalTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.approved_company, self.approved_user = make_employer(
            'approved@company.com', 'Approved Company AU', User.RecruiterStatus.ACTIVE
        )
        self.pending_company, self.pending_user = make_employer(
            'pending@company.com', 'Pending Company AU', User.RecruiterStatus.PENDING
        )
        self.rejected_company, self.rejected_user = make_employer(
            'rejected@company.com', 'Rejected Company AU',
            User.RecruiterStatus.REJECTED, is_active=False
        )

        self.candidate_user = User.objects.create_user(
            email='candidate@example.com',
            password='CandidatePassword123!',
            role=User.Role.CANDIDATE,
            is_active=True,
            is_verified=True,
        )
        CandidateProfile.objects.create(
            user=self.candidate_user,
            full_name='HireNest Candidate',
            location='Sydney NSW',
            department='Engineering',
            candidate_status='ACTIVE',
        )

        self.super_admin = User.objects.create_superuser(
            email='admin@hirenest.com.au', password='AdminPassword123!'
        )

        self.job = Job.objects.create(
            company=self.approved_company,
            title='Senior Python Engineer',
            location='Sydney NSW',
            job_type='FULL_TIME',
            work_mode='HYBRID',
            department='Engineering',
            min_salary=Decimal('150000.00'),
            max_salary=Decimal('190000.00'),
            currency='AUD',
            status='ACTIVE',
            required_skills_text='Python, Django, AWS',
            description='Australian role.',
            created_by=self.approved_user,
        )

    # ------------------------------------------------------------------
    # 1. Registration route stays within HireNest
    # ------------------------------------------------------------------
    def test_register_as_employer_route_stays_in_hirenest(self):
        landing = self.client.get('/employers/')
        self.assertEqual(landing.status_code, 200)
        self.assertContains(landing, 'href="/employers/register/"')
        self.assertNotContains(landing, 'talent-vault.in')

        register_page = self.client.get('/employers/register/')
        self.assertEqual(register_page.status_code, 200)

        response = self.client.post('/employers/register/', data={
            'org_name': 'New Aussie Pty Ltd',
            'email': 'hr@newaussie.com',
            'phone_number': '+61 2 8000 1111',
            'hiring_type': 'organization',
            'industry': 'Technology',
            'location': 'Melbourne VIC',
            'password': 'SecureEmployer123!',
            'confirm_password': 'SecureEmployer123!',
            'terms': 'on',
        }, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/employers/registration-pending/')
        self.assertNotIn('talent-vault.in', response.url)

        pending_page = self.client.get('/employers/registration-pending/')
        self.assertEqual(pending_page.status_code, 200)
        self.assertContains(pending_page, 'awaiting approval')
        self.assertNotContains(pending_page, 'talent-vault.in')

    # ------------------------------------------------------------------
    # 2. Registration creates a PENDING HireNest employer
    # ------------------------------------------------------------------
    def test_employer_registration_creates_pending_hirenest_employer(self):
        self.client.post('/employers/register/', data={
            'org_name': 'Pending Co Australia',
            'email': 'jobs@pendingco.com',
            'phone_number': '+61 3 9000 2222',
            'hiring_type': 'organization',
            'industry': 'Healthcare',
            'location': 'Brisbane QLD',
            'password': 'SecureEmployer123!',
            'confirm_password': 'SecureEmployer123!',
            'terms': 'on',
        })

        employer = User.objects.filter(email='jobs@pendingco.com').first()
        self.assertIsNotNone(employer)
        self.assertEqual(employer.role, User.Role.RECRUITER)
        self.assertEqual(employer.recruiter_status, User.RecruiterStatus.PENDING)
        self.assertFalse(employer.is_verified)
        self.assertTrue(CompanyMember.objects.filter(user=employer).exists())

    # ------------------------------------------------------------------
    # 3. TalentVault admin can see pending HireNest employers
    # ------------------------------------------------------------------
    def test_talentvault_admin_can_see_pending_hirenest_employers(self):
        response = self.client.get(
            API_LIST_URL + '?status=PENDING',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['source'], 'hirenest')
        emails = {e['email'] for e in payload['employers']}
        self.assertIn('pending@company.com', emails)
        self.assertNotIn('approved@company.com', emails)
        # The integration payload must never contain jobs/candidate data.
        self.assertNotIn('jobs', payload)
        for employer in payload['employers']:
            self.assertNotIn('jobs', employer)
            self.assertIn('company_name', employer)
            self.assertIn('registration_date', employer)

    # ------------------------------------------------------------------
    # 4. TalentVault admin can approve a HireNest employer
    # ------------------------------------------------------------------
    def test_talentvault_admin_can_approve_hirenest_employer(self):
        url = f'{API_LIST_URL}{self.pending_user.id}/'
        response = self.client.post(
            url,
            data=json.dumps({'action': 'approve'}),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(response.status_code, 200)
        self.pending_user.refresh_from_db()
        self.assertEqual(self.pending_user.recruiter_status, User.RecruiterStatus.ACTIVE)
        self.assertTrue(self.pending_user.is_active)

    # ------------------------------------------------------------------
    # 5. TalentVault admin can reject a HireNest employer
    # ------------------------------------------------------------------
    def test_talentvault_admin_can_reject_hirenest_employer(self):
        url = f'{API_LIST_URL}{self.pending_user.id}/'
        response = self.client.post(
            url,
            data=json.dumps({'action': 'reject', 'reason': 'Unverifiable business details'}),
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY,
        )
        self.assertEqual(response.status_code, 200)
        self.pending_user.refresh_from_db()
        self.assertEqual(self.pending_user.recruiter_status, User.RecruiterStatus.REJECTED)
        # Registration record is retained, never deleted.
        self.assertTrue(User.objects.filter(pk=self.pending_user.pk).exists())

    # ------------------------------------------------------------------
    # 6. Pending employer cannot access the recruiter workspace
    # ------------------------------------------------------------------
    def test_pending_hirenest_employer_cannot_access_recruiter_workspace(self):
        self.client.force_login(self.pending_user)
        response = self.client.get('/employers/dashboard/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/employers/login/')

    # ------------------------------------------------------------------
    # 7. Approved employer can access the recruiter workspace
    # ------------------------------------------------------------------
    def test_approved_hirenest_employer_can_access_recruiter_workspace(self):
        self.client.force_login(self.approved_user)
        dashboard = self.client.get('/employers/dashboard/')
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'Recruiter Dashboard')

        self.assertEqual(self.client.get('/employers/jobs/').status_code, 200)
        self.assertEqual(self.client.get('/employers/jobs/new/').status_code, 200)
        self.assertEqual(self.client.get('/employers/profile/').status_code, 200)

    # ------------------------------------------------------------------
    # 8. Rejected employer cannot access the recruiter workspace
    # ------------------------------------------------------------------
    def test_rejected_hirenest_employer_cannot_access_recruiter_workspace(self):
        self.client.force_login(self.rejected_user)
        response = self.client.get('/employers/dashboard/')
        self.assertEqual(response.status_code, 302)
        # Rejected employers are inactive, so the session is invalid and the
        # request is bounced to the HireNest employer login (never TalentVault).
        self.assertTrue(response.url.startswith('/employers/login/'))
        self.assertNotIn('talent-vault.in', response.url)

    # ------------------------------------------------------------------
    # 9. Normal TalentVault recruiter cannot approve HireNest employers
    # ------------------------------------------------------------------
    def test_normal_talentvault_recruiter_cannot_approve_hirenest_employers(self):
        # No shared secret + a recruiter session must be rejected.
        self.client.force_login(self.approved_user)
        list_response = self.client.get(API_LIST_URL)
        self.assertEqual(list_response.status_code, 403)

        action_response = self.client.post(
            f'{API_LIST_URL}{self.pending_user.id}/',
            data=json.dumps({'action': 'approve'}),
            content_type='application/json',
        )
        self.assertEqual(action_response.status_code, 403)

        self.pending_user.refresh_from_db()
        self.assertEqual(self.pending_user.recruiter_status, User.RecruiterStatus.PENDING)

    # ------------------------------------------------------------------
    # 10. HireNest candidate cannot access employer approval
    # ------------------------------------------------------------------
    def test_hirenest_candidate_cannot_access_employer_approval(self):
        self.client.force_login(self.candidate_user)
        self.assertEqual(self.client.get(APPROVALS_PAGE_URL).status_code, 403)
        self.assertEqual(self.client.get(API_LIST_URL).status_code, 403)

        # Anonymous visitors are also denied.
        self.client.logout()
        self.assertEqual(self.client.get(API_LIST_URL).status_code, 403)

    # ------------------------------------------------------------------
    # Admin page access control
    # ------------------------------------------------------------------
    def test_super_admin_can_access_employer_approvals_page(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(APPROVALS_PAGE_URL + '?status=PENDING')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HireNest Australia Approvals')
        self.assertContains(response, 'pending@company.com')

    # ------------------------------------------------------------------
    # Employer login status messages
    # ------------------------------------------------------------------
    def test_pending_and_rejected_login_show_status_messages(self):
        pending_login = self.client.post('/employers/login/', data={
            'email': 'pending@company.com',
            'password': 'EmployerPassword123!',
        })
        self.assertEqual(pending_login.status_code, 200)
        self.assertContains(pending_login, 'awaiting approval')

        rejected_login = self.client.post('/employers/login/', data={
            'email': 'rejected@company.com',
            'password': 'EmployerPassword123!',
        })
        self.assertEqual(rejected_login.status_code, 200)
        self.assertContains(rejected_login, 'was not approved')

    def test_approved_login_enters_hirenest_workspace(self):
        response = self.client.post('/employers/login/', data={
            'email': 'approved@company.com',
            'password': 'EmployerPassword123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/employers/dashboard/')
        self.assertNotIn('talent-vault.in', response.url)

    # ------------------------------------------------------------------
    # 11. HireNest jobs remain isolated from TalentVault
    # ------------------------------------------------------------------
    def test_hirenest_jobs_remain_isolated_from_talentvault(self):
        # A TalentVault-style (non-Australian) job must never surface in HireNest.
        intl_company = Company.objects.create(
            name='Bangalore Tech Ltd',
            slug='bangalore-tech-ltd',
            industry='IT',
            location='Bangalore, India',
            description='Indian development center.',
        )
        intl_job = Job.objects.create(
            company=intl_company,
            title='Java Engineer (India)',
            location='Bangalore, India',
            job_type='FULL_TIME',
            currency='INR',
            min_salary=Decimal('1200000.00'),
            max_salary=Decimal('2000000.00'),
            status='ACTIVE',
            description='India role.',
            created_by=self.approved_user,
        )

        au_jobs = get_australian_jobs_queryset()
        self.assertIn(self.job, au_jobs)
        self.assertNotIn(intl_job, au_jobs)

        search = self.client.get('/jobs/')
        self.assertNotContains(search, 'Java Engineer (India)')

    # ------------------------------------------------------------------
    # 12. TalentVault/other-company jobs remain isolated from HireNest
    # ------------------------------------------------------------------
    def test_talentvault_jobs_remain_isolated_from_hirenest(self):
        other_company = Company.objects.create(
            name='Other Employer Ltd',
            slug='other-employer-ltd',
            industry='IT',
            location='Melbourne VIC',
            description='Another company.',
        )
        other_job = Job.objects.create(
            company=other_company,
            title='Secret Other Company Role',
            location='Melbourne VIC',
            job_type='FULL_TIME',
            currency='AUD',
            status='ACTIVE',
            description='Belongs to a different company.',
            created_by=self.approved_user,
        )

        self.client.force_login(self.approved_user)
        jobs_page = self.client.get('/employers/jobs/')
        self.assertEqual(jobs_page.status_code, 200)
        self.assertContains(jobs_page, 'Senior Python Engineer')
        # The employer workspace only exposes its own company's jobs.
        self.assertNotContains(jobs_page, 'Secret Other Company Role')


class HireNestEmailNotificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        mail.outbox.clear()

    @override_settings(HIRENEST_ADMIN_NOTIFICATION_EMAIL='admin@hirenest.com.au')
    def test_employer_registration_sends_admin_notification_email(self):
        payload = {
            'org_name': 'Atlassian Sydney',
            'email': 'newrecruiter@atlassian.com.au',
            'phone_number': '+61 2 9123 4567',
            'hiring_type': 'organization',
            'industry': 'Software & Tech',
            'website': 'https://www.atlassian.com',
            'location': 'Sydney NSW',
            'password': 'VerySecurePassword123!',
            'confirm_password': 'VerySecurePassword123!',
            'terms': 'on',
        }
        response = self.client.post('/employers/register/', data=payload, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/employers/registration-pending/')

        # Verify admin notification email was sent exactly once (no duplicates)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn('admin@hirenest.com.au', email.to)
        self.assertEqual(email.subject, 'New HireNest Australia Employer Registration')
        body = email.body
        self.assertIn('Atlassian Sydney', body)
        self.assertIn('newrecruiter@atlassian.com.au', body)
        self.assertIn('+61 2 9123 4567', body)
        self.assertIn('Software & Tech', body)
        self.assertIn('Sydney NSW', body)
        self.assertIn('https://www.atlassian.com', body)
        self.assertIn('PENDING', body)
        self.assertIn('/employers/approvals/', body)
        # Verify password is NEVER in the email
        self.assertNotIn('VerySecurePassword123!', body)

    @override_settings(HIRENEST_ADMIN_NOTIFICATION_EMAIL='admin@hirenest.com.au')
    def test_employer_registration_succeeds_when_email_fails(self):
        with patch('portal.email_service.send_mail', side_effect=Exception("SMTP Connection Error")):
            payload = {
                'org_name': 'Resilient Corp',
                'email': 'resilient@corp.com.au',
                'phone_number': '+61 2 9876 5432',
                'hiring_type': 'organization',
                'industry': 'Mining',
                'location': 'Perth WA',
                'password': 'SecurePassword123!',
                'confirm_password': 'SecurePassword123!',
                'terms': 'on',
            }
            response = self.client.post('/employers/register/', data=payload, follow=False)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, '/employers/registration-pending/')

            user = User.objects.filter(email='resilient@corp.com.au').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.recruiter_status, User.RecruiterStatus.PENDING)

    def test_employer_approval_sends_approval_email(self):
        company, user = make_employer('pending2@company.com', 'Pending Company 2', User.RecruiterStatus.PENDING)
        mail.outbox.clear()

        ok, message = apply_employer_action(user, 'approve')
        self.assertTrue(ok)
        self.assertEqual(user.recruiter_status, User.RecruiterStatus.ACTIVE)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(user.email, email.to)
        self.assertEqual(email.subject, 'Your HireNest Australia Employer Account Has Been Approved')
        body = email.body
        self.assertIn('Pending Company 2', body)
        self.assertIn('ACTIVE', body)
        self.assertIn('/employers/login/', body)
        self.assertNotIn('EmployerPassword123!', body)

    def test_employer_rejection_suspension_reactivation_emails(self):
        company, user = make_employer('action@company.com', 'Action Company', User.RecruiterStatus.PENDING)
        mail.outbox.clear()

        # Reject
        ok, _ = apply_employer_action(user, 'reject', reason='Incomplete business details')
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('HireNest Australia Employer Registration Update', mail.outbox[0].subject)
        self.assertIn('Rejected', mail.outbox[0].body)
        self.assertIn('Incomplete business details', mail.outbox[0].body)

        mail.outbox.clear()
        # Reactivate
        ok, _ = apply_employer_action(user, 'reactivate')
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Your HireNest Australia Employer Account Has Been Approved', mail.outbox[0].subject)

        mail.outbox.clear()
        # Suspend
        ok, _ = apply_employer_action(user, 'suspend')
        self.assertTrue(ok)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Your HireNest Australia Employer Account Has Been Suspended', mail.outbox[0].subject)
        self.assertIn('SUSPENDED', mail.outbox[0].body)

    def test_failed_approval_action_does_not_send_email(self):
        company, user = make_employer('invalid@company.com', 'Invalid Company', User.RecruiterStatus.PENDING)
        mail.outbox.clear()

        ok, message = apply_employer_action(user, 'invalid_action')
        self.assertFalse(ok)
        self.assertEqual(len(mail.outbox), 0)
