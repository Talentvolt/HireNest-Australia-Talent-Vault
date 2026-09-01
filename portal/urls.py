from django.urls import path
from .views import (
    HirenestLandingView,
    HirenestJobSearchView,
    HirenestJobDetailView,
    HirenestJobApplyView,
    HirenestCandidateRegisterView,
    HirenestCandidateLoginView,
    HirenestCandidateLogoutView,
    HirenestCandidateProfileView,
    HirenestCandidateApplicationsView,
    HirenestCandidateSavedJobsView,
    HirenestToggleSaveJobView,
    HirenestEmployerLandingView,
    HirenestEmployerRegisterView,
    HirenestEmployerLoginView,
    HirenestCompaniesView,
    HirenestCompanyDetailView,
    HirenestSalaryGuideView,
    HirenestCareerAdviceView,
    HirenestResourcesView,
)

app_name = 'portal'

urlpatterns = [
    # Homepage / Candidate Portal
    path('', HirenestLandingView.as_view(), name='landing'),
    path('jobs/', HirenestJobSearchView.as_view(), name='jobs_search'),
    path('jobs/<uuid:pk>/', HirenestJobDetailView.as_view(), name='job_detail'),
    path('jobs/<uuid:pk>/apply/', HirenestJobApplyView.as_view(), name='job_apply'),
    path('jobs/saved/toggle/', HirenestToggleSaveJobView.as_view(), name='toggle_saved_job'),

    # Candidate Authentication & Management
    path('register/', HirenestCandidateRegisterView.as_view(), name='candidate_register'),
    path('login/', HirenestCandidateLoginView.as_view(), name='candidate_login'),
    path('logout/', HirenestCandidateLogoutView.as_view(), name='candidate_logout'),
    path('profile/', HirenestCandidateProfileView.as_view(), name='candidate_profile'),
    path('applications/', HirenestCandidateApplicationsView.as_view(), name='candidate_applications'),
    path('saved-jobs/', HirenestCandidateSavedJobsView.as_view(), name='candidate_saved_jobs'),

    # Employer Suite
    path('employers/', HirenestEmployerLandingView.as_view(), name='employer_landing'),
    path('employers/register/', HirenestEmployerRegisterView.as_view(), name='employer_register'),
    path('employers/login/', HirenestEmployerLoginView.as_view(), name='employer_login'),

    # Informational & Directories
    path('companies/', HirenestCompaniesView.as_view(), name='companies'),
    path('companies/<slug:slug>/', HirenestCompanyDetailView.as_view(), name='company_detail'),
    path('salary-guide/', HirenestSalaryGuideView.as_view(), name='salary_guide'),
    path('career-advice/', HirenestCareerAdviceView.as_view(), name='career_advice'),
    path('resources/', HirenestResourcesView.as_view(), name='resources'),
]
