#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.mips32 import DecodeError, decode
from mips32_frontend_v1 import FrontendError, convert, load_hex

FIXTURE_HEX = ROOT / "examples" / "mips32-v1" / "fixture.hex"
FIXTURE_META = ROOT / "examples" / "mips32-v1" / "fixture.json"
HOST_CONTRACT = ROOT / "contracts" / "host_contract.json"


def expect_reject(label: str, fn) -> None:
    try:
        fn()
    except (FrontendError, DecodeError):
        print(f"PASS {label}")
    else:
        raise AssertionError(f"{label}: invalid input was accepted")


def main() -> None:
    words, source_hash = load_hex(FIXTURE_HEX)
    meta = json.loads(FIXTURE_META.read_text(encoding="utf-8"))
    contract = json.loads(HOST_CONTRACT.read_text(encoding="utf-8"))

    addiu = decode(0x1004, words[0x1004])
    assert addiu == {
        "address": 0x1004,
        "word": words[0x1004],
        "op": "addiu",
        "rs": 0,
        "rt": 8,
        "imm": 5,
    }
    jal = decode(0x101C, words[0x101C])
    assert jal["op"] == "jal" and jal["target"] == 0x1080
    jr = decode(0x1084, words[0x1084])
    assert jr == {"address": 0x1084, "word": words[0x1084], "op": "jr", "rs": 31}
    print("PASS decoder-known-words")

    ir_a, sidecar_a, report_a = convert(meta, words, source_hash, contract)
    ir_b, sidecar_b, report_b = convert(meta, words, source_hash, contract)
    assert ir_a == ir_b and sidecar_a == sidecar_b and report_a == report_b
    assert report_a["delay_slots_lowered"] == 7
    assert len(ir_a["functions"]) == 2
    assert ir_a["source"]["architecture"] == "mips32-le"
    print("PASS deterministic-frontend")

    bad_delay = dict(words)
    bad_delay[0x1018] = 0x10000000  # beq $zero,$zero,0 in a delay slot
    expect_reject("control-in-delay-slot-rejected", lambda: convert(meta, bad_delay, source_hash, contract))

    bad_target = dict(words)
    bad_target[0x101C] = 0x0C000800  # jal 0x2000, not a declared function
    expect_reject("unknown-call-target-rejected", lambda: convert(meta, bad_target, source_hash, contract))

    bad_meta = copy.deepcopy(meta)
    bad_meta["architecture"] = "mips32-be"
    expect_reject("wrong-endianness-profile-rejected", lambda: convert(bad_meta, words, source_hash, contract))

    expect_reject("misaligned-decode-rejected", lambda: decode(0x1002, words[0x1004]))

    try:
        decode(0x1000, 0xFC000000)
    except DecodeError:
        print("PASS unsupported-opcode-rejected")
    else:
        raise AssertionError("unsupported opcode was accepted")

    print("OPENRECOMP_MIPS32_FRONTEND_V1_TESTS=PASS tests=7")


if __name__ == "__main__":
    main()
