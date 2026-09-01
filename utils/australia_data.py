"""
Australia Localization & Reference Data for HireNest Australia.
Provides structured data for Australian states, suburbs, classifications, 
salary guides, career advice, and candidate resources.
"""

AUSTRALIAN_STATES = [
    {"code": "NSW", "name": "New South Wales", "capital": "Sydney"},
    {"code": "VIC", "name": "Victoria", "capital": "Melbourne"},
    {"code": "QLD", "name": "Queensland", "capital": "Brisbane"},
    {"code": "WA", "name": "Western Australia", "capital": "Perth"},
    {"code": "SA", "name": "South Australia", "capital": "Adelaide"},
    {"code": "TAS", "name": "Tasmania", "capital": "Hobart"},
    {"code": "ACT", "name": "Australian Capital Territory", "capital": "Canberra"},
    {"code": "NT", "name": "Northern Territory", "capital": "Darwin"},
]

POPULAR_AUSTRALIAN_LOCATIONS = [
    "Sydney NSW",
    "Melbourne VIC",
    "Brisbane QLD",
    "Perth WA",
    "Adelaide SA",
    "Gold Coast QLD",
    "Canberra ACT",
    "Newcastle NSW",
    "Wollongong NSW",
    "Geelong VIC",
    "Hobart TAS",
    "Darwin NT",
    "Townsville QLD",
    "Cairns QLD",
    "Toowoomba QLD",
    "Ballarat VIC",
    "Bendigo VIC",
    "Albury-Wodonga NSW/VIC",
    "Launceston TAS",
    "Sunshine Coast QLD",
    "Remote - Australia",
]

AUSTRALIAN_CLASSIFICATIONS = [
    {
        "id": "ict",
        "name": "Information & Communication Technology",
        "icon": "bi-laptop",
        "badge": "In Demand",
        "roles_count": "3,400+",
        "popular_roles": ["Software Engineer", "DevOps Engineer", "Cloud Architect", "Data Analyst", "Cyber Security Specialist", "Full Stack Developer"]
    },
    {
        "id": "healthcare",
        "name": "Healthcare & Nursing",
        "icon": "bi-heart-pulse-fill",
        "badge": "High Growth",
        "roles_count": "4,100+",
        "popular_roles": ["Registered Nurse", "Aged Care Worker", "Physiotherapist", "General Practitioner", "Occupational Therapist", "Clinical Nurse Specialist"]
    },
    {
        "id": "accounting-finance",
        "name": "Accounting & Finance",
        "icon": "bi-calculator-fill",
        "badge": "Essential",
        "roles_count": "2,200+",
        "popular_roles": ["Financial Accountant", "Management Accountant", "Payroll Officer", "Financial Analyst", "Audit Senior", "Bookkeeper"]
    },
    {
        "id": "engineering",
        "name": "Engineering",
        "icon": "bi-gear-wide-connected",
        "badge": "Major Projects",
        "roles_count": "1,850+",
        "popular_roles": ["Civil Engineer", "Mechanical Engineer", "Electrical Engineer", "Mining Engineer", "Structural Engineer", "Project Engineer"]
    },
    {
        "id": "trades-services",
        "name": "Trades & Services",
        "icon": "bi-tools",
        "badge": "Booming",
        "roles_count": "3,100+",
        "popular_roles": ["Licensed Electrician", "Plumber", "Carpenter", "Diesel Mechanic", "HVAC Technician", "Boilermaker"]
    },
    {
        "id": "sales-customer-service",
        "name": "Sales & Customer Service",
        "icon": "bi-headset",
        "badge": "Entry to Senior",
        "roles_count": "2,700+",
        "popular_roles": ["Customer Service Representative", "Account Executive", "Business Development Manager", "Sales Representative", "Call Centre Consultant"]
    },
    {
        "id": "education-training",
        "name": "Education & Training",
        "icon": "bi-book-half",
        "badge": "National Priority",
        "roles_count": "1,950+",
        "popular_roles": ["Secondary Teacher", "Early Childhood Educator", "Primary School Teacher", "Vocational Trainer", "Special Education Teacher"]
    },
    {
        "id": "construction",
        "name": "Construction & Architecture",
        "icon": "bi-building-fill-gear",
        "badge": "Infrastructure",
        "roles_count": "2,400+",
        "popular_roles": ["Site Supervisor", "Construction Project Manager", "Estimator", "Architect", "Safety Officer (WHS)", "Leading Hand"]
    },
    {
        "id": "hospitality-tourism",
        "name": "Hospitality & Tourism",
        "icon": "bi-cup-hot-fill",
        "badge": "Flexible",
        "roles_count": "2,600+",
        "popular_roles": ["Head Chef", "Restaurant Manager", "Barista", "Hotel Duty Manager", "Food & Beverage Attendant", "Sous Chef"]
    },
    {
        "id": "admin-office",
        "name": "Administration & Office Support",
        "icon": "bi-folder2-open",
        "badge": "Versatile",
        "roles_count": "2,100+",
        "popular_roles": ["Executive Assistant", "Office Manager", "Receptionist", "Data Entry Clerk", "Operations Coordinator"]
    },
    {
        "id": "marketing-comms",
        "name": "Marketing & Communications",
        "icon": "bi-megaphone-fill",
        "badge": "Digital Focus",
        "roles_count": "1,400+",
        "popular_roles": ["Digital Marketing Specialist", "Content Strategist", "Brand Manager", "SEO/SEM Manager", "Communications Officer"]
    },
    {
        "id": "legal-hr",
        "name": "Human Resources & Legal",
        "icon": "bi-people-fill",
        "badge": "Professional",
        "roles_count": "1,200+",
        "popular_roles": ["HR Business Partner", "Talent Acquisition Specialist", "In-House Legal Counsel", "People & Culture Coordinator", "Paralegal"]
    }
]

SALARY_GUIDE_DATA = [
    {
        "role": "Senior Full Stack Engineer",
        "category": "Information & Communication Technology",
        "junior_aud": "$95,000 - $115,000",
        "mid_aud": "$125,000 - $150,000",
        "senior_aud": "$160,000 - $195,000",
        "lead_aud": "$200,000 - $240,000",
        "avg_hourly": "$85 - $130 / hr",
        "growth": "+8.4% YoY",
        "top_states": ["NSW", "VIC", "QLD"]
    },
    {
        "role": "Cloud DevOps Engineer",
        "category": "Information & Communication Technology",
        "junior_aud": "$100,000 - $120,000",
        "mid_aud": "$135,000 - $165,000",
        "senior_aud": "$175,000 - $210,000",
        "lead_aud": "$215,000 - $255,000",
        "avg_hourly": "$95 - $145 / hr",
        "growth": "+11.2% YoY",
        "top_states": ["NSW", "VIC", "ACT", "WA"]
    },
    {
        "role": "Registered Nurse (RN)",
        "category": "Healthcare & Nursing",
        "junior_aud": "$75,000 - $85,000",
        "mid_aud": "$88,000 - $102,000",
        "senior_aud": "$105,000 - $125,000",
        "lead_aud": "$130,000 - $155,000",
        "avg_hourly": "$42 - $68 / hr",
        "growth": "+6.5% YoY",
        "top_states": ["NSW", "QLD", "VIC", "WA", "SA"]
    },
    {
        "role": "Financial Accountant (CPA / CA)",
        "category": "Accounting & Finance",
        "junior_aud": "$75,000 - $88,000",
        "mid_aud": "$95,000 - $120,000",
        "senior_aud": "$125,000 - $155,000",
        "lead_aud": "$165,000 - $205,000",
        "avg_hourly": "$65 - $110 / hr",
        "growth": "+5.2% YoY",
        "top_states": ["NSW", "VIC", "WA"]
    },
    {
        "role": "Civil Project Engineer",
        "category": "Engineering",
        "junior_aud": "$85,000 - $100,000",
        "mid_aud": "$110,000 - $135,000",
        "senior_aud": "$145,000 - $180,000",
        "lead_aud": "$190,000 - $235,000",
        "avg_hourly": "$80 - $135 / hr",
        "growth": "+7.1% YoY",
        "top_states": ["NSW", "QLD", "VIC", "WA"]
    },
    {
        "role": "Construction Site Manager",
        "category": "Construction & Architecture",
        "junior_aud": "$90,000 - $110,000",
        "mid_aud": "$120,000 - $150,000",
        "senior_aud": "$160,000 - $200,000",
        "lead_aud": "$210,000 - $260,000",
        "avg_hourly": "$85 - $140 / hr",
        "growth": "+6.8% YoY",
        "top_states": ["NSW", "VIC", "QLD"]
    },
    {
        "role": "Customer Success / Service Specialist",
        "category": "Sales & Customer Service",
        "junior_aud": "$60,000 - $70,000",
        "mid_aud": "$75,000 - $90,000",
        "senior_aud": "$95,000 - $115,000",
        "lead_aud": "$120,000 - $145,000",
        "avg_hourly": "$32 - $55 / hr",
        "growth": "+4.9% YoY",
        "top_states": ["NSW", "VIC", "QLD", "SA"]
    },
    {
        "role": "Licensed Electrician",
        "category": "Trades & Services",
        "junior_aud": "$70,000 - $85,000",
        "mid_aud": "$90,000 - $115,000",
        "senior_aud": "$120,000 - $150,000",
        "lead_aud": "$155,000 - $190,000",
        "avg_hourly": "$48 - $85 / hr",
        "growth": "+9.0% YoY",
        "top_states": ["WA", "QLD", "NSW", "VIC"]
    },
    {
        "role": "Secondary School Teacher",
        "category": "Education & Training",
        "junior_aud": "$78,000 - $88,000",
        "mid_aud": "$92,000 - $108,000",
        "senior_aud": "$112,000 - $128,000",
        "lead_aud": "$132,000 - $150,000",
        "avg_hourly": "$45 - $70 / hr",
        "growth": "+5.8% YoY",
        "top_states": ["NSW", "VIC", "QLD", "WA"]
    },
    {
        "role": "Digital Marketing Manager",
        "category": "Marketing & Communications",
        "junior_aud": "$70,000 - $85,000",
        "mid_aud": "$95,000 - $120,000",
        "senior_aud": "$130,000 - $160,000",
        "lead_aud": "$170,000 - $210,000",
        "avg_hourly": "$60 - $105 / hr",
        "growth": "+6.1% YoY",
        "top_states": ["NSW", "VIC", "QLD"]
    }
]

CAREER_ADVICE_ARTICLES = [
    {
        "slug": "australian-resume-format-guide-2026",
        "category": "Resume Advice",
        "title": "The Ultimate Australian Resume Format Guide (2026 Standards)",
        "read_time": "5 min read",
        "summary": "Learn what Australian recruiters and hiring managers look for in a CV: length, Australian spelling, key achievements, and avoiding common pitfalls.",
        "icon": "bi-file-earmark-person-fill",
        "highlights": [
            "Australian standard length: 2 to 3 pages for professionals",
            "No photo, date of birth, or marital status required",
            "Focus on quantified achievements rather than just duties",
            "Tailor keywords for Australian Applicant Tracking Systems"
        ]
    },
    {
        "slug": "mastering-star-technique-australian-interviews",
        "category": "Interview Tips",
        "title": "Mastering the STAR Technique in Australian Behavioral Interviews",
        "read_time": "6 min read",
        "summary": "Australian employers heavily favor competency-based questions. Structure your answers with Situation, Task, Action, and Result to stand out.",
        "icon": "bi-chat-quote-fill",
        "highlights": [
            "Explain the context clearly (Situation)",
            "Define your specific role (Task)",
            "Highlight what YOU did using active verbs (Action)",
            "Quantify the positive business outcome (Result)"
        ]
    },
    {
        "slug": "understanding-superannuation-workplace-rights-australia",
        "category": "Workplace Advice",
        "title": "Understanding Superannuation, Awards & Australian Workplace Rights",
        "read_time": "7 min read",
        "summary": "A comprehensive guide to Fair Work Australia regulations, national minimum wage, modern awards, leave entitlements, and compulsory superannuation.",
        "icon": "bi-shield-check",
        "highlights": [
            "Superannuation guarantee rate and employee rights",
            "Difference between Full-Time, Part-Time, and Casual loading (+25%)",
            "National Employment Standards (NES) 11 minimum entitlements",
            "How Modern Awards determine overtime and penalty rates"
        ]
    },
    {
        "slug": "how-to-negotiate-salary-aud-market",
        "category": "Salary Negotiation",
        "title": "How to Confidently Negotiate Your Salary in the Australian Market",
        "read_time": "4 min read",
        "summary": "Know your market value in AUD, understand total remuneration packages including superannuation vs base salary, and negotiate strategically.",
        "icon": "bi-currency-dollar",
        "highlights": [
            "Always clarify whether an offer is 'Base Salary' or 'Package (Base + Super)'",
            "Benchmark with verified Australian industry pay scales",
            "Consider non-salary benefits: WFH flexibility, training budgets, novated leases",
            "When and how to present your counter-offer professionally"
        ]
    },
    {
        "slug": "career-transition-australia-growing-industries",
        "category": "Career Development",
        "title": "Transitioning Careers into Australia's Fastest-Growing Industries",
        "read_time": "5 min read",
        "summary": "Explore high-demand Australian sectors like renewable energy, cybersecurity, aged care, and infrastructure, plus upskilling pathways.",
        "icon": "bi-graph-up-arrow",
        "highlights": [
            "Identify transferable skills from your previous domain",
            "Government-subsidized training pathways (Fee-Free TAFE)",
            "Networking through Australian professional associations",
            "How to structure a career changer CV"
        ]
    }
]

RESOURCES_DATA = [
    {
        "category": "Templates & Downloads",
        "title": "Modern Australian Resume Template (Docx / PDF)",
        "description": "ATS-friendly 2-page template structured according to Australian recruitment best practices.",
        "icon": "bi-file-earmark-arrow-down-fill",
        "badge": "Free Download",
        "type": "Template"
    },
    {
        "category": "Templates & Downloads",
        "title": "Australian Cover Letter Formula & Examples",
        "description": "Customizable 1-page cover letter template with targeted opening hooks and Australian phrasing.",
        "icon": "bi-envelope-paper-fill",
        "badge": "Free Download",
        "type": "Template"
    },
    {
        "category": "Guides & Checklists",
        "title": "Australian Interview Preparation Checklist",
        "description": "A step-by-step checklist to prepare for video, phone screening, and in-person Australian interviews.",
        "icon": "bi-card-checklist",
        "badge": "Checklist",
        "type": "Guide"
    },
    {
        "category": "Visa & Working Rights",
        "title": "Australian Work Rights & Visa Categories Quick Guide",
        "description": "Overview of working rights for Citizens, Permanent Residents, Temporary Skill Shortage (Subclass 482), and Working Holiday Visas.",
        "icon": "bi-passport-fill",
        "badge": "Official Reference",
        "type": "Guide"
    },
    {
        "category": "Industry Insights",
        "title": "Fair Work & Superannuation 2026 Factsheet",
        "description": "Concise summary of Australian National Employment Standards, mandatory superannuation, and casual conversion rules.",
        "icon": "bi-info-circle-fill",
        "badge": "Factsheet",
        "type": "Reference"
    }
]
