"""
HireNest Australia role-aware navigation tests.

Covers the public navbar, the mobile menu and the footer for every role:
anonymous, candidate, approved employer, pending employer, rejected/suspended
employer and admin. Also verifies logout behaviour.
"""
from decimal import Decimal

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.candidates.models import CandidateProfile
from apps.companies.models import Company, CompanyMember

from portal.navigation import get_navigation_state, add_logout_link


def _mobile_menu_html(html):
    """Return just the mobile drawer markup so assertions are role-scoped."""
    marker = 'id="hnMobileMenu"'
    start = html.find(marker)
    if start == -1:
        return ''
    end = html.find('<!-- Django Messages Alert Bar -->', start)
    return html[start:end if end != -1 else len(html)]


def make_employer(email, company_name, status, is_active=True):
    company = Company.objects.create(
        name=company_name,
        slug=company_name.lower().replace(' ', '-'),
        industry='Information Technology',
        location='Sydney NSW',
        description=f"{company_name} is an Australian employer.",
    )
    user = User.objects.create_user(
        email=email,
        password='EmployerPassword123!',
        phone_number='+61 2 9000 0000',
        role=User.Role.RECRUITER,
        recruiter_status=status,
        is_active=is_active,
    )
    CompanyMember.objects.create(
        company=company, user=user,
        role=CompanyMember.MemberRole.ADMIN, designation='Hiring Lead',
    )
    return company, user


class HireNestNavigationTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.candidate_user = User.objects.create_user(
            email='nav.candidate@example.com',
            password='CandidatePassword123!',
            first_name='Nina',
            last_name='Candidate',
            role=User.Role.CANDIDATE,
            is_active=True,
            is_verified=True,
        )
        CandidateProfile.objects.create(
            user=self.candidate_user, full_name='Nina Candidate',
            location='Sydney NSW', candidate_status='ACTIVE',
        )

        self.approved_company, self.approved_user = make_employer(
            'nav.approved@company.com', 'Nav Approved Co', User.RecruiterStatus.ACTIVE
        )
        self.pending_company, self.pending_user = make_employer(
            'nav.pending@company.com', 'Nav Pending Co', User.RecruiterStatus.PENDING
        )
        # Rejected employers are inactive in production (cannot hold a session);
        # keep is_active=True here purely to exercise the navbar rendering.
        self.rejected_company, self.rejected_user = make_employer(
            'nav.rejected@company.com', 'Nav Rejected Co', User.RecruiterStatus.REJECTED
        )

        self.admin_user = User.objects.create_superuser(
            email='nav.admin@hirenest.com.au', password='AdminPassword123!'
        )

    # ------------------------------------------------------------------
    # 1. Anonymous
    # ------------------------------------------------------------------
    def test_anonymous_navbar(self):
        resp = self.client.get('/')
        self.assertContains(resp, 'For Employers')
        self.assertContains(resp, 'Log In')
        self.assertContains(resp, 'Sign In / Register')
        self.assertContains(resp, 'openCandidateAuthModal(')
        self.assertNotContains(resp, 'Log Out')
        self.assertNotContains(resp, 'My Dashboard')
        self.assertNotContains(resp, 'Recruiter Dashboard')
        self.assertNotContains(resp, 'Admin Approvals')

    # ------------------------------------------------------------------
    # 2. Candidate
    # ------------------------------------------------------------------
    def test_candidate_navbar(self):
        self.client.force_login(self.candidate_user)
        resp = self.client.get('/')
        self.assertContains(resp, 'My Dashboard')
        self.assertContains(resp, 'My Profile')
        self.assertContains(resp, 'Saved Jobs')
        self.assertContains(resp, 'Applications')
        self.assertContains(resp, 'Log Out')
        # No logged-out auth controls, no employer/admin workspace.
        self.assertNotContains(resp, 'openCandidateAuthModal(')
        self.assertNotContains(resp, 'data-auth-modal=')
        self.assertNotContains(resp, 'Sign In / Register')
        self.assertNotContains(resp, 'Recruiter Dashboard')
        self.assertNotContains(resp, 'Admin Approvals')

    # ------------------------------------------------------------------
    # 3. Approved employer
    # ------------------------------------------------------------------
    def test_approved_employer_navbar(self):
        self.client.force_login(self.approved_user)
        resp = self.client.get('/')
        self.assertContains(resp, 'Recruiter Dashboard')
        self.assertContains(resp, 'Manage Jobs')
        self.assertContains(resp, 'Find Candidates')
        self.assertContains(resp, 'Company Profile')
        self.assertContains(resp, 'Log Out')
        self.assertNotContains(resp, 'openCandidateAuthModal(')
        self.assertNotContains(resp, 'Sign In / Register')
        self.assertNotContains(resp, 'My Dashboard')
        self.assertNotContains(resp, 'Admin Approvals')

    # ------------------------------------------------------------------
    # 4. Pending employer
    # ------------------------------------------------------------------
    def test_pending_employer_navbar(self):
        self.client.force_login(self.pending_user)
        resp = self.client.get('/')
        self.assertContains(resp, 'Check Approval Status')
        self.assertContains(resp, 'Log Out')
        self.assertContains(resp, 'awaiting approval')
        self.assertNotContains(resp, 'Recruiter Dashboard')
        self.assertNotContains(resp, 'Manage Jobs')
        self.assertNotContains(resp, 'openCandidateAuthModal(')
        self.assertNotContains(resp, 'Sign In / Register')

    # ------------------------------------------------------------------
    # 5. Rejected / suspended employer
    # ------------------------------------------------------------------
    def test_rejected_employer_navbar(self):
        self.client.force_login(self.rejected_user)
        resp = self.client.get('/')
        self.assertContains(resp, 'Log Out')
        self.assertContains(resp, 'was not approved')
        self.assertNotContains(resp, 'Recruiter Dashboard')
        self.assertNotContains(resp, 'Manage Jobs')
        self.assertNotContains(resp, 'openCandidateAuthModal(')

    # ------------------------------------------------------------------
    # 6. Admin
    # ------------------------------------------------------------------
    def test_admin_navbar(self):
        self.client.force_login(self.admin_user)
        resp = self.client.get('/')
        self.assertContains(resp, 'Admin Approvals')
        self.assertContains(resp, 'Log Out')
        self.assertNotContains(resp, 'openCandidateAuthModal(')
        self.assertNotContains(resp, 'Sign In / Register')
        self.assertNotContains(resp, 'Recruiter Dashboard')
        self.assertNotContains(resp, 'My Dashboard')

    # ------------------------------------------------------------------
    # 7. Mobile menu follows the same role logic
    # ------------------------------------------------------------------
    def test_mobile_menu_anonymous(self):
        menu = _mobile_menu_html(self.client.get('/').content.decode('utf-8'))
        self.assertIn('For Employers', menu)
        self.assertIn('Sign In / Register', menu)
        self.assertIn('Log In', menu)
        self.assertIn('Employer Log In', menu)
        self.assertNotIn('Log Out', menu)

    def test_mobile_menu_candidate(self):
        self.client.force_login(self.candidate_user)
        menu = _mobile_menu_html(self.client.get('/').content.decode('utf-8'))
        for label in ['My Dashboard', 'My Profile', 'Saved Jobs', 'Applications', 'Log Out']:
            self.assertIn(label, menu)
        self.assertNotIn('Recruiter Dashboard', menu)
        self.assertNotIn('openCandidateAuthModal(', menu)

    def test_mobile_menu_employer(self):
        self.client.force_login(self.approved_user)
        menu = _mobile_menu_html(self.client.get('/').content.decode('utf-8'))
        for label in ['Recruiter Dashboard', 'Manage Jobs', 'Find Candidates', 'Company Profile', 'Log Out']:
            self.assertIn(label, menu)
        self.assertNotIn('My Dashboard', menu)
        self.assertNotIn('openCandidateAuthModal(', menu)

    def test_mobile_menu_pending_employer(self):
        self.client.force_login(self.pending_user)
        menu = _mobile_menu_html(self.client.get('/').content.decode('utf-8'))
        self.assertIn('Check Approval Status', menu)
        self.assertIn('Log Out', menu)
        self.assertIn('awaiting approval', menu)
        self.assertNotIn('Recruiter Dashboard', menu)
        self.assertNotIn('openCandidateAuthModal(', menu)

    # ------------------------------------------------------------------
    # 8. Logout behaviour
    # ------------------------------------------------------------------
    def test_candidate_logout_redirects_home_and_shows_anonymous_navbar(self):
        self.client.force_login(self.candidate_user)
        resp = self.client.get('/logout/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/')

        home = self.client.get('/')
        self.assertContains(home, 'openCandidateAuthModal(')
        self.assertNotContains(home, 'My Dashboard')

    def test_employer_logout_redirects_home_and_shows_anonymous_navbar(self):
        self.client.force_login(self.approved_user)
        resp = self.client.get('/logout/')
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/')

        home = self.client.get('/')
        self.assertContains(home, 'openCandidateAuthModal(')
        self.assertNotContains(home, 'Recruiter Dashboard')

    # ------------------------------------------------------------------
    # 9. Navigation state unit tests (pure function, all statuses)
    # ------------------------------------------------------------------
    def test_navigation_state_for_each_role(self):
        anonymous = get_navigation_state(None)
        self.assertEqual(anonymous['nav_role'], 'ANONYMOUS')

        candidate = get_navigation_state(self.candidate_user)
        self.assertEqual(candidate['nav_role'], 'CANDIDATE')
        self.assertIn('/dashboard/', [l['url'] for l in candidate['nav_account_links']])

        approved = get_navigation_state(self.approved_user)
        self.assertEqual(approved['nav_role'], 'EMPLOYER_APPROVED')
        self.assertIn('/employers/dashboard/', [l['url'] for l in approved['nav_account_links']])

        pending = get_navigation_state(self.pending_user)
        self.assertEqual(pending['nav_role'], 'EMPLOYER_PENDING')
        self.assertTrue(pending['nav_status_message'])

        rejected = get_navigation_state(self.rejected_user)
        self.assertEqual(rejected['nav_role'], 'EMPLOYER_REJECTED')

        admin = get_navigation_state(self.admin_user)
        self.assertEqual(admin['nav_role'], 'ADMIN')

    def test_logout_link_only_added_for_authenticated_users(self):
        self.assertIsNone(add_logout_link(get_navigation_state(None))['nav_logout_link'])
        state = add_logout_link(get_navigation_state(self.candidate_user))
        self.assertEqual(state['nav_logout_link']['url'], '/logout/')
