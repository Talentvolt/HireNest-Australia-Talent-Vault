"""
HireNest Australia candidate social (Google) provisioning service.

Centralises the "Continue with Google" account creation / linking logic so it can
be reused by the allauth social adapter and unit tested without performing a
real OAuth handshake.
"""
import logging
from typing import Optional, Tuple

from django.db import transaction

logger = logging.getLogger(__name__)

DEFAULT_AU_LOCATION = "Sydney NSW"


def _split_name(full_name: str) -> Tuple[str, str]:
    parts = (full_name or "").strip().split(" ", 1)
    first = parts[0] if parts else ""
    last = parts[1] if len(parts) > 1 else ""
    return first, last


def get_or_create_candidate_from_social(
    email: str,
    first_name: str = "",
    last_name: str = "",
    full_name: str = "",
    picture: str = "",
) -> Tuple[Optional[object], bool, bool]:
    """
    Find or create a CANDIDATE user + CandidateProfile for a verified social email.

    Guarantees a single account per email address (duplicate prevention) by
    matching case-insensitively on the existing User record.

    Returns a tuple of (user, user_created, profile_created).
    """
    from apps.accounts.models import User
    from apps.candidates.models import CandidateProfile

    email = (email or "").strip().lower()
    if not email:
        return None, False, False

    if not first_name and not last_name and full_name:
        first_name, last_name = _split_name(full_name)

    display_name = " ".join(p for p in [first_name, last_name] if p).strip()

    with transaction.atomic():
        user = User.objects.filter(email__iexact=email).first()
        user_created = False

        if user is None:
            user = User.objects.create_user(
                email=email,
                first_name=first_name or email.split("@")[0].title(),
                last_name=last_name,
                role=User.Role.CANDIDATE,
                is_active=True,
                is_verified=True,
                profile_picture=picture or None,
            )
            user_created = True
        else:
            updated_fields = []
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated_fields.append("first_name")
            if last_name and user.last_name != last_name:
                user.last_name = last_name
                updated_fields.append("last_name")
            if picture and not user.profile_picture:
                user.profile_picture = picture
                updated_fields.append("profile_picture")
            if not user.is_active:
                user.is_active = True
                updated_fields.append("is_active")
            if not user.is_verified:
                user.is_verified = True
                updated_fields.append("is_verified")
            # Only promote accounts that have no established non-candidate role.
            if user.role not in (User.Role.CANDIDATE, User.Role.SUPER_ADMIN):
                user.role = User.Role.CANDIDATE
                updated_fields.append("role")
            if updated_fields:
                user.save(update_fields=updated_fields)

        profile, profile_created = CandidateProfile.objects.get_or_create(
            user=user,
            defaults={
                "full_name": display_name or user.get_full_name() or email.split("@")[0].title(),
                "location": DEFAULT_AU_LOCATION,
                "candidate_status": "ACTIVE",
            },
        )
        if not profile_created and not profile.full_name and display_name:
            profile.full_name = display_name
            profile.save(update_fields=["full_name"])

    return user, user_created, profile_created
