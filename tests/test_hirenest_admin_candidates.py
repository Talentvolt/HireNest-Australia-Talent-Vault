"""
HireNest admin candidates create & list API tests.

Verifies the secure server-to-server candidates endpoint consumed by TalentVault's
HireNest Candidate Parser, ensuring international candidates are created with
country of residence, work rights/visa status, relocation availability, structured
experience (with employer country) and education (with institution country) in the
HireNest database.
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

    def test_international_candidate_create_api_success(self):
        payload = {
            'full_name': 'Alistair Vance',
            'email': 'alistair.vance@uk-tech.co.uk',
            'phone_number': '+44 20 7946 0915',
            'location': 'London',
            'country_of_residence': 'United Kingdom',
            'work_rights_visa_status': 'Temporary Working Visa (e.g. 482, 457)',
            'relocation_availability': True,
            'current_company': 'London Fintech Ltd',
            'current_designation': 'Senior Solutions Architect',
            'total_experience': 8.5,
            'summary': 'International tech leader relocating to Australia.',
            'skills': 'Cloud Architecture, Python, AWS, Kubernetes',
            'linkedin_url': 'https://linkedin.com/in/alistairvance',
            'experiences': [
                {
                    'company_name': 'London Fintech Ltd',
                    'employer_country': 'United Kingdom',
                    'designation': 'Senior Solutions Architect',
                    'is_current': True,
                    'description': 'Designed multi-cloud architectures across Europe.'
                }
            ],
            'educations': [
                {
                    'degree': 'M.Sc. Computer Science',
                    'institution': 'University of Oxford',
                    'institution_country': 'United Kingdom',
                    'field_of_study': 'Distributed Systems',
                    'passing_year': 2016,
                    'percentage_or_cgpa': 'First Class Honours'
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

        # Verify profile created in HireNest DB with international fields
        profile = CandidateProfile.objects.get(id=data['candidate_id'])
        self.assertEqual(profile.full_name, 'Alistair Vance')
        self.assertEqual(profile.source, 'RESUME_PARSER')
        self.assertEqual(profile.country_of_residence, 'United Kingdom')
        self.assertEqual(profile.work_rights_visa_status, 'Temporary Working Visa (e.g. 482, 457)')
        self.assertTrue(profile.relocation_availability)

        # Verify structured experiences and educations with country metadata
        self.assertEqual(profile.experiences.count(), 1)
        exp = profile.experiences.first()
        self.assertEqual(exp.company_name, 'London Fintech Ltd')
        self.assertEqual(exp.employer_country, 'United Kingdom')

        self.assertEqual(profile.educations.count(), 1)
        edu = profile.educations.first()
        self.assertEqual(edu.degree, 'M.Sc. Computer Science')
        self.assertEqual(edu.institution, 'University of Oxford')
        self.assertEqual(edu.institution_country, 'United Kingdom')
        self.assertEqual(edu.passing_year, 2016)

        # Test GET candidate listing API with international details
        response_get = self.client.get(
            CANDIDATES_API_URL + '?source=RESUME_PARSER',
            HTTP_X_HIRENEST_ADMIN_KEY=ADMIN_API_KEY
        )
        self.assertEqual(response_get.status_code, 200)
        get_data = response_get.json()
        self.assertEqual(get_data['source'], 'hirenest')
        cand_found = next((c for c in get_data['candidates'] if c['id'] == str(profile.id)), None)
        self.assertIsNotNone(cand_found)
        self.assertEqual(cand_found['country_of_residence'], 'United Kingdom')
        self.assertEqual(cand_found['work_rights_visa_status'], 'Temporary Working Visa (e.g. 482, 457)')
        self.assertTrue(cand_found['relocation_availability'])
        self.assertEqual(cand_found['experiences'][0]['employer_country'], 'United Kingdom')
        self.assertEqual(cand_found['educations'][0]['institution_country'], 'United Kingdom')
