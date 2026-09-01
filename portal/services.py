"""
HireNest Australia Localization, Marketplace Filtering & Candidate Services.
Provides:
- Australia-only marketplace QuerySet filtering
- Australian employment classifications, states, cities, and locations
- Australian salary benchmarks in AUD, career guides, and candidate resources
- Candidate recommendation and preference matching engine
"""
import re
from decimal import Decimal
from typing import List, Dict, Any, Optional
from django.db.models import Q, QuerySet, Case, When, Value, IntegerField
from apps.jobs.models import Job

AUSTRALIAN_STATES = [
    {"code": "NSW", "name": "New South Wales"},
    {"code": "VIC", "name": "Victoria"},
    {"code": "QLD", "name": "Queensland"},
    {"code": "WA", "name": "Western Australia"},
    {"code": "SA", "name": "South Australia"},
    {"code": "TAS", "name": "Tasmania"},
    {"code": "ACT", "name": "Australian Capital Territory"},
    {"code": "NT", "name": "Northern Territory"},
]

AU_STATE_CODES = [s["code"] for s in AUSTRALIAN_STATES]

POPULAR_CITIES = [
    {
        "name": "Sydney",
        "state": "NSW",
        "image_url": "https://images.unsplash.com/photo-1506973035872-a4ec16b8e8d9?w=600&auto=format&fit=crop&q=80",
        "description": "Australia's financial & technology capital",
        "query": "Sydney NSW",
    },
    {
        "name": "Melbourne",
        "state": "VIC",
        "image_url": "https://images.unsplash.com/photo-1514395462725-fb4566210144?w=600&auto=format&fit=crop&q=80",
        "description": "Cultural, healthcare & innovation hub",
        "query": "Melbourne VIC",
    },
    {
        "name": "Brisbane",
        "state": "QLD",
        "image_url": "https://images.unsplash.com/photo-1577717903315-1691ae25ab3f?w=600&auto=format&fit=crop&q=80",
        "description": "Fastest growing economy & lifestyle market",
        "query": "Brisbane QLD",
    },
    {
        "name": "Perth",
        "state": "WA",
        "image_url": "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=600&auto=format&fit=crop&q=80",
        "description": "Mining, energy & resources headquarters",
        "query": "Perth WA",
    },
    {
        "name": "Adelaide",
        "state": "SA",
        "image_url": "https://images.unsplash.com/photo-1548567117-02324f0c7fc5?w=600&auto=format&fit=crop&q=80",
        "description": "Defense, aerospace & wine tech centre",
        "query": "Adelaide SA",
    },
    {
        "name": "Gold Coast",
        "state": "QLD",
        "image_url": "https://images.unsplash.com/photo-1563805042-7684c019e1cb?w=600&auto=format&fit=crop&q=80",
        "description": "Tourism, health & coastal enterprise",
        "query": "Gold Coast QLD",
    },
]

POPULAR_SEARCH_CHIPS = [
    {"label": "Software Engineer", "query": "Software Engineer"},
    {"label": "Nursing & Healthcare", "query": "Nursing"},
    {"label": "Accounting & Finance", "query": "Accounting"},
    {"label": "Civil Engineering", "query": "Engineer"},
    {"label": "Project Manager", "query": "Project Manager"},
    {"label": "Customer Service", "query": "Customer Service"},
    {"label": "Electrician & Trades", "query": "Electrician"},
    {"label": "Marketing Specialist", "query": "Marketing"},
]

POPULAR_AU_LOCATIONS = [
    "Sydney NSW", "Melbourne VIC", "Brisbane QLD", "Perth WA",
    "Adelaide SA", "Gold Coast QLD", "Canberra ACT", "Newcastle NSW",
    "Wollongong NSW", "Hobart TAS", "Darwin NT", "Geelong VIC",
    "Sunshine Coast QLD", "Townsville QLD", "Cairns QLD", "Remote • Australia"
]

ALL_AUSTRALIAN_LOCATIONS = [
    {"name": "Sydney", "state": "NSW", "label": "Sydney NSW", "category": "Major City"},
    {"name": "Melbourne", "state": "VIC", "label": "Melbourne VIC", "category": "Major City"},
    {"name": "Brisbane", "state": "QLD", "label": "Brisbane QLD", "category": "Major City"},
    {"name": "Perth", "state": "WA", "label": "Perth WA", "category": "Major City"},
    {"name": "Adelaide", "state": "SA", "label": "Adelaide SA", "category": "Major City"},
    {"name": "Canberra", "state": "ACT", "label": "Canberra ACT", "category": "Capital City"},
    {"name": "Hobart", "state": "TAS", "label": "Hobart TAS", "category": "Capital City"},
    {"name": "Darwin", "state": "NT", "label": "Darwin NT", "category": "Capital City"},
    {"name": "Gold Coast", "state": "QLD", "label": "Gold Coast QLD", "category": "Regional Hub"},
    {"name": "Newcastle", "state": "NSW", "label": "Newcastle NSW", "category": "Regional Hub"},
    {"name": "Wollongong", "state": "NSW", "label": "Wollongong NSW", "category": "Regional Hub"},
    {"name": "Sunshine Coast", "state": "QLD", "label": "Sunshine Coast QLD", "category": "Regional Hub"},
    {"name": "Geelong", "state": "VIC", "label": "Geelong VIC", "category": "Regional Hub"},
    {"name": "Townsville", "state": "QLD", "label": "Townsville QLD", "category": "Regional Hub"},
    {"name": "Cairns", "state": "QLD", "label": "Cairns QLD", "category": "Regional Hub"},
    {"name": "Toowoomba", "state": "QLD", "label": "Toowoomba QLD", "category": "Regional Hub"},
    {"name": "Ballarat", "state": "VIC", "label": "Ballarat VIC", "category": "Regional Hub"},
    {"name": "Bendigo", "state": "VIC", "label": "Bendigo VIC", "category": "Regional Hub"},
    {"name": "Albury-Wodonga", "state": "NSW", "label": "Albury-Wodonga NSW/VIC", "category": "Regional Hub"},
    {"name": "Launceston", "state": "TAS", "label": "Launceston TAS", "category": "Regional Hub"},
    {"name": "Central Coast", "state": "NSW", "label": "Central Coast NSW", "category": "Regional Hub"},
    {"name": "Mackay", "state": "QLD", "label": "Mackay QLD", "category": "Regional Hub"},
    {"name": "Rockhampton", "state": "QLD", "label": "Rockhampton QLD", "category": "Regional Hub"},
    {"name": "Bunbury", "state": "WA", "label": "Bunbury WA", "category": "Regional Hub"},
    {"name": "Remote", "state": "Australia", "label": "Remote • Australia", "category": "Remote"},
]

AUSTRALIAN_CLASSIFICATIONS = [
    {
        "id": "ict",
        "name": "IT & Software Development",
        "icon": "bi-code-slash",
        "badge": "Top Remuneration",
        "roles_count": "3,150+",
        "popular_roles": ["Software Engineer", "Frontend Developer", "DevOps Engineer", "Cloud Architect", "Data Engineer", "Python Developer"]
    },
    {
        "id": "healthcare",
        "name": "Healthcare & Medical",
        "icon": "bi-heart-pulse-fill",
        "badge": "High Demand",
        "roles_count": "2,400+",
        "popular_roles": ["Registered Nurse", "Clinical Specialist", "Physiotherapist", "General Practitioner", "Occupational Therapist", "Aged Care"]
    },
    {
        "id": "finance",
        "name": "Accounting & Finance",
        "icon": "bi-cash-coin",
        "badge": "Essential",
        "roles_count": "1,650+",
        "popular_roles": ["Financial Accountant (CPA)", "Management Accountant", "Financial Analyst", "Payroll Officer", "Audit Senior"]
    },
    {
        "id": "engineering",
        "name": "Engineering",
        "icon": "bi-gear-wide-connected",
        "badge": "Critical Skill",
        "roles_count": "1,310+",
        "popular_roles": ["Civil Engineer", "Project Engineer", "Mechanical Engineer", "Electrical Engineer", "Structural Engineer"]
    },
    {
        "id": "construction",
        "name": "Construction & Trades",
        "icon": "bi-tools",
        "badge": "Booming Sector",
        "roles_count": "1,890+",
        "popular_roles": ["Site Supervisor", "Licensed Electrician", "Carpenter", "Plumber", "HVAC Technician", "Construction Manager"]
    },
    {
        "id": "sales",
        "name": "Sales & Customer Service",
        "icon": "bi-graph-up-arrow",
        "badge": "Competitive",
        "roles_count": "1,420+",
        "popular_roles": ["Account Executive", "Business Development Manager", "Customer Success Specialist", "Sales Representative"]
    },
    {
        "id": "education",
        "name": "Education & Training",
        "icon": "bi-mortarboard-fill",
        "badge": "Growing Demand",
        "roles_count": "1,240+",
        "popular_roles": ["Secondary Teacher", "Primary Teacher", "Early Childhood Educator", "Vocational Trainer", "Lecturer"]
    },
    {
        "id": "mining",
        "name": "Mining, Energy & Resources",
        "icon": "bi-gem",
        "badge": "Top Earning",
        "roles_count": "870+",
        "popular_roles": ["Mining Engineer", "Geologist", "Plant Operator", "Health & Safety (WHS)", "Operations Supervisor"]
    },
    {
        "id": "admin",
        "name": "Administration & Office Support",
        "icon": "bi-folder2-open",
        "badge": "Immediate Start",
        "roles_count": "1,120+",
        "popular_roles": ["Executive Assistant", "Office Manager", "Receptionist", "Operations Coordinator", "Data Entry"]
    },
    {
        "id": "marketing",
        "name": "Marketing & Communications",
        "icon": "bi-megaphone-fill",
        "badge": "Creative",
        "roles_count": "790+",
        "popular_roles": ["Digital Marketing Specialist", "Content Strategist", "SEO/SEM Manager", "Brand Manager", "Social Media Manager"]
    },
    {
        "id": "hospitality",
        "name": "Hospitality & Tourism",
        "icon": "bi-cup-hot-fill",
        "badge": "Expanding",
        "roles_count": "980+",
        "popular_roles": ["Head Chef", "Restaurant Manager", "Duty Manager", "Barista", "Event Coordinator"]
    },
    {
        "id": "hr",
        "name": "Human Resources & Recruitment",
        "icon": "bi-people-fill",
        "badge": "Steady Growth",
        "roles_count": "640+",
        "popular_roles": ["HR Business Partner", "Talent Acquisition Specialist", "People & Culture Lead", "Recruitment Consultant"]
    },
]

AU_EMPLOYMENT_TYPES = [
    {"code": "FULL_TIME", "label": "Full-time", "badge": "Permanent"},
    {"code": "PART_TIME", "label": "Part-time", "badge": "Flexible"},
    {"code": "CONTRACT", "label": "Contract", "badge": "Fixed Term"},
    {"code": "CASUAL", "label": "Casual", "badge": "+25% Loading"},
    {"code": "TEMPORARY", "label": "Temporary", "badge": "Short Term"},
    {"code": "INTERNSHIP", "label": "Internship", "badge": "Entry"},
    {"code": "GRADUATE", "label": "Graduate", "badge": "Program"},
    {"code": "REMOTE", "label": "Remote", "badge": "Anywhere in AU"},
]

# ==============================================================================
# 1. AUSTRALIA MARKETPLACE BACKEND FILTERING (SERVER-SIDE ENFORCEMENT)
# ==============================================================================
def get_australian_jobs_queryset() -> QuerySet:
    """
    CRITICAL: Returns an active Job QuerySet strictly restricted to the Australia marketplace.
    Enforces server-side filtering:
    1. Includes jobs with currency='AUD'
    2. Includes jobs with Australian location tags (States, Cities, 'Australia')
    3. Excludes jobs with INR currency or explicit Indian/International cities.
    """
    au_cities = [
        'Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide', 'Gold Coast',
        'Canberra', 'Newcastle', 'Wollongong', 'Geelong', 'Hobart', 'Darwin',
        'Townsville', 'Cairns', 'Toowoomba', 'Ballarat', 'Bendigo', 'Launceston',
        'Sunshine Coast', 'Central Coast', 'Albury', 'Wodonga', 'Mackay', 'Rockhampton'
    ]

    au_location_q = (
        Q(location__icontains='Australia') |
        Q(location__icontains='Remote Australia') |
        Q(location__icontains='Remote • Australia') |
        Q(location__icontains='Remote - Australia')
    )

    for state in AU_STATE_CODES:
        au_location_q |= (
            Q(location__icontains=f" {state}") |
            Q(location__icontains=f",{state}") |
            Q(location__icontains=f", {state}") |
            Q(location__endswith=state)
        )

    for city in au_cities:
        au_location_q |= Q(location__icontains=city)

    # General inclusion: Currency AUD or recognized Australian location
    base_au_q = Q(currency='AUD') | au_location_q

    qs = Job.objects.filter(status='ACTIVE').filter(base_au_q).select_related('company')

    # Strict exclusion of international hubs unless clearly flagged Australia
    non_au_terms = [
        'India', 'Bangalore', 'Bengaluru', 'Mumbai', 'Delhi', 'Hyderabad',
        'Pune', 'Chennai', 'Noida', 'Gurgaon', 'Kolkata', 'United States',
        'USA', 'United Kingdom', 'London', 'New York'
    ]
    for term in non_au_terms:
        qs = qs.exclude(Q(location__icontains=term) & ~Q(location__icontains='Australia'))

    # Exclude INR jobs unless location is explicitly Australia
    qs = qs.exclude(Q(currency='INR') & ~Q(location__icontains='Australia'))

    return qs


def normalize_australian_location(raw_loc: str) -> str:
    """
    Normalizes a location string to clean Australian standard format.
    Example: 'sydney' -> 'Sydney NSW', 'remote' -> 'Remote • Australia'
    """
    if not raw_loc:
        return "Australia"

    val = raw_loc.strip()
    val_upper = val.upper()

    if 'REMOTE' in val_upper:
        return "Remote • Australia"

    for city in POPULAR_CITIES:
        if city['name'].upper() in val_upper:
            return f"{city['name']}, {city['state']}"

    for state in AUSTRALIAN_STATES:
        if state['code'] in val_upper or state['name'].upper() in val_upper:
            return f"{val} {state['code']}" if state['code'] not in val else val

    return val


# ==============================================================================
# 2. CANDIDATE JOB MATCHING & RECOMMENDATION ENGINE
# ==============================================================================
def get_candidate_recommended_jobs(candidate_profile, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Personalizes Australian jobs for a candidate based on:
    - Preferred work category (Question 1)
    - Preferred location / Remote preference (Question 2)
    - Preferred employment type (Question 3)
    - Skills and experience
    Returns prioritized list of jobs with match score and reasons.
    """
    base_qs = get_australian_jobs_queryset()

    if not candidate_profile:
        return list(base_qs.order_by('-created_at')[:limit])

    pref_dept = getattr(candidate_profile, 'department', '') or ''
    pref_role = getattr(candidate_profile, 'preferred_job_role', '') or ''
    pref_loc = getattr(candidate_profile, 'preferred_location', '') or getattr(candidate_profile, 'location', '') or ''
    pref_emp = getattr(candidate_profile, 'employment_type', '') or ''

    # Get skills
    skills = list(candidate_profile.skills.values_list('skill_name', flat=True))
    if not skills and getattr(candidate_profile, 'ai_skills', None):
        skills = candidate_profile.ai_skills if isinstance(candidate_profile.ai_skills, list) else []

    scored_jobs = []
    for job in base_qs[:100]:
        score = 0
        match_reasons = []

        # 1. Classification / Department match (+35 points)
        if pref_dept and (pref_dept.lower() in (job.department or '').lower() or pref_dept.lower() in (job.company.industry or '').lower()):
            score += 35
            match_reasons.append(f"Matches category: {pref_dept}")
        elif pref_role and (pref_role.lower() in job.title.lower()):
            score += 35
            match_reasons.append(f"Matches role: {pref_role}")

        # 2. Location match (+30 points)
        if 'REMOTE' in pref_loc.upper() and (job.work_mode == 'REMOTE' or job.is_remote or 'REMOTE' in job.location.upper()):
            score += 30
            match_reasons.append("Remote match")
        elif pref_loc and any(term.lower() in job.location.lower() for term in pref_loc.split(',') if term.strip()):
            score += 30
            match_reasons.append(f"Location match: {job.location}")

        # 3. Employment type match (+20 points)
        if pref_emp and pref_emp == job.job_type:
            score += 20
            match_reasons.append("Employment type match")

        # 4. Skills match (+15 points)
        job_skills = [s.lower() for s in job.get_required_skills_list + job.get_preferred_skills_list]
        matched_skills = [s for s in skills if s.lower() in job_skills]
        if matched_skills:
            score += min(20, len(matched_skills) * 5)
            match_reasons.append(f"Matched {len(matched_skills)} skills")

        is_recommended = score >= 30
        scored_jobs.append({
            'job': job,
            'score': score,
            'is_recommended': is_recommended,
            'match_reasons': match_reasons,
        })

    # Sort descending by score, then date
    scored_jobs.sort(key=lambda x: (x['score'], x['job'].created_at), reverse=True)

    # Return top matches
    return [item['job'] for item in scored_jobs[:limit]]


# ==============================================================================
# 3. SALARY BENCHMARKS & CAREER RESOURCES DATA
# ==============================================================================
AU_SALARY_BENCHMARKS = [
    {
        "role": "Senior Software Engineer",
        "category": "IT & Software Development",
        "junior_aud": "$85,000 - $105,000",
        "mid_aud": "$120,000 - $155,000",
        "senior_aud": "$160,000 - $200,000",
        "lead_aud": "$210,000 - $260,000",
        "avg_hourly": "$85 - $130 / hr",
        "growth": "+7.5% YoY",
        "top_states": ["NSW", "VIC", "QLD"]
    },
    {
        "role": "Registered Nurse (RN)",
        "category": "Healthcare & Medical",
        "junior_aud": "$72,000 - $82,000",
        "mid_aud": "$85,000 - $98,000",
        "senior_aud": "$102,000 - $120,000",
        "lead_aud": "$125,000 - $145,000",
        "avg_hourly": "$42 - $68 / hr",
        "growth": "+6.8% YoY",
        "top_states": ["NSW", "VIC", "QLD", "WA"]
    },
    {
        "role": "Financial Accountant (CPA/CA)",
        "category": "Accounting & Finance",
        "junior_aud": "$68,000 - $80,000",
        "mid_aud": "$90,000 - $115,000",
        "senior_aud": "$125,000 - $150,000",
        "lead_aud": "$160,000 - $195,000",
        "avg_hourly": "$55 - $95 / hr",
        "growth": "+5.2% YoY",
        "top_states": ["NSW", "VIC", "WA"]
    },
    {
        "role": "Civil / Structural Project Engineer",
        "category": "Construction & Engineering",
        "junior_aud": "$78,000 - $92,000",
        "mid_aud": "$105,000 - $135,000",
        "senior_aud": "$145,000 - $185,000",
        "lead_aud": "$190,000 - $240,000",
        "avg_hourly": "$70 - $125 / hr",
        "growth": "+8.1% YoY",
        "top_states": ["NSW", "QLD", "VIC", "WA"]
    },
    {
        "role": "Digital Marketing Specialist",
        "category": "Marketing & Communications",
        "junior_aud": "$60,000 - $72,000",
        "mid_aud": "$80,000 - $98,000",
        "senior_aud": "$105,000 - $130,000",
        "lead_aud": "$140,000 - $175,000",
        "avg_hourly": "$48 - $85 / hr",
        "growth": "+4.9% YoY",
        "top_states": ["NSW", "VIC", "QLD"]
    },
    {
        "role": "Mining Operations Supervisor",
        "category": "Mining, Energy & Resources",
        "junior_aud": "$95,000 - $120,000",
        "mid_aud": "$135,000 - $170,000",
        "senior_aud": "$180,000 - $230,000",
        "lead_aud": "$240,000 - $310,000",
        "avg_hourly": "$90 - $160 / hr",
        "growth": "+9.4% YoY",
        "top_states": ["WA", "QLD", "SA", "NT"]
    }
]

AU_CAREER_ARTICLES = [
    {
        "title": "Mastering the Australian Resume Format (2026 Standards)",
        "slug": "australian-resume-format-standards",
        "category": "Resume Writing",
        "read_time": "5 min read",
        "icon": "bi-file-earmark-person-fill",
        "summary": "Australian hiring managers prioritize reverse-chronological resumes without photos or marital status. Focus on measurable achievements, key competencies, and Australian residency or visa working rights.",
        "highlights": [
            "Keep resumes between 2 to 3 pages maximum",
            "State your Australian working rights clearly (Citizen, PR, TSS 482)",
            "Highlight quantifiable metrics (e.g. 'Grew ARR by 28% in 12 months')"
        ]
    },
    {
        "title": "Nailing Behavioral Interviews with the STAR Technique",
        "slug": "star-interview-technique-australia",
        "category": "Interview Preparation",
        "read_time": "6 min read",
        "icon": "bi-chat-quote-fill",
        "summary": "Australian employers frequently evaluate candidates using behavioral questions. Learn how to structure your answers using Situation, Task, Action, and Result to showcase your problem-solving impact.",
        "highlights": [
            "Situation: Set the context and challenge concisely",
            "Task: Clarify your specific responsibility",
            "Action: Detail the initiatives you led and tools used",
            "Result: Conclude with hard outcomes and lessons learned"
        ]
    },
    {
        "title": "Understanding Fair Work Rights & Superannuation (11.5%)",
        "slug": "fair-work-superannuation-rights",
        "category": "Workplace Rights",
        "read_time": "4 min read",
        "icon": "bi-shield-check",
        "summary": "Understand your legal entitlements under the National Employment Standards (NES), compulsory employer superannuation contributions (currently 11.5% and moving to 12%), overtime rules, and leave entitlements.",
        "highlights": [
            "Compulsory Superannuation Guarantee (SG) paid on top of OTE",
            "4 weeks annual leave for standard full-time employees",
            "Protection against unfair dismissal under Fair Work Ombudsman rules"
        ]
    },
    {
        "title": "How to Negotiate Your Salary Package in AUD",
        "slug": "negotiating-salary-package-australia",
        "category": "Salary & Benefits",
        "read_time": "5 min read",
        "icon": "bi-currency-dollar",
        "summary": "Distinguish between base salary and total remuneration package (TRP including superannuation). Discover how to research market benchmarks, leverage competing offers, and negotiate flexible hybrid arrangements.",
        "highlights": [
            "Always clarify whether an offer is 'plus super' or 'inclusive of super'",
            "Benchmark your level against current market salary bands",
            "Incorporate non-cash benefits such as remote stipends and bonus structures"
        ]
    }
]

AU_RESOURCES = [
    {
        "title": "Standard Australian ATS Resume Template",
        "category": "Resume Templates",
        "badge": "Word & PDF",
        "icon": "bi-file-earmark-word-fill",
        "description": "Clean, two-column and single-column ATS-friendly templates optimized for Australian recruiters and recruitment software.",
    },
    {
        "title": "Australian Cover Letter Framework",
        "category": "Cover Letters",
        "badge": "Proven Formula",
        "icon": "bi-envelope-paper-heart-fill",
        "description": "A structured 3-paragraph framework connecting your key accomplishments directly to the role requirements.",
    },
    {
        "title": "Working Rights & Visa Verification Checklist",
        "category": "Legal & Compliance",
        "badge": "Official Guidance",
        "icon": "bi-passport-fill",
        "description": "Comprehensive guide on VEVO checks, working holiday visa restrictions (Subclass 417/462), TSS 482, and PR pathways.",
    },
    {
        "title": "Australian Interview Preparation Checklist",
        "category": "Interview Success",
        "badge": "Checklist",
        "icon": "bi-card-checklist",
        "description": "Step-by-step checklist for in-person, phone screening, and video interviews with Australian recruiters.",
    }
]
