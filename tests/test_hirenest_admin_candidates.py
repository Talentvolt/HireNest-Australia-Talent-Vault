"""
HireNest admin candidates create API tests.

Verifies the secure server-to-server candidates endpoint consumed by TalentVault's
HireNest Candidate Parser, ensuring candidates are created in the HireNest database
with duplicate detection and API key authorization.
"""
from decimal import Decimal
from django.test import Client, TestCase, override_settings
from apps.accounts.models import User
from apps.candidates.models import CandidateProfile, CandidateSkill


ADMIN_API_KEY = 'test-hirenest-admin-key-candidates-123'
CANDIDATES_CREATE_URL = '/api/admin/candidates/'


@override_settings(HIRENEST_ADMIN_API_KEY=ADMIN_API_KEY, USE_LOCAL_STORAGE='1')
class HireNestAdminCandidatesCreateAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_candidates_create_api_requires_admin_key(self):
        response = self.client.post(CANDIDATES_CREATE_URL, {
            'full_name': 'Test Candidate',
            'email': 'test@example.com'
        })
        self.assertEqual(response.status_code, 403)

    def test_candidates_create_api_success(self):
        response = self.client.post(
            CANDIDATES_CREATE_URL,
            data={
                'full_name': 'Steve Rogers',
                'email': 'steve.rogers@avengers.org',
                'phone_number': '+1 555 0199',
                'location': 'Sydney NSW',
                'current_company': 'Shield',
                'current_designation': 'Captain',
                'total_experience': 10.0,
                'summary': 'First Avenger',
                'skills': 'Leadership, Strategy, Combat',
                'linkedin_url': 'https://linkedin.com/in/steverogers'
            },
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('candidate_id', data)

        # Verify profile created in HireNest DB
        profile = CandidateProfile.objects.get(id=data['candidate_id'])
        self.assertEqual(profile.full_name, 'Steve Rogers')
        self.assertEqual(profile.user.email, 'steve.rogers@avengers.org')
        self.assertEqual(profile.location, 'Sydney NSW')
        self.assertEqual(profile.total_experience, Decimal('10.0'))
        self.assertEqual(profile.skills.count(), 3)

    def test_candidates_create_api_duplicate_detection(self):
        # Create initial candidate
        user = User.objects.create_user(
            email='thor.odinson@asgard.org',
            role=User.Role.CANDIDATE,
            phone_number='+61 411 222 333'
        )
        CandidateProfile.objects.create(
            user=user,
            full_name='Thor Odinson',
            location='Melbourne VIC',
            current_company='Asgard Defense'
        )

        # Attempt to create duplicate with same email
        response = self.client.post(
            CANDIDATES_CREATE_URL,
            data={
                'full_name': 'Thor Duplicate',
                'email': 'thor.odinson@asgard.org',
                'phone_number': '+61 411 222 333'
            },
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['stage'], 'duplicate')
        self.assertEqual(data['duplicate_candidate']['name'], 'Thor Odinson')

        # Attempt with ignore_duplicate=true
        response_ignore = self.client.post(
            CANDIDATES_CREATE_URL,
            data={
                'full_name': 'Thor Duplicate',
                'email': 'thor.odinson@asgard.org',
                'phone_number': '+61 411 222 333',
                'ignore_duplicate': True
            },
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY
        )
        self.assertEqual(response_ignore.status_code, 200)
        self.assertTrue(response_ignore.json()['success'])
