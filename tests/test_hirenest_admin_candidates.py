"""
HireNest admin candidates create & list API tests.

Verifies the secure server-to-server candidates endpoint consumed by TalentVault's
HireNest Candidate Parser, ensuring candidates are created with structured experience
and education in the HireNest database, with duplicate detection and API key authorization.
"""
from decimal import Decimal
from django.test import Client, TestCase, override_settings
from apps.accounts.models import User
from apps.candidates.models import CandidateProfile, CandidateSkill, Experience, Education


ADMIN_API_KEY = 'test-hirenest-admin-key-candidates-123'
CANDIDATES_API_URL = '/api/admin/candidates/'


@override_settings(HIRENEST_ADMIN_API_KEY=ADMIN_API_KEY, USE_LOCAL_STORAGE='1')
class HireNestAdminCandidatesCreateAPITests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_candidates_api_requires_admin_key(self):
        response = self.client.post(CANDIDATES_API_URL, {
            'full_name': 'Test Candidate',
            'email': 'test@example.com'
        })
        self.assertEqual(response.status_code, 403)

        response_get = self.client.get(CANDIDATES_API_URL)
        self.assertEqual(response_get.status_code, 403)

    def test_candidates_create_api_success_with_experience_and_education(self):
        payload = {
            'full_name': 'Steve Rogers',
            'email': 'steve.rogers@avengers.org',
            'phone_number': '+1 555 0199',
            'location': 'Sydney NSW',
            'current_company': 'Shield',
            'current_designation': 'Captain',
            'total_experience': 10.0,
            'summary': 'First Avenger',
            'skills': 'Leadership, Strategy, Combat',
            'linkedin_url': 'https://linkedin.com/in/steverogers',
            'experiences': [
                {
                    'company_name': 'Stark Industries',
                    'designation': 'Security Consultant',
                    'is_current': False,
                    'description': 'Provided tactical security consulting.'
                }
            ],
            'educations': [
                {
                    'degree': 'B.Sc. Military Science',
                    'institution': 'United States Military Academy',
                    'field_of_study': 'Tactical Operations',
                    'passing_year': 1941,
                    'percentage_or_cgpa': '3.8 GPA'
                }
            ]
        }
        response = self.client.post(
            CANDIDATES_API_URL,
            data=payload,
            content_type='application/json',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('candidate_id', data)

        # Verify profile created in HireNest DB with source=RESUME_PARSER
        profile = CandidateProfile.objects.get(id=data['candidate_id'])
        self.assertEqual(profile.full_name, 'Steve Rogers')
        self.assertEqual(profile.source, 'RESUME_PARSER')
        self.assertEqual(profile.user.email, 'steve.rogers@avengers.org')
        self.assertEqual(profile.location, 'Sydney NSW')
        self.assertEqual(profile.total_experience, Decimal('10.0'))
        self.assertEqual(profile.skills.count(), 3)

        # Verify experiences and educations saved
        self.assertEqual(profile.experiences.count(), 1)
        exp = profile.experiences.first()
        self.assertEqual(exp.company_name, 'Stark Industries')
        self.assertEqual(exp.designation, 'Security Consultant')

        self.assertEqual(profile.educations.count(), 1)
        edu = profile.educations.first()
        self.assertEqual(edu.degree, 'B.Sc. Military Science')
        self.assertEqual(edu.institution, 'United States Military Academy')
        self.assertEqual(edu.passing_year, 1941)

        # Test GET candidate listing API
        response_get = self.client.get(
            CANDIDATES_API_URL + '?source=RESUME_PARSER',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY
        )
        self.assertEqual(response_get.status_code, 200)
        get_data = response_get.json()
        self.assertEqual(get_data['source'], 'hirenest')
        self.assertGreaterEqual(get_data['count'], 1)
        cand_found = next((c for c in get_data['candidates'] if c['id'] == str(profile.id)), None)
        self.assertIsNotNone(cand_found)
        self.assertEqual(cand_found['full_name'], 'Steve Rogers')
        self.assertEqual(len(cand_found['experiences']), 1)
        self.assertEqual(len(cand_found['educations']), 1)

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
            current_company='Asgard Defense',
            source='PORTAL_REGISTRATION'
        )

        # Attempt to create duplicate with same email
        response = self.client.post(
            CANDIDATES_API_URL,
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
            CANDIDATES_API_URL,
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
