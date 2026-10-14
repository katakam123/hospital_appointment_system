import re

from pydantic import field_validator


def validate_phone_number(value: str) -> str:
    value = value.strip()

    if not re.fullmatch(r"[0-9]{10}", value):
        raise ValueError("Phone number must contain exactly 10 digits.")

    return value


def validate_required_text(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("This field cannot be empty.")

    return value