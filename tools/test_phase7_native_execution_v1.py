#!/usr/bin/env python3
"""OpenRecomp Phase-7 native execution gate (P7-09).

Builds and runs generated host code for the public Phase-7 indirect-flow
fixture across the three runtime paths: exact (proven single target), finite
(proven four-target set, index 2) and unresolved (excluded from emission,
must fail closed at runtime). The original guest 6502 image is only ever data
in the runtime support; execution is generated host code through the typed
runtime ABI.

On success it emits::

    OPENRECOMP_P7_09=PASS
    OPENRECOMP_PHASE7_NATIVE_EXECUTION_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_native_execution_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-09
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL7 = ROOT / ".openrecomp-phase7"
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src"),
              str(CONTROL7 / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import adapters.nes6502 as nes  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p7_bank_reachability_v1 as bank_model  # noqa: E402
import p7_frontier_integration_v1 as integration  # noqa: E402
import p7_indirect_evidence_v1 as evidence  # noqa: E402
import p7_indirect_flow_fixture_v1 as fixture  # noqa: E402

STAGE = "P7-09"
STAGE_MARKER = "OPENRECOMP_P7_09"
FEATURE_MARKER = "OPENRECOMP_PHASE7_NATIVE_EXECUTION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_08_RECORD_REL = ".openrecomp-phase7/evidence/P7-08/p7_08_tests.json"
P7_08_GATE = "tools/test_phase7_frontier_integration_v1.py"

VARIANT_EXPECTATIONS = {
    "exact": {
        "selector": 0,
        "executable_sha256":
            "23679fb850d427951dc4f685b5322ccc9de3c4f50df5cd18fa97f2a2b83426ab",
        "program_sha256":
            "231a3a09924e94c7977ffaae71712ad9d48e443495c633ae2b6b96a8539b0b38",
        "steps": "38",
        "clock": "108",
        "ram_fnv1a64": "0xAA5AB26EB40CAD39",
        "state_fnv1a64": "0x9F99C6AE48D9D1FD",
    },
    "finite": {
        "selector": 1,
        "executable_sha256":
            "7da08a48b96394acb0c569c5c71142225c5fb6e0fa6c74b802978dae49405e77",
        "steps": "43",
        "clock": "123",
        "ram_fnv1a64": "0x7F6B5F2544B66B7F",
        "state_fnv1a64": "0xB9A21356FD7EF677",
    },
    "unresolved": {
        "selector": 2,
        "executable_sha256":
            "ea6bef2371f7246219298788167c763cb82effbe868510191deb66d3266f31d8",
        "steps": "33",
        "clock": "88",
        "pc": "0x8030",
    },
}

REGRESSIONS = ("tools/test_nes_rom_v1.py",)

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


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_observable(stdout: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    frames: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("frame["):
            frames.append(line)
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    return fields, frames


def run_regression(script: str, extra: list[str] | None = None) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, script, *(extra or [])],
                               cwd=str(ROOT), capture_output=True)
    stdout = completed.stdout
    stderr = completed.stderr
    markers = [line for line in stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "command": ["python", script, *(extra or [])],
        "returncode": completed.returncode,
        "stdout_bytes": len(stdout),
        "stdout_sha256_raw": sha256_bytes(stdout),
        "stdout_sha256_lf": sha256_bytes(stdout.replace(b"\r\n", b"\n")),
        "stderr_bytes": len(stderr),
        "stderr_empty": not stderr,
        "markers": markers,
    }


def build_variant(name: str, selector: int, metadata: dict,
                  scratch: pathlib.Path) -> dict[str, Any]:
    rom, fresh_metadata = fixture.build()
    if canonical(fresh_metadata) != canonical(metadata):
        raise AssertionError("fixture metadata changed between variants")
    patched = fixture.patched_rom(rom, metadata, selector)
    inventory = fixture.inventory(patched)
    prg = patched[16:16 + inventory["prg_bytes"]]
    roots = [inventory["vectors"][key] for key in ("reset", "nmi", "irq")]
    banks = metadata["prg_banks"]
    bank_report = bank_model.analyze(prg, banks, roots)
    identifiers: dict[int, list[dict]] = {}
    for entry in bank_report["instructions"]:
        identifiers.setdefault(entry["address"], []).append(entry)
    image = fixture.cpu_image_for_bank(patched, inventory, 1)
    evidence_report = evidence.analyze_image(
        image, prg, banks, metadata["sites"],
        bank_identities=identifiers, roots=roots)
    assignment = {metadata["sites"][1]:
                  [1, metadata["labels"]["finite_target_b"]]}
    specialized = integration.specialize(prg, banks, roots, bank_report,
                                         evidence_report, assignment)
    emission = integration.emit_host(
        patched, inventory, prg, banks, specialized, {
            "rom_sha256": metadata["rom_sha256"],
            "vectors": inventory["vectors"],
            "prg_banks": banks,
            "chr_banks": metadata["chr_banks"],
            "prg_size": inventory["prg_bytes"],
            "chr_size": inventory["chr_bytes"],
        })
    workspace = scratch / name
    if workspace.exists():
        shutil.rmtree(workspace)
    comparison = integration.build_native(
        emission, fixture_id=f"p7-09-{name}", workspace=workspace)
    executable = workspace / "run1" / "program.exe"
    if not executable.is_file():
        raise AssertionError(f"{name}: executable is missing")
    runs = []
    for _index in range(3):
        completed = subprocess.run([str(executable)], capture_output=True,
                                   text=True, encoding="utf-8",
                                   errors="replace", timeout=600)
        runs.append({"returncode": completed.returncode,
                     "stdout": completed.stdout,
                     "stderr": completed.stderr})
    fields, frames = parse_observable(runs[0]["stdout"])
    return {
        "name": name,
        "selector": selector,
        "classification": comparison.classification.name,
        "executable_reproducible": comparison.executable_reproducible,
        "executable_sha256": sha256_bytes(executable.read_bytes()),
        "program_sha256": emission["host_program_sha256"],
        "support_sha256": emission["support_sha256"],
        "instructions": emission["instructions"],
        "frontier_count": specialized["frontier_count"],
        "frontier": specialized["frontier"],
        "host_program": emission["host_program"],
        "runs": runs,
        "fields": fields,
        "frames": frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-09 native execution gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-09")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-09"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-09 Native Execution Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = CONTROL7 / "SOURCE_SHA256SUMS.txt"
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)

        banner("anchors")
        check("anchor:p7-08-record-pass",
              read_json(ROOT / P7_08_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-09 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("fixture")
        rom, metadata = fixture.build()
        inventory = fixture.inventory(rom)
        check("fixture:inventory",
              inventory["phase6"]["status"] == "SUPPORTED_MMC1"
              and len(metadata["sites"]) == 3)
        FINDINGS["fixture"] = {"rom_sha256": metadata["rom_sha256"],
                               "sites": metadata["sites"]}

        variants = {}
        for name, expectation in VARIANT_EXPECTATIONS.items():
            banner(f"variant_{name}")
            variant = build_variant(name, expectation["selector"], metadata,
                                    SCRATCH)
            variants[name] = variant
            host = variant.pop("host_program")
            check(f"{name}:reproducible-build",
                  variant["classification"] == "EXECUTABLE_REPRODUCIBLE"
                  and variant["executable_reproducible"] is True)
            check(f"{name}:executable-identity",
                  variant["executable_sha256"]
                  == expectation["executable_sha256"])
            check(f"{name}:deterministic-runs",
                  len({run["stdout"] for run in variant["runs"]}) == 1
                  and len({run["stderr"] for run in variant["runs"]}) == 1
                  and all(run["stderr"] == "" for run in variant["runs"]))
            fields = variant["fields"]
            check(f"{name}:host-is-switch-machine",
                  "switch (g_pc)" in host
                  and f"case 0x{metadata['sites'][2]:04X}u:" not in host
                  and f"case 0x{metadata['labels']['exact_target']:04X}u:"
                  in host)
            check(f"{name}:bank-switching-active",
                  fields.get("mmc1_regs") == "0C000001"
                  and fields.get("prg_window_8000") == "1"
                  and fields.get("prg_window_c000") == "3")
            if name in ("exact", "finite"):
                check(f"{name}:completed",
                      fields.get("failed") == "0"
                      and fields.get("exit") == "1"
                      and fields.get("pc")
                      == f"0x{metadata['exit_site']:04X}"
                      and fields.get("exit_arg")
                      == f"0x{metadata['exit_site']:08X}"
                      and fields.get("steps") == expectation["steps"]
                      and fields.get("clock") == expectation["clock"]
                      and fields.get("ram_fnv1a64")
                      == expectation["ram_fnv1a64"]
                      and fields.get("state_fnv1a64")
                      == expectation["state_fnv1a64"])
            else:
                check(f"{name}:fail-closed",
                      fields.get("failed") == "1"
                      and fields.get("exit") == "0"
                      and fields.get("error")
                      == "pc outside the emitted image"
                      and fields.get("pc") == expectation["pc"]
                      and fields.get("steps") == expectation["steps"])
            variant.pop("runs")
        check("differential:paths-distinct",
              variants["exact"]["fields"]["ram_fnv1a64"]
              != variants["finite"]["fields"]["ram_fnv1a64"]
              and variants["exact"]["fields"]["state_fnv1a64"]
              != variants["finite"]["fields"]["state_fnv1a64"])
        FINDINGS["variants"] = variants

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_08_regression = run_regression(
            P7_08_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-09/regression_p7_08"])
        check("regression:p7-08:exit", p7_08_regression["returncode"] == 0)
        check("regression:p7-08:stderr", p7_08_regression["stderr_empty"])
        check("regression:p7-08:marker",
              any(marker == "OPENRECOMP_P7_08=PASS"
                  for marker in p7_08_regression["markers"]))
        regressions.append(p7_08_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("native_execution.json", {
            "stage": STAGE,
            "fixture": FINDINGS["fixture"],
            "variants": variants,
            "guest_execution": {
                "host_code_only": True,
                "note": "the original 6502 image is data in the runtime "
                        "support; execution is emitted host code",
            },
            "public_claim": metadata["public_claim"],
        })
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(path.suffix.lower() in (".nes", ".fds", ".unf", ".unif")
                      for path in SCRATCH.rglob("*") if path.is_file()))
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
            "playability": f"{PLAYABILITY_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p7_09_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    print(f"{PLAYABILITY_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
