"""
HireNest Australia role-aware navigation.

A single source of truth for the public navbar, mobile menu and footer. It only
reads the existing authenticated user/session (``request.user``); it does not
introduce a second authentication system.

Resolved navigation roles:
    ANONYMOUS            - not signed in
    CANDIDATE            - signed-in candidate
    EMPLOYER_APPROVED    - approved HireNest employer (recruiter_status ACTIVE)
    EMPLOYER_PENDING     - employer awaiting approval
    EMPLOYER_REJECTED    - rejected or suspended employer
    ADMIN                - authorized HireNest/TalentVault admin
"""
from apps.accounts.models import User


LOGOUT_URL = '/logout/'

PUBLIC_NAV_LINKS = [
    {'label': 'Find Jobs', 'url': '/jobs/'},
    {'label': 'Companies', 'url': '/companies/'},
    {'label': 'Career Advice', 'url': '/career-advice/'},
    {'label': 'Salary Guide', 'url': '/salary-guide/'},
    {'label': 'Resources', 'url': '/resources/'},
]


def _display_name(user):
    full_name = ''
    try:
        full_name = (user.get_full_name() or '').strip()
    except Exception:
        full_name = ''
    return full_name or getattr(user, 'email', '') or 'Account'


def _base_state(user):
    return {
        'nav_role': 'ANONYMOUS',
        'nav_user_display': '',
        'nav_user_initial': '',
        'nav_account_links': [],
        'nav_logout_link': None,
        'nav_status_message': '',
        'nav_status_tone': '',
    }


def get_navigation_state(user):
    """Return the role-aware navigation state for the given user."""
    state = _base_state(user)

    if not user or not getattr(user, 'is_authenticated', False):
        return state

    display = _display_name(user)
    state['nav_user_display'] = display
    state['nav_user_initial'] = (display[:1] or 'U').upper()

    role = getattr(user, 'role', None)
    is_admin = (
        role == User.Role.SUPER_ADMIN
        or getattr(user, 'is_superuser', False)
        or getattr(user, 'is_staff', False)
    )

    if is_admin:
        state['nav_role'] = 'ADMIN'
        state['nav_account_links'] = [
            {'label': 'Admin Approvals', 'url': '/employers/approvals/', 'icon': 'bi-shield-check'},
        ]
        return state

    if role == User.Role.CANDIDATE:
        state['nav_role'] = 'CANDIDATE'
        state['nav_account_links'] = [
            {'label': 'My Dashboard', 'url': '/dashboard/', 'icon': 'bi-grid-1x2'},
            {'label': 'My Profile', 'url': '/profile/', 'icon': 'bi-person'},
            {'label': 'Saved Jobs', 'url': '/saved-jobs/', 'icon': 'bi-bookmark'},
            {'label': 'Applications', 'url': '/applications/', 'icon': 'bi-file-earmark-text'},
        ]
        return state

    if role in (User.Role.RECRUITER, User.Role.COMPANY_ADMIN):
        status = getattr(user, 'recruiter_status', None)

        if status == User.RecruiterStatus.ACTIVE:
            state['nav_role'] = 'EMPLOYER_APPROVED'
            state['nav_account_links'] = [
                {'label': 'Recruiter Dashboard', 'url': '/employers/dashboard/', 'icon': 'bi-speedometer2'},
                {'label': 'Manage Jobs', 'url': '/employers/jobs/', 'icon': 'bi-briefcase'},
                {'label': 'Find Candidates', 'url': '/employers/candidates/', 'icon': 'bi-people'},
                {'label': 'Company Profile', 'url': '/employers/profile/', 'icon': 'bi-building'},
            ]
            return state

        if status == User.RecruiterStatus.PENDING:
            state['nav_role'] = 'EMPLOYER_PENDING'
            state['nav_status_message'] = 'Your employer account is awaiting approval.'
            state['nav_status_tone'] = 'warning'
            state['nav_account_links'] = [
                {'label': 'Check Approval Status', 'url': '/employers/registration-pending/', 'icon': 'bi-hourglass-split'},
            ]
            return state

        # Rejected / suspended (or any non-active, non-pending state).
        state['nav_role'] = 'EMPLOYER_REJECTED'
        if status == User.RecruiterStatus.SUSPENDED:
            state['nav_status_message'] = 'Your employer account has been suspended.'
        else:
            state['nav_status_message'] = 'Your employer registration was not approved.'
        state['nav_status_tone'] = 'danger'
        return state

    # Unknown/legacy role: treat as anonymous-style public navigation.
    return state


def add_logout_link(state):
    """Expose a Log Out action for any authenticated navigation state."""
    state['nav_logout_link'] = None
    if state.get('nav_role') and state['nav_role'] != 'ANONYMOUS':
        state['nav_logout_link'] = {
            'label': 'Log Out',
            'url': LOGOUT_URL,
            'icon': 'bi-box-arrow-right',
        }
    return state


def hirenest_navigation(request):
    """Django context processor exposing role-aware navigation to templates."""
    state = get_navigation_state(getattr(request, 'user', None))
    add_logout_link(state)
    state['public_nav_links'] = PUBLIC_NAV_LINKS
    return state
