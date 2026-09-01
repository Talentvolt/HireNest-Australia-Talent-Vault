"""
HireNest Australia Localization and Services Module.
Provides Australian employment classifications, states, major cities,
salary benchmarks in AUD, career guides, and search filtering helpers.
"""
from decimal import Decimal
from django.db.models import Q

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
    {"label": "Accounts", "query": "Accounts"},
    {"label": "Nursing", "query": "Nursing"},
    {"label": "Customer Service", "query": "Customer Service"},
    {"label": "Engineer", "query": "Engineer"},
    {"label": "Teacher", "query": "Teacher"},
    {"label": "Developer", "query": "Developer"},
    {"label": "Project Manager", "query": "Project Manager"},
    {"label": "Marketing", "query": "Marketing"},
]

POPULAR_AU_LOCATIONS = [
    "Sydney NSW", "Melbourne VIC", "Brisbane QLD", "Perth WA",
    "Adelaide SA", "Gold Coast QLD", "Canberra ACT", "Newcastle NSW",
    "Wollongong NSW", "Hobart TAS", "Darwin NT", "Geelong VIC",
    "Sunshine Coast QLD", "Townsville QLD", "Cairns QLD", "Remote Australia"
]

AUSTRALIAN_CLASSIFICATIONS = [
    {"name": "Healthcare & Medical", "icon": "bi-heart-pulse-fill", "badge": "High Demand", "roles_count": "2,400+"},
    {"name": "IT & Software Development", "icon": "bi-code-slash", "badge": "Top Remuneration", "roles_count": "3,150+"},
    {"name": "Construction & Trades", "icon": "bi-tools", "badge": "Booming Sector", "roles_count": "1,890+"},
    {"name": "Education & Training", "icon": "bi-mortarboard-fill", "badge": "Growing Demand", "roles_count": "1,240+"},
    {"name": "Accounting & Finance", "icon": "bi-cash-coin", "badge": "Essential", "roles_count": "1,650+"},
    {"name": "Sales & Relationship Management", "icon": "bi-graph-up-arrow", "badge": "Competitive", "roles_count": "1,420+"},
    {"name": "Hospitality & Tourism", "icon": "bi-cup-hot-fill", "badge": "Expanding", "roles_count": "980+"},
    {"name": "Mining, Energy & Resources", "icon": "bi-gem", "badge": "Top Earning", "roles_count": "870+"},
    {"name": "Administration & Office Support", "icon": "bi-folder2-open", "badge": "Immediate Start", "roles_count": "1,120+"},
    {"name": "Marketing & Communications", "icon": "bi-megaphone-fill", "badge": "Creative", "roles_count": "790+"},
    {"name": "Engineering", "icon": "bi-gear-wide-connected", "badge": "Critical Skill", "roles_count": "1,310+"},
    {"name": "Human Resources & Recruitment", "icon": "bi-people-fill", "badge": "Steady Growth", "roles_count": "640+"},
]

AU_SALARY_BENCHMARKS = [
    {
        "role": "Senior Software Engineer",
        "category": "Information Technology",
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
