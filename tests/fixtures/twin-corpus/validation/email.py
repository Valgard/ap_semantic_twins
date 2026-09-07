def validate(value):
    """Reject anything that is not a plausible email address."""
    if "@" not in value:
        raise ValueError("not an email address")
    return value.strip().lower()
