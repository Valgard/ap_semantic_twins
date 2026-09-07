def net_amount_in_cents(amount, rate):
    """Strip the tax share off an amount and express it in cents."""
    without_tax = amount / (1 + rate)
    return int(without_tax * 100)
