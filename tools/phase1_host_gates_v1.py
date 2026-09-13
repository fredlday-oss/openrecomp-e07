#!/usr/bin/env python3
"""Phase 1 deterministic host-gate runner and verification inventory.

This tool is the reproducible regression command for OpenRecomp Phase 1. It
enumerates every repository verification gate, classifies each one as runnable
or toolchain-gated on the current host, executes the runnable ones and reports
a deterministic pass/fail/skip summary.

Rules enforced here:
- a skipped gate is never counted as a pass;
- an unexpected return code or a missing gate marker is a failure;
- `SOURCE_SHA256SUMS.txt` integrity is verified before any gate runs;
- output contains no timestamps, no absolute paths and sorted keys so two runs
  on the same tree are byte-identical.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMS_PATH = ROOT / "SOURCE_SHA256SUMS.txt"
WASM_RUNNER_PATH = ROOT / "tools" / "wasm_run.js"

STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIPPED_TOOLCHAIN_UNAVAILABLE"


class Gate:
    __slots__ = ("gate_id", "area", "argv", "marker", "requires", "note")

    def __init__(
        self,
        gate_id: str,
        area: str,
        argv: list[str],
        marker: str,
        requires: tuple[str, ...] = (),
        note: str = "",
    ) -> None:
        self.gate_id = gate_id
        self.area = area
        self.argv = argv
        self.marker = marker
        self.requires = requires
        self.note = note

    def as_inventory(self) -> dict:
        return {
            "area": self.area,
            "gate_id": self.gate_id,
            "marker": self.marker,
            "note": self.note,
            "requires": list(self.requires),
        }


def _py(script: str, *args: str) -> list[str]:
    return [sys.executable, str(Path("tools") / script), *args]


GATES: tuple[Gate, ...] = (
    Gate(
        "ir-v1-spec",
        "normalized-ir-v1",
        _py("test_ir_v1.py"),
        "OPENRECOMP_IR_V1_SPEC=PASS",
    ),
    Gate(
        "ir-v1-minimal-example",
        "normalized-ir-v1",
        _py("validate_ir_v1.py", "examples/ir-v1/minimal.json"),
        "OPENRECOMP_IR_V1_VALID=PASS",
    ),
    Gate(
        "core-api-v1",
        "core-api-v1",
        _py("test_core_api_v1.py"),
        "OPENRECOMP_CORE_API_V1_TESTS=PASS",
    ),
    Gate(
        "adapter-seam",
        "architecture-seam",
        _py("check_adapter_seam.py"),
        "PASS: shared adapter interface is real",
    ),
    Gate(
        "frontend-contract-v1",
        "architecture-seam",
        _py("check_frontend_contract_v1.py"),
        "OPENRECOMP_FRONTEND_CONTRACT_V1=PASS",
        note="executable gate for contracts/frontend_contract_v1.json: adapter surface, lowering probes, neutral chain proofs",
    ),
    Gate(
        "frontend-scaffold-v1",
        "architecture-seam",
        _py("test_frontend_scaffold_v1.py"),
        "OPENRECOMP_FRONTEND_SCAFFOLD_V1=PASS",
        note="fail-closed scaffolding (openrecomp/frontends/scaffold.py) plus deterministic synthetic Core API proof",
    ),
    Gate(
        "arch-harness-mips32-v1",
        "architecture-seam",
        _py("arch_harness_v1.py", "examples/mips32-v1/arch-harness-v1.json"),
        "OPENRECOMP_ARCH_HARNESS_V1=PASS",
        note="shared architecture harness: 35 pinned decode cases, 4 fail-closed rejections, full fixture chain",
    ),
    Gate(
        "arch-harness-riscv32-v1",
        "architecture-seam",
        _py("arch_harness_v1.py", "examples/riscv32-v1/arch-harness-v1.json"),
        "OPENRECOMP_ARCH_HARNESS_V1=PASS",
        note="shared architecture harness: 10 pinned RV32I decode cases, 3 rejections, prebuilt IR V1 module chain",
    ),
    Gate(
        "sm83-state-v1",
        "sm83",
        _py("test_sm83_state_v1.py"),
        "OPENRECOMP_SM83_STATE_V1=PASS",
        note="P1-10: documented SM83 register/flag state model + fail-closed checks + neutral-chain AF composition proof",
    ),
    Gate(
        "sm83-decode-v1",
        "sm83",
        _py("test_sm83_decode_v1.py"),
        "OPENRECOMP_SM83_DECODE_V1=PASS",
        note="P1-11: full SM83 base+CB decoder coverage, operand resolution, fail-closed undocumented/truncated handling",
    ),
    Gate(
        "sm83-semantics-v1",
        "sm83",
        _py("test_sm83_semantics_v1.py"),
        "OPENRECOMP_SM83_SEMANTICS_V1=PASS",
        note="P1-12: independent SM83 reference interpreter; documented flag/register/memory semantics pinned + full coverage",
    ),
    Gate(
        "sm83-lowering-v1",
        "sm83",
        _py("test_sm83_lowering_v1.py"),
        "OPENRECOMP_SM83_LOWERING_V1=PASS",
        note="P1-13: SM83 control flow + IR V1 lowering; differential proof reference == Core API (state + 64 KiB memory)",
    ),
    Gate(
        "gb-rom-v1",
        "gameboy",
        _py("test_gb_rom_v1.py"),
        "OPENRECOMP_GB_ROM_V1=PASS",
        note="P1-14: synthetic GB ROM header/classification/mapper contract; documented MBC1 rules; fail-closed ingestion",
    ),
    Gate(
        "gb-headless-v1",
        "gameboy",
        _py("test_gb_headless_v1.py"),
        "OPENRECOMP_GB_HEADLESS_V1=PASS",
        note="P1-15: deterministic headless proof ROM->map->reference==Core API; timer/joypad/interrupt/HALT contracts; local-ROM metadata",
    ),
    Gate(
        "gb-mode-v1",
        "gameboy",
        _py("test_gb_mode_v1.py"),
        "OPENRECOMP_GB_MODE_V1=PASS",
        note="P1-16: documented GB vs GBC platform-mode selection; KEY1/VBK/SVBK CGB-only surfaces; speed switch; double-speed timer rates",
    ),
    Gate(
        "sm83-gb-gbc-regression-v1",
        "sm83",
        _py("test_sm83_regression_v1.py"),
        "OPENRECOMP_SM83_GB_GBC_REGRESSION_V1=PASS",
        note="P1-17: SM83/GB/GBC regression + differential audit; every chain gate run twice, byte-identical; frozen markers re-pinned",
    ),
    Gate(
        "z80-state-v1",
        "z80",
        _py("test_z80_state_v1.py"),
        "OPENRECOMP_Z80_STATE_V1=PASS",
        note="P1-20: documented Z80 register/flag state model (shadow set, IX/IY, I/R, IFF/IM) + fail-closed checks",
    ),
    Gate(
        "z80-decode-v1",
        "z80",
        _py("test_z80_decode_v1.py"),
        "OPENRECOMP_Z80_DECODE_V1=PASS",
        note="P1-20: full documented Z80 decode: 256 base + 65 ED + 248 CB + DD/FD index + DDCB/FDCB; undocumented fail closed",
    ),
    Gate(
        "z80-semantics-v1",
        "z80",
        _py("test_z80_semantics_v1.py"),
        "OPENRECOMP_Z80_SEMANTICS_V1=PASS",
        note="P1-21: independent Z80 reference interpreter; documented flag/register/memory/port semantics pinned + full coverage",
    ),
    Gate(
        "z80-lowering-v1",
        "z80",
        _py("test_z80_lowering_v1.py"),
        "OPENRECOMP_Z80_LOWERING_V1=PASS",
        note="P1-21: Z80 control flow + IR V1 lowering; differential proof reference == Core API (state + 64 KiB memory + ports)",
    ),
    Gate(
        "sms-platform-v1",
        "master-system",
        _py("test_sms_platform_v1.py"),
        "OPENRECOMP_SMS_PLATFORM_V1=PASS",
        note="P1-22: SMS ROM ingestion + Sega mapper + memory map + VDP/PSG/controller port contract; synthetic ROMs, fail closed",
    ),
    Gate(
        "sms-headless-v1",
        "master-system",
        _py("test_sms_headless_v1.py"),
        "OPENRECOMP_SMS_HEADLESS_V1=PASS",
        note="P1-23: SMS deterministic headless proof; synthetic ROM runs reference == Core API (CPU state, RAM, mapper mirrors, flat ports); paging + VDP status pins",
    ),
    Gate(
        "z80-sms-regression-v1",
        "z80",
        _py("test_sms_regression_v1.py"),
        "OPENRECOMP_Z80_SMS_REGRESSION_V1=PASS",
        note="P1-24: Z80/SMS regression + differential audit; every chain gate run twice, byte-identical; frozen markers re-pinned",
    ),
    Gate(
        "nes6502-state-v1",
        "nes6502",
        _py("test_nes6502_state_v1.py"),
        "OPENRECOMP_NES6502_STATE_V1=PASS",
        note="P1-30: documented NES 6502 register/flag state model + fail-closed checks + neutral-chain proof",
    ),
    Gate(
        "nes6502-decode-v1",
        "nes6502",
        _py("test_nes6502_decode_v1.py"),
        "OPENRECOMP_NES6502_DECODE_V1=PASS",
        note="P1-30: full documented NES 6502 opcode map (151 official opcode values; documented addressing modes) with fail-closed undocumented handling",
    ),
    Gate(
        "nes6502-semantics-v1",
        "nes6502",
        _py("test_nes6502_semantics_v1.py"),
        "OPENRECOMP_NES6502_SEMANTICS_V1=PASS",
        note="P1-31: independent NES 6502 reference interpreter; documented flag/address-mode/interrupt/BRK-RTI semantics pinned + full coverage",
    ),
    Gate(
        "nes6502-lowering-v1",
        "nes6502",
        _py("test_nes6502_lowering_v1.py"),
        "OPENRECOMP_NES6502_LOWERING_V1=PASS",
        note="P1-31: NES 6502 control flow + IR V1 lowering; differential proof reference == Core API (state + 64 KiB memory)",
    ),
    Gate(
        "nes-rom-v1",
        "nes",
        _py("test_nes_rom_v1.py"),
        "OPENRECOMP_NES_ROM_V1=PASS",
        note="P1-32: iNES/NES 2.0 header ingestion + NROM (mapper 0) contract; synthetic ROMs, unsupported mappers fail closed",
    ),
    Gate(
        "nes-platform-v1",
        "nes",
        _py("test_nes_platform_v1.py"),
        "OPENRECOMP_NES_PLATFORM_V1=PASS",
        note="P1-33: NES CPU bus + PPU register/memory contract + APU latch + standard controller protocol; fail closed",
    ),
    Gate(
        "nes-headless-v1",
        "nes",
        _py("test_nes_headless_v1.py"),
        "OPENRECOMP_NES_HEADLESS_V1=PASS",
        note="P1-34: NES deterministic headless proof; synthetic NROM reference == Core API (CPU state + 64 KiB); PPU/APU/controller/OAM-DMA protocol pinned",
    ),
    Gate(
        "nes-regression-v1",
        "nes",
        _py("test_nes_regression_v1.py"),
        "OPENRECOMP_NES_REGRESSION_V1=PASS",
        note="P1-35: 6502/NES regression + differential audit; every NES chain gate run twice, byte-identical; frozen markers re-pinned",
    ),
    Gate(
        "arch-harness-sm83-v1",
        "sm83",
        _py("arch_harness_v1.py", "examples/sm83-v1/arch-harness-v1.json"),
        "OPENRECOMP_ARCH_HARNESS_V1=PASS",
        note="shared architecture harness: 87 pinned SM83 decode cases, 13 fail-closed rejections (decode-only stage)",
    ),
    Gate(
        "mips32-frontend-v1",
        "mips32",
        _py("test_mips32_frontend_v1.py"),
        "OPENRECOMP_MIPS32_FRONTEND_V1_TESTS=PASS",
    ),
    Gate(
        "mips32-expansion-v1-negative",
        "mips32",
        _py("test_mips32_expansion_v1.py"),
        "OPENRECOMP_MIPS32_EXPANSION_NEGATIVE_TESTS=PASS",
    ),
    Gate(
        "mips32-microtests-v1",
        "mips32",
        _py("test_mips32_microtests_v1.py"),
        "0 failed",
    ),
    Gate(
        "mips32-causality-v1",
        "mips32",
        _py("test_mips32_causality_v1.py"),
        "CAUSALITY_PASS",
        requires=("c_compiler",),
        note="compiles generated C through the local default compiler",
    ),
    Gate(
        "mips32-equivalence-v1",
        "mips32",
        _py("test_mips32_equivalence_v1.py"),
        "EQUIVALENCE_PASS",
        requires=("c_compiler",),
        note="compiles generated C through the local default compiler",
    ),
    Gate(
        "public-safety-scan",
        "safety",
        _py("public_safety_scan.py"),
        "OPENRECOMP_PUBLIC_SAFETY=PASS",
    ),
    Gate(
        "public-safety-missing-file-test",
        "safety",
        _py("test_public_safety_scan.py"),
        "OPENRECOMP_PUBLIC_SAFETY_MISSING_FILE_TEST=PASS",
    ),
    Gate(
        "doc-links",
        "documentation",
        _py("check_markdown_links.py"),
        "OPENRECOMP_DOC_LINKS=PASS",
    ),
    Gate(
        "release-metadata-tests",
        "release",
        _py("test_release_metadata.py"),
        "OPENRECOMP_RELEASE_AUTOMATION_V1_TESTS=PASS",
    ),
    Gate(
        "release-v0_2_0-metadata",
        "release",
        _py("verify_release_v0_2_0.py"),
        "OPENRECOMP_V0_2_RELEASE_METADATA=PASS",
    ),
    Gate(
        "e07-hardened-end-to-end",
        "rv32i-e07",
        ["bash", "RUN.sh"],
        "PASS: E07 V1.1 HARDENED END-TO-END",
        requires=("bash", "clang", "gcc", "node"),
        note="hardened RV32I proof: ELF rejection, native + WebAssembly parity, golden regression",
    ),
    Gate(
        "external-repro-v1",
        "reviewer-gate",
        ["bash", "EXTERNAL_REPRO_V1.sh"],
        "OPENRECOMP_EXTERNAL_REPRO_V1=PASS",
        requires=("bash", "clang", "gcc", "node", "posix"),
        note="reference reviewer environment is Ubuntu 24.04; requires a clean tracked tree",
    ),
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_source_integrity() -> tuple[str, list[str]]:
    if not SUMS_PATH.exists():
        return STATUS_FAIL, ["SOURCE_SHA256SUMS.txt is missing"]
    problems: list[str] = []
    checked = 0
    for raw in SUMS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if " *" not in line:
            problems.append(f"unparsable manifest line: {line[:80]}")
            continue
        expected, relative = line.split(" *", 1)
        path = ROOT / relative.replace("/", os.sep)
        if not path.exists():
            problems.append(f"manifest entry missing from tree: {relative}")
            continue
        actual = _sha256_bytes(path.read_bytes())
        if actual != expected:
            problems.append(f"integrity mismatch: {relative}")
        checked += 1
    if problems:
        return STATUS_FAIL, problems
    return STATUS_PASS, [f"verified {checked} manifest entries"]


def check_wasm_runner() -> tuple[str, list[str]]:
    """Guard the WebAssembly fixture runner against silent truncation.

    Commit 2edb212 emptied `tools/wasm_run.js`, which broke the RUN.sh
    native/WebAssembly parity step while `SOURCE_SHA256SUMS.txt` was
    regenerated around the empty file. This check fails closed if the runner
    is empty or loses its observable contract.
    """
    if not WASM_RUNNER_PATH.exists():
        return STATUS_FAIL, ["tools/wasm_run.js is missing"]
    data = WASM_RUNNER_PATH.read_bytes()
    problems = []
    if not data.strip():
        problems.append("tools/wasm_run.js is empty")
    text = data.decode("utf-8", "replace")
    for required in ("run_fixture", "WASM_CHECKSUM="):
        if required not in text:
            problems.append(f"tools/wasm_run.js lost required marker {required}")
    if b"\r\n" in data:
        problems.append("tools/wasm_run.js must keep LF line endings (.gitattributes pins *.js to LF)")
    if problems:
        return STATUS_FAIL, problems
    return STATUS_PASS, [f"sha256={_sha256_bytes(data)}"]


@contextlib.contextmanager
def _devnull_stdio():
    """Silence a child compiler at file-descriptor level.

    `cl.exe` writes progress to the inherited console handles, so Python-level
    redirection is not enough to keep harness output deterministic.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    saved_out = os.dup(1)
    saved_err = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(devnull)
        os.close(saved_out)
        os.close(saved_err)


def probe_c_compiler() -> str | None:
    """Report a usable C compiler the way the repository gates find one.

    Existing gates compile generated C through `setuptools._distutils`, which
    locates MSVC without `cl` being on `PATH`. The probe therefore performs a
    real trial compile in a temporary directory outside the repository instead
    of guessing from `PATH` alone.
    """
    for name in ("cl", "clang-cl", "clang", "gcc", "cc"):
        if shutil.which(name):
            return name
    try:
        import tempfile

        from setuptools._distutils.ccompiler import new_compiler

        with tempfile.TemporaryDirectory(prefix="openrecomp-cprobe-") as work:
            source = Path(work) / "probe.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            compiler = new_compiler()
            with _devnull_stdio():
                compiler.initialize()
                objects = compiler.compile([str(source)], output_dir=work)
                compiler.link_executable(objects, str(Path(work) / "probe"), output_dir=work)
        return f"distutils:{type(compiler).__name__}"
    except Exception:
        return None


def available_tools() -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in ("bash", "clang", "gcc", "node", "sha256sum", "cmp"):
        found[name] = shutil.which(name)
    found["c_compiler"] = probe_c_compiler()
    found["posix"] = "available" if os.name == "posix" else None
    return found


def missing_requirements(gate: Gate, tools: dict[str, str | None]) -> list[str]:
    return [name for name in gate.requires if not tools.get(name)]


def child_env() -> dict[str, str]:
    """Reproduce the documented gate environment (`RUN.sh` exports PYTHONPATH=ROOT)."""
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(ROOT) if not existing else f"{ROOT}{os.pathsep}{existing}"
    return env


def run_gate(gate: Gate) -> dict:
    try:
        completed = subprocess.run(
            gate.argv,
            cwd=str(ROOT),
            env=child_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        return {
            "detail": f"unable to start gate: {exc}",
            "gate_id": gate.gate_id,
            "returncode": None,
            "status": STATUS_FAIL,
        }
    combined = (completed.stdout or "") + (completed.stderr or "")
    marker_seen = gate.marker in combined
    if completed.returncode == 0 and marker_seen:
        status = STATUS_PASS
        detail = f"marker {gate.marker!r} present"
    elif completed.returncode != 0 and not marker_seen:
        status = STATUS_FAIL
        detail = _last_meaningful_line(combined) or f"exit {completed.returncode}"
    else:
        status = STATUS_FAIL
        detail = (
            f"exit {completed.returncode} but marker {gate.marker!r} "
            f"{'missing' if not marker_seen else 'present'}"
        )
    return {"detail": detail, "gate_id": gate.gate_id, "returncode": completed.returncode, "status": status}


def _last_meaningful_line(text: str) -> str:
    for line in reversed([item.strip() for item in text.splitlines()]):
        if line:
            return line[:300]
    return ""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", help="write the deterministic inventory/result JSON here")
    parser.add_argument("--only", action="append", default=[], help="run gates whose id contains this substring")
    parser.add_argument("--include-toolchain-gated", action="store_true", help="also run gates whose tools are missing")
    parser.add_argument("--inventory-only", action="store_true", help="print the inventory without executing gates")
    args = parser.parse_args(argv[1:])

    tools = available_tools()
    selected = [gate for gate in GATES if not args.only or any(part in gate.gate_id for part in args.only)]

    results: list[dict] = []
    integrity_status, integrity_detail = check_source_integrity()
    results.append(
        {
            "detail": "; ".join(integrity_detail),
            "gate_id": "source-integrity",
            "returncode": 0 if integrity_status == STATUS_PASS else 1,
            "status": integrity_status,
        }
    )
    runner_status, runner_detail = check_wasm_runner()
    results.append(
        {
            "detail": "; ".join(runner_detail),
            "gate_id": "wasm-runner-intact",
            "returncode": 0 if runner_status == STATUS_PASS else 1,
            "status": runner_status,
        }
    )

    if not args.inventory_only:
        for gate in selected:
            missing = missing_requirements(gate, tools)
            if missing and not args.include_toolchain_gated:
                results.append(
                    {
                        "detail": "missing required tool(s): " + ", ".join(sorted(missing)),
                        "gate_id": gate.gate_id,
                        "returncode": None,
                        "status": STATUS_SKIP,
                    }
                )
                continue
            results.append(run_gate(gate))

    counts = {STATUS_FAIL: 0, STATUS_PASS: 0, STATUS_SKIP: 0}
    for item in results:
        counts[item["status"]] += 1

    for item in results:
        print(f"{item['status']:<32} {item['gate_id']:<32} {item['detail']}")

    record = {
        "counts": {
            "fail": counts[STATUS_FAIL],
            "pass": counts[STATUS_PASS],
            "skipped_toolchain_unavailable": counts[STATUS_SKIP],
        },
        "gates": sorted(results, key=lambda item: item["gate_id"]),
        "inventory": [gate.as_inventory() for gate in GATES],
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "schema_version": "1.0.0",
        "toolchain": {name: ("available" if value else None) for name, value in sorted(tools.items())},
    }
    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENRECOMP_PHASE1_HOST_GATES_JSON={out.name}")

    print(
        "OPENRECOMP_PHASE1_HOST_GATES_PASS=%d FAIL=%d SKIPPED=%d"
        % (counts[STATUS_PASS], counts[STATUS_FAIL], counts[STATUS_SKIP])
    )
    if counts[STATUS_FAIL]:
        print("OPENRECOMP_PHASE1_HOST_GATES_V1=FAIL")
        return 1
    print("OPENRECOMP_PHASE1_HOST_GATES_V1=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
