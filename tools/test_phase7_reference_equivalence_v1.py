#!/usr/bin/env python3
"""OpenRecomp Phase-7 independent reference equivalence gate (P7-10).

Compares the generated native execution of the public indirect-flow fixture
(exact and finite proven paths) against the independently structured reference
execution over: CPU state, RAM, mapper/bank state, PPU state, controller
transcript, interrupt counts, indirect-control-flow transcript, translation/
service transcript and bounded final state. Requires exact bounded
equivalence except for the documented dispatch-specialization timing delta
(a resolved `jmp ($E2)` is emitted as a direct jump: -2 cycles per executed
resolved site; cycle accuracy is explicitly out of scope).

The unresolved path is a documented policy divergence: the native program
fails closed at the excluded site while the reference executes it.

On success it emits::

    OPENRECOMP_P7_10=PASS
    OPENRECOMP_PHASE7_REFERENCE_EQUIVALENCE_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_reference_equivalence_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-10
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
import p7_dispatch_reference_v1 as reference  # noqa: E402
import p7_frontier_integration_v1 as integration  # noqa: E402
import p7_indirect_evidence_v1 as evidence  # noqa: E402
import p7_indirect_flow_fixture_v1 as fixture  # noqa: E402

STAGE = "P7-10"
STAGE_MARKER = "OPENRECOMP_P7_10"
FEATURE_MARKER = "OPENRECOMP_PHASE7_REFERENCE_EQUIVALENCE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_09_RECORD_REL = ".openrecomp-phase7/evidence/P7-09/p7_09_tests.json"
P7_09_GATE = "tools/test_phase7_native_execution_v1.py"

EQUIVALENT_VARIANTS = {
    "exact": {"selector": 0, "expected_target": "exact_target"},
    "finite": {"selector": 1, "expected_target": "finite_target_b"},
}
TIMING_DELTA_PER_SITE = 2

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


def build_native_variant(name: str, selector: int, metadata: dict,
                         scratch: pathlib.Path) -> tuple:
    rom, _fresh = fixture.build()
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
        emission, fixture_id=f"p7-10-{name}", workspace=workspace)
    executable = workspace / "run1" / "program.exe"
    if not executable.is_file():
        raise AssertionError(f"{name}: executable is missing")
    outputs = []
    for _index in range(3):
        completed = subprocess.run([str(executable)], capture_output=True,
                                   text=True, encoding="utf-8",
                                   errors="replace", timeout=600)
        outputs.append(completed.stdout)
    fields, frames = parse_observable(outputs[0])
    return patched, inventory, comparison, executable, fields, frames, outputs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-10 reference equivalence gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-10")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-10"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-10 Independent Reference Equivalence Gate ===", flush=True)
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
        check("anchor:p7-09-record-pass",
              read_json(ROOT / P7_09_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged", len(nes.OPCODES) == 151)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-10 |" in queue)
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
        records = {}

        for name, expectation in EQUIVALENT_VARIANTS.items():
            banner(f"variant_{name}")
            patched, inventory, comparison, executable, fields, frames, \
                outputs = build_native_variant(name, expectation["selector"],
                                               metadata, SCRATCH)
            check(f"{name}:native-deterministic",
                  len(set(outputs)) == 1)
            reference_result = reference.run(
                patched, inventory, exit_site=metadata["exit_site"],
                indirect_sites=tuple(metadata["sites"]))
            reference_fields = reference_result["fields"]
            check(f"{name}:field-sets",
                  set(reference_fields) == set(fields) - {"exit_word"})
            mismatches = [key for key in reference_fields
                          if key != "clock"
                          and fields[key] != reference_fields[key]]
            check(f"{name}:exact-fields", mismatches == [])
            delta = int(fields["clock"]) - int(reference_fields["clock"])
            check(f"{name}:timing-delta",
                  delta == -TIMING_DELTA_PER_SITE)
            check(f"{name}:frames",
                  frames == reference_result["frames"]
                  and len(frames) == 1)
            check(f"{name}:exit-word",
                  reference_result["exit_word"] == "0000000000000000"
                  and fields["exit_word"] == reference_result["exit_word"])
            expected_target = metadata["labels"][expectation["expected_target"]]
            transcript = reference_result["indirect_transcript"]
            check(f"{name}:indirect-transcript",
                  len(transcript) == 1
                  and transcript[0]["target"] == expected_target
                  and transcript[0]["target"]
                  in reference_result["executed_addresses"])
            check(f"{name}:service-transcript",
                  reference_result["service_transcript"]
                  == [{"service": "p7.exit", "argc": 1,
                       "args": [metadata["exit_site"]]}])
            check(f"{name}:native-at-exit",
                  fields["failed"] == "0" and fields["exit"] == "1"
                  and fields["pc"] == f"0x{metadata['exit_site']:04X}")
            records[name] = {
                "selector": expectation["selector"],
                "native_fields": fields,
                "reference_fields": reference_fields,
                "clock_delta": delta,
                "frames": frames,
                "indirect_transcript": transcript,
                "excluded_from_equality": ["clock"],
                "timing_note": "a resolved jmp ($E2) is emitted as a direct "
                               "jump; -2 cycles per executed resolved site "
                               "(cycle accuracy is out of scope)",
                "executable_sha256": sha256_bytes(executable.read_bytes()),
                "build_classification": comparison.classification.name,
            }

        banner("unresolved_policy_divergence")
        patched, inventory, comparison, executable, fields, frames, \
            outputs = build_native_variant("unresolved", 2, metadata, SCRATCH)
        reference_result = reference.run(
            patched, inventory, exit_site=metadata["exit_site"],
            indirect_sites=tuple(metadata["sites"]))
        check("unresolved:native-fail-closed",
              fields["failed"] == "1" and fields["exit"] == "0"
              and fields["error"] == "pc outside the emitted image"
              and int(fields["pc"], 16) == metadata["sites"][2])
        check("unresolved:reference-executes",
              reference_result["exit_reached"] is True
              and len(reference_result["indirect_transcript"]) == 1
              and reference_result["indirect_transcript"][0]["target"]
              == metadata["labels"]["fixed_target"])
        check("unresolved:divergence-documented",
              fields["failed"] != reference_result["fields"]["failed"])
        records["unresolved"] = {
            "selector": 2,
            "native_fields": fields,
            "reference_fields": reference_result["fields"],
            "policy": "native emits no host case for the unresolved site and "
                      "fails closed at 0x8030; the reference executes it and "
                      "reaches the runtime target $C200",
            "indirect_transcript": reference_result["indirect_transcript"],
            "build_classification": comparison.classification.name,
        }

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_09_regression = run_regression(
            P7_09_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-10/regression_p7_09"])
        check("regression:p7-09:exit", p7_09_regression["returncode"] == 0)
        check("regression:p7-09:stderr", p7_09_regression["stderr_empty"])
        check("regression:p7-09:marker",
              any(marker == "OPENRECOMP_P7_09=PASS"
                  for marker in p7_09_regression["markers"]))
        regressions.append(p7_09_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("reference_equivalence.json", {
            "stage": STAGE,
            "fixture": {
                "rom_sha256": metadata["rom_sha256"],
                "sites": metadata["sites"],
                "exit_site": metadata["exit_site"],
            },
            "variants": records,
            "equivalence_scope": [
                "CPU state", "RAM", "PPU state",
                "mapper/bank state", "controller transcript",
                "interrupt counts", "indirect-control-flow transcript",
                "translation/service transcript", "bounded final state",
            ],
            "excluded_observable": {
                "clock": "dispatch specialization reduces the emitted cost by "
                         "2 cycles per executed resolved indirect site; cycle "
                         "accuracy is explicitly out of scope",
            },
            "claim": "exact bounded equivalence for the proven public paths; "
                     "the unresolved path diverges by design (native fails "
                     "closed)",
            "public_claim": metadata["public_claim"],
        })
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(path.suffix.lower() in (".nes", ".fds", ".unf", ".unif")
                      for path in SCRATCH.rglob("*") if path.is_file()))
        FINDINGS["variants"] = {name: {
            "clock_delta": record.get("clock_delta"),
            "executable_sha256": record.get("executable_sha256"),
            "policy": record.get("policy"),
        } for name, record in records.items()}
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
    (EVIDENCE_DIR / "p7_10_tests.json").write_text(
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
