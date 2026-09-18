#!/usr/bin/env python3
"""OpenRecomp Phase-5 PPU boundary / deterministic graphics model gate (P5-06).

Differentially verifies the original Phase-5 bounded PPU against the frozen
independent PPU contract (`tools/nes_platform_v1.py::NesPpu`):

* every CPU-facing register and the documented write/read latch behaviour;
* all 16384 PPU addresses (CHR/nametable/palette) including the $3000-$3EFF
  mirrors and greyscale palette read masking;
* deterministic frame observation (bounded tile-space view) and its transport
  through the Phase-4 graphics boundary;
* fail-closed unsupported behaviours (four-screen, CHR-ROM writes, unknown
  registers, out-of-range addresses).

On success it emits::

    OPENRECOMP_P5_06=PASS
    OPENRECOMP_PHASE5_PPU_BOUNDARY_V1=PASS tests=<count>
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
for entry in (str(ROOT), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase4" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import nes_rom_v1 as frozen_rom  # noqa: E402
import p5_fixture_build_v1 as fixture_build  # noqa: E402
import p5_ines_v1 as ingestion  # noqa: E402
import p5_ppu_v1 as ppu_module  # noqa: E402
from nes_platform_v1 import NESPlatformError, NesPpu  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from p4_graphics_audio_v1 import GraphicsCapabilities, HeadlessGraphics  # noqa: E402

STAGE = "P5-06"
STAGE_MARKER = "OPENRECOMP_P5_06"
FEATURE_MARKER = "OPENRECOMP_PHASE5_PPU_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

BACKEND_TOKENS = ("rt64", "sdl", "vulkan", "direct3d", "d3d12", "opengl")

REGRESSIONS = (
    ("tools/test_phase4_graphics_audio_v1.py", []),
    ("tools/test_nes_platform_v1.py", []),
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


def frozen_state(ppu: NesPpu) -> dict[str, Any]:
    return {
        "ctrl": ppu.ctrl,
        "mask": ppu.mask,
        "status": ppu.status,
        "oam_addr": ppu.oam_addr,
        "addr": ppu.addr,
        "t": ppu.t,
        "w": ppu.w,
        "scroll_x": ppu.scroll_x,
        "scroll_y": ppu.scroll_y,
        "buffer": ppu.buffer,
        "open_bus": ppu.open_bus,
        "vram_sha256": hashlib.sha256(bytes(ppu.vram)).hexdigest(),
        "palette_sha256": hashlib.sha256(bytes(ppu.palette)).hexdigest(),
        "oam_sha256": hashlib.sha256(bytes(ppu.oam)).hexdigest(),
        "vblank": bool(ppu.status & 0x80),
        "nmi_enabled": bool(ppu.ctrl & 0x80),
    }


def _lcg(state: int) -> int:
    return (state * 1103515245 + 12345) & 0x7FFFFFFF


def register_differential(frozen: NesPpu, our: ppu_module.P5Ppu) -> dict[str, Any]:
    mismatches: list[str] = []
    state = 0xA11CE
    for step in range(3000):
        state = _lcg(state)
        register = state % 8
        value = (state >> 7) & 0xFF
        if register == 7:
            frozen.cpu_read(2)
            our.cpu_read(2)
            frozen.cpu_write(6, 0x20)
            frozen.cpu_write(6, 0x00)
            our.cpu_write(6, 0x20)
            our.cpu_write(6, 0x00)
        frozen.cpu_write(register, value)
        our.cpu_write(register, value)
        frozen_value = frozen.cpu_read(register)
        our_value = our.cpu_read(register)
        if frozen_value != our_value:
            mismatches.append(
                f"step{step}:read:r{register}:{frozen_value:#x}!={our_value:#x}")
            break
        left = frozen_state(frozen)
        right = {key: our.state_document()[key] for key in left}
        if left != right:
            for key in left:
                if left[key] != right[key]:
                    mismatches.append(f"step{step}:state:{key}")
            break
    return {
        "steps": 3000,
        "mismatches": mismatches,
        "final_state_sha256": sha256_bytes(canonical(frozen_state(frozen))),
    }


def memory_differential(frozen: NesPpu, our: ppu_module.P5Ppu) -> dict[str, Any]:
    read_mismatches: list[str] = []
    write_mismatches: list[str] = []
    chr_write_outcomes: dict[int, str] = {}
    for address in range(0x4000):
        frozen_value = frozen.memory_read(address)
        our_value = our.memory_read(address)
        if frozen_value != our_value:
            read_mismatches.append(f"0x{address:04x}")
        value = (address * 11 + 29) & 0xFF
        frozen_outcome = "ok"
        our_outcome = "ok"
        try:
            frozen.memory_write(address, value)
        except frozen_rom.NESROMError:
            frozen_outcome = "chr-rom"
        except NESPlatformError:
            frozen_outcome = "platform"
        try:
            our.memory_write(address, value)
        except ppu_module.P5PpuError as exc:
            our_outcome = "chr-rom" if "CHR ROM" in str(exc) else "platform"
        if frozen_outcome != our_outcome:
            write_mismatches.append(
                f"0x{address:04x}:{frozen_outcome}!={our_outcome}")
        if address < 0x2000:
            chr_write_outcomes[address] = our_outcome
        if bytes(frozen.vram) != bytes(our.vram):
            write_mismatches.append(f"vram:0x{address:04x}")
            break
        if bytes(frozen.palette) != bytes(our.palette):
            write_mismatches.append(f"palette:0x{address:04x}")
            break
    return {
        "addresses": 0x4000,
        "read_mismatches": read_mismatches[:8],
        "write_mismatches": write_mismatches[:8],
        "chr_rom_writes_failed": sum(
            1 for outcome in chr_write_outcomes.values() if outcome == "chr-rom"),
        "vram_sha256": sha256_bytes(bytes(our.vram)),
        "palette_sha256": sha256_bytes(bytes(our.palette)),
    }


def mirroring_differential(rom: bytes, mirroring: str) -> dict[str, Any]:
    frozen = NesPpu(frozen_rom.make_mapper(rom), mirroring)
    our = ppu_module.P5Ppu(mirroring, chr_rom=rom[16 + 0x4000:16 + 0x4000 + 0x2000])
    mismatches: list[str] = []
    for address in range(0x2000, 0x3F00):
        if frozen.memory_read(address) != our.memory_read(address):
            mismatches.append(f"0x{address:04x}")
    for address in range(0x2000, 0x3F00, 7):
        value = (address * 5) & 0xFF
        frozen.memory_write(address, value)
        our.memory_write(address, value)
    if bytes(frozen.vram) != bytes(our.vram):
        mismatches.append("vram")
    return {"mirroring": mirroring, "mismatches": mismatches[:8]}


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-06 PPU boundary gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-06")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-06 PPU Boundary / Deterministic Graphics Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("fixtures")
        rom, metadata = fixture_build.build()
        inventory = ingestion.ingest(rom, source_label="public_fixture").to_document()
        check("fixture:mirroring", inventory["mirroring"] == "horizontal")
        check("fixture:chr-rom", inventory["chr_bytes"] == 0x2000)
        chr_rom = rom[16 + 0x4000:16 + 0x4000 + 0x2000]
        frozen = NesPpu(frozen_rom.make_mapper(rom), "horizontal")
        our = ppu_module.P5Ppu("horizontal", chr_rom=chr_rom)

        banner("register_differential")
        register_report = register_differential(frozen, our)
        check("register:mismatches", register_report["mismatches"] == [])

        banner("memory_differential")
        memory_report = memory_differential(frozen, our)
        check("memory:reads", memory_report["read_mismatches"] == [])
        check("memory:writes", memory_report["write_mismatches"] == [])
        check("memory:chr-rom-writes-fail",
              memory_report["chr_rom_writes_failed"] == 0x2000)

        banner("mirroring")
        for arrangement in ("horizontal", "vertical"):
            report = mirroring_differential(rom, arrangement)
            check(f"mirroring:{arrangement}", report["mismatches"] == [])

        banner("frame_observation")
        our.set_vblank(True)
        our.cpu_write(0, 0x80)
        check("frame:vblank", our.vblank() is True and our.nmi_enabled() is True)
        frame_a = our.frame_observable(0)
        frame_b = our.frame_observable(0)
        check("frame:runtime-frame-type", isinstance(frame_a, rt.RuntimeFrame))
        check("frame:dimensions", frame_a.width == 32 and frame_a.height == 30
              and frame_a.pixel_format is rt.RuntimePixelFormat.GRAY8)
        check("frame:payload", frame_a.payload == our.tile_space()
              and len(frame_a.payload) == 960)
        check("frame:deterministic", frame_a.payload == frame_b.payload)
        digest_before = our.digest()
        our.memory_write(0x2000, 0x01)
        check("frame:digest-sensitive", our.digest() != digest_before)
        check("frame:tile-space-sensitive",
              our.frame_observable(0).payload != frame_a.payload)
        capabilities = GraphicsCapabilities(("GRAY8",), 32, 30)
        check("frame:boundary-supports",
              capabilities.supports(32, 30, rt.RuntimePixelFormat.GRAY8.value))
        graphics = HeadlessGraphics(capabilities)
        graphics.present(frame_a)
        ledger = graphics.to_document()
        record = graphics.presentations[0]
        check("frame:boundary-presented",
              len(graphics.presentations) == 1 and record.sequence == 0)
        check("frame:boundary-checksum", record.checksum == frame_a.checksum())

        banner("timing_assumptions")
        timing = ppu_module.timing_assumptions()
        check("timing:documented",
              timing["cycle_accuracy"] is False
              and timing["sprite_rendering"] is False
              and timing["sprite_zero_hit"] is False
              and timing["four_screen"].startswith("unsupported"))
        check("timing:model", "29780" in timing["frame_length_model"])

        banner("negative")
        expect_fail("four-screen",
                    lambda: ppu_module.P5Ppu("four-screen", chr_rom=chr_rom),
                    (ppu_module.P5PpuError,))
        expect_fail("chr-rom-write",
                    lambda: ppu_module.P5Ppu(
                        "horizontal", chr_rom=chr_rom).memory_write(0x0000, 0x55),
                    (ppu_module.P5PpuError,))
        expect_fail("unknown-register",
                    lambda: ppu_module.P5Ppu(
                        "horizontal", chr_rom=chr_rom).cpu_write(8, 0),
                    (ppu_module.P5PpuError,))
        expect_fail("address-range",
                    lambda: ppu_module.P5Ppu(
                        "horizontal", chr_rom=chr_rom).memory_read(0x10000),
                    (ppu_module.P5PpuError,))
        source = (ROOT / ".openrecomp-phase5" / "src" / "p5_ppu_v1.py").read_text(
            encoding="utf-8").lower()
        check("negative:no-backend-tokens",
              not any(token in source for token in BACKEND_TOKENS))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("ppu.json", {
            "stage": STAGE,
            "register_differential": register_report,
            "memory_differential": memory_report,
            "mirroring": [mirroring_differential(rom, "horizontal"),
                          mirroring_differential(rom, "vertical")],
            "unsupported": ppu_module.timing_assumptions(),
        })
        write_json("frame.json", {
            "stage": STAGE,
            "tile_space_sha256": sha256_bytes(our.tile_space()),
            "ppu_digest": our.digest(),
            "frame": {
                "width": frame_a.width,
                "height": frame_a.height,
                "pixel_format": frame_a.pixel_format.value,
                "payload_sha256": sha256_bytes(frame_a.payload),
            },
            "graphics_boundary": {
                "capabilities": capabilities.to_document(),
                "ledger_sha256": sha256_bytes(canonical(ledger)),
                "presentations": len(graphics.presentations),
            },
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
    (EVIDENCE_DIR / "p5_06_tests.json").write_text(
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
