def gross_to_net_minor_units(gross, tax_rate):
    """Convert a gross price into net minor units."""
    if tax_rate < 0:
        raise ValueError("tax rate must not be negative")
    net = gross / (1 + tax_rate)
    return int(net * 100 + 0.5)
