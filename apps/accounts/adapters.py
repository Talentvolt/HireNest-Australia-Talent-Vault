import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.models import SocialAccount
from allauth.account.models import EmailAddress

from apps.accounts.models import User
from apps.companies.models import Company, CompanyMember

logger = logging.getLogger(__name__)


class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user_profile(self, user, sociallogin):
        try:
            extra_data = sociallogin.account.extra_data

            # Update first and last name from Google extra_data
            if 'name' in extra_data:
                user.first_name = extra_data.get('given_name', '')
                user.last_name = extra_data.get('family_name', '')
                if not user.first_name and not user.last_name:
                    user.first_name = extra_data.get('name', '')
            if 'picture' in extra_data:
                user.profile_picture = extra_data.get('picture', '')

            # Ensure user role is RECRUITER
            user.role = User.Role.RECRUITER
            user.save()

            # Ensure default company association exists for dashboard integrity
            try:
                company, _ = Company.objects.get_or_create(
                    name="TalentVault Technologies",
                    defaults={
                        'slug': 'talentvault-technologies',
                        'industry': 'Software Product',
                        'description': 'Default organization created during Google Sign-In.',
                        'location': 'Remote'
                    }
                )
                CompanyMember.objects.get_or_create(
                    company=company,
                    user=user,
                    defaults={
                        'designation': 'Recruiter',
                        'role': CompanyMember.MemberRole.ADMIN
                    }
                )
            except Exception as company_err:
                logger.error(f"Error associating default company: {company_err}")
        except Exception as profile_err:
            logger.error(f"Error in populate_user_profile: {profile_err}")
            raise profile_err

    def pre_social_login(self, request, sociallogin):
        try:
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                email = getattr(sociallogin.user, 'email', None) or sociallogin.account.extra_data.get('email')
                target_user = getattr(sociallogin, 'user', None)
                if (target_user and target_user.pk and request.user.pk != target_user.pk) or (email and request.user.email.lower() != email.lower()):
                    from django.contrib.auth import logout
                    logout(request)

            if sociallogin.is_existing:
                self.populate_user_profile(sociallogin.user, sociallogin)
                return

            email = sociallogin.user.email
            if not email:
                return

            try:
                user = User.objects.get(email__iexact=email)
                SocialAccount.objects.get_or_create(
                    user=user,
                    provider=sociallogin.account.provider,
                    uid=sociallogin.account.uid,
                    defaults={'extra_data': sociallogin.account.extra_data}
                )
                EmailAddress.objects.get_or_create(
                    user=user,
                    email=email,
                    defaults={'verified': True, 'primary': True}
                )
                sociallogin.user = user
                self.populate_user_profile(user, sociallogin)
            except User.DoesNotExist:
                pass
        except Exception as pre_login_err:
            logger.error(f"Error in pre_social_login: {pre_login_err}")
            raise pre_login_err

    def save_user(self, request, sociallogin, form=None):
        try:
            user = super().save_user(request, sociallogin, form)
            self.populate_user_profile(user, sociallogin)
            return user
        except Exception as save_user_err:
            logger.error(f"Error in save_user: {save_user_err}")
            raise save_user_err

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        logger.error(f"GOOGLE OAUTH AUTHENTICATION ERROR Provider: {provider}, Error: {error}, Exception: {exception}")
        super().on_authentication_error(request, provider, error, exception, extra_context)


class CandidateSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    allauth social adapter used exclusively for HireNest Australia candidate
    "Continue with Google" authentication.

    Reuses the existing User + CandidateProfile models and the Google SocialApp
    configured from environment variables (no hardcoded secrets). Employer
    authentication is untouched because employers sign in with email/password.
    """

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        # For new user signups, always provision a CANDIDATE identity.
        user.role = User.Role.CANDIDATE
        user.is_verified = True
        user.is_active = True
        return user

    def populate_user_profile(self, user, sociallogin):
        try:
            extra_data = sociallogin.account.extra_data or {}

            if 'name' in extra_data:
                user.first_name = extra_data.get('given_name', '') or user.first_name
                user.last_name = extra_data.get('family_name', '') or user.last_name
                if not user.first_name and not user.last_name:
                    user.first_name = extra_data.get('name', '')
            if 'picture' in extra_data and not user.profile_picture:
                user.profile_picture = extra_data.get('picture', '')
            user.save()

            if user.role == User.Role.CANDIDATE:
                from apps.accounts.services.candidate_social import (
                    get_or_create_candidate_from_social,
                )
                get_or_create_candidate_from_social(
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    full_name=extra_data.get('name', ''),
                    picture=user.profile_picture or extra_data.get('picture', ''),
                )
        except Exception as profile_err:
            logger.error(f"Error in populate_user_profile: {profile_err}")
            raise profile_err

    def pre_social_login(self, request, sociallogin):
        """
        Link an incoming Google identity to an existing account with the same
        email (case-insensitive) so a duplicate account is never created.
        """
        try:
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                email = getattr(sociallogin.user, 'email', None) or sociallogin.account.extra_data.get('email')
                target_user = getattr(sociallogin, 'user', None)
                if (target_user and target_user.pk and request.user.pk != target_user.pk) or (email and request.user.email.lower() != email.lower()):
                    from django.contrib.auth import logout
                    logout(request)

            if sociallogin.is_existing:
                self.populate_user_profile(sociallogin.user, sociallogin)
                return

            email = sociallogin.user.email
            if not email:
                return

            try:
                user = User.objects.get(email__iexact=email)
                SocialAccount.objects.get_or_create(
                    user=user,
                    provider=sociallogin.account.provider,
                    uid=sociallogin.account.uid,
                    defaults={'extra_data': sociallogin.account.extra_data}
                )
                EmailAddress.objects.get_or_create(
                    user=user,
                    email=email,
                    defaults={'verified': True, 'primary': True}
                )
                sociallogin.user = user
                self.populate_user_profile(user, sociallogin)
            except User.DoesNotExist:
                pass
        except Exception as pre_login_err:
            logger.error(f"Error in pre_social_login: {pre_login_err}")
            raise pre_login_err

    def save_user(self, request, sociallogin, form=None):
        try:
            user = super().save_user(request, sociallogin, form)
            self.populate_user_profile(user, sociallogin)
            return user
        except Exception as save_user_err:
            logger.error(f"Error in save_user: {save_user_err}")
            raise save_user_err

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        logger.error(f"GOOGLE OAUTH AUTHENTICATION ERROR Provider: {provider}, Error: {error}, Exception: {exception}")
        super().on_authentication_error(request, provider, error, exception, extra_context)


class CandidateAccountAdapter(DefaultAccountAdapter):
    """
    Account adapter that routes candidates after sign-in.

    New / incomplete candidates are sent to the branded onboarding flow while
    candidates with a completed profile go straight to the dashboard. Non
    candidate accounts fall back to the default redirect behaviour.
    """

    @staticmethod
    def _candidate_redirect(user):
        profile = getattr(user, 'candidate_profile', None)
        if profile is not None and profile.is_onboarding_complete:
            return '/dashboard/'
        return '/onboarding/'

    def get_login_redirect_url(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and getattr(user, 'role', None) == User.Role.CANDIDATE:
            return self._candidate_redirect(user)
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and getattr(user, 'role', None) == User.Role.CANDIDATE:
            return self._candidate_redirect(user)
        return super().get_signup_redirect_url(request)
