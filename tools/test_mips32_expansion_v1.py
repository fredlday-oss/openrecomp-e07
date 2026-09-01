#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mips32 import DecodeError, decode
from mips32_expansion_frontend_v1 import FrontendError, convert, load_hex
from run_mips32_expansion_reference import ReferenceError, ReferenceMachine

FIXTURES = ROOT / "examples" / "mips32-expansion-v1"
HOST_CONTRACT = ROOT / "contracts" / "host_contract.json"


def expect_reject(label: str, fn, exceptions=(FrontendError, DecodeError, ReferenceError)) -> None:
    try:
        fn()
    except exceptions:
        print(f"PASS {label}")
    else:
        raise AssertionError(f"{label}: invalid input was accepted")


def main() -> None:
    logic_words, _ = load_hex(FIXTURES / "logic-shift.hex")
    memory_words, _ = load_hex(FIXTURES / "memory-width.hex")
    branch_words, branch_hash = load_hex(FIXTURES / "branches-calls.hex")
    mult_words, _ = load_hex(FIXTURES / "mult-hilo.hex")

    assert decode(0x1018, logic_words[0x1018])["op"] == "sll"
    assert decode(0x1010, memory_words[0x1010])["op"] == "lb"
    assert decode(0x1034, branch_words[0x1034])["op"] == "bgez"
    assert decode(0x1020, mult_words[0x1020])["op"] == "multu"
    print("OPENRECOMP_MIPS32_EXPANSION_DECODER=PASS")

    expect_reject("div-rejected-with-frozen-ir-v1", lambda: decode(0x1000, 0x0109001A))
    malformed_shift = (1 << 21) | (2 << 16) | (3 << 11) | (1 << 6)
    expect_reject("malformed-fixed-shift-rejected", lambda: decode(0x1000, malformed_shift))
    unsupported_regimm = (0x01 << 26) | (8 << 21) | (2 << 16)
    expect_reject("unsupported-regimm-rejected", lambda: decode(0x1000, unsupported_regimm))

    with tempfile.TemporaryDirectory() as tmp:
        bad_hex = Path(tmp) / "bad.hex"
        bad_hex.write_text("00001002 00000000\n", encoding="utf-8")
        expect_reject("misaligned-source-record-rejected", lambda: load_hex(bad_hex))

    branch_meta = json.loads((FIXTURES / "branches-calls.json").read_text(encoding="utf-8"))
    contract = json.loads(HOST_CONTRACT.read_text(encoding="utf-8"))
    bad_branch = dict(branch_words)
    bad_branch[0x1010] = 0x19007FFF
    expect_reject(
        "branch-target-outside-function-rejected",
        lambda: convert(branch_meta, bad_branch, branch_hash, contract),
    )

    misaligned_meta = copy.deepcopy(branch_meta)
    misaligned_meta["functions"] = [{"id": "misaligned", "address": 0x1000}]
    misaligned_meta["entry_address"] = 0x1000
    misaligned_meta["max_reference_steps"] = 20
    misaligned_words = {
        0x1000: 0x24092001,
        0x1004: 0x85220000,
        0x1008: 0x03E00008,
        0x100C: 0x00000000,
    }
    expect_reject(
        "misaligned-halfword-load-rejected",
        lambda: ReferenceMachine(misaligned_words, misaligned_meta).run(),
    )

    limited_meta = copy.deepcopy(branch_meta)
    limited_meta["functions"] = [{"id": "loop", "address": 0x1000}]
    limited_meta["entry_address"] = 0x1000
    limited_meta["max_reference_steps"] = 4
    loop_words = {0x1000: 0x08000400, 0x1004: 0x00000000}
    expect_reject(
        "reference-execution-limit-enforced",
        lambda: ReferenceMachine(loop_words, limited_meta).run(),
    )

    print("OPENRECOMP_MIPS32_EXPANSION_NEGATIVE_TESTS=PASS tests=7")


if __name__ == "__main__":
    main()
