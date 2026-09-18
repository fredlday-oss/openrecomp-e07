#!/usr/bin/env python3
"""OpenRecomp Phase-5 reproducible NES package gate (P5-12).

Verifies the deterministic public package: byte-identical rebuilds, member
manifest completeness, UTF-8/LF text policy, the private-fixture exclusion
scan, and a self-contained native rebuild from the packaged generated sources
that reproduces the canonical P5-08 observable.

On success it emits::

    OPENRECOMP_P5_12=PASS
    OPENRECOMP_PHASE5_PACKAGE_V1=PASS tests=<count>
    OPENRECOMP_PHASE5_NES_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / ".openrecomp-phase5" / "src"), str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p5_emit_v1 as emit  # noqa: E402
import p5_package_v1 as package  # noqa: E402

STAGE = "P5-12"
STAGE_MARKER = "OPENRECOMP_P5_12"
FEATURE_MARKER = "OPENRECOMP_PHASE5_PACKAGE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE5_NES_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE5_GENERAL_NES_COMPATIBILITY"

PACKAGE_SHA256 = "447f72cc616d80fa72e3681c5acd34b00833d7e3fe3fb5bf8bf3230347cc4c13"
PACKAGE_FINGERPRINT = "dfabe4ffc3517b7782fc85d0a4ed16e640991a33e726664a5dcb32608a4cf298"
PACKAGE_MEMBERS = 169
ZIG = ROOT / ".openrecomp-phase3" / "tools" / "zig" / "zig.exe"
EXPECTED_OBSERVABLE = {
    "failed": "0",
    "exit": "1",
    "steps": "90904",
    "frames": "11",
    "nmi": "8",
    "clock": "298327",
    "state_fnv1a64": "0x440A095E452B3BA9",
}

REGRESSIONS = (
    ("tools/test_phase5_tmnt_private_v1.py",
     ["--evidence-dir", ".openrecomp-phase5/scratch/regression_p5_12_p5_11"]),
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


def parse_observable(stdout: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields


def main() -> int:
    parser = argparse.ArgumentParser(description="P5-12 package gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase5/evidence/P5-12")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P5-12 Reproducible NES Package Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("package")
        data_a, manifest_a = package.build_package()
        data_b, manifest_b = package.build_package()
        check("package:reproducible-bytes", data_a == data_b)
        check("package:reproducible-manifest",
              canonical(manifest_a) == canonical(manifest_b))
        check("package:members", manifest_a["member_count"] == PACKAGE_MEMBERS)
        check("package:fingerprint", manifest_a["fingerprint"] == PACKAGE_FINGERPRINT)
        check("package:sha256", sha256_bytes(data_a) == PACKAGE_SHA256)
        package.write_package()

        banner("members")
        with zipfile.ZipFile(__import__("io").BytesIO(data_a)) as archive:
            names = archive.namelist()
            check("members:sorted", names == sorted(names))
            check("members:no-private-evidence",
                  not any(name.startswith("evidence/P5-11/") for name in names))
            check("members:no-binaries",
                  not any(name.lower().endswith(
                      (".nes", ".fds", ".unf", ".unif", ".exe", ".obj", ".bin"))
                      for name in names))
            required = [
                "REPRODUCE.md", package.MANIFEST_NAME,
                "fixture/p5_public_fixture.asm",
                "generated/p5_nes_program.c", "generated/p5_nes_support.c",
                "gates/test_phase5_reference_equiv_v1.py",
                "src/p5_emit_v1.py", "src/p5_support_v1.py",
            ]
            for name in package.CONTROL_FILES:
                required.append(f"control/{name}")
            for stage in package.EVIDENCE_STAGES:
                required.append(f"evidence/{stage}/RESULT.md")
            missing = [name for name in required if name not in names]
            check("members:required", missing == [])
            listed = {item["name"]: item for item in manifest_a["members"]}
            check("members:manifest-listed", set(listed) | {package.MANIFEST_NAME}
                  == set(names))
            for name in names:
                payload = archive.read(name)
                try:
                    payload.decode("utf-8")
                except UnicodeDecodeError:
                    raise AssertionError(f"{name}: not UTF-8")
                if b"\r" in payload:
                    raise AssertionError(f"{name}: CR byte present")
                if name != package.MANIFEST_NAME:
                    item = listed[name]
                    if item["size"] != len(payload) or item["sha256"] != sha256_bytes(payload):
                        raise AssertionError(f"{name}: manifest mismatch")
            check("members:all-text-and-hashes", True)

        banner("exclusions")
        probe = package._private_probe()
        rom_bytes = package.PRIVATE_ROM.read_bytes()
        for name in names:
            payload = zipfile.ZipFile(__import__("io").BytesIO(data_a)).read(name)
            check(f"exclusion:probe:{name}", probe not in payload)
            if rom_bytes in payload:
                raise AssertionError(f"{name}: private ROM bytes packaged")
        check("exclusions:no-private-bytes",
              all(rom_bytes not in zipfile.ZipFile(
                  __import__("io").BytesIO(data_a)).read(name) for name in names))

        banner("self_contained_rebuild")
        check("rebuild:zig-present", ZIG.is_file())
        with tempfile.TemporaryDirectory(prefix="p5_pkg_") as tmp:
            tmp_path = pathlib.Path(tmp)
            with zipfile.ZipFile(__import__("io").BytesIO(data_a)) as archive:
                program = archive.read("generated/p5_nes_program.c")
                support = archive.read("generated/p5_nes_support.c")
            (tmp_path / "program.c").write_bytes(program)
            (tmp_path / "support.c").write_bytes(support)
            executable = tmp_path / "program.exe"
            completed = subprocess.run(
                [str(ZIG), "cc", "-std=c11", "-O1", "-o", str(executable),
                 str(tmp_path / "program.c"), str(tmp_path / "support.c")],
                capture_output=True, text=True, timeout=600)
            check("rebuild:compile", completed.returncode == 0)
            run = subprocess.run([str(executable)], capture_output=True, text=True,
                                 timeout=600)
            check("rebuild:run", run.returncode == 0)
            fields = parse_observable(run.stdout)
            check("rebuild:observable",
                  all(fields.get(key) == value
                      for key, value in EXPECTED_OBSERVABLE.items()))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("package_manifest.json", manifest_a)
        write_json("verification.json", {
            "stage": STAGE,
            "package_sha256": PACKAGE_SHA256,
            "fingerprint": PACKAGE_FINGERPRINT,
            "members": PACKAGE_MEMBERS,
            "zip_size": len(data_a),
            "rebuild": dict(EXPECTED_OBSERVABLE),
        })
        write_json("regressions.json", {"stage": STAGE, "regressions": regressions})
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
    (EVIDENCE_DIR / "p5_12_tests.json").write_text(
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
