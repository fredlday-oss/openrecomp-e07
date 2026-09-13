#!/usr/bin/env python3
"""P1-15 gate: Game Boy deterministic headless proof.

Proves the full documented platform chain deterministically with synthetic,
original inputs only (no commercial ROM bytes anywhere):

1. ROM ingestion (`tools/gb_rom_loader_v1.py`, P1-14) and entry-stub region
   extraction (`tools/gb_platform_v1.py`);
2. differential proof: the mapped 64 KiB memory image runs through the
   independent P1-12 reference interpreter AND through the P1-13 frontend ->
   normalized IR V1 -> Module Image V1 -> Core API `ReferenceExecutor`, with
   identical final CPU state, `platform:halted` and full 64 KiB memory;
3. the documented platform memory surface (WRAM echo, HRAM/OAM, ROM-write
   no-op, fail-closed cartridge RAM / unusable region / unmodelled I/O);
4. the documented timer contract (DIV 16384 Hz + write reset; TAC rates and
   enable; TIMA overflow -> TMA reload + IF bit 2);
5. the documented joypad contract (select bits, pressed-as-0, low nibble
   read-only, neither-selected reads 0xF);
6. the documented interrupt contract, driven step-by-step by the platform
   driver with the reference oracle: EI one-instruction delay (pinned via the
   pushed PC), priority order (bit 0 first), IF acknowledgement, IME=0 during
   servicing, RETI re-enabling, post-RETI dispatch, and HALT wake with IME=0
   (resume, no servicing) and with IME=1 (serviced before the next
   instruction);
7. fail-closed handling: tampered header checksum, unsupported mapper, the
   documented halt bug, and malformed frontend data_ranges;
8. secondary local-ROM metadata evidence (ROM_INVENTORY.json): header fields,
   classifier output and SHA-256 only - never ROM bytes.

Documented facts follow the gbdev.io Pan Docs pages for Interrupts, HALT,
Timer/Divider Registers and Joypad Input.
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

from gb_rom_loader_v1 import GBROMError, classify, compute_header_checksum, make_mapper  # noqa: E402
from gb_platform_v1 import (  # noqa: E402
    GBPlatform,
    GBPlatformError,
    PlatformBoundSM83,
    extract_entry_meta,
    map_rom_romonly,
    run_headless,
)
from openrecomp import CallbackHostBinding, ModuleImage, ReferenceExecutor  # noqa: E402
from sm83_frontend_v1 import SM83FrontendError, convert  # noqa: E402
from sm83_reference_v1 import SM83State, ReferenceSM83  # noqa: E402

CONTRACT_PATH = ROOT / "contracts" / "host_contract.json"
MEMORY_SIZE = 1 << 16


def build_boot_rom(*, program: bytes = b"", isr40: bytes = b"", isr48: bytes = b"", isr50: bytes = b"",
                   cartridge_type: int = 0x00, cgb_flag: int = 0x00) -> bytes:
    """Synthetic original ROM-only boot image: documented header stub
    (`nop; jp $0150` at 0x0100), valid header checksum, no Nintendo logo."""
    data = bytearray(0x8000)
    data[0x0100:0x0104] = b"\x00\xC3\x50\x01"
    data[0x0134:0x0143] = b"OPENRECOMP".ljust(15, b"\x00")
    data[0x0143] = cgb_flag
    data[0x0146] = 0x00
    data[0x0147] = cartridge_type
    data[0x0148] = 0x00
    data[0x0149] = 0x00
    data[0x014A] = 0x00
    data[0x014B] = 0x33
    data[0x014C] = 0x00
    data[0x014D] = compute_header_checksum(bytes(data))
    data[0x014E:0x0150] = b"\x00\x00"
    if isr40:
        data[0x0040:0x0040 + len(isr40)] = isr40
    if isr48:
        data[0x0048:0x0048 + len(isr48)] = isr48
    if isr50:
        data[0x0050:0x0050 + len(isr50)] = isr50
    if program:
        data[0x0150:0x0150 + len(program)] = program
    return bytes(data)


# Differential program (HALT-terminated; exercised surfaces: ALU/flags,
# CB page, DAA, memory forms, 16-bit arithmetic, stack, call/ret,
# conditional and unconditional relative jumps). The subroutine sits at
# 0x0190 (padding NOPs at 0x0188..0x018F keep the CALL target exact).
DIFF_PROGRAM = bytes([
    0x3E, 0x2A, 0x06, 0x0F, 0x80, 0xE6, 0x0F, 0x0E, 0x05, 0x81,
    0x05, 0x04, 0x07, 0xCB, 0x11, 0x27,
    0x21, 0x00, 0xC0, 0x36, 0x5A, 0x2A, 0x2C, 0x34,
    0x01, 0x34, 0x12, 0x03, 0x0B, 0x19,
    0x31, 0x00, 0xFF, 0xE8, 0x10, 0xF8, 0xFC, 0xF9,
    0xCD, 0x90, 0x01, 0xC5, 0xE1,
    0x3E, 0x07, 0x00, 0x00, 0xFE, 0x07, 0x28, 0x02,
    0x3E, 0x99, 0x18, 0x00, 0x76,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # 0x0188..0x018F
    0x3E, 0x55, 0x04, 0xC9,  # 0x0190: LD A, 0x55; INC B; RET
])


def serialize(document: object) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def core_result(image: bytes, meta: dict, contract: dict, contract_bytes: bytes):
    ir, sidecar, report = convert(image, meta, contract)
    ir_bytes = serialize(ir).encode("utf-8")
    segments = []
    for segment in sorted(sidecar["memory_segments"], key=lambda item: (item["guest_address"], item["name"])):
        data = bytes.fromhex(segment["data_hex"])
        segments.append(
            {
                "name": segment["name"],
                "guest_address": segment["guest_address"],
                "data_hex": data.hex(),
                "data_sha256": digest(data),
            }
        )
    manifest = {
        "module_format_version": "1.0.0",
        "module_id": ir["module_id"],
        "ir": {
            "version": ir["ir_version"],
            "sha256": digest(ir_bytes),
            "source_input_sha256": ir["source"]["input_sha256"],
        },
        "host_contract": {
            "version": contract["contract_version"],
            "sha256": digest(contract_bytes),
        },
        "memory": {"size_bytes": sidecar["memory_size_bytes"], "segments": segments},
        "initial_state": [
            {"slot": slot, "value": value} for slot, value in sorted(sidecar["initial_state"].items())
        ],
        "entry": {
            "function": ir["entry_function"],
            "observe_state_slot": sidecar["entry_state_slot"],
        },
        "limits": {"max_operations": sidecar["max_operations"], "max_call_depth": 1024},
        "provenance": {
            "producer": "openrecomp.sm83-frontend-v1",
            "source_input_sha256": ir["source"]["input_sha256"],
        },
    }
    module = ModuleImage.from_documents(
        manifest,
        ir,
        contract,
        ir_sha256=digest(ir_bytes),
        contract_sha256=digest(contract_bytes),
    )
    executor = ReferenceExecutor(module, CallbackHostBinding(contract["contract_version"], {}))
    execution = executor.run()
    return execution, bytes(executor.memory.data), ir, sidecar, report


def expect_platform_fail(label: str, action) -> None:
    try:
        action()
    except (GBPlatformError, GBROMError, SM83FrontendError):
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"{label}: accepted")


def main() -> int:
    tests = 0
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    contract_bytes = CONTRACT_PATH.read_bytes()

    # 1. Ingestion + mapping ---------------------------------------------
    rom = build_boot_rom(program=DIFF_PROGRAM)
    info = classify(rom)
    assert info.mapper == "none" and info.cgb_mode == "dmg" and info.rom_bytes == 0x8000
    mapper = make_mapper(rom)
    image = map_rom_romonly(rom)
    assert bytes(image[0x0000:0x8000]) == rom
    print("PASS ingestion rom-only/dmg + documented 32 KiB mapping")
    tests += 1

    # 2. Entry-stub region extraction ------------------------------------
    meta = extract_entry_meta(rom)
    assert meta["entry_address"] == 0x0100
    assert meta["region_start"] == 0x0100 and meta["region_end"] == 0x8000
    assert meta["data_ranges"] == [[0x0104, 0x0150]]
    bad_stub = bytearray(rom)
    bad_stub[0x0101] = 0x18  # jr instead of jp -> not the documented stub
    expect_platform_fail("entry-stub-not-documented", lambda: extract_entry_meta(bytes(bad_stub)))
    expect_platform_fail("entry-stub-short-rom", lambda: extract_entry_meta(rom[:0x7FFF]))
    print("PASS entry-stub region extraction (data span 0x0104..0x014F)")
    tests += 1

    # 3. Differential proof: reference == Core API -----------------------
    ref = ReferenceSM83(image, SM83State())
    ref_state = ref.run(max_steps=100000)
    execution, core_memory, ir, sidecar, report = core_result(bytes(image), meta, contract, contract_bytes)
    for key in ("a", "f", "b", "c", "d", "e", "h", "l", "sp"):
        expected = ref_state[key]
        actual = execution.state[f"cpu:{key}"]
        if actual != expected:
            raise AssertionError(f"cpu:{key} = {actual:#x} != reference {expected:#x}")
    if ref_state["halted"] != int(execution.state["platform:halted"]):
        raise AssertionError("halted state differs from the reference")
    ref_memory = bytes(ref.memory)
    core_guest_memory = core_memory[:MEMORY_SIZE]
    if ref_memory != core_guest_memory:
        for index, (left, right) in enumerate(zip(ref_memory, core_guest_memory)):
            if left != right:
                raise AssertionError(f"guest memory differs at 0x{index:04x}: {left:#x} != {right:#x}")
        raise AssertionError("guest memory length differs")
    pinned = {
        "a": 0x07, "f": 0xC0, "b": 0x13, "c": 0x34, "h": 0x13, "l": 0x34,
        "sp": 0xFF0C, "halted": 1, "mem_c000": 0x5A, "mem_c002": 0x01,
    }
    for name, expected in pinned.items():
        if name == "halted":
            actual = int(execution.state["platform:halted"])
        elif name.startswith("mem_"):
            actual = core_guest_memory[int(name.split("_")[1], 16)]
        elif name == "sp":
            actual = execution.state["cpu:sp"]
        else:
            actual = execution.state[f"cpu:{name}"]
        if actual != expected:
            raise AssertionError(f"pinned {name}: {actual:#x} != {expected:#x}")
    print(
        "PASS differential-proof ROM->map->frontend->IR->Core API == reference "
        f"(a={ref_state['a']:#x} f={ref_state['f']:#x} hl={ref_state['h']:#x}{ref_state['l']:02x} "
        f"sp={ref_state['sp']:#x} halted={ref_state['halted']} operations={execution.operations} "
        f"blocks={report['blocks']})"
    )
    tests += 1

    ir_again, sidecar_again, report_again = convert(bytes(image), meta, contract)
    if serialize(ir) != serialize(ir_again) or serialize(sidecar) != serialize(sidecar_again):
        raise AssertionError("frontend output is not deterministic with data_ranges")
    print("PASS frontend-determinism with declared data spans")
    tests += 1

    # 4. Platform memory surface ------------------------------------------
    platform = GBPlatform(map_rom_romonly(rom), make_mapper(rom))
    assert platform.read8(0x0150) == 0x3E and platform.read8(0x7FFF) == 0x00
    platform.write8(0x0100, 0xAA)  # documented: ROM writes have no effect (ROM-only)
    assert platform.read8(0x0100) == 0x00
    platform.write8(0xC100, 0x5A)  # WRAM echo, both directions
    assert platform.read8(0xE100) == 0x5A
    platform.write8(0xE101, 0x77)
    assert platform.read8(0xC101) == 0x77
    platform.write8(0xFF80, 0x33)  # HRAM
    assert platform.read8(0xFF80) == 0x33
    platform.write8(0xFE00, 0x44)  # OAM
    assert platform.read8(0xFE00) == 0x44
    expect_platform_fail("cart-ram-read-no-mapper", lambda: platform.read8(0xA000))
    expect_platform_fail("cart-ram-write-no-mapper", lambda: platform.write8(0xA000, 1))
    expect_platform_fail("unusable-region-read", lambda: platform.read8(0xFEA0))
    expect_platform_fail("unmodelled-io-read", lambda: platform.read8(0xFF40))
    expect_platform_fail("unmodelled-io-write", lambda: platform.write8(0xFF40, 0))
    print("PASS platform memory surface (echo/HRAM/OAM/ROM-noop/fail-closed)")
    tests += 1

    # 5. Timer contract ---------------------------------------------------
    timer = GBPlatform(map_rom_romonly(rom), make_mapper(rom))
    timer.step_timer(256)
    assert timer.div == 1  # DIV at 16384 Hz (1 increment per 256 T-cycles)
    timer.write8(0xFF04, 0xFF)  # documented: any DIV write resets it
    assert timer.div == 0 and timer.read8(0xFF04) == 0
    timer.write8(0xFF07, 0x04)  # enable, select 00 (1024 T/increment)
    timer.step_timer(1024)
    assert timer.tima == 1
    timer.write8(0xFF07, 0x00)  # disabled: TIMA must not count
    timer.step_timer(10000)
    assert timer.tima == 1
    timer.write8(0xFF05, 0xFE)
    timer.write8(0xFF06, 0x5A)
    timer.write8(0xFF07, 0x05)  # enable, select 01 (16 T/increment)
    timer.step_timer(16)
    assert timer.tima == 0xFF
    timer.step_timer(16)  # overflow: TIMA = TMA and IF bit 2 requested
    assert timer.tima == 0x5A and timer.if_flags == 0x04 and timer.read8(0xFF0F) == 0xE4
    timer.write8(0xFF07, 0xF8)  # documented: TAC writes mask 0x07
    assert timer.tac == 0x00 and timer.read8(0xFF07) == 0xF8
    print("PASS timer contract (DIV/TIMA/TMA/TAC + overflow interrupt request)")
    tests += 1

    # 6. Joypad contract ---------------------------------------------------
    joy = GBPlatform(map_rom_romonly(rom), make_mapper(rom))
    assert joy.read8(0xFF00) == 0xFF  # neither group selected: low nibble reads 0xF
    joy.write8(0xFF00, 0x20)  # bit 5: buttons deselected -> d-pad selected
    joy.joypad.d_pad = 0x0B  # Right + Down pressed (bits 0 and 3 are 0)
    assert joy.read8(0xFF00) == 0xEB
    joy.write8(0xFF00, 0x10)  # bit 4: d-pad deselected -> buttons selected
    joy.joypad.buttons = 0x0E  # A pressed (bit 0 is 0)
    assert joy.read8(0xFF00) == 0xDE
    joy.write8(0xFF00, 0x00)  # both groups selected
    assert joy.read8(0xFF00) == 0xCA  # 0x0E & 0x0B = 0x0A
    joy.write8(0xFF00, 0x3F)  # low nibble writes are ignored (documented read-only)
    assert joy.read8(0xFF00) == 0xFF
    print("PASS joypad contract (select bits/pressed-as-0/read-only low nibble)")
    tests += 1

    # 7. Interrupt contract: EI delay --------------------------------------
    ei_program = bytes([
        0xF3,                       # DI
        0x31, 0xFE, 0xFF,           # LD SP, 0xFFFE
        0x3E, 0x01,
        0xEA, 0x0F, 0xFF,           # LD (0xFF0F), A  -> IF = 0x01
        0x3E, 0x01,
        0xEA, 0xFF, 0xFF,           # LD (0xFFFF), A  -> IE = 0x01
        0xFB,                       # EI
        0x00,                       # NOP (IME becomes 1 here)
        0x3E, 0x0F,                 # LD A, 0x0F (after RETI)
        0x76,                       # HALT
    ])
    ei_isr = bytes([
        0x3E, 0x5A,                 # LD A, 0x5A
        0x21, 0x00, 0xC8,           # LD HL, 0xC800
        0x36, 0x42,                 # LD (HL), 0x42
        0xD9,                       # RETI
    ])
    ei_rom = build_boot_rom(program=ei_program, isr40=ei_isr)
    ei_platform = GBPlatform(map_rom_romonly(ei_rom))
    ei_cpu = PlatformBoundSM83(ei_platform, SM83State(pc=0x0150))
    ei_final = run_headless(ei_cpu, ei_platform)
    assert ei_platform.memory[0xC800] == 0x42  # ISR ran
    assert ei_platform.memory[0xFFFC] == 0x60 and ei_platform.memory[0xFFFD] == 0x01
    # ^ pushed PC = 0x0160: the interrupt was serviced only after the NOP
    #   following EI (the documented one-instruction EI delay; an immediate
    #   EI would have pushed 0x015F).
    assert ei_final["a"] == 0x0F and ei_final["sp"] == 0xFFFE
    assert ei_final["ime"] == 1 and ei_final["halted"] == 1
    assert ei_platform.if_flags == 0x00  # IF bit acknowledged
    print("PASS interrupt contract EI-delay + dispatch + RETI (pinned pushed PC)")
    tests += 1

    # 8. Interrupt contract: priority + post-RETI dispatch ------------------
    prio_program = bytes([
        0xF3,                       # DI
        0x31, 0xFE, 0xFF,           # LD SP, 0xFFFE
        0x3E, 0x03,
        0xEA, 0x0F, 0xFF,           # IF = 0x03
        0x3E, 0x03,
        0xEA, 0xFF, 0xFF,           # IE = 0x03
        0xFB,                       # EI
        0x00,                       # NOP -> dispatch bit 0 first
        0x3E, 0x99,                 # LD A, 0x99
        0x76,                       # HALT
    ])
    prio_isr40 = bytes([
        0x3E, 0x11, 0x21, 0x00, 0xC8, 0x36, 0x11, 0xD9,  # writes 0x11 to 0xC800
    ])
    prio_isr48 = bytes([
        0x3E, 0x22, 0x21, 0x00, 0xC8, 0x36, 0x22, 0xD9,  # writes 0x22 to 0xC800
    ])
    prio_rom = build_boot_rom(program=prio_program, isr40=prio_isr40, isr48=prio_isr48)
    prio_platform = GBPlatform(map_rom_romonly(prio_rom))
    prio_cpu = PlatformBoundSM83(prio_platform, SM83State(pc=0x0150))
    prio_final = run_headless(prio_cpu, prio_platform)
    # 0x22 (bit 1 handler) wins -> bit 0 was serviced first (documented priority).
    assert prio_platform.memory[0xC800] == 0x22
    assert prio_final["a"] == 0x99 and prio_final["sp"] == 0xFFFE
    assert prio_final["ime"] == 1 and prio_final["halted"] == 1
    assert prio_platform.if_flags == 0x00  # both bits acknowledged
    print("PASS interrupt priority (bit 0 first) + dispatch after RETI")
    tests += 1

    # 9. HALT wake with IME=0 (resume, no servicing) -------------------------
    wake0_program = bytes([
        0xF3,                       # DI
        0x3E, 0x04,
        0xEA, 0xFF, 0xFF,           # IE = 0x04
        0x3E, 0xFE,
        0xEA, 0x05, 0xFF,           # TIMA = 0xFE
        0x3E, 0x04,
        0xEA, 0x07, 0xFF,           # TAC = 0x04 (enabled, 1024 T)
        0x76,                       # HALT (clean: IF = 0)
        0xF0, 0x0F,                 # LDH A, (0xFF0F) -> 0xE4 (IF not cleared by the wake)
        0xEA, 0x00, 0xC9,           # LD (0xC900), A
        0xAF,                       # XOR A
        0xEA, 0x0F, 0xFF,           # IF = 0
        0xEA, 0x07, 0xFF,           # TAC = 0
        0x3E, 0x2B,                 # LD A, 0x2B
        0x76,                       # HALT (stays halted)
    ])
    wake0_rom = build_boot_rom(program=wake0_program)
    wake0_platform = GBPlatform(map_rom_romonly(wake0_rom))
    wake0_cpu = PlatformBoundSM83(wake0_platform, SM83State(pc=0x0150))
    wake0_ticks = {"remaining": 10}

    def wake0_tick() -> bool:
        if wake0_ticks["remaining"] <= 0:
            return False
        wake0_ticks["remaining"] -= 1
        wake0_platform.step_timer(1024)
        return True

    wake0_final = run_headless(wake0_cpu, wake0_platform, tick=wake0_tick)
    assert wake0_platform.memory[0xC900] == 0xE4  # IF survived the IME=0 wake
    assert wake0_final["a"] == 0x2B and wake0_final["halted"] == 1 and wake0_final["ime"] == 0
    assert wake0_platform.if_flags == 0x00
    print("PASS halt-wake with IME=0 (resume without servicing; documented (IE & IF) trigger)")
    tests += 1

    # 10. HALT wake with IME=1 (handler called before the next instruction) ---
    wake1_program = bytes([
        0xFB,                       # EI
        0x00,                       # NOP (IME = 1)
        0x3E, 0x04,
        0xEA, 0xFF, 0xFF,           # IE = 0x04
        0x3E, 0x04,
        0xEA, 0x07, 0xFF,           # TAC = 0x04
        0x76,                       # HALT (clean: IF = 0)
        0x3E, 0x77,                 # LD A, 0x77 (after the handler returns)
        0x76,                       # HALT
    ])
    wake1_isr = bytes([
        0x3E, 0x55,                 # LD A, 0x55
        0x21, 0x00, 0xC8,
        0x36, 0x55,                 # LD (0xC800), 0x55
        0xAF,                       # XOR A
        0xEA, 0x07, 0xFF,           # TAC = 0
        0xD9,                       # RETI
    ])
    wake1_rom = build_boot_rom(program=wake1_program, isr50=wake1_isr)  # timer interrupt -> vector 0x0050
    wake1_platform = GBPlatform(map_rom_romonly(wake1_rom))
    wake1_cpu = PlatformBoundSM83(wake1_platform, SM83State(pc=0x0150))
    wake1_ticks = {"remaining": 300}

    def wake1_tick() -> bool:
        if wake1_ticks["remaining"] <= 0:
            return False
        wake1_ticks["remaining"] -= 1
        wake1_platform.step_timer(1024)
        return True

    wake1_final = run_headless(wake1_cpu, wake1_platform, tick=wake1_tick)
    assert wake1_platform.memory[0xC800] == 0x55  # handler ran
    # Handler was called before the instruction after HALT: the pushed PC is
    # exactly that instruction's address.
    assert wake1_platform.memory[0xFFFC] == 0x5D and wake1_platform.memory[0xFFFD] == 0x01
    assert wake1_final["a"] == 0x77 and wake1_final["halted"] == 1 and wake1_final["ime"] == 1
    print("PASS halt-wake with IME=1 (handler called before the next instruction)")
    tests += 1

    # 11. Fail-closed: documented halt bug -----------------------------------
    bug_program = bytes([
        0xF3,                       # DI
        0x3E, 0x01,
        0xEA, 0x0F, 0xFF,           # IF = 0x01
        0x3E, 0x01,
        0xEA, 0xFF, 0xFF,           # IE = 0x01
        0x76,                       # HALT with IME=0 and interrupt pending -> halt bug
    ])
    bug_rom = build_boot_rom(program=bug_program)
    bug_platform = GBPlatform(map_rom_romonly(bug_rom))
    bug_cpu = PlatformBoundSM83(bug_platform, SM83State(pc=0x0150))
    expect_platform_fail("halt-bug-unsupported", lambda: run_headless(bug_cpu, bug_platform))
    tests += 1

    # 12. Fail-closed: ingestion and frontend data_ranges --------------------
    tampered = bytearray(rom)
    tampered[0x014D] ^= 0xFF
    expect_platform_fail("tampered-header-checksum", lambda: classify(bytes(tampered)))
    expect_platform_fail("unsupported-mapper", lambda: make_mapper(build_boot_rom(cartridge_type=0x19)))

    bad_meta = dict(meta)
    bad_meta["data_ranges"] = [[0x0104, 0x0160], [0x0150, 0x0180]]  # overlapping
    expect_platform_fail("data-ranges-overlap", lambda: convert(bytes(image), bad_meta, contract))
    bad_meta = dict(meta)
    bad_meta["data_ranges"] = [[0x0104, 0x9000]]  # outside the region
    expect_platform_fail("data-range-outside-region", lambda: convert(bytes(image), bad_meta, contract))
    bad_meta = dict(meta)
    bad_meta["data_ranges"] = [[0x0100, 0x0150]]  # region start inside the range
    expect_platform_fail("region-start-inside-data-range", lambda: convert(bytes(image), bad_meta, contract))
    bad_meta = dict(meta)
    bad_meta["data_ranges"] = [[0x0140, 0x0160]]  # jp target 0x0150 inside the range
    expect_platform_fail("control-flow-target-inside-data-range", lambda: convert(bytes(image), bad_meta, contract))
    tests += 1

    # 13. Secondary local-ROM metadata evidence (never ROM bytes) ------------
    inventory_path = ROOT / ".openrecomp-phase1" / "ROM_INVENTORY.json"
    if inventory_path.exists():
        inventory = json.loads(inventory_path.read_text(encoding="utf-8-sig"))
        entry = inventory["platforms"]["gameboy"][0]
        rom_path = Path(entry["full_path"])
        if rom_path.exists():
            rom_bytes = rom_path.read_bytes()
            assert digest(rom_bytes) == entry["sha256"], "local ROM hash drifted from ROM_INVENTORY.json"
            assert len(rom_bytes) == entry["bytes"]
            local = classify(rom_bytes)
            print(
                f"LOCAL_GB_ROM metadata-only sha256={digest(rom_bytes)} bytes={len(rom_bytes)} "
                f"title={local_header_title(rom_bytes)} mapper={local.mapper} cgb_mode={local.cgb_mode} "
                f"rom_banks={local.rom_banks} ram_banks={local.ram_banks} header_checksum_valid=1"
            )
        else:
            print(f"LOCAL_GB_ROM SKIPPED (file absent: {entry['full_path']})")
    else:
        print("LOCAL_GB_ROM SKIPPED (no ROM_INVENTORY.json)")
    tests += 1

    print(f"OPENRECOMP_GB_HEADLESS_V1=PASS tests={tests}")
    return 0


def local_header_title(rom_bytes: bytes) -> str:
    title = bytes(rom_bytes[0x0134:0x0143]).rstrip(b"\x00")
    return title.decode("ascii", "replace")


if __name__ == "__main__":
    raise SystemExit(main())
