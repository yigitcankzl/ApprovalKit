"""
PII masking for audit logs.

Masks emails, names, and other personally identifiable information
before storing in audit trail. Keeps first/last chars for debugging.
"""
import re

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_PII_PARAM_KEYS = {"email", "customer", "recipient", "beneficiary", "name", "username",
                    "patient_name", "patient_id", "user_email", "account_holder",
                    "contact", "subject_email", "phone", "address", "ssn", "account_email"}


def _mask_email(email: str) -> str:
    """alice@example.com → a***@e***.com"""
    local, _, domain = email.partition("@")
    if not domain:
        return email
    parts = domain.rsplit(".", 1)
    masked_local = local[0] + "***" if local else "***"
    masked_domain = parts[0][0] + "***" if parts[0] else "***"
    tld = "." + parts[1] if len(parts) > 1 else ""
    return f"{masked_local}@{masked_domain}{tld}"


def _mask_string(value: str) -> str:
    """Mask a string: keep first 2 and last 1 char. 'Alice' → 'Al***e'"""
    if len(value) <= 3:
        return value[0] + "***" if value else "***"
    return value[:2] + "***" + value[-1]


def mask_text(text: str) -> str:
    """Mask emails found in free text (binding messages, notes)."""
    return _EMAIL_RE.sub(lambda m: _mask_email(m.group()), text)


def mask_params(params: dict | None) -> dict | None:
    """Mask PII values in a params dict. Returns new dict, original untouched."""
    if not params:
        return params
    masked = {}
    for k, v in params.items():
        if k.lower() in _PII_PARAM_KEYS and isinstance(v, str):
            if "@" in v:
                masked[k] = _mask_email(v)
            else:
                masked[k] = _mask_string(v)
        else:
            masked[k] = v
    return masked
