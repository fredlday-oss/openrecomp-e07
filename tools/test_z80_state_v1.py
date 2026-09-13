#!/usr/bin/env python3
"""P1-20 gate: Z80 architectural state model.

Pins the documented Zilog Z80 register/flag model used by the SMS platform:

- 8-bit registers A/F/B/C/D/E/H/L plus the complete shadow set exchanged by
  EXX and EX AF,AF';
- 16-bit registers IX/IY/SP/PC with the documented high-byte-first pair
  composition AF/BC/DE/HL;
- flag bit positions in F: S(7) Z(6) H(4) P/V(2) N(1) C(0); the undocumented
  X(3)/Y(5) bits are pinned to 0 in this model (documented limitation);
- I/R and the interrupt state (IFF1/IFF2, IM 0/1/2);
- fail-closed width checks and deterministic snapshots.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from adapters.z80 import (  # noqa: E402
    FLAG_C,
    FLAG_H,
    FLAG_N,
    FLAG_PV,
    FLAG_S,
    FLAG_X,
    FLAG_Y,
    FLAG_Z,
    Z80Error,
    Z80State,
    exchange_af,
    exchange_all,
    get_pair,
    pair_halves,
    pair_of,
    set_pair,
)


def expect_fail(label: str, action) -> None:
    try:
        action()
    except (Z80Error, KeyError):
        print(f"PASS reject: {label}")
        return
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0

    # 1. Register file ------------------------------------------------------
    state = Z80State(
        a=0x12, f=0x34, b=0xAB, c=0xCD, d=0x56, e=0x78, h=0x9A, l=0xBC,
        a2=0x21, f2=0x43, b2=0xBA, c2=0xDC, d2=0x65, e2=0x87, h2=0xA9, l2=0xCB,
        ix=0x1234, iy=0x5678, sp=0xC000, pc=0x0100,
        i=0x7F, r=0x3E, iff1=True, iff2=True, im=1,
    )
    assert state.a == 0x12 and state.f == 0x34 and state.b == 0xAB
    assert state.ix == 0x1234 and state.iy == 0x5678
    assert state.sp == 0xC000 and state.pc == 0x0100
    assert state.i == 0x7F and state.r == 0x3E
    assert state.iff1 is True and state.iff2 is True and state.im == 1
    assert state.halted is False
    snapshot = state.snapshot()
    assert snapshot["a"] == 0x12 and snapshot["iff1"] == 1 and snapshot["im"] == 1
    assert state.snapshot() == snapshot  # deterministic
    print("PASS register file + deterministic snapshot")
    tests += 1

    # 2. Flag bit positions ---------------------------------------------------
    assert FLAG_C == 0x01 and FLAG_N == 0x02 and FLAG_PV == 0x04
    assert FLAG_H == 0x10 and FLAG_Z == 0x40 and FLAG_S == 0x80
    assert FLAG_X == 0x08 and FLAG_Y == 0x20  # undocumented, pinned to 0 in the model
    print("PASS documented flag bit positions S/Z/H/PV/N/C (X/Y pinned 0)")
    tests += 1

    # 3. Pair composition (documented high byte first) -------------------------
    assert pair_of(0x12, 0x34) == 0x1234
    assert pair_halves(0xABCD) == (0xAB, 0xCD)
    assert get_pair(state, "bc") == 0xABCD
    assert get_pair(state, "af") == 0x1234
    set_pair(state, "de", 0x0BAD)
    assert state.d == 0x0B and state.e == 0xAD
    set_pair(state, "hl", 0xFFFF)
    assert state.h == 0xFF and state.l == 0xFF
    print("PASS pair composition af/bc/de/hl high-byte-first")
    tests += 1

    # 4. EXX: documented shadow exchange ---------------------------------------
    before = (state.b, state.c, state.d, state.e, state.h, state.l)
    shadow = (state.b2, state.c2, state.d2, state.e2, state.h2, state.l2)
    exchange_all(state)
    assert (state.b, state.c, state.d, state.e, state.h, state.l) == shadow
    assert (state.b2, state.c2, state.d2, state.e2, state.h2, state.l2) == before
    exchange_all(state)
    assert (state.b, state.c, state.d, state.e, state.h, state.l) == before
    print("PASS EXX shadow exchange BC/DE/HL (double EXX restores)")
    tests += 1

    # 5. EX AF,AF': documented shadow exchange ----------------------------------
    exchange_af(state)
    assert state.a == 0x21 and state.f == 0x43 and state.a2 == 0x12 and state.f2 == 0x34
    exchange_af(state)
    assert state.a == 0x12 and state.f == 0x34
    print("PASS EX AF,AF' shadow exchange (double restores)")
    tests += 1

    # 6. Fail-closed width checks ------------------------------------------------
    expect_fail("pair-high-byte-out-of-range", lambda: pair_of(0x100, 0x00))
    expect_fail("pair-low-byte-out-of-range", lambda: pair_of(0x00, -1))
    expect_fail("pair-halves-out-of-range", lambda: pair_halves(0x10000))
    expect_fail("unknown-pair-name", lambda: get_pair(state, "ix"))
    print("PASS fail-closed width and pair-name checks")
    tests += 1

    print(f"OPENRECOMP_Z80_STATE_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
