#!/usr/bin/env python3
"""OpenRecomp Phase-5 APU/input/timing/interrupt boundary gate (P5-07).

Verifies the bounded deterministic platform scheduler:

* the documented base instruction-cost table covers every official opcode;
* virtual frame/vblank scheduling at the documented NTSC nominal constants;
* per-frame controller input plan application and transcript;
* NMI queueing on PPUCTRL bit 7 and driver-side delivery;
* the asserted-line IRQ interface with explicit acknowledgment;
* APU register-latch consistency with the frozen independent platform;
* fail-closed unknown opcodes, empty/invalid input plans and invalid timing.

On success it emits::

    OPENRECOMP_P5_07=PASS
    OPENRECOMP_PHASE5_TIMING_INPUT_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
import p5_bus_v1 as bus_module  # noqa: E402
import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402
import p5_platform_v1 as platform_module  # noqa: E402
import p5_ppu_v1 as ppu_module  # noqa: E402
from nes_platform_v1 import NesMachine  # noqa: E402

STAGE = "P5-07"
STAGE_MARKER = "OPENRECOMP_P5_07"
FEATURE_MARKER = "OPENRECOMP_PHASE5_TIMING_INPUT_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

COST_TABLE_SHA256 = "57447c2cbd02303f589a25940272d6f225a00acf1131174fcc98a610dca53daf"
EXPECTED_COSTS = {
    0x00: 7,   # brk
    0x20: 6,   # jsr
    0x60: 6,   # rts
    0x40: 6,   # rti
    0x4C: 3,   # jmp abs
    0x6C: 5,   # jmp ind
    0xD0: 2,   # bne
    0x48: 3,   # pha
    0xA9: 2,   # lda imm
    0xAD: 4,   # lda abs
    0xBD: 4,   # lda absx
    0x9D: 5,   # sta absx
    0xFE: 7,   # inc absx
    0xB1: 6,   # lda indy
    0x81: 6,   # sta indx
    0x26: 5,   # rol zp
}

REGRESSIONS = (
    ("tools/test_nes_platform_v1.py", []),
    ("tools/test_phase4_deterministic_io_v1.py",
     ["--evidence-dir", ".openrecomp-phase5/scratch/regression_p5_07_p4_04"]),
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
EVIDENCE_WRITES: dict[str, bytes] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def expect_fail(label: str, thunk, error_types) -> None:
    try:
        thunk()
    except error_types:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"reject:{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"reject:{label}: accepted")


def run_regression(script: str, extra: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra],
        cwd=str(ROOT), capture_output=True)
    return {
        "script": script,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
    }


def build_platform(rom: bytes, inventory: dict, plan) -> platform_module.P5Platform:
    chr_rom = rom[16 + 0x4000:16 + 0x4000 + 0x2000]
    ppu = ppu_module.P5Ppu(inventory["mirroring"], chr_rom=chr_rom)
    bus = bus_module.P5NesBus(
        bus_module.P5Cartridge(rom, inventory), ppu,
        bus_module.P5ControllerPorts())
    return platform_module.P5Platform(bus, input_plan=plan)


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-07 timing/input gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-07")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-07 APU/Input/Timing/Interrupt Boundary Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("costs")
        cost_table = platform_module.INSTRUCTION_COST
        check("costs:coverage", len(cost_table) == len(nes_adapter.OPCODES))
        check("costs:values",
              all(cost_table[opcode] == expected
                  for opcode, expected in EXPECTED_COSTS.items()))
        check("costs:range", all(1 <= cost <= 8 for cost in cost_table.values()))
        timing = platform_module.timing_document()
        check("costs:table-sha256",
              timing["cost_table_sha256"] == COST_TABLE_SHA256)
        check("costs:timing-document",
              timing["cycle_accuracy"] is False
              and timing["page_cross_penalty"] == "not modelled"
              and timing["taken_branch_penalty"] == "not modelled")

        banner("fixtures")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()
        plan = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80)

        banner("scheduling")
        platform = build_platform(rom, inventory, plan)
        platform.bus.ppu.cpu_write(0, 0x80)  # NMI enable
        nop = 0xEA
        instructions = 300000
        for _ in range(instructions):
            platform.begin_instruction(nop)
        units = platform.clock
        check("schedule:clock",
              units == instructions * 2)
        expected_frames = units // platform_module.FRAME_CLOCK_UNITS + 1
        check("schedule:frame-count", platform.frame_index == expected_frames)
        check("schedule:frame-boundaries",
              all(item["clock"] == index * platform_module.FRAME_CLOCK_UNITS
                  for index, item in enumerate(platform.frames)))
        check("schedule:input-plan",
              [item["input"] for item in platform.frames]
              == [plan[min(index, len(plan) - 1)] for index in range(expected_frames)])
        check("schedule:nmi-queued", platform.pending_nmi == expected_frames
              and all(item["nmi_queued"] for item in platform.frames))
        check("schedule:vblank-ends",
              sum(1 for item in platform.events
                  if item["kind"] == "vblank_end") == expected_frames)
        first_vblank_end = next(item for item in platform.events
                                if item["kind"] == "vblank_end")
        check("schedule:vblank-window",
              first_vblank_end["clock"] == platform_module.VBLANK_CLOCK_UNITS)
        delivered = sum(1 for _ in range(expected_frames) if platform.take_nmi())
        check("schedule:nmi-delivered", delivered == expected_frames
              and platform.pending_nmi == 0)

        banner("vblank_and_interrupts")
        platform2 = build_platform(rom, inventory, plan)
        platform2.begin_instruction(nop)
        check("vblank:set-at-frame-start", platform2.bus.ppu.vblank() is True)
        platform2.bus.ppu.cpu_read(2)
        check("vblank:cleared-by-status-read", platform2.bus.ppu.vblank() is False)
        for _ in range(platform_module.VBLANK_CLOCK_UNITS // 2 + 2):
            platform2.begin_instruction(nop)
        check("vblank:remains-clear", platform2.bus.ppu.vblank() is False)
        check("irq:assert", (platform2.set_irq_line(True) or True)
              and platform2.irq_pending is True)
        check("irq:take", platform2.take_irq() is True
              and platform2.irq_pending is False)
        platform2.set_irq_line(True)
        platform2.set_irq_line(False)
        check("irq:deassert-clears", platform2.irq_pending is False)

        platform3 = build_platform(rom, inventory, plan)
        for _ in range(platform_module.FRAME_CLOCK_UNITS + 4):
            platform3.begin_instruction(nop)
        expected3 = platform3.clock // platform_module.FRAME_CLOCK_UNITS + 1
        check("nmi:disabled-when-ctrl-clear",
              platform3.frame_index == expected3 and platform3.pending_nmi == 0
              and all(not item["nmi_queued"] for item in platform3.frames))

        banner("apu_registers")
        frozen = NesMachine(rom)
        bus = bus_module.P5NesBus(
            bus_module.P5Cartridge(rom, inventory),
            ppu_module.P5Ppu(inventory["mirroring"],
                             chr_rom=rom[16 + 0x4000:16 + 0x6000]),
            bus_module.P5ControllerPorts())
        mismatches = []
        for value in (0x00, 0x0F, 0x10, 0x40, 0x7F, 0xC0, 0xFF):
            frozen.write_memory(0x4015, value)
            bus.write(0x4015, value)
            for address in (0x4015, 0x4017, 0x4000, 0x4001, 0x4008, 0x4013):
                if frozen.read_memory(address) != bus.read(address):
                    mismatches.append(f"0x{address:04x}:{value:#x}")
            for address in (0x4000, 0x4001, 0x4008, 0x4013, 0x4017):
                frozen.write_memory(address, value)
                bus.write(address, value)
        if bytes(frozen.apu_registers) != bytes(bus.apu_registers):
            mismatches.append("latches")
        check("apu:mismatches", mismatches == [])

        banner("determinism")
        run_a = build_platform(rom, inventory, plan)
        run_b = build_platform(rom, inventory, plan)
        for _ in range(5000):
            run_a.begin_instruction(nop)
            run_b.begin_instruction(nop)
        check("determinism:digest", run_a.digest() == run_b.digest())

        banner("negative")
        expect_fail("unknown-opcode",
                    lambda: platform_module.cost_of(0x02),
                    (platform_module.P5PlatformError,))
        expect_fail("empty-plan",
                    lambda: build_platform(rom, inventory, []),
                    (platform_module.P5PlatformError,))
        expect_fail("bad-plan-value",
                    lambda: build_platform(rom, inventory, [0x100]),
                    (platform_module.P5PlatformError,))
        expect_fail("bad-frame-units",
                    lambda: platform_module.P5Platform(
                        build_platform(rom, inventory, plan).bus,
                        input_plan=plan, frame_units=0),
                    (platform_module.P5PlatformError,))
        expect_fail("bad-vblank-units",
                    lambda: platform_module.P5Platform(
                        build_platform(rom, inventory, plan).bus,
                        input_plan=plan, vblank_units=99999),
                    (platform_module.P5PlatformError,))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("platform.json", {
            "stage": STAGE,
            "timing": timing,
            "scheduling": {
                "instructions": platform.instructions,
                "clock": platform.clock,
                "frames": platform.frame_index,
                "nmi_delivered": platform.nmi_delivered,
                "transcript_sha256": platform.digest(),
            },
            "input_plan": list(plan),
        })
        write_json("transcript.json", {
            "stage": STAGE,
            "first_frames": platform.frames[:4],
            "last_frames": platform.frames[-2:],
            "first_events": platform.events[:8],
            "event_count": len(platform.events),
            "digest": platform.digest(),
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-public-rom-bytes:{name}", rom not in data)
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p5_07_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
