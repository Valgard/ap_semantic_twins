def validate(value):
    """Reject anything that is not a five-digit German postcode."""
    if not value.isdigit() or len(value) != 5:
        raise ValueError("not a postcode")
    return value
