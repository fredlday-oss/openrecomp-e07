from __future__ import annotations

DIVREM_KINDS = {"udiv", "urem", "sdiv", "srem"}


def _mask(bits: int) -> int:
    if bits not in {1, 8, 16, 32, 64}:
        raise ValueError(f"unsupported integer width {bits}")
    return (1 << bits) - 1


def _signed(value: int, bits: int) -> int:
    value &= _mask(bits)
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def divrem_result(kind: str, lhs: int, rhs: int, bits: int) -> int:
    """Total deterministic integer division/remainder semantics for IR V1.1."""
    if kind not in DIVREM_KINDS:
        raise ValueError(f"unsupported div/rem kind {kind}")
    mask = _mask(bits)
    lhs &= mask
    rhs &= mask

    if rhs == 0:
        return mask if kind in {"udiv", "sdiv"} else lhs
    if kind == "udiv":
        return (lhs // rhs) & mask
    if kind == "urem":
        return (lhs % rhs) & mask

    min_pattern = 1 << (bits - 1)
    if lhs == min_pattern and rhs == mask:
        return min_pattern if kind == "sdiv" else 0

    a = _signed(lhs, bits)
    b = _signed(rhs, bits)
    quotient = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        quotient = -quotient
    if kind == "sdiv":
        return quotient & mask
    return (a - quotient * b) & mask
