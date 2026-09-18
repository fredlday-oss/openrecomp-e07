#!/usr/bin/env python3
"""OpenRecomp Phase-4 reproducible package gate (P4-10).

Produces and verifies the reproducible Phase-4 package:

* writes the reproduction instructions (`REPRODUCE.md`) and the generated host
  translation sources into the P4-10 evidence (pinned to the P4-08 hashes);
* builds the deterministic package twice from the audited tree and requires
  byte-identical archives;
* verifies the member manifest, sorted members, fixed metadata, per-member
  hashes and the fail-closed content policy (text only, UTF-8/LF, no host
  paths/timestamps/UUIDs/sensitive markers, no compiled or guest binaries);
* checks package completeness (control plane, sources, contracts, ports,
  fixture, all Phase-4 gates, evidence through P4-09, generated sources,
  reproduction instructions and the Phase-4 source manifest);
* runs the bounded regression set from the audited tree (P2-08, the fast
  Phase-4 gates, Phase-1 host gates, public safety) and checks the committed
  P4-00/P4-08/P4-09 boundary records; the heavy end-to-end re-execution is the
  whole-regression audit in P4-90.

It emits::

    OPENRECOMP_P4_10=PASS
    OPENRECOMP_PHASE4_PACKAGE_REGRESSION_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_package_regression_v1.py
    python tools/test_phase4_package_regression_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-10
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / ".openrecomp-phase4" / "src"),
                  str(ROOT / ".openrecomp-phase3" / "src")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import p4_fixture_exec_v1 as fx  # noqa: E402
import p4_package_v1 as pkg  # noqa: E402

STAGE = "P4-10"
STAGE_MARKER = "OPENRECOMP_P4_10"
FEATURE_MARKER = "OPENRECOMP_PHASE4_PACKAGE_REGRESSION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"

PROGRAM_SHA256 = "abd138ea391fb48cd5ba17b54f56f93a77aaa6ebab201d715210635a7f1edc48"
SUPPORT_SHA256 = "755a004630560ae606ce571c2c111934b94e945db6c4c6d6aea5c105a2b8a8fd"
PACKAGE_PATH = ".openrecomp-phase4/package/phase4_package_v1.zip"

FAST_REGRESSIONS = (
    ("regression_p2_08", "tools/test_runtime_abi_v1.py", "OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169"),
    ("regression_p4_01", "tools/test_phase4_runtime_abi_v1.py", "OPENRECOMP_PHASE4_RUNTIME_ABI_V1=PASS tests=156"),
    ("regression_p4_02", "tools/test_phase4_guest_memory_v1.py", "OPENRECOMP_PHASE4_GUEST_MEMORY_V1=PASS tests=113"),
    ("regression_p4_03", "tools/test_phase4_runtime_services_v1.py", "OPENRECOMP_PHASE4_RUNTIME_SERVICES_V1=PASS tests=86"),
    ("regression_p4_04", "tools/test_phase4_deterministic_io_v1.py", "OPENRECOMP_PHASE4_DETERMINISTIC_IO_V1=PASS tests=101"),
    ("regression_p4_05", "tools/test_phase4_platform_adapter_v1.py", "OPENRECOMP_PHASE4_PLATFORM_ADAPTER_V1=PASS tests=76"),
    ("regression_p4_06", "tools/test_phase4_graphics_audio_v1.py", "OPENRECOMP_PHASE4_GRAPHICS_AUDIO_V1=PASS tests=72"),
    ("regression_p4_07", "tools/test_phase4_fixture_v1.py", "OPENRECOMP_PHASE4_FIXTURE_V1=PASS tests=49"),
    ("regression_phase1_host_gates", "tools/phase1_host_gates_v1.py", "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS"),
    ("regression_public_safety", "tools/public_safety_scan.py", "OPENRECOMP_PUBLIC_SAFETY=PASS"),
)
BOUNDARY_RECORDS = (
    ".openrecomp-phase4/evidence/P4-00/p4_00_tests.json",
    ".openrecomp-phase4/evidence/P4-08/p4_08_tests.json",
    ".openrecomp-phase4/evidence/P4-09/p4_09_tests.json",
)

REPRODUCE = """\
# Reproducing the OpenRecomp Phase-4 generic runtime / platform layer

This package is a deterministic snapshot of the audited Phase-4 tree
(branch `phase4/generic-runtime-v1`, descending from the frozen Phase-3 tag
`openrecomp-phase3-pass` = `e16e4b29b90f379615f1af97e47747cd1d531796`).

## Requirements

- Python 3.11 (standard library only for the gates).
- `git` with the recorded repository history (the Phase-1/Phase-2/Phase-3
  frozen tags).
- External toolchains, pinned by recorded identity and not shipped:
  - `zig` 0.13.0 (`zig cc` = clang 18.1.5, LLD 18.1.6) at
    `.openrecomp-phase3/tools/zig/zig.exe` for the MIPS32 fixtures;
  - LLVM/clang-cl 22.1.8 plus `lld-link.exe` for the deterministic host
    build pipeline.
  The fixture and translation are rebuilt from source by the gates; no
  prebuilt binary is required.

## Package contents

- `control/` - the Phase-4 control plane (policy, scope, queue, state,
  handoff, evidence schema, source manifest).
- `src/` - the Phase-4 runtime/ABI/memory/service/I/O/adapter/graphics-audio,
  fixture translation and reference modules.
- `contracts/`, `ports/` - the generated-code <-> runtime ABI contract
  document, C header and the frozen Phase-3 instance profile.
- `fixture/` - the original Apache-2.0 interactive fixture sources and its
  deterministic input plan.
- `gates/` - every Phase-4 stage gate.
- `generated/` - the generated host translation for the fixture
  (`p4_fixture_program.c`, `p4_fixture_support.c`), pinned to
  `abd138ea...` / `755a004630...`.
- `evidence/` - the tracked stage evidence `P4-00` .. `P4-09`.
- `P4_PACKAGE_MANIFEST.json` - member sizes, sha256 hashes and the canonical
  package fingerprint.

## Reproduction

1. Check out the audited commit and verify the frozen chain:

       git rev-parse openrecomp-phase3-pass^{commit}
       python tools/test_phase4_boundary_v1.py

2. Rebuild the fixture and its translation deterministically:

       python tools/test_phase4_fixture_v1.py
       python tools/test_phase4_adapter_execution_v1.py

3. Re-run the end-to-end proof with the independent reference:

       python tools/test_phase4_generic_runtime_proof_v1.py

4. Rebuild this package and verify its manifest:

       python tools/test_phase4_package_regression_v1.py

5. Whole-regression audit (P4-90):

       python tools/test_phase4_whole_regression_v1.py

## Reproducibility bound

Package bytes are reproducible from the same tree state. The external
toolchains are pinned by identity in the stage evidence; rebuilding the
fixture ELF and the native executable requires those exact toolchains.
""".replace("abd138ea...", PROGRAM_SHA256[:8]).replace(
    "755a004630...", SUPPORT_SHA256[:10])

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def parse_manifest(path: pathlib.Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in read_text(path).strip().splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match is None:
            raise AssertionError(f"malformed manifest line: {line[:80]}")
        entries.append((match.group(1), match.group(2)))
    return entries


def audit_source_integrity() -> None:
    check("source:root-manifest", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    root_entries = parse_manifest(ROOT / SOURCE_SUMS)
    check("source:root-manifest-entries", len(root_entries) == SOURCE_SUMS_ENTRIES)
    check("source:root-manifest-verified",
          all((ROOT / rel).is_file() and sha256_file(ROOT / rel) == digest
              for digest, rel in root_entries))
    check("source:phase3-manifest", sha256_file(ROOT / P3_SUMS) == P3_SUMS_SHA256)
    phase3_entries = parse_manifest(ROOT / P3_SUMS)
    check("source:phase3-manifest-entries", len(phase3_entries) == P3_SUMS_ENTRIES)
    phase4_entries = parse_manifest(ROOT / P4_SUMS)
    bad = [rel for digest, rel in phase4_entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:phase4-manifest-verified", phase4_entries and not bad)
    FINDINGS["source_integrity"] = {"root_entries": len(root_entries),
                                    "phase3_entries": len(phase3_entries),
                                    "phase4_entries": len(phase4_entries)}


def audit_evidence_generation() -> None:
    generated = EVIDENCE_DIR / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "REPRODUCE.md").write_bytes(REPRODUCE.encode("utf-8"))
    translation = fx.translate_fixture(fx.load_fixture_elf())
    check("evidence:program-sha256", translation.program_sha256 == PROGRAM_SHA256)
    check("evidence:support-sha256", translation.support_sha256 == SUPPORT_SHA256)
    (generated / "p4_fixture_program.c").write_bytes(
        translation.program_text.encode("utf-8"))
    (generated / "p4_fixture_support.c").write_bytes(
        translation.support_text.encode("utf-8"))
    check("evidence:program-identical",
          sha256_file(generated / "p4_fixture_program.c") == PROGRAM_SHA256)
    check("evidence:support-identical",
          sha256_file(generated / "p4_fixture_support.c") == SUPPORT_SHA256)
    check("evidence:reproduce-instructions",
          "Reproduction" in REPRODUCE and "test_phase4_whole_regression_v1.py" in REPRODUCE)


def audit_package() -> dict[str, Any]:
    first, manifest_a = pkg.build_package(ROOT)
    second, manifest_b = pkg.build_package(ROOT)
    check("package:byte-identical", first == second)
    check("package:manifest-identical", manifest_a == manifest_b)
    check("package:manifest-fingerprint",
          manifest_a["fingerprint"] == manifest_b["fingerprint"])
    verification = pkg.verify_package(first)
    check("package:verify-members", verification["member_count"] == manifest_a["member_count"])

    package_path = ROOT / PACKAGE_PATH
    package_path.parent.mkdir(parents=True, exist_ok=True)
    package_path.write_bytes(first)
    check("package:written", sha256_file(package_path) == sha256_bytes(first))
    check("package:size-bound", 0 < len(first) < 8 * 1024 * 1024)

    names = set(verification["members"])
    required = {
        f"{pkg.MEMBERS_ROOT}/control/STATE.md",
        f"{pkg.MEMBERS_ROOT}/control/STAGE_QUEUE.md",
        f"{pkg.MEMBERS_ROOT}/control/SOURCE_SHA256SUMS.txt",
        f"{pkg.MEMBERS_ROOT}/src/p4_runtime_abi_v1.py",
        f"{pkg.MEMBERS_ROOT}/src/p4_guest_memory_v1.py",
        f"{pkg.MEMBERS_ROOT}/src/p4_runtime_services_v1.py",
        f"{pkg.MEMBERS_ROOT}/src/p4_deterministic_io_v1.py",
        f"{pkg.MEMBERS_ROOT}/src/p4_platform_adapter_v1.py",
        f"{pkg.MEMBERS_ROOT}/src/p4_graphics_audio_v1.py",
        f"{pkg.MEMBERS_ROOT}/src/p4_fixture_exec_v1.py",
        f"{pkg.MEMBERS_ROOT}/src/p4_reference_fixture_v1.py",
        f"{pkg.MEMBERS_ROOT}/src/p4_package_v1.py",
        f"{pkg.MEMBERS_ROOT}/fixture/p4_fixture_main.c",
        f"{pkg.MEMBERS_ROOT}/fixture/input_plan.json",
        f"{pkg.MEMBERS_ROOT}/evidence/P4-10/REPRODUCE.md",
        f"{pkg.MEMBERS_ROOT}/evidence/P4-10/generated/p4_fixture_program.c",
        f"{pkg.MEMBERS_ROOT}/evidence/P4-10/generated/p4_fixture_support.c",
    }
    check("package:required-members", required <= names)
    gates = {name for name in names if "/gates/test_phase4_" in name}
    expected_gate_names = {
        "boundary", "runtime_abi", "guest_memory", "runtime_services",
        "deterministic_io", "platform_adapter", "graphics_audio", "fixture",
        "adapter_execution", "generic_runtime_proof", "package_regression",
    }
    check("package:all-gates",
          {f"{pkg.MEMBERS_ROOT}/gates/test_phase4_{name}_v1.py"
           for name in expected_gate_names} <= gates)
    for stage in range(0, 10):
        stage_dir = f"{pkg.MEMBERS_ROOT}/evidence/P4-{stage:02d}/"
        check(f"package:evidence-P4-{stage:02d}",
              any(name.startswith(stage_dir) for name in names))
    check("package:manifest-member",
          f"{pkg.MEMBERS_ROOT}/{pkg.MANIFEST_NAME}" in set(verification["archive_members"]))
    check("package:host-specific-exclusions",
          tuple(sorted(pkg.HOST_SPECIFIC_EXCLUSIONS))
          == (f"{pkg.MEMBERS_ROOT}/evidence/P4-07/build.json",)
          and all(name not in names for name in pkg.HOST_SPECIFIC_EXCLUSIONS))
    check("package:policy-exempt-members",
          pkg.is_policy_exempt(f"{pkg.MEMBERS_ROOT}/gates/test_phase4_boundary_v1.py")
          and pkg.is_policy_exempt(f"{pkg.MEMBERS_ROOT}/src/p4_package_v1.py")
          and not pkg.is_policy_exempt(f"{pkg.MEMBERS_ROOT}/control/STATE.md")
          and not pkg.is_policy_exempt(f"{pkg.MEMBERS_ROOT}/evidence/P4-09/RESULT.md")
          and f"{pkg.MEMBERS_ROOT}/src/p4_package_v1.py" in names)

    ARTIFACTS["package_manifest.json"] = (
        json.dumps(manifest_a, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ARTIFACTS["package_sha256.txt"] = (
        f"{sha256_bytes(first)}  {pkg.PACKAGE_NAME}\n"
        f"fingerprint {manifest_a['fingerprint']}\n"
        f"members {manifest_a['member_count']}\n").encode("utf-8")
    FINDINGS["package"] = {
        "sha256": sha256_bytes(first),
        "fingerprint": manifest_a["fingerprint"],
        "member_count": manifest_a["member_count"],
        "size": len(first),
        "host_specific_exclusions": sorted(pkg.HOST_SPECIFIC_EXCLUSIONS),
    }
    return verification


def audit_regressions() -> None:
    rows = []
    for name, script, marker in FAST_REGRESSIONS:
        completed = subprocess.run([sys.executable, script], cwd=str(ROOT),
                                   capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", timeout=900)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        check(f"{name}:returncode", completed.returncode == 0)
        check(f"{name}:stderr-empty", not stderr.strip())
        check(f"{name}:marker", marker in stdout)
        (EVIDENCE_DIR / f"{name}.txt").write_bytes(
            stdout.replace("\r\n", "\n").encode("utf-8"))
        rows.append({"name": name, "returncode": completed.returncode,
                     "stdout_sha256_lf": sha256_bytes(
                         stdout.replace("\r\n", "\n").encode("utf-8")),
                     "marker": marker})
    for relative in BOUNDARY_RECORDS:
        path = ROOT / relative
        check(f"boundary:{relative.split('/')[-1]}", path.is_file())
        document = json.loads(read_text(path))
        check(f"boundary:{relative.split('/')[-1]}:pass", document["status"] == "PASS")
        check(f"boundary:{relative.split('/')[-1]}:no-failure",
              document["failure"] is None)
    FINDINGS["regressions"] = rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-10 package gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-10")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P4-10 Reproducible Package Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        audit_source_integrity()
        banner("evidence_generation")
        audit_evidence_generation()
        banner("package")
        audit_package()
        banner("regressions")
        audit_regressions()
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
    for name, payload in ARTIFACTS.items():
        (EVIDENCE_DIR / name).write_bytes(payload)
    (EVIDENCE_DIR / "p4_10_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        print(f"{COMPAT_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
