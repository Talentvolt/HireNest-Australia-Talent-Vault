"""
Worldwide currency, salary period and work-authorisation reference data for the
HireNest candidate application flow.

Kept self-contained so the candidate application form and the admin API share a
single source of truth. HireNest remains an Australian product, so AUD and an
annual salary period are the safe defaults for pre-existing applications.
"""

DEFAULT_CURRENCY = 'AUD'
DEFAULT_SALARY_PERIOD = 'ANNUALLY'

SALARY_PERIOD_CHOICES = [
    ('HOURLY', 'Hourly'),
    ('MONTHLY', 'Monthly'),
    ('ANNUALLY', 'Annually'),
]

CURRENCY_CHOICES = [
    ('AUD', 'AUD — Australian Dollar (A$)'),
    ('USD', 'USD — US Dollar ($)'),
    ('INR', 'INR — Indian Rupee (₹)'),
    ('GBP', 'GBP — British Pound (£)'),
    ('EUR', 'EUR — Euro (€)'),
    ('CAD', 'CAD — Canadian Dollar (C$)'),
    ('NZD', 'NZD — New Zealand Dollar (NZ$)'),
    ('SGD', 'SGD — Singapore Dollar (S$)'),
    ('AED', 'AED — UAE Dirham'),
    ('SAR', 'SAR — Saudi Riyal'),
    ('QAR', 'QAR — Qatari Riyal'),
    ('KWD', 'KWD — Kuwaiti Dinar'),
    ('BHD', 'BHD — Bahraini Dinar'),
    ('OMR', 'OMR — Omani Rial'),
    ('JOD', 'JOD — Jordanian Dinar'),
    ('LBP', 'LBP — Lebanese Pound'),
    ('JPY', 'JPY — Japanese Yen (¥)'),
    ('CNY', 'CNY — Chinese Yuan (¥)'),
    ('HKD', 'HKD — Hong Kong Dollar (HK$)'),
    ('KRW', 'KRW — South Korean Won (₩)'),
    ('TWD', 'TWD — New Taiwan Dollar'),
    ('CHF', 'CHF — Swiss Franc'),
    ('SEK', 'SEK — Swedish Krona'),
    ('NOK', 'NOK — Norwegian Krone'),
    ('DKK', 'DKK — Danish Krone'),
    ('PLN', 'PLN — Polish Zloty'),
    ('CZK', 'CZK — Czech Koruna'),
    ('HUF', 'HUF — Hungarian Forint'),
    ('RON', 'RON — Romanian Leu'),
    ('BGN', 'BGN — Bulgarian Lev'),
    ('TRY', 'TRY — Turkish Lira'),
    ('ILS', 'ILS — Israeli New Shekel'),
    ('EGP', 'EGP — Egyptian Pound'),
    ('ZAR', 'ZAR — South African Rand'),
    ('NGN', 'NGN — Nigerian Naira'),
    ('KES', 'KES — Kenyan Shilling'),
    ('GHS', 'GHS — Ghanaian Cedi'),
    ('MAD', 'MAD — Moroccan Dirham'),
    ('TND', 'TND — Tunisian Dinar'),
    ('DZD', 'DZD — Algerian Dinar'),
    ('BRL', 'BRL — Brazilian Real'),
    ('MXN', 'MXN — Mexican Peso'),
    ('ARS', 'ARS — Argentine Peso'),
    ('CLP', 'CLP — Chilean Peso'),
    ('COP', 'COP — Colombian Peso'),
    ('PEN', 'PEN — Peruvian Sol'),
    ('FJD', 'FJD — Fijian Dollar'),
    ('MYR', 'MYR — Malaysian Ringgit'),
    ('IDR', 'IDR — Indonesian Rupiah'),
    ('THB', 'THB — Thai Baht'),
    ('VND', 'VND — Vietnamese Dong'),
    ('PHP', 'PHP — Philippine Peso'),
    ('PKR', 'PKR — Pakistani Rupee'),
    ('BDT', 'BDT — Bangladeshi Taka'),
    ('LKR', 'LKR — Sri Lankan Rupee'),
    ('NPR', 'NPR — Nepalese Rupee'),
    ('MMK', 'MMK — Myanmar Kyat'),
]

# Currency symbols used when formatting a compact salary display for the
# admin API. Falls back to the code itself for currencies without a symbol.
CURRENCY_SYMBOLS = {
    'AUD': 'A$', 'USD': '$', 'INR': '₹', 'GBP': '£', 'EUR': '€',
    'CAD': 'C$', 'NZD': 'NZ$', 'SGD': 'S$', 'AED': 'AED', 'SAR': 'SAR',
    'QAR': 'QAR', 'KWD': 'KWD', 'BHD': 'BHD', 'OMR': 'OMR', 'JOD': 'JOD',
    'LBP': 'LBP', 'JPY': '¥', 'CNY': '¥', 'HKD': 'HK$', 'KRW': '₩',
    'TWD': 'NT$', 'CHF': 'CHF', 'SEK': 'kr', 'NOK': 'kr', 'DKK': 'kr',
    'PLN': 'zł', 'CZK': 'Kč', 'HUF': 'Ft', 'RON': 'lei', 'BGN': 'лв',
    'TRY': '₺', 'ILS': '₪', 'EGP': 'E£', 'ZAR': 'R', 'NGN': '₦',
    'KES': 'KSh', 'GHS': 'GH₵', 'MAD': 'MAD', 'TND': 'TND', 'DZD': 'DZD',
    'BRL': 'R$', 'MXN': 'MX$', 'ARS': 'AR$', 'CLP': 'CLP$', 'COP': 'COP$',
    'PEN': 'S/', 'FJD': 'FJ$', 'MYR': 'RM', 'IDR': 'Rp', 'THB': '฿',
    'VND': '₫', 'PHP': '₱', 'PKR': '₨', 'BDT': '৳', 'LKR': 'Rs',
    'NPR': 'Rs', 'MMK': 'K',
}

SALARY_PERIOD_SUFFIX = {
    'HOURLY': '/ hour',
    'MONTHLY': '/ month',
    'ANNUALLY': '/ year',
}

# International work-authorisation choices. These replace the Australia-only
# citizenship options on the job application form.
WORK_RIGHTS_CHOICES = [
    ('Citizen', 'Citizen of the job\'s country'),
    ('Permanent Resident', 'Permanent resident of the job\'s country'),
    ('Work Visa / Permit', 'Hold a valid work visa / permit for the job\'s country'),
    ('Requires Sponsorship', 'Require visa sponsorship'),
    ('Other', 'Other'),
]


def format_salary_with_currency(amount, currency, salary_period=None):
    """Return a compact, human-readable salary string for the admin API."""
    if amount is None:
        return ''
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return str(amount)

    symbol = CURRENCY_SYMBOLS.get((currency or DEFAULT_CURRENCY).upper(), currency or '')
    if value >= 1000 and value == int(value):
        number = f"{int(value):,}"
    else:
        number = f"{value:,.2f}".rstrip('0').rstrip('.')
    suffix = SALARY_PERIOD_SUFFIX.get((salary_period or '').upper(), '')
    return f"{symbol}{number}{suffix}"
