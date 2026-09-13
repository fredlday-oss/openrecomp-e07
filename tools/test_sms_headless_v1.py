#!/usr/bin/env python3
"""P1-23 gate: Master System deterministic headless proof.

Runs one synthetic SMS ROM twice:
- through the machine-backed Z80 reference oracle
  (`tools/sms_headless_v1.SmsReferenceZ80` over the P1-22 `SmsMachine`);
- through the P1-21 Z80 frontend -> normalized IR V1 -> Module Image V1 ->
  the architecture-neutral Core API `ReferenceExecutor`.

Requires identical final CPU state (register file, shadow set, IX/IY/SP,
IFF/IM/halted), identical system RAM, identical control-register mirrors
($fffc-$ffff write-through), an untouched ROM window and an identical flat
port segment (the machine's `port_trace`). The platform port protocol
results (VDP VRAM/register/status, PSG latches, mapper state) are pinned
separately on the reference side with the same guest code.

Also pins: guest-code driven slot-2 paging on a two-bank ROM, a guest-code
VDP status read (documented read-and-reset), fail-closed ROM writes, and
deterministic reference/frontend outputs. Synthetic inputs only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from sms_headless_v1 import (  # noqa: E402
    DATA_RANGE,
    PAGING_PROGRAM,
    PROGRAM_END,
    ROM_PROGRAM,
    STATUS_PROGRAM,
    SmsReferenceZ80,
    build_rom,
    run_core,
    run_reference,
)
from sms_platform_v1 import SMSPlatformError, SmsMachine  # noqa: E402
from z80_frontend_v1 import PORT_BASE, convert  # noqa: E402
from z80_reference_v1 import MEMORY_SIZE, Z80State  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"

CPU_KEYS = ("a", "f", "b", "c", "d", "e", "h", "l", "a2", "f2", "b2", "c2", "d2", "e2", "h2", "l2", "ix", "iy", "sp")
PLATFORM_KEYS = ("iff1", "iff2", "im", "halted")


def base_meta() -> dict:
    return {
        "architecture": "z80-sms",
        "entry_address": 0x0000,
        "region_start": 0x0000,
        "region_end": DATA_RANGE[1],
        "data_ranges": [list(DATA_RANGE)],
        "initial_state": {"cpu:a": 0, "cpu:f": 0, "cpu:sp": 0xDFF0},
        "observe_state_slot": "cpu:a",
        "max_operations": 1000000,
    }


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()

    # 1. Differential proof: reference == Core API -----------------------------
    rom = build_rom(1)
    machine, _ref, final = run_reference(rom)
    execution, core_memory, ir, sidecar = run_core(rom, base_meta(), contract, contract_bytes)
    for key in CPU_KEYS:
        expected = final[key]
        actual = execution.state[f"cpu:{key}"]
        if actual != expected:
            raise AssertionError(f"cpu:{key} = {actual:#x} != reference {expected:#x}")
    for key in PLATFORM_KEYS:
        expected = final[key]
        actual = execution.state[f"platform:{key}"]
        if actual != expected:
            raise AssertionError(f"platform:{key} = {actual} != reference {expected}")
    if bytes(machine.ram[0:0x1FFC]) != core_memory[0xC000:0xDFFC]:
        raise AssertionError("system RAM differs between reference and Core API")
    if bytes(machine.ram[0x1FFC:0x2000]) != core_memory[0xFFFC:0x10000]:
        raise AssertionError("control-register write-through mirror differs")
    if rom != core_memory[0:len(rom)]:
        raise AssertionError("ROM window was modified by the Core API path")
    if bytes(machine.port_trace) != core_memory[PORT_BASE:PORT_BASE + 256]:
        raise AssertionError("flat port segment differs from the machine port trace")
    print(
        "PASS differential-proof reference == Core API "
        f"(a={final['a']:#x} f={final['f']:#x} hl={final['h']:#x}{final['l']:02x} "
        f"sp={final['sp']:#x} b={final['b']:#x} im={final['im']} halted={final['halted']})"
    )
    tests += 1

    # 2. Platform protocol results (same guest code, reference side) ------------
    assert machine.vdp.vram[0:4] == bytes([0x11, 0x22, 0x33, 0x44])
    assert machine.vdp.address == 0x0004 and machine.vdp.code == 0x01
    assert machine.vdp.registers[1] == 0xE4
    assert machine.psg.registers[0] == 0x0F
    assert machine.mapper.fffc == 0x00 and machine.mapper.slot == [0, 1, 2]
    assert machine.ram[0] == 0x5A and machine.read_memory(0xE000) == 0x5A
    print("PASS platform-protocol pins (VDP VRAM/register, PSG, mapper, RAM mirror)")
    tests += 1

    # 3. Guest-code slot-2 paging on a two-bank ROM ----------------------------
    paging_rom = build_rom(2, PAGING_PROGRAM, marker=0xE7)
    paging_machine, _paging_ref, paging_final = run_reference(paging_rom)
    assert paging_final["a"] == 0x01 and paging_final["f"] == 0x42 and paging_final["halted"] == 1
    assert paging_machine.mapper.slot[2] == 1
    assert paging_machine.ram[0x1FFF] == 0x01  # write-through mirror (0xFFFF -> 0x1FFF)
    print("PASS guest-code slot-2 paging (bank 1 marker read through the mapper)")
    tests += 1

    # 4. Guest-code VDP status read (documented read-and-reset) ----------------
    status_machine = SmsMachine(build_rom(1, STATUS_PROGRAM))
    status_machine.vdp.set_status(vblank=True)
    status_ref = SmsReferenceZ80(status_machine, Z80State(pc=0x0000, sp=0xDFF0))
    status_final = status_ref.run()
    assert status_final["a"] == 0x80  # VBlank flag
    assert status_machine.vdp.status_flags == 0  # documented: reset on read
    assert status_machine.vdp.second_pending is False
    print("PASS guest-code VDP status read (flag returned, flags reset, latch cleared)")
    tests += 1

    # 5. Fail-closed: guest ROM write ------------------------------------------
    try:
        run_reference(build_rom(1, bytes([0x3E, 0x01, 0x32, 0x00, 0x80, 0x76])))
    except SMSPlatformError:
        print("PASS reject: guest-ROM-write-protected")
        tests += 1
    else:
        raise AssertionError("guest ROM write was accepted")

    # 6. Determinism -----------------------------------------------------------
    _machine_a, _ref_a, final_a = run_reference(rom)
    _machine_b, _ref_b, final_b = run_reference(rom)
    if final_a != final_b:
        raise AssertionError("reference run is not deterministic")
    execution_a, _mem_a, ir_a, sidecar_a = run_core(rom, base_meta(), contract, contract_bytes)
    execution_b, _mem_b, ir_b, sidecar_b = run_core(rom, base_meta(), contract, contract_bytes)
    if serialize(ir_a) != serialize(ir_b) or serialize(sidecar_a) != serialize(sidecar_b):
        raise AssertionError("frontend output is not deterministic")
    if execution_a.state != execution_b.state:
        raise AssertionError("Core API execution is not deterministic")
    print(f"PASS determinism (reference + frontend + Core API; ir sha256={hashlib.sha256(serialize(ir_a).encode('utf-8')).hexdigest()[:16]}...)")
    tests += 1

    print(f"OPENRECOMP_SMS_HEADLESS_V1=PASS tests={tests}")
    return 0


def serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
