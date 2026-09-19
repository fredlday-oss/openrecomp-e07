#!/usr/bin/env python3
"""OpenRecomp Phase-7 undocumented-opcode classification gate (P7-02).

Classifies the `0x7C` byte at `0xC570` in the private image from structural
evidence (control-flow predecessor, callee return-address consumption, inline
pointer table, code resume) and proves the classifier on original synthetic
public images. No undocumented-opcode semantics are implemented and no
universal undocumented-opcode claim is made.

On success it emits::

    OPENRECOMP_P7_02=PASS
    OPENRECOMP_PHASE7_OPCODE_CLASSIFICATION_V1=PASS tests=<count>
    OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE7_TMMT_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase7_opcode_classification_v1.py \
        --evidence-dir .openrecomp-phase7/evidence/P7-02
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
import p7_opcode_7c_v1 as classification  # noqa: E402
import p7_frontier_rederive_v1 as rederive_module  # noqa: E402

STAGE = "P7-02"
STAGE_MARKER = "OPENRECOMP_P7_02"
FEATURE_MARKER = "OPENRECOMP_PHASE7_OPCODE_CLASSIFICATION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE7_TRANSLATION_FRONTIER_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE7_GENERAL_NES_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE7_TMMT_PLAYABILITY"

P7_01_RECORD_REL = ".openrecomp-phase7/evidence/P7-01/p7_01_tests.json"
P7_01_GATE = "tools/test_phase7_frontier_rederive_v1.py"

EXPECTED_PREDECESSORS = [{"address": 0xC56D, "op": "jsr",
                          "edge": "fallthrough"}]
EXPECTED_TABLE_TARGETS = (0xC57C, 0xC644, 0xC679, 0xC686, 0xCB24, 0xC6B6)
EXPECTED_NESTED_TARGETS = (0xC589, 0xC5B4, 0xC5FE, 0xC62C)

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


def synthetic(segments: dict[int, bytes]) -> bytes:
    image = bytearray(0x10000)
    for address, payload in segments.items():
        image[address:address + len(payload)] = payload
    return bytes(image)


def dispatch_callee() -> bytes:
    # PLA; STA $00; PLA; STA $01; LDA ($00),Y; JMP ($0002)
    return bytes([0x68, 0x85, 0x00, 0x68, 0x85, 0x01, 0xB1, 0x00, 0x6C,
                  0x02, 0x00])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P7-02 undocumented-opcode classification gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase7/evidence/P7-02")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES, SCRATCH
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH = CONTROL7 / "scratch" / "P7-02"
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P7-02 Undocumented Opcode Classification Gate ===", flush=True)
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
        check("anchor:p6-10-pipeline",
              sha256_file(ROOT / rederive_module.P6_10_PIPELINE_REL)
              == rederive_module.P6_10_PIPELINE_SHA256)
        check("anchor:p6-13-frontier",
              sha256_file(ROOT / rederive_module.P6_13_FRONTIER_REL)
              == rederive_module.P6_13_FRONTIER_SHA256)
        check("anchor:private-image",
              private_fixture.PRIVATE_ROM.is_file()
              and private_fixture.PRIVATE_ROM.stat().st_size
              == rederive_module.PRIVATE_SIZE
              and sha256_file(private_fixture.PRIVATE_ROM)
              == rederive_module.PRIVATE_IMAGE_SHA256)
        check("anchor:decoder-unchanged",
              len(nes.OPCODES) == 151
              and classification.TARGET_OPCODE not in nes.OPCODES)

        banner("control_plane")
        state = (CONTROL7 / "STATE.md").read_text(encoding="utf-8")
        queue = (CONTROL7 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P7-02 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue
              and f"{TERMINAL_MARKER}=NOT_PROVEN" in state)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)
        check("control-plane:playability-reserved",
              f"{PLAYABILITY_MARKER}=NOT_PROVEN" in queue
              and f"{PLAYABILITY_MARKER}=NOT_PROVEN" in state)

        banner("classification")
        record_a = classification.run()
        record_b = classification.run()
        check("classify:deterministic", canonical(record_a) == canonical(record_b))
        check("classify:data-not-code",
              record_a["classification"] == "DATA_NOT_CODE"
              and record_a["opcode"] == "0x7c"
              and record_a["address"] == 0xC570)
        check("classify:method", record_a["method"] == "inline_dispatch_table_v1")
        check("classify:predecessor",
              record_a["predecessors"] == EXPECTED_PREDECESSORS
              and record_a["predecessors"][0]["address"]
              != record_a["address"])
        callee = record_a["callee"]
        check("classify:call-site", record_a["call_site"] == 0xC56D
              and callee["address"] == 0xC71F)
        check("classify:return-consumption",
              callee["consumes_return_address"] is True
              and callee["pulls"] >= 2
              and callee["indirect_reads"] >= 1
              and callee["indirect_jump"] is True)
        table = record_a["inline_table"]
        check("classify:inline-table",
              table["base"] == 0xC570 and table["entries"] == 6
              and table["byte_length"] == 12
              and tuple(table["targets"]) == EXPECTED_TABLE_TARGETS
              and table["all_targets_in_code_window"] is True
              and table["all_targets_decode"] is True
              and table["resume_address"] == 0xC57C)
        resume = record_a["code_resume"]
        check("classify:code-resume",
              resume["address"] == 0xC57C
              and resume["first_op"] == "lda"
              and resume["second_op"] == "jsr"
              and resume["second_target"] == 0xC71F)
        nested = resume["nested_table"]
        check("classify:nested-table",
              nested["base"] == 0xC581 and nested["entries"] == 4
              and tuple(nested["targets"]) == EXPECTED_NESTED_TARGETS
              and nested["all_targets_in_code_window"] is True)
        corroboration = record_a["corroboration"]
        check("classify:corroboration",
              corroboration["linear_undocumented_offset"] == 9
              and corroboration["linear_undocumented_address"] == 0xC579
              and corroboration["coherent_documented_stream"] is False)
        basis = record_a["reference_basis"]
        check("classify:reference-basis",
              "2A03" in basis["cpu_variant"]
              and "documented" in basis["documented_semantics_used"].lower()
              and "does not depend on any undocumented-opcode" in
              basis["opcode_table_basis"])
        check("classify:no-semantics-added",
              record_a["opcode_semantics_required"] is False
              and record_a["semantics_added"] is False
              and record_a["universal_claim"] is False
              and record_a["target_opcode_supported_by_decoder"] is False
              and record_a["documented_opcode_count"] == 151)
        FINDINGS["classification"] = record_a["classification"]
        FINDINGS["method"] = record_a["method"]

        banner("mechanism_tests_public_synthetic")
        # Full idiom: JSR $8010; inline table with two $C1xx/$C2xx targets;
        # code resume; callee consumes the return address.
        image = synthetic({
            0x8000: bytes([0x20, 0x10, 0x80]),
            0x8003: bytes([0x7C, 0xC1, 0x7C, 0xC2]),
            0x8007: bytes([0xA9, 0x00, 0x60]),
            0x8010: dispatch_callee(),
            0xC17C: bytes([0x60]),
            0xC27C: bytes([0x60]),
        })
        positive = classification.classify(image, 0x8003, [0x8000])
        check("synthetic:full-idiom-data-not-code",
              positive["classification"] == "DATA_NOT_CODE"
              and tuple(positive["inline_table"]["targets"])
              == (0xC17C, 0xC27C)
              and positive["inline_table"]["entries"] == 2
              and positive["code_resume"]["first_op"] == "lda")

        # Non-consuming callee (plain RTS) must be AMBIGUOUS.
        image = synthetic({
            0x8000: bytes([0x20, 0x10, 0x80]),
            0x8003: bytes([0x7C, 0xC1, 0x7C, 0xC2]),
            0x8010: bytes([0x60]),
        })
        non_consuming = classification.classify(image, 0x8003, [0x8000])
        check("synthetic:non-consuming-callee-ambiguous",
              non_consuming["classification"] == "AMBIGUOUS"
              and "does not consume" in non_consuming["reason"])

        # Consuming callee but no in-window table: AMBIGUOUS.
        image = synthetic({
            0x8000: bytes([0x20, 0x10, 0x80]),
            0x8003: bytes([0x7C, 0x00, 0x7C, 0x00]),
            0x8010: dispatch_callee(),
        })
        no_table = classification.classify(image, 0x8003, [0x8000])
        check("synthetic:no-table-ambiguous",
              no_table["classification"] == "AMBIGUOUS"
              and "inline dispatch table" in no_table["reason"])

        # Literal (non-jsr) predecessor: AMBIGUOUS.
        image = synthetic({
            0x8000: bytes([0x4C, 0x06, 0x80]),
            0x8006: bytes([0x7C, 0xC1, 0x7C, 0xC2]),
            0xC17C: bytes([0x60]),
        })
        literal = classification.classify(image, 0x8006, [0x8000])
        check("synthetic:literal-predecessor-ambiguous",
              literal["classification"] == "AMBIGUOUS"
              and "not a jsr fallthrough" in literal["reason"])

        # An address that the walk decodes is documented reachable code.
        image = synthetic({
            0x8000: bytes([0xEA, 0x60]),
        })
        reachable = classification.classify(image, 0x8000, [0x8000])
        check("synthetic:reachable-code",
              reachable["classification"] == "REACHABLE_CODE")

        # An address with no predecessor at all is unreachable.
        image = synthetic({
            0x8000: bytes([0xEA, 0x60]),
            0x9000: bytes([0x60]),
        })
        unreachable = classification.classify(image, 0x9000, [0x8000])
        check("synthetic:unreachable",
              unreachable["classification"] == "UNREACHABLE")

        banner("fail_closed")
        try:
            classification.run(
                pathlib.Path(r"D:\OpenRecomp\Roms\phase1\nes\primary\absent.nes"))
        except classification.P7OpcodeError:
            check("negative:missing-path", True)
        else:
            raise AssertionError("negative:missing-path: accepted")
        malformed = SCRATCH / "malformed_input.bin"
        malformed.write_bytes(b"OPENRECOMP-NOT-A-ROM\x00\x01\x02")
        try:
            classification.run(malformed)
        except classification.P7OpcodeError:
            check("negative:malformed-container", True)
        else:
            raise AssertionError("negative:malformed-container: accepted")

        banner("regressions")
        regressions = []
        for script in REGRESSIONS:
            record = run_regression(script)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        p7_01_regression = run_regression(
            P7_01_GATE, ["--evidence-dir",
                         ".openrecomp-phase7/scratch/P7-02/regression_p7_01"])
        check("regression:p7-01:exit", p7_01_regression["returncode"] == 0)
        check("regression:p7-01:stderr", p7_01_regression["stderr_empty"])
        check("regression:p7-01:marker",
              any(marker == "OPENRECOMP_P7_01=PASS"
                  for marker in p7_01_regression["markers"]))
        regressions.append(p7_01_regression)
        FINDINGS["regressions"] = regressions

        banner("evidence")
        write_json("opcode_classification.json", {
            "stage": STAGE,
            "fixture": record_a["fixture"],
            "image_sha256": record_a["image_sha256"],
            "image_size": record_a["image_size"],
            "address": record_a["address"],
            "opcode": record_a["opcode"],
            "classification": record_a["classification"],
            "method": record_a["method"],
            "reason": record_a["reason"],
            "predecessors": record_a["predecessors"],
            "call_site": record_a["call_site"],
            "callee": record_a["callee"],
            "inline_table": record_a["inline_table"],
            "code_resume": record_a["code_resume"],
            "corroboration": record_a["corroboration"],
            "reference_basis": record_a["reference_basis"],
            "opcode_semantics_required": record_a["opcode_semantics_required"],
            "semantics_added": record_a["semantics_added"],
            "universal_claim": record_a["universal_claim"],
            "documented_opcode_count": record_a["documented_opcode_count"],
            "public_claim": record_a["public_claim"],
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
    (EVIDENCE_DIR / "p7_02_tests.json").write_text(
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
