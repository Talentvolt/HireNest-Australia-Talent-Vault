from django import forms
from django.contrib.auth import authenticate
from django.core.validators import FileExtensionValidator
from apps.accounts.models import User
from apps.candidates.models import CandidateProfile
from apps.companies.models import Company
from apps.jobs.models import Job
from .services import AUSTRALIAN_CLASSIFICATIONS

CITIZENSHIP_CHOICES = [
    ('Australian Citizen', 'Australian Citizen'),
    ('Australian Permanent Resident', 'Australian Permanent Resident'),
    ('New Zealand Citizen', 'New Zealand Citizen'),
    ('Temporary Work Visa (Subclass 482)', 'Temporary Work Visa (Subclass 482)'),
    ('Student Visa (Subclass 500)', 'Student Visa (Subclass 500)'),
    ('Working Holiday Visa (Subclass 417/462)', 'Working Holiday Visa (Subclass 417/462)'),
    ('Other / Requires Sponsorship', 'Other / Requires Sponsorship'),
]

RESUME_EXTENSIONS = ['pdf', 'doc', 'docx']


class CandidateOnboardingForm(forms.Form):
    """
    HireNest Australia candidate onboarding form.

    Reuses the existing CandidateProfile fields (department, employment_type,
    work_permit_countries, resume) so no unnecessary schema changes are needed.
    """
    first_name = forms.CharField(max_length=50, required=True, label="First Name")
    last_name = forms.CharField(max_length=50, required=True, label="Last Name")
    phone_number = forms.CharField(max_length=30, required=True, label="Phone Number")
    location = forms.CharField(max_length=100, required=True, label="Australian Location")
    citizenship = forms.ChoiceField(choices=CITIZENSHIP_CHOICES, required=True, label="Citizenship / Work Rights")
    resume = forms.FileField(
        required=False,
        label="Resume",
        validators=[FileExtensionValidator(allowed_extensions=RESUME_EXTENSIONS)],
        help_text="Upload your resume (PDF, DOC or DOCX).",
    )
    preferred_job_category = forms.ChoiceField(required=True, label="Preferred Job Category")
    work_type = forms.ChoiceField(required=True, label="Work Type")
    preferred_job_role = forms.CharField(max_length=255, required=False, label="Preferred Job Title")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_job_category'].choices = [
            (cat['name'], cat['name']) for cat in AUSTRALIAN_CLASSIFICATIONS
        ]
        self.fields['work_type'].choices = list(
            CandidateProfile._meta.get_field('employment_type').choices
        )

    def clean_resume(self):
        resume = self.cleaned_data.get('resume')
        if resume and resume.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Resume file must be 10 MB or smaller.")
        return resume


class CandidateProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    phone_number = forms.CharField(max_length=30, required=False)
    skills = forms.CharField(required=False, widget=forms.TextInput(attrs={'placeholder': 'e.g. React, Python, AWS'}))

    class Meta:
        model = CandidateProfile
        fields = [
            'full_name', 'current_designation', 'current_company',
            'location', 'total_experience', 'expected_salary',
            'notice_period', 'summary', 'resume'
        ]


class EmployerRegistrationForm(forms.Form):
    org_name = forms.CharField(max_length=150, required=True, label="Organization Name")
    email = forms.EmailField(required=True, label="Work Email Address")
    phone_number = forms.CharField(max_length=30, required=True, label="Contact Phone Number")
    hiring_type = forms.ChoiceField(
        choices=[('organization', 'Direct Employer'), ('agency', 'Recruitment Agency')],
        required=False,
        initial='organization'
    )
    industry = forms.CharField(max_length=100, required=False)
    website = forms.URLField(required=False, max_length=500, assume_scheme='https')
    location = forms.CharField(max_length=100, required=False, initial='Sydney NSW')
    password = forms.CharField(widget=forms.PasswordInput, min_length=8, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, min_length=8, required=True)
    terms = forms.BooleanField(required=True)

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An employer account with this email address already exists. Please log in.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match. Please try again.")
        return cleaned_data


class EmployerLoginForm(forms.Form):
    email = forms.EmailField(required=True, label="Work Email Address")
    password = forms.CharField(widget=forms.PasswordInput, required=True, label="Password")
    remember_me = forms.BooleanField(required=False, initial=True)


class EmployerJobForm(forms.ModelForm):
    """
    HireNest-only job posting form for the employer recruiter workspace.

    Only Australian (AUD) fields are exposed. The company, currency and audit
    fields are set server-side by the view.
    """
    class Meta:
        model = Job
        fields = [
            'title', 'department', 'location', 'job_type', 'work_mode',
            'min_experience', 'max_experience', 'min_salary', 'max_salary',
            'required_skills_text', 'preferred_skills_text', 'description',
            'status',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 6}),
            'required_skills_text': forms.TextInput(attrs={'placeholder': 'e.g. Python, Django, AWS'}),
            'preferred_skills_text': forms.TextInput(attrs={'placeholder': 'e.g. Kubernetes, Terraform'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choice_fields = {'job_type', 'work_mode', 'status'}
        for name, field in self.fields.items():
            css = 'form-select hn-form-control' if name in choice_fields else 'form-control hn-form-control'
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} {css}".strip()


class JobApplicationForm(forms.Form):
    full_name = forms.CharField(max_length=100, required=True)
    phone_number = forms.CharField(max_length=30, required=True)
    location = forms.CharField(max_length=100, required=True)
    total_experience = forms.DecimalField(max_digits=4, decimal_places=1, required=False, initial=0.0)
    expected_salary = forms.DecimalField(max_digits=12, decimal_places=2, required=False)
    notice_period = forms.IntegerField(required=False, initial=30)
    resume_file = forms.FileField(required=False)
    cover_letter = forms.CharField(widget=forms.Textarea, required=False)
