from django.urls import path
from django.views.generic import RedirectView
from .views import (
    HirenestLandingView,
    HirenestJobSearchView,
    HirenestJobDetailView,
    HirenestJobApplyView,
    HirenestCandidateRegisterView,
    HirenestCandidateLoginView,
    HirenestCandidateLogoutView,
    HirenestCandidateProfileView,
    HirenestCandidateDeleteAccountView,
    HirenestCandidateApplicationsView,
    HirenestCandidateSavedJobsView,
    HirenestToggleSaveJobView,
    HirenestCandidateOnboardingView,
    AustralianLocationsLookupView,
    HirenestCandidateDashboardView,
    HirenestEmployerLandingView,
    HirenestEmployerRegisterView,
    HirenestEmployerLoginView,
    HirenestEmployerOTPVerificationView,
    HirenestEmployerOTPResendView,
    HirenestCompaniesView,
    HirenestCompanyDetailView,
    HirenestSalaryGuideView,
    HirenestCareerAdviceView,
    HirenestResourcesView,
)
from .employer_views import (
    HirenestEmployerRegistrationPendingView,
    HirenestEmployerDashboardView,
    HirenestEmployerJobsView,
    HirenestEmployerJobCreateView,
    HirenestEmployerProfileView,
    HirenestEmployerApprovalsView,
    HirenestEmployerApprovalsAPIView,
    HirenestAdminJobsAPIView,
)

app_name = 'portal'

urlpatterns = [
    # Homepage / Candidate Portal
    path('', HirenestLandingView.as_view(), name='landing'),
    path('jobs/', HirenestJobSearchView.as_view(), name='jobs_search'),
    path('jobs/<uuid:pk>/', HirenestJobDetailView.as_view(), name='job_detail'),
    path('jobs/<uuid:pk>/apply/', HirenestJobApplyView.as_view(), name='job_apply'),
    path('jobs/saved/toggle/', HirenestToggleSaveJobView.as_view(), name='toggle_saved_job'),

    # Candidate Onboarding & Location Lookup
    path('onboarding/', HirenestCandidateOnboardingView.as_view(), name='candidate_onboarding'),
    path('api/locations/', AustralianLocationsLookupView.as_view(), name='locations_lookup'),

    # Candidate Dashboard & Management
    path('dashboard/', HirenestCandidateDashboardView.as_view(), name='candidate_dashboard'),
    path('register/', HirenestCandidateRegisterView.as_view(), name='candidate_register'),
    path('login/', HirenestCandidateLoginView.as_view(), name='candidate_login'),
    path('logout/', HirenestCandidateLogoutView.as_view(), name='candidate_logout'),
    path('profile/', HirenestCandidateProfileView.as_view(), name='candidate_profile'),
    path('profile/delete/', HirenestCandidateDeleteAccountView.as_view(), name='candidate_delete_account'),
    path('applications/', HirenestCandidateApplicationsView.as_view(), name='candidate_applications'),
    path('saved-jobs/', HirenestCandidateSavedJobsView.as_view(), name='candidate_saved_jobs'),

    # Employer Suite (HireNest-only — never redirects to TalentVault)
    path('employers/', HirenestEmployerLandingView.as_view(), name='employer_landing'),
    path('employers/register/', HirenestEmployerRegisterView.as_view(), name='employer_register'),
    path('employers/verify-otp/', HirenestEmployerOTPVerificationView.as_view(), name='employer_verify_otp'),
    path('employers/verify-otp/resend/', HirenestEmployerOTPResendView.as_view(), name='employer_otp_resend'),
    path('employers/registration-pending/', HirenestEmployerRegistrationPendingView.as_view(), name='employer_registration_pending'),
    path('employers/login/', HirenestEmployerLoginView.as_view(), name='employer_login'),

    # HireNest Recruiter Workspace (approved employers only)
    path('employers/dashboard/', HirenestEmployerDashboardView.as_view(), name='employer_dashboard'),
    path('employers/jobs/', HirenestEmployerJobsView.as_view(), name='employer_jobs'),
    path('employers/jobs/new/', HirenestEmployerJobCreateView.as_view(), name='employer_job_create'),
    path('employers/candidates/', RedirectView.as_view(url='/employers/dashboard/'), name='employer_candidates'),
    path('employers/profile/', HirenestEmployerProfileView.as_view(), name='employer_profile'),

    # HireNest employer approvals (admin-only)
    path('employers/approvals/', HirenestEmployerApprovalsView.as_view(), name='employer_approvals'),

    # Secure server-to-server admin API (TalentVault Admin Portal integration)
    path('api/admin/employer-approvals/', HirenestEmployerApprovalsAPIView.as_view(), name='employer_approvals_api'),
    path('api/admin/employer-approvals/<uuid:user_id>/', HirenestEmployerApprovalsAPIView.as_view(), name='employer_approval_action_api'),

    # Secure server-to-server admin jobs API (TalentVault Admin Portal integration)
    path('api/admin/jobs/', HirenestAdminJobsAPIView.as_view(), name='admin_jobs_api'),
    path('api/admin/jobs/<uuid:job_id>/', HirenestAdminJobsAPIView.as_view(), name='admin_job_detail_api'),

    # Informational & Directories
    path('companies/', HirenestCompaniesView.as_view(), name='companies'),
    path('companies/<slug:slug>/', HirenestCompanyDetailView.as_view(), name='company_detail'),
    path('salary-guide/', HirenestSalaryGuideView.as_view(), name='salary_guide'),
    path('career-advice/', HirenestCareerAdviceView.as_view(), name='career_advice'),
    path('resources/', HirenestResourcesView.as_view(), name='resources'),
]
