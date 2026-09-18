#!/usr/bin/env python3
"""OpenRecomp Phase-5 NES CPU memory map / mapper model gate (P5-05).

Differentially verifies the original Phase-5 bounded NES CPU bus against the
frozen independent platform contract (`tools/nes_platform_v1.py`):

* 2 KiB RAM and its four mirrors;
* the complete $2000-$3FFF PPU register window routing (all 8192 addresses);
* APU/IO latches, $4015 status, $4014 OAM DMA and controller ports;
* NROM-128 PRG mapping and mirroring;
* fail-closed disabled I/O, expansion and absent PRG-RAM windows.

On success it emits::

    OPENRECOMP_P5_05=PASS
    OPENRECOMP_PHASE5_MEMORY_MAP_V1=PASS tests=<count>
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

import nes_rom_v1 as frozen_rom  # noqa: E402
import p5_bus_v1 as bus_module  # noqa: E402
import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402
from nes_platform_v1 import NESPlatformError, NesMachine, NesPpu  # noqa: E402

STAGE = "P5-05"
STAGE_MARKER = "OPENRECOMP_P5_05"
FEATURE_MARKER = "OPENRECOMP_PHASE5_MEMORY_MAP_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

REG_NAMES = ("PPUCTRL", "PPUMASK", "PPUSTATUS", "OAMADDR", "OAMDATA",
             "PPUSCROLL", "PPUADDR", "PPUDATA")

REGRESSIONS = (
    ("tools/test_nes_platform_v1.py", []),
    ("tools/test_nes_rom_v1.py", []),
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


class RecordingPpu:
    """PPU port wrapper that records the register indices the bus routes."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.log: list[tuple] = []

    def cpu_read(self, register: int) -> int:
        value = self.inner.cpu_read(register)
        self.log.append(("r", register, value))
        return value

    def cpu_write(self, register: int, value: int) -> None:
        self.inner.cpu_write(register, value)
        self.log.append(("w", register, value))

    @property
    def oam(self) -> bytearray:
        return self.inner.oam


def _lcg(state: int) -> int:
    return (state * 1103515245 + 12345) & 0x7FFFFFFF


def build_pair(rom: bytes, inventory: dict):
    frozen = NesMachine(rom)
    mapper = frozen_rom.make_mapper(rom)
    ppu = NesPpu(mapper, inventory["mirroring"])
    our = bus_module.P5NesBus(
        bus_module.P5Cartridge(rom, inventory), ppu,
        bus_module.P5ControllerPorts())
    return frozen, our, ppu


def state_digest(frozen, our) -> dict[str, Any]:
    frozen_ppu = frozen.ppu
    our_ppu = our.ppu
    return {
        "ram_equal": bytes(frozen.ram) == bytes(our.ram),
        "apu_registers_equal": bytes(frozen.apu_registers) == bytes(our.apu_registers),
        "apu_status_equal": frozen.apu_status == our.apu_status,
        "controller_states_equal": frozen.controllers == our.controllers.states,
        "controller_bits_equal": frozen.controller_bits_read == our.controllers.bits_read,
        "strobe_equal": frozen.strobe == our.controllers.strobe,
        "oam_equal": bytes(frozen_ppu.oam) == bytes(our_ppu.oam),
        "vram_equal": bytes(frozen_ppu.vram) == bytes(our_ppu.vram),
        "palette_equal": bytes(frozen_ppu.palette) == bytes(our_ppu.palette),
        "ppu_ctrl_equal": frozen_ppu.ctrl == our_ppu.ctrl,
        "ppu_mask_equal": frozen_ppu.mask == our_ppu.mask,
        "ppu_status_equal": frozen_ppu.status == our_ppu.status,
        "ppu_addr_equal": frozen_ppu.addr == our_ppu.addr,
        "ppu_t_equal": frozen_ppu.t == our_ppu.t,
        "ppu_w_equal": frozen_ppu.w == our_ppu.w,
        "ppu_buffer_equal": frozen_ppu.buffer == our_ppu.buffer,
    }


def differential(rom: bytes, inventory: dict) -> dict[str, Any]:
    frozen, our, ppu = build_pair(rom, inventory)
    report: dict[str, Any] = {"sections": {}}

    ram = {}
    for index in range(0x0800):
        frozen.write_memory(index, (index * 7 + 3) & 0xFF)
        our.write(index, (index * 7 + 3) & 0xFF)
    mirrors = {}
    for index in range(0x0800):
        value_frozen = frozen.read_memory(index)
        value_our = our.read(index)
        if value_frozen != value_our:
            mirrors[f"0x{index:04x}"] = [value_frozen, value_our]
        for mirror in range(1, 4):
            address = index + mirror * 0x0800
            if frozen.read_memory(address) != our.read(address):
                mirrors[f"0x{address:04x}"] = [
                    frozen.read_memory(address), our.read(address)]
    ram["mismatches"] = mirrors
    report["sections"]["ram"] = ram

    frozen_recorder = RecordingPpu(frozen.ppu)
    frozen.ppu = frozen_recorder
    our_recorder = RecordingPpu(our.ppu)
    our.ppu = our_recorder
    for address in range(0x2000, 0x4000):
        value = (address * 13 + 7) & 0xFF
        register = (address - 0x2000) & 0x07
        if register == 7:
            frozen.write_memory(0x2006, 0x20)
            frozen.write_memory(0x2006, 0x00)
            our.write(0x2006, 0x20)
            our.write(0x2006, 0x00)
        frozen.write_memory(address, value)
        our.write(address, value)
        frozen.read_memory(address)
        our.read(address)
    report["sections"]["ppu_window"] = {
        "addresses": 0x2000,
        "log_equal": frozen_recorder.log == our_recorder.log,
        "log_entries": len(our_recorder.log),
        "log_sha256": sha256_bytes(canonical(
            [list(entry) for entry in our_recorder.log])),
    }
    frozen.ppu = frozen_recorder.inner
    our.ppu = our_recorder.inner

    apu = {"mismatches": []}
    for address in list(range(0x4000, 0x4014)) + [0x4015, 0x4017]:
        for value in (0x00, 0x55, 0xFF):
            frozen.write_memory(address, value)
            our.write(address, value)
            if frozen.read_memory(address) != our.read(address):
                apu["mismatches"].append(f"read:0x{address:04x}")
    if bytes(frozen.apu_registers) != bytes(our.apu_registers):
        apu["mismatches"].append("registers")
    if frozen.apu_status != our.apu_status:
        apu["mismatches"].append("status")
    for address in (0x4014, 0x4015, 0x4000, 0x4001, 0x4008, 0x4013):
        if frozen.read_memory(address) != our.read(address):
            apu["mismatches"].append(f"read-value:0x{address:04x}")
    report["sections"]["apu_io"] = apu

    controllers = {"mismatches": []}
    for state0, state1 in ((0x00, 0x00), (0x09, 0x02), (0xFF, 0x55)):
        frozen.set_controller(0, state0)
        frozen.set_controller(1, state1)
        our.controllers.set_controller(0, state0)
        our.controllers.set_controller(1, state1)
        transcript_frozen = []
        transcript_our = []
        for step in range(14):
            if step == 3 or step == 9:
                frozen.write_memory(0x4016, 1)
                our.write(0x4016, 1)
            if step == 4 or step == 10:
                frozen.write_memory(0x4016, 0)
                our.write(0x4016, 0)
            transcript_frozen.append(frozen.read_memory(0x4016))
            transcript_frozen.append(frozen.read_memory(0x4017))
            transcript_our.append(our.read(0x4016))
            transcript_our.append(our.read(0x4017))
        if transcript_frozen != transcript_our:
            controllers["mismatches"].append(
                {"states": [state0, state1],
                 "frozen": transcript_frozen, "our": transcript_our})
    report["sections"]["controllers"] = controllers

    for offset in range(0x100):
        value = (offset * 5 + 1) & 0xFF
        frozen.write_memory(0x0200 + offset, value)
        our.write(0x0200 + offset, value)
    frozen.write_memory(0x4014, 0x02)
    our.write(0x4014, 0x02)
    report["sections"]["oam_dma"] = {
        "equal": bytes(frozen.ppu.oam) == bytes(our.ppu.oam),
    }

    cartridge = {"mismatches": []}
    for address in range(0x8000, 0x10000):
        if frozen.read_memory(address) != our.read(address):
            cartridge["mismatches"].append(f"0x{address:04x}")
    frozen.write_memory(0x8000, 0xAA)
    our.write(0x8000, 0xAA)
    frozen.write_memory(0xC000, 0x55)
    our.write(0xC000, 0x55)
    if (frozen.read_memory(0x8000) != our.read(0x8000)
            or frozen.read_memory(0xC000) != our.read(0xC000)):
        cartridge["mismatches"].append("post-write")
    report["sections"]["cartridge"] = cartridge

    closed = {"pairs": []}
    for address in (0x4018, 0x401F, 0x4020, 0x5FFF, 0x6000, 0x7FFF):
        for operation in ("read", "write"):
            frozen_failed = False
            our_failed = False
            try:
                if operation == "read":
                    frozen.read_memory(address)
                else:
                    frozen.write_memory(address, 0)
            except (NESPlatformError, frozen_rom.NESROMError):
                frozen_failed = True
            try:
                if operation == "read":
                    our.read(address)
                else:
                    our.write(address, 0)
            except bus_module.P5BusError:
                our_failed = True
            closed["pairs"].append({
                "address": address, "operation": operation,
                "frozen_failed": frozen_failed, "our_failed": our_failed,
            })
    report["sections"]["fail_closed"] = closed

    mixed = {"mismatches": []}
    state = 0x5EED
    for step in range(5000):
        state = _lcg(state)
        kind = state % 6
        address = state & 0xFFFF
        value = (state >> 8) & 0xFF
        try:
            if kind == 0:
                frozen.write_memory(address & 0x1FFF, value)
                our.write(address & 0x1FFF, value)
            elif kind == 1:
                frozen.write_memory(0x4000 + (address % 0x18), value)
                our.write(0x4000 + (address % 0x18), value)
            elif kind == 2:
                frozen.write_memory(0x4016, value)
                our.write(0x4016, value)
            elif kind == 3:
                if frozen.read_memory(address & 0x1FFF) != our.read(address & 0x1FFF):
                    mixed["mismatches"].append(f"step{step}:ram-read")
            elif kind == 4:
                register = address & 0x07
                if register == 7:
                    continue
                frozen.write_memory(0x2000 + register, value)
                our.write(0x2000 + register, value)
            else:
                register = address & 0x07
                if register == 2:
                    pass
                if frozen.read_memory(0x2000 + register) != our.read(0x2000 + register):
                    mixed["mismatches"].append(f"step{step}:ppu-read")
        except NESPlatformError as exc:
            mixed["mismatches"].append(f"step{step}:frozen-error:{exc}")
        except bus_module.P5BusError as exc:
            mixed["mismatches"].append(f"step{step}:our-error:{exc}")
    mixed.update(state_digest(frozen, our))
    report["sections"]["mixed"] = mixed
    report["state_digest"] = state_digest(frozen, our)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-05 memory map gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-05")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-05 NES CPU Memory Map / Mapper Model Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("fixtures")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()
        check("fixture:rom-sha256",
              metadata["rom_sha256"]
              == "272c94cdc79463cd1020ff14db1892ba56af07e4cfda97f5f1df89dd807772b9")
        check("fixture:prg-ram-absent", inventory["prg_ram_bytes"] == 0)

        banner("differential")
        report_a = differential(rom, inventory)
        report_b = differential(rom, inventory)
        check("differential:deterministic",
              canonical(report_a) == canonical(report_b))
        check("differential:ram",
              report_a["sections"]["ram"]["mismatches"] == {})
        check("differential:ppu-window",
              report_a["sections"]["ppu_window"]["log_equal"] is True
              and report_a["sections"]["ppu_window"]["log_entries"] > 0)
        check("differential:apu-io",
              report_a["sections"]["apu_io"]["mismatches"] == [])
        check("differential:controllers",
              report_a["sections"]["controllers"]["mismatches"] == [])
        check("differential:oam-dma",
              report_a["sections"]["oam_dma"]["equal"] is True)
        check("differential:cartridge",
              report_a["sections"]["cartridge"]["mismatches"] == [])
        check("differential:fail-closed",
              all(item["frozen_failed"] and item["our_failed"]
                  for item in report_a["sections"]["fail_closed"]["pairs"]))
        check("differential:mixed",
              report_a["sections"]["mixed"]["mismatches"] == [])
        check("differential:state",
              all(value is True for key, value in report_a["state_digest"].items()
                  if key.endswith("_equal")))
        FINDINGS["differential_sha256"] = sha256_bytes(canonical(report_a))
        FINDINGS["ppu_routing_sha256"] = report_a["sections"]["ppu_window"]["log_sha256"]

        banner("negative")
        bad_inventory = dict(inventory)
        bad_inventory["mapper"] = 1
        expect_fail("non-nrom-mapper",
                    lambda: bus_module.P5Cartridge(rom, bad_inventory),
                    (bus_module.P5BusError,))
        expect_fail("bad-controller-port",
                    lambda: bus_module.P5ControllerPorts().set_controller(2, 0),
                    (bus_module.P5BusError,))
        expect_fail("address-range",
                    lambda: bus_module.P5NesBus(
                        bus_module.P5Cartridge(rom, inventory),
                        NesPpu(frozen_rom.make_mapper(rom), inventory["mirroring"])).read(0x10000),
                    (bus_module.P5BusError,))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("bus.json", report_a)
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
    (EVIDENCE_DIR / "p5_05_tests.json").write_text(
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
