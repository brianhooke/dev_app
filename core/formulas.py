"""Domain formulas / arithmetic helpers.

Anything that does GST math or AUD rounding lives here so the answer is
the same in every view, every formula, and every export.

Project-level "what counts as committed?" rollups now live in
``core/services/costing_rollups.py``; the old global ``Committed()``
function that used to live in this module was unreferenced (audit
A.M-H-01) and was removed in the P-5 / A.M-R-02 cleanup.
"""
from decimal import Decimal, ROUND_HALF_UP


# --- Money helpers ----------------------------------------------------------

GST_RATE = Decimal('0.10')  # Australian GST is 10% — change in one place.
TWO_PLACES = Decimal('0.01')


def to_decimal(value, default=Decimal('0')):
    """Coerce ``value`` to ``Decimal`` safely.

    Accepts ``None``, empty strings, ints, floats, Decimals, and numeric
    strings. Returns ``default`` for anything we can't parse. Floats are
    rounded by string conversion (avoids the binary float surprise).
    """
    if value is None or value == '':
        return default
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (ArithmeticError, ValueError, TypeError):
        return default


def quantize_money(value):
    """Round to 2 dp using banker's-rounding-free HALF_UP (matches AUD)."""
    return to_decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def gst_from_net(net):
    """Return the GST component for a given net amount."""
    return quantize_money(to_decimal(net) * GST_RATE)


def gross_from_net(net):
    """Return net + gst, rounded to 2 dp."""
    net_d = to_decimal(net)
    return quantize_money(net_d + (net_d * GST_RATE))


def net_from_gross(gross):
    """Return the net component of a GST-inclusive figure."""
    return quantize_money(to_decimal(gross) / (Decimal('1') + GST_RATE))


def sum_decimals(values, default=Decimal('0')):
    """Decimal-safe sum that ignores ``None`` and empty strings."""
    total = default
    for v in values:
        total += to_decimal(v)
    return total
