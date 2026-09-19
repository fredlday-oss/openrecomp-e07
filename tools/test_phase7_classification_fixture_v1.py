#!/usr/bin/env python3
"""OpenRecomp Phase-7 public classification-fixture gate (P7-03).

P7-02 proved the `0x7C` byte is data, so P7-03 proves the classification
mechanism end-to-end on an original Apache-2.0 public NES fixture instead of
adding false undocumented-opcode semantics:

* the fixture reproduces the inline-dispatch idiom (jsr followed by an inline
  pointer table whose first byte is `0x7C`, return-address-consuming
  dispatcher, documented code resume);
* the frozen classifier returns `DATA_NOT_CODE` for the table base with the
  same structural evidence as the private image;
* the frozen independent 6502 reference core executes the fixture for
  selectors 0/1/2 and the independently structured dispatch model predicts the
  same targets and markers;
* the frozen decoder stays unchanged (151 documented opcodes, `0x7C` absent).

On success it emits::

    OPENRECOMP_P7_03=PASS
    OPENRECOMP_PHASE7_OPCODE_FIXTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_classification_fixture_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-03
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
import p6_reference_v1 as frozen_reference  # noqa: E402
import p7_opcode_7c_v1 as classification  # noqa: E402
import p7_classification_fixture_v1 as fixture  # noqa: E402
import p7_dispatch_reference_v1 as dispatch_reference  # noqa: E402

STAGE = "P7-03"
STAGE_MARKER = "OPENRECOMP_P7_03"
FEATURE_MARKER = "OPENRECOMP_PHASE7_OPCODE_FIXTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_02_RECORD_REL = ".openrecomp-phase7/evidence/P7-02/p7_02_tests.json"
P7_02_GATE = "tools/test_phase7_opcode_classification_v1.py"
P7_01_RECORD_REL = ".openrecomp-phase7/evidence/P7-01/p7_01_tests.json"

EXPECTED_MARKERS = {0: 0x10, 1: 0x11, 2: 0x12}
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


def canonical_text(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-03 public classification-fixture gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-03")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-03"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-03 Public Classification Fixture Gate ===", flush=True)
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
        check("anchor:p7-01-record-pass",
              read_json(ROOT / P7_01_RECORD_REL)["status"] == "PASS")
        check("anchor:p7-02-record-pass",
              read_json(ROOT / P7_02_RECORD_REL)["status"] == "PASS")
        check("anchor:decoder-unchanged",
              len(nes.OPCODES) == 151
              and classification.TARGET_OPCODE not in nes.OPCODES)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-03 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("fixture_build")
        rom_a, metadata_a = fixture.build()
        rom_b, metadata_b = fixture.build()
        check("fixture:deterministic",
              rom_a == rom_b
              and canonical(metadata_a) == canonical(metadata_b))
        check("fixture:license-and-origin",
              metadata_a["license"] == "Apache-2.0"
              and metadata_a["origin"] == "original"
              and metadata_a["source"]
              == ".openrecomp-phase7/fixture/p7_inline_dispatch_fixture.asm")
        source_text = fixture.ASM_PATH.read_text(encoding="utf-8")
        check("fixture:source-provenance",
              "Apache-2.0" in source_text
              and "original work" in source_text
              and "no third-party or console-derived program data" in source_text)
        check("fixture:assembled-cross-checked",
              metadata_a["instruction_count"] > 0
              and metadata_a["instructions_cross_checked"]
              == metadata_a["instruction_count"])
        check("fixture:mapper-configuration",
              metadata_a["mapper"] == 1
              and metadata_a["mirroring"] == "horizontal"
              and metadata_a["prg_banks"] == 2
              and metadata_a["chr_banks"] == 1)
        inventory = fixture.inventory(rom_a)
        check("fixture:inventory-supported",
              inventory["phase6"]["status"] == "SUPPORTED_MMC1"
              and inventory["mapper"] == 1
              and inventory["prg_bytes"] == 0x8000
              and inventory["chr_bytes"] == 0x2000)
        vectors = inventory["vectors"]
        labels = metadata_a["labels"]
        check("fixture:vectors",
              vectors["reset"] == labels["reset"]
              and vectors["nmi"] == labels["nmi_handler"]
              and vectors["irq"] == labels["irq_handler"])
        FINDINGS["fixture"] = {
            "rom_sha256": metadata_a["rom_sha256"],
            "rom_size": metadata_a["rom_size"],
            "prg_sha256": metadata_a["prg_sha256"],
            "chr_sha256": metadata_a["chr_sha256"],
            "source_sha256": metadata_a["source_sha256"],
            "instruction_count": metadata_a["instruction_count"],
        }

        banner("classification_mechanism")
        mechanism = metadata_a["mechanism"]
        image = fixture.cpu_image(rom_a, inventory)
        roots = [vectors["reset"], vectors["nmi"], vectors["irq"]]
        classification_record = classification.classify(
            image, mechanism["table_base"], roots)
        check("classify:data-not-code",
              classification_record["classification"] == "DATA_NOT_CODE"
              and classification_record["address"] == mechanism["table_base"])
        check("classify:predecessor",
              classification_record["predecessors"]
              == [{"address": mechanism["call_site"], "op": "jsr",
                   "edge": "fallthrough"}])
        check("classify:callee-consumes",
              classification_record["callee"]["address"]
              == mechanism["dispatch_entry"]
              and classification_record["callee"]["consumes_return_address"]
              is True)
        check("classify:inline-table",
              tuple(classification_record["inline_table"]["targets"])
              == tuple(mechanism["targets"])
              and classification_record["inline_table"]["entries"] == 3
              and classification_record["inline_table"]["resume_address"]
              == mechanism["resume_code"])
        check("classify:code-resume",
              classification_record["code_resume"]["address"]
              == mechanism["resume_code"]
              and classification_record["code_resume"]["first_op"] == "lda")
        check("classify:table-first-byte",
              image[mechanism["table_base"]] == classification.TARGET_OPCODE)
        FINDINGS["classification"] = {
            "classification": classification_record["classification"],
            "targets": classification_record["inline_table"]["targets"],
            "resume_address": classification_record["inline_table"]["resume_address"],
        }

        banner("independent_dispatch_reference")
        shared = sorted(set(dispatch_reference.P7_COSTS)
                        & set(frozen_reference.REFERENCE_COSTS))
        check("costs:cross-check-shared",
              all(dispatch_reference.P7_COSTS[opcode]
                  == frozen_reference.REFERENCE_COSTS[opcode]
                  for opcode in shared))
        predictions = {}
        runs = {}
        for selector in (0, 1, 2):
            patched = fixture.patched_rom(rom_a, metadata_a, selector)
            patched_inventory = fixture.inventory(patched)
            predicted = dispatch_reference.predict_target(
                image, mechanism["call_site"], selector)
            expected = mechanism["targets"][selector]
            check(f"dispatch:predicted-selector-{selector}",
                  predicted == expected)
            run = dispatch_reference.run(
                patched, patched_inventory, exit_site=mechanism["exit_site"])
            check(f"reference:exit-selector-{selector}",
                  run["exit_reached"] is True
                  and run["pc"] == mechanism["exit_site"])
            check(f"reference:marker-selector-{selector}",
                  run["markers"]["marker"] == EXPECTED_MARKERS[selector]
                  and run["markers"]["plain_out"] == 0x22)
            check(f"reference:target-executed-selector-{selector}",
                  predicted in run["executed_addresses"])
            predictions[str(selector)] = predicted
            runs[str(selector)] = {
                "predicted_target": predicted,
                "marker": run["markers"]["marker"],
                "selector_out": run["markers"]["selector"],
                "plain_out": run["markers"]["plain_out"],
                "steps": run["steps"],
                "clock": run["clock"],
                "pc": run["pc"],
                "executed_count": run["executed_count"],
                "exit_reached": run["exit_reached"],
            }
        check("differential:static-models-agree",
              tuple(predictions[str(index)]
                    for index in range(3)) == tuple(mechanism["targets"]))
        check("differential:dynamic-matches-static",
              all(runs[str(selector)]["marker"] == EXPECTED_MARKERS[selector]
                  and runs[str(selector)]["predicted_target"]
                  in classification_record["inline_table"]["targets"]
                  for selector in range(3)))
        try:
            dispatch_reference.predict_target(image, mechanism["call_site"], 3)
        except dispatch_reference.P7DispatchError:
            check("edge:out-of-range-selector-fail-closed", True)
        else:
            raise AssertionError("edge:out-of-range-selector-fail-closed")

        banner("negative")
        tampered = bytearray(image)
        tampered[mechanism["dispatcher_pla_addresses"][0]] = 0xEA
        tampered_result = classification.classify(
            bytes(tampered), mechanism["table_base"], roots)
        check("negative:tampered-dispatcher-ambiguous",
              tampered_result["classification"] == "AMBIGUOUS"
              and "does not consume" in tampered_result["reason"])
        for bad_selector in (-1, True, "1"):
            try:
                dispatch_reference.predict_target(
                    image, mechanism["call_site"], bad_selector)
            except dispatch_reference.P7DispatchError:
                check(f"negative:bad-selector-{bad_selector!r}", True)
            else:
                raise AssertionError(f"negative:bad-selector-{bad_selector!r}")

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_02_regression = run_regression(
            P7_02_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-03/regression_p7_02"])
        check("regression:p7-02:exit", p7_02_regression["returncode"] == 0)
        check("regression:p7-02:stderr", p7_02_regression["stderr_empty"])
        check("regression:p7-02:marker",
              any(marker == "OPENRECOMP_P7_02=PASS"
                  for marker in p7_02_regression["markers"]))
        regressions.append(p7_02_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("classification_fixture.json", {
            "stage": STAGE,
            "fixture": metadata_a["fixture"],
            "license": metadata_a["license"],
            "origin": metadata_a["origin"],
            "source": metadata_a["source"],
            "source_sha256": metadata_a["source_sha256"],
            "rom_sha256": metadata_a["rom_sha256"],
            "rom_size": metadata_a["rom_size"],
            "prg_sha256": metadata_a["prg_sha256"],
            "chr_sha256": metadata_a["chr_sha256"],
            "mapper": metadata_a["mapper"],
            "mirroring": metadata_a["mirroring"],
            "prg_banks": metadata_a["prg_banks"],
            "chr_banks": metadata_a["chr_banks"],
            "vectors": vectors,
            "mechanism": mechanism,
            "classification": {
                "classification": classification_record["classification"],
                "address": classification_record["address"],
                "predecessors": classification_record["predecessors"],
                "callee": classification_record["callee"],
                "inline_table": classification_record["inline_table"],
                "code_resume": classification_record["code_resume"],
            },
            "predictions": predictions,
            "reference_runs": runs,
            "cost_cross_check": {
                "shared_opcodes": shared,
                "all_match": True,
            },
            "decoder_unchanged": {
                "documented_opcodes": len(nes.OPCODES),
                "opcode_0x7c_supported": classification.TARGET_OPCODE
                in nes.OPCODES,
            },
            "semantics_added": False,
            "public_claim": metadata_a["public_claim"],
        })
        private_bytes = private_fixture.PRIVATE_ROM.read_bytes()
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", private_bytes not in data)
        check("hygiene:no-rom-extension-in-scratch",
              not any(path.suffix.lower() in (".nes", ".fds", ".unf", ".unif")
                      for path in SCRATCH.rglob("*") if path.is_file()))
        check("hygiene:public-fixture-not-written-to-worktree",
              not any(path.suffix.lower() in (".nes",)
                      for path in (ROOT / ".openrecomp-phase7").rglob("*")
                      if path.is_file()))
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
    (EVIDENCE_DIR / "p7_03_tests.json").write_text(
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
