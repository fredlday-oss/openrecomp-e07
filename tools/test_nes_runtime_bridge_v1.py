#!/usr/bin/env python3
"""OpenRecomp NES runtime bridge proof V1 (P2-22).

Connects the architecture-neutral generic runtime ABI (`openrecomp.runtime_abi`)
to a bounded NES platform adapter (`openrecomp.frontends.nes_runtime`):

    generic runtime memory contract   <- routed -> NES CPU bus (RAM mirrors,
                                                          PRG-ROM/RAM, controllers)
    generic runtime input contract    <- mapped -> NES standard-controller bits
    generic runtime frame contract    <- service -> `nes.frame.submit`
    generic runtime audio contract    <- service -> `nes.audio.submit`

The gate uses a synthetic, reproducible NROM-style fixture generated in-tree.
The original 26-byte P2-21 6502 region is preserved unchanged; an expansion
exercises the controller and frame/audio host-call surfaces. No commercial ROM,
BIOS, firmware or copyrighted game data is used.

This stage proves only the runtime-bridge infrastructure. It is not a claim of
full NES game compatibility, full PPU/APU emulation, or guest/host equivalence.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes_adapter  # noqa: E402
from openrecomp import runtime_abi as rt  # noqa: E402
from openrecomp.frontends import nes_runtime as nes_rt  # noqa: E402

ARCH = "nes6502"
ENTRY = 0x8000
MEMORY_SIZE = 0x10000
HALT = nes_adapter.HALT_OPCODE
FIXTURE_ID = "p2-22-nes-runtime-bridge-v1"
FRAME_BUFFER = 0x0200
AUDIO_BUFFER = 0x0300

RESULTS: list[dict[str, str]] = []


def check(label, condition):
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}")


def expect_fail(label, thunk, error_type):
    try:
        thunk()
    except error_type:
        RESULTS.append({"check": f"reject:{label}", "status": "PASS"})
        print(f"PASS reject: {label}")
        return
    except Exception as exc:  # noqa: BLE001
        RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
        raise AssertionError(f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}: {exc}") from exc
    RESULTS.append({"check": f"reject:{label}", "status": "FAIL"})
    raise AssertionError(f"{label}: accepted")


# --- deterministic fixture assembler ---------------------------------------
def assemble_fixture():
    """Assemble the synthetic NES6502 region, preserving the P2-21 core."""
    items = [
        ("start", bytes([0xA2, 0x03])),           # ldx #$03
        ("loop", bytes([0x18])),                  # clc
        (None, bytes([0x69, 0x05])),              # adc #$05
        (None, bytes([0x9D, 0x00, 0x04])),        # sta $0400,x
        (None, bytes([0xCA])),                    # dex
        ("bne", bytes([0xD0, 0x00])),             # bne loop (patched)
        ("call", bytes([0x20, 0x00, 0x00])),      # jsr helper (patched)
        ("jmpd", bytes([0x4C, 0x00, 0x00])),      # jmp dispatch (patched)
        (None, bytes([0xEA])),                    # nop
        ("dispatch", bytes([0x6C, 0x00, 0x03])),  # jmp ($0300)
        (None, bytes([0xEA])),
        (None, bytes([0xEA])),
        (None, bytes([0xEA])),
        ("helper", bytes([0xE8])),                # inx
        (None, bytes([0x60])),                    # rts
        # P2-22 expansion: probe controller and reserve frame/audio triggers.
        ("input_probe", bytes([
            0xA9, 0x01,        # lda #$01
            0x8D, 0x16, 0x40,  # sta $4016
            0xA9, 0x00,        # lda #$00
            0x8D, 0x16, 0x40,  # sta $4016
            0xAD, 0x16, 0x40,  # lda $4016
        ])),
        ("frame_trigger", bytes([0xEA])),  # nop (host-call trigger in P2-23)
        ("audio_trigger", bytes([0xEA])),  # nop (host-call trigger in P2-23)
        ("halt", bytes([HALT])),           # synthetic halt
    ]
    labels: dict[str, int] = {}
    address = ENTRY
    for label, data in items:
        if label is not None:
            labels[label] = address
        address += len(data)
    out = bytearray()
    address = ENTRY
    for label, data in items:
        if label == "bne":
            data = bytes([0xD0, (labels["loop"] - (address + 2)) & 0xFF])
        elif label == "call":
            target = labels["helper"]
            data = bytes([0x20, target & 0xFF, target >> 8])
        elif label == "jmpd":
            target = labels["dispatch"]
            data = bytes([0x4C, target & 0xFF, target >> 8])
        out.extend(data)
        address += len(data)
    return bytes(out), labels, address


CODE, LABELS, REGION_END = assemble_fixture()
FIXTURE_SHA256 = hashlib.sha256(CODE).hexdigest()


def prg_rom_image() -> bytes:
    """Pad the fixture to a 16 KiB NROM PRG-ROM bank."""
    if len(CODE) > nes_rt.PRG_BANK_SIZE:
        raise ValueError("fixture exceeds 16 KiB")
    return CODE + bytes([HALT] * (nes_rt.PRG_BANK_SIZE - len(CODE)))


def make_adapter():
    """Build a deterministic NES runtime adapter with the fixture loaded."""
    return nes_rt.NESRuntimeAdapter(prg_rom=prg_rom_image(), mapper=0)


def _write_text(path, text):
    data = text.encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def write_evidence(evidence_dir, staging):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    hashes = {}

    fixture_lines = [
        "P2-22 synthetic NES runtime-bridge fixture",
        "==========================================",
        f"architecture: {ARCH}",
        "endianness: little",
        "address width: 16 bits",
        f"entry: 0x{ENTRY:04x}",
        f"core region end: 0x{LABELS['start'] + len(CODE):04x}",
        f"core region length: {len(CODE)}",
        f"core region sha256: {FIXTURE_SHA256}",
        "origin: synthetic/original (no commercial ROM bytes)",
        "P2-21 core region preserved: yes",
        "labels: " + ", ".join(f"{name}=0x{value:04x}" for name, value in sorted(LABELS.items())),
        "",
        "core region bytes (hex):",
        CODE.hex(),
        "",
    ]
    hashes["fixture.txt"] = _write_text(evidence_dir / "fixture.txt", "\n".join(fixture_lines))

    adapter = staging["adapter"]
    hashes["adapter.txt"] = _write_text(
        evidence_dir / "adapter.txt",
        "\n".join([
            "P2-22 NES runtime adapter configuration",
            "========================================",
            f"prg_rom_size: {adapter._prg_rom_size}",
            f"prg_ram_size: {adapter._prg_ram_size}",
            f"mapper: 0",
            f"services: {list(adapter.services.service_ids)}",
            f"state_fingerprint: {adapter.state.fingerprint()}",
            "",
        ]),
    )

    hashes["frame_submission.txt"] = _write_text(
        evidence_dir / "frame_submission.txt",
        "\n".join([
            "P2-22 frame contract evidence",
            "=============================",
            f"frame count: {len(adapter.state.frames)}",
            f"frame checksum: {adapter.state.frames[0].checksum() if adapter.state.frames else 'n/a'}",
            f"frame descriptor: {adapter.state.frames[0].to_document() if adapter.state.frames else 'n/a'}",
            "",
        ]),
    )

    hashes["audio_submission.txt"] = _write_text(
        evidence_dir / "audio_submission.txt",
        "\n".join([
            "P2-22 audio contract evidence",
            "=============================",
            f"audio count: {len(adapter.state.audio)}",
            f"audio checksum: {adapter.state.audio[0].checksum() if adapter.state.audio else 'n/a'}",
            f"audio descriptor: {adapter.state.audio[0].to_document() if adapter.state.audio else 'n/a'}",
            "",
        ]),
    )

    hashes["input_mapping.txt"] = _write_text(
        evidence_dir / "input_mapping.txt",
        "\n".join([
            "P2-22 input contract evidence",
            "=============================",
            f"input snapshot fingerprint: {adapter.state.input.fingerprint()}",
            f"controller[0]: 0x{adapter._controllers[0]:02x}",
            f"controller[1]: 0x{adapter._controllers[1]:02x}",
            f"port0 read bits (with strobe): {staging['port0_bits']}",
            f"port1 read bits (with strobe): {staging['port1_bits']}",
            "",
        ]),
    )

    # Regression captures
    for name, output in staging.get("regressions", {}).items():
        hashes[f"regression_{name}.txt"] = _write_text(evidence_dir / f"regression_{name}.txt", output)

    return hashes


def run_regression(name, argv):
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / name), *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic test record here")
    parser.add_argument("--evidence-dir", help="write deterministic UTF-8 evidence here (output only)")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    # A. fixture ------------------------------------------------------------
    check("fixture-assembler-deterministic", assemble_fixture() == (CODE, LABELS, REGION_END))
    check("fixture-p2-21-core-length", len(CODE) == 42)
    check("fixture-p2-21-region-preserved", CODE[:26] == bytes([
        0xA2, 0x03, 0x18, 0x69, 0x05, 0x9D, 0x00, 0x04, 0xCA, 0xD0, 0xF7,
        0x20, 0x18, 0x80, 0x4C, 0x12, 0x80, 0xEA, 0x6C, 0x00, 0x03, 0xEA,
        0xEA, 0xEA, 0xE8, 0x60,
    ]))
    check("fixture-sha256", FIXTURE_SHA256 == hashlib.sha256(CODE).hexdigest())
    check("fixture-prg-bank-size", len(prg_rom_image()) == nes_rt.PRG_BANK_SIZE)
    check("fixture-synthetic-origin", all(0 <= byte <= 0xFF for byte in CODE))

    # B. adapter construction -----------------------------------------------
    adapter = make_adapter()
    check("adapter-state-type", isinstance(adapter.state, rt.RuntimeState))
    check("adapter-memory-size", adapter.state.memory.size_bytes == MEMORY_SIZE)
    check("adapter-services-declared", adapter.services.service_ids == ("nes.audio.submit", "nes.frame.submit"))
    check("adapter-mapper-zero", adapter._prg_rom_size == nes_rt.PRG_BANK_SIZE)

    # C. memory contract ----------------------------------------------------
    adapter.cpu_write(0x0000, 0xAB)
    check("memory-ram-write", adapter.cpu_read(0x0000) == 0xAB)
    check("memory-ram-mirror-0800", adapter.cpu_read(0x0800) == 0xAB)
    check("memory-ram-mirror-1000", adapter.cpu_read(0x1000) == 0xAB)
    check("memory-ram-mirror-1800", adapter.cpu_read(0x1800) == 0xAB)
    check("memory-prg-read", adapter.cpu_read(ENTRY) == CODE[0])
    check("memory-prg-mirror", adapter.cpu_read(ENTRY + 0x4000) == CODE[0])
    expect_fail("memory-disabled-io-read", lambda: adapter.cpu_read(0x4018), nes_rt.NESRuntimeError)
    expect_fail("memory-expansion-read", lambda: adapter.cpu_read(0x5000), nes_rt.NESRuntimeError)
    expect_fail("memory-prg-ram-absent", lambda: adapter.cpu_write(0x6000, 0x01), nes_rt.NESRuntimeError)
    expect_fail("memory-ppu-read", lambda: adapter.cpu_read(0x2002), nes_rt.NESRuntimeError)
    expect_fail("memory-ppu-write", lambda: adapter.cpu_write(0x2000, 0x00), nes_rt.NESRuntimeError)
    expect_fail("memory-address-space", lambda: adapter.cpu_read(0x10000), nes_rt.NESRuntimeError)
    expect_fail("memory-invalid-value", lambda: adapter.cpu_write(0x0000, "bad"), nes_rt.NESRuntimeError)

    # D. input contract -----------------------------------------------------
    # Port 0: A + Start. Port 1: B.
    input_snapshot = rt.RuntimeInputSnapshot(
        digital=(True, False, False, True, False, False, False, False, False, True),
        analog=(),
        analog_bits=16,
    )
    adapter.set_input(input_snapshot)
    check("input-snapshot-recorded", adapter.state.input.fingerprint() == input_snapshot.fingerprint())
    check("input-controller-0", adapter._controllers[0] == 0x09)  # A | Start
    check("input-controller-1", adapter._controllers[1] == 0x02)  # B

    # Standard-controller serial protocol.
    adapter.cpu_write(nes_rt.CONTROLLER_STROBE, 1)
    adapter.cpu_write(nes_rt.CONTROLLER_STROBE, 0)
    port0_bits = [(adapter.cpu_read(nes_rt.CONTROLLER_PORT1) & 0x01) for _ in range(10)]
    port1_bits = [(adapter.cpu_read(nes_rt.CONTROLLER_PORT2) & 0x01) for _ in range(10)]
    check("input-port0-serial", port0_bits == [1, 0, 0, 1, 0, 0, 0, 0, 1, 1])
    check("input-port1-serial", port1_bits == [0, 1, 0, 0, 0, 0, 0, 0, 1, 1])
    check("input-open-bus", all((adapter.cpu_read(nes_rt.CONTROLLER_PORT1) & 0x40) == 0x40 for _ in range(3)))

    # E. frame contract -----------------------------------------------------
    # Write a 2x2 RGBA8 pattern at FRAME_BUFFER.
    frame_payload = bytes([
        0xFF, 0x00, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF,
        0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00,
    ])
    for index, byte in enumerate(frame_payload):
        adapter.cpu_write(FRAME_BUFFER + index, byte)
    result = adapter.submit_frame(FRAME_BUFFER, 2, 2, 0)
    check("frame-submit-success", result.ok)
    check("frame-count", len(adapter.state.frames) == 1)
    frame = adapter.state.frames[0]
    check("frame-dimensions", frame.width == 2 and frame.height == 2)
    check("frame-format", frame.pixel_format is rt.RuntimePixelFormat.RGBA8)
    check("frame-payload-match", frame.payload == frame_payload)
    check("frame-checksum-deterministic", frame.checksum() == hashlib.sha256(frame_payload).hexdigest())
    expect_fail("frame-unsupported-format", lambda: adapter.submit_frame(FRAME_BUFFER, 1, 1, 99), nes_rt.NESRuntimeError)

    # F. audio contract -----------------------------------------------------
    audio_payload = bytes([0x10, 0x20, 0x30, 0x40])
    for index, byte in enumerate(audio_payload):
        adapter.cpu_write(AUDIO_BUFFER + index, byte)
    result = adapter.submit_audio(AUDIO_BUFFER, 8000, 1, 4, 0)
    check("audio-submit-success", result.ok)
    check("audio-count", len(adapter.state.audio) == 1)
    audio = adapter.state.audio[0]
    check("audio-descriptor", audio.sample_rate == 8000 and audio.channels == 1 and audio.frames == 4)
    check("audio-format", audio.sample_format is rt.RuntimeSampleFormat.U8)
    check("audio-payload-match", audio.payload == audio_payload)
    expect_fail("audio-unsupported-format", lambda: adapter.submit_audio(AUDIO_BUFFER, 1, 1, 1, 99), nes_rt.NESRuntimeError)

    # G. host-call ABI integration ------------------------------------------
    table = adapter.services
    check("abi-service-ids", table.service_ids == ("nes.audio.submit", "nes.frame.submit"))
    check("abi-audio-numeric-id", table.numeric_id("nes.audio.submit") == 1)
    check("abi-frame-numeric-id", table.numeric_id("nes.frame.submit") == 2)
    check("abi-audio-macro", table.macro("nes.audio.submit") == "OR_RT_SERVICE_NES_AUDIO_SUBMIT")
    check("abi-frame-macro", table.macro("nes.frame.submit") == "OR_RT_SERVICE_NES_FRAME_SUBMIT")

    # Dispatch through the generic state host-call seam.
    frame_call = adapter.state.host_call("nes.frame.submit", (FRAME_BUFFER, 2, 2, 0))
    check("state-frame-host-call", frame_call.ok)
    audio_call = adapter.state.host_call("nes.audio.submit", (AUDIO_BUFFER, 8000, 1, 4, 0))
    check("state-audio-host-call", audio_call.ok)
    bad_arity = adapter.state.host_call("nes.frame.submit", (FRAME_BUFFER, 2, 2))
    check("state-host-call-arity-fails-closed", not bad_arity.ok and bad_arity.failure.code is rt.RuntimeFailureCode.HOST_CALL_ARITY)

    # H. determinism --------------------------------------------------------
    def scenario():
        a = make_adapter()
        a.set_input(rt.RuntimeInputSnapshot(digital=(True, True, False, False, False, False, False, False)))
        a.cpu_write(0x0001, 0xCD)
        for i, b in enumerate(frame_payload):
            a.cpu_write(FRAME_BUFFER + i, b)
        a.submit_frame(FRAME_BUFFER, 2, 2, 0)
        a.submit_audio(AUDIO_BUFFER, 8000, 1, 4, 0)
        return a.state.fingerprint()

    check("determinism-scenario", scenario() == scenario())

    # I. fail-closed / unsupported ------------------------------------------
    expect_fail("unsupported-mapper", lambda: nes_rt.NESRuntimeAdapter(mapper=1), nes_rt.NESRuntimeError)
    expect_fail("prg-rom-oversized", lambda: nes_rt.NESRuntimeAdapter(prg_rom=bytes(65536)), nes_rt.NESRuntimeError)
    expect_fail("bad-input-type", lambda: adapter.set_input({"digital": []}), nes_rt.NESRuntimeError)

    # J. architecture-neutrality audit --------------------------------------
    shared_modules = [
        "openrecomp.program_model",
        "openrecomp.cfg",
        "openrecomp.functions",
        "openrecomp.call_graph",
        "openrecomp.translation_units",
        "openrecomp.indirect_control_flow",
        "openrecomp.runtime_abi",
        "openrecomp.host_emitter",
        "openrecomp.build_pipeline",
    ]
    for module_name in shared_modules:
        module = __import__(module_name, fromlist=["dummy"])
        source = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        check(f"neutrality-no-nes-import:{module_name}",
              not any(token in value.lower() for value in imported for token in ("nes_runtime", "frontends.nes_runtime", "nes6502", "adapters.nes6502")))

    # K. regression gates ---------------------------------------------------
    regressions = {}
    if args.evidence_dir:
        for script, marker in (
            ("test_nes6502_host_emitter_v1.py", "OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS"),
            ("test_runtime_abi_v1.py", "OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS"),
            ("test_nes_platform_v1.py", "OPENRECOMP_NES_PLATFORM_V1=PASS"),
        ):
            completed = run_regression(script, [])
            text = (completed.stdout or "") + (completed.stderr or "")
            regressions[script.replace(".py", "")] = text
            check(f"regression-{script}", completed.returncode == 0 and marker in text)

    tests = sum(1 for item in RESULTS if item["status"] == "PASS")

    if args.evidence_dir:
        write_evidence(
            pathlib.Path(args.evidence_dir),
            {
                "adapter": adapter,
                "port0_bits": port0_bits,
                "port1_bits": port1_bits,
                "regressions": regressions,
            },
        )

    if args.json:
        record = {
            "stage": "P2-22",
            "marker": f"OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests={tests}",
            "tests": tests,
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "fixture_id": FIXTURE_ID,
            "fixture_sha256": FIXTURE_SHA256,
            "fixture_byte_length": len(CODE),
            "state_fingerprint": adapter.state.fingerprint(),
            "services": list(adapter.services.service_ids),
            "results": sorted(RESULTS, key=lambda item: item["check"]),
        }
        out = pathlib.Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_NES_RUNTIME_BRIDGE_V1_JSON={out.name}")

    print(f"OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests={tests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
