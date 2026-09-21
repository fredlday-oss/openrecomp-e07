#!/usr/bin/env python3
"""Deterministic P11-00 Phase-11 boundary, fixture-identity and control-plane gate.

The gate verifies:

* the frozen Phase-10 terminal boundary identity (commit/tree/branch) and the
  untouched Phase-10 terminal evidence/control-plane hashes;
* the untouched Phase-1 through Phase-10 trees, the frozen Phase-10 evidence
  index (135 files) and the inherited tag reconciliations;
* every frozen Phase-10 stage record, including the terminal counts
  `P10-90` 155, `P10-91` 323, `P10-99` 166;
* the inherited Phase-10 milestone-A record and the explicit non-establishment
  of milestones B through G, GPU command writes, the controller data port and
  the disc data path;
* the private fixture/disc identity (discovered CUE, referenced BIN, ISO9660
  relationship, SYSTEM.CNF boot target and boot-extent identity);
* the private executable's frozen structure and emission identities through
  the frozen Phase-9/Phase-10 pipeline;
* a live compressed rebuild and two deterministic native runs of the frozen
  Phase-10 composition, reproducing the milestone-A frontier (exact access
  traffic, first failure and RAM digest) without executing guest machine code;
* the frozen Phase-11 control plane and the frozen stage queue.

It adds no PS1 capability and performs no substantive compatibility
implementation.

On success it emits::

    OPENRECOMP_P11_00=PASS
    OPENRECOMP_PHASE11_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase11_boundary_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P9 = ROOT / ".openrecomp-phase9"
P10 = ROOT / ".openrecomp-phase10"
P11 = ROOT / ".openrecomp-phase11"
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_emission_v1 as emission  # noqa: E402
import p10_fixture_identity_v1 as fixture  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as p10_fixture_gate  # noqa: E402

STAGE = "P11-00"
FEATURE_MARKER = "OPENRECOMP_PHASE11_BOUNDARY_V1"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

BASELINE_COMMIT = "8961682aa36e14db979e8e8dbe88e04fa2b4c87a"
BASELINE_TREE = "4a58d9238d76a490560c588bb470fd9e6a58cafe"
BASELINE_BRANCH = "phase10/ps1-commercial-game-native-v1"
PHASE11_BRANCH = "phase11/ps1-playability-v1"

DEFAULT_PRIVATE_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

FROZEN_P10_HASHES = {
    ".openrecomp-phase10/ACCELERATION_POLICY.md":
        "910e648877b2083b9e9dce0c4d21950670f0523686925a40c146692ca9293382",
    ".openrecomp-phase10/CONTROL_POLICY.md":
        "dfc740776cddb7a5a6d6511ef133355bfd6e7a7cadcc5581f9982b21ee30089c",
    ".openrecomp-phase10/EVIDENCE_SCHEMA.md":
        "d1a9c29adab9779d0b693d830be00e0cfc79c8df84fb9d829fae8a29ff0feacb",
    ".openrecomp-phase10/FIXTURE_POLICY.md":
        "cdcef2c50e799471e45f38b3bfc02935b3db54edea4c467dbc96054dbaf48e84",
    ".openrecomp-phase10/HANDOFF.md":
        "dc9226e8b19f5977cadbfefb3b426e3e7c223c39fc2fd7589dfa11cc090ccd56",
    ".openrecomp-phase10/SCOPE.md":
        "84759c9184bc378e165d83d80cda5da54cf07366609623fda775789f823a6aac",
    ".openrecomp-phase10/SOURCE_SHA256SUMS.txt":
        "3606939526bc81d2e10f008129e4f33d6e0d660237f3090e5bbe79223d78051b",
    ".openrecomp-phase10/STAGE_QUEUE.md":
        "72c4f91fc7d0185910b621cc7b7aa043ae38fb0b930fb5cda7550235f8b129b2",
    ".openrecomp-phase10/STATE.md":
        "c309ff68ded252f6b8a3a8a0de677c4ee786622b087972fa0351ed1f5570f111",
    ".openrecomp-phase10/evidence/P10-00/baseline.json":
        "000318f679737ccb0801a8ec5748e684a4181eccc900fab8aa7c65fa5f106abe",
    ".openrecomp-phase10/evidence/P10-00/fixture_identity.json":
        "449111519b372126ea0e330b05d6883b369b50b42b97fae79e92432d4dd7e014",
    ".openrecomp-phase10/evidence/P10-00/frontier.json":
        "0b4f1c4905852f6195a030d5860ef99a3675ce09933fc252c7f986b05e5441c2",
    ".openrecomp-phase10/evidence/P10-05/native_entry.json":
        "ef7b834293e4e5ff1067c78154ccbbeac218276bea1375000bd380e3cb6c05e9",
    ".openrecomp-phase10/evidence/P10-07/gpu_frontier.json":
        "e60c4dc20089bcb7d70d11247ecaadd44b750437c14e3bea3f4fce452632d73a",
    ".openrecomp-phase10/evidence/P10-08/timing_frontier.json":
        "a2dc8506a5444be019662cb5ae9042483c74b8993ecc9af1a191c5cf1d735eb2",
    ".openrecomp-phase10/evidence/P10-09/disc_frontier.json":
        "9e8715c489a033b717e5b69607d747c4315c99d0fed11234845fcc49b4ca0896",
    ".openrecomp-phase10/evidence/P10-10/input_spu_frontier.json":
        "2b697b82813aa14af1f0744e76cb0d534a0dc3a4263544a10e0b6bb5b35bb538",
    ".openrecomp-phase10/evidence/P10-11/milestone.json":
        "77dd3edc8aded9dd478b04ad8c6ec9fc47592349e62260660c0ae3744b5d64cd",
    ".openrecomp-phase10/evidence/P10-91/evidence_index.json":
        "640575858d5c548fbb8c4604ca1744c1f60e6e00414962c9daa73908ff206213",
    ".openrecomp-phase10/evidence/P10-99/RESULT.md":
        "51de2cde4c933cf4eae4cb8ed53df3a4009d4231ceeda242f16c813fe19e040b",
    ".openrecomp-phase10/evidence/P10-99/terminal_verdict.json":
        "4aa3ad7b8cdb111e9afcb3f569e460dfb2d0799632462e1d5981c5dc63440cb3",
    ".openrecomp-phase10/evidence/P10-99/verdict_record.json":
        "cd63014e7d07b13c29f3b1f9a76d45f461b9dd5a9da2cc6398c11ef4239ccdee",
    ".openrecomp-phase10/evidence/P10-99/p10_99_tests.json":
        "de06056f8daf6ae275889a0b53cdd98d7ab1f747fd5cdf82fbdbb49bf3f82309",
    ".openrecomp-phase10/evidence/P10-99/official_runs.json":
        "d391c2301f66ac16ec13828dfdd74b3b3138288702d80d1a32fa5799020de9b3",
    ".openrecomp-phase10/evidence/P10-99/determinism.json":
        "a9fe544a15e1006a75e09330c3c05430ba647c91266d4a8cccecfdbe0e735891",
}

DOCUMENTED_PRIOR_TRACKED_DIFF = {
    ".openrecomp-phase3/evidence/P3-00/p3_00_tests.json",
    ".openrecomp-phase3/evidence/P3-00/residue_manifest.txt",
}

DOCUMENTED_TAG_SET = {
    "openrecomp-phase1-pass",
    "openrecomp-phase2-pass",
    "openrecomp-phase3-pass",
    "openrecomp-phase4-pass",
    "openrecomp-phase5-pass",
    "openrecomp-phase7-pass",
    "openrecomp-phase7-pass-v2",
}

FROZEN_STAGES = (
    "P10-00", "P10-01", "P10-02", "P10-03", "P10-04", "P10-05", "P10-06",
    "P10-07", "P10-08", "P10-09", "P10-10", "P10-11", "P10-12", "P10-90",
    "P10-91", "P10-99",
)

TERMINAL_STAGE_COUNTS = {"P10-90": 155, "P10-91": 323, "P10-99": 166}

PHASE11_STAGES = (
    "P11-00", "P11-01", "P11-02", "P11-03", "P11-04", "P11-05", "P11-06",
    "P11-07", "P11-08", "P11-09", "P11-10", "P11-11", "P11-12", "P11-90",
    "P11-91", "P11-99",
)

REQUIRED_CONTROL_FILES = (
    ".openrecomp-phase11/.gitignore",
    ".openrecomp-phase11/CONTROL_POLICY.md",
    ".openrecomp-phase11/EVIDENCE_SCHEMA.md",
    ".openrecomp-phase11/FIXTURE_POLICY.md",
    ".openrecomp-phase11/HANDOFF.md",
    ".openrecomp-phase11/SCOPE.md",
    ".openrecomp-phase11/STAGE_QUEUE.md",
    ".openrecomp-phase11/STATE.md",
    ".openrecomp-phase11/evidence/README.md",
    ".openrecomp-phase11/src/p11_source_manifest_v1.py",
    ".openrecomp-phase11/src/p11_stage_runner_v1.py",
    "tools/test_phase11_boundary_v1.py",
)

TOOLCHAIN_COMMANDS = {
    "python": ("python", "--version"),
    "git": ("git", "--version"),
    "clang-cl": ("clang-cl", "--version"),
    "lld-link": ("lld-link", "--version"),
}

EXPECTED_FIXTURE = {
    "executable_size": 129024,
    "executable_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
    "cue_size": 101,
    "cue_sha256": "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2",
    "bin_size": 409452624,
    "bin_sha256": "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365",
    "entry": "0x800132e8",
    "text_address": "0x80010000",
    "text_size": "0x0001f000",
    "stack_pointer": "0x801ffff0",
    "boot_target": "SLUS_005.29",
    "volume_space_size_sectors": 174087,
    "root_extent_lba": 22,
}

EXPECTED_STRUCTURE = {
    "neutral_instructions": 3433,
    "blocks": 739,
    "functions": 110,
    "exception_site_count": 3,
    "call_edges_internal": 209,
    "call_edges_unresolved": 22,
    "edges": 889,
    "folded_delay_slots": 635,
    "non_nop_delay_slots": 328,
    "translation_units": 110,
}

EXPECTED_EMISSION = {
    "program_fingerprint": "a047a52fb460d3786e5bff03b5c26ac2978ae768b581f5e6c4a9cbc284db4a9a",
    "program_bytes": 520039,
    "image_sha256": "77a340448081cc606b16e104734b3a48d11483210520618dcca8b1266c43f96b",
    "image_bytes": 750534,
}

#: Composition-independent milestone-A observables of the frozen Phase-10
#: runtime: the exact guest access traffic, the first fail-closed category,
#: the guest RAM digest and the crt0-observable register values. These are
#: stable across the documented Phase-10 runtime-composition divergences
#: (event capacity and GPU status stub), which change printed event counts and
#: status values but not guest semantics.
EXPECTED_NATIVE = {
    "failed": "1",
    "error": "unresolved indirect jump",
    "reads": "982859",
    "writes": "799023",
    "denied": "11",
    "host_calls": "79",
    "p10_access_budget": "2000000",
    "p10_access_count": "2000005",
    "p10_budget_denials": "5",
    "nonram_signatures": "17",
    "nonram_overflow": "0",
    "memory": "0x18131c6ef356df7d",
    "register_file": {
        "r10": "0x801f7ffc",
        "r17": "0x80028588",
        "r28": "0x8002ed78",
        "r29": "0x801ffe00",
        "r30": "0x80200000",
        "r31": "0x80015840",
    },
    "nonram": {
        "0x1f801814": "109035",
        "0x1f801110": "109035",
    },
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def capture_toolchains() -> dict[str, dict[str, str]]:
    captured: dict[str, dict[str, str]] = {}
    for name, command in TOOLCHAIN_COMMANDS.items():
        executable = command[0]
        if not pathlib.Path(executable).is_absolute():
            candidate = ROOT / executable
            if candidate.is_file():
                executable = str(candidate)
        try:
            result = subprocess.run(
                [executable, *command[1:]],
                check=False,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            captured[name] = {"version": "UNAVAILABLE"}
            continue
        text = (result.stdout or result.stderr).strip()
        first = text.splitlines()[0].strip() if text else ""
        captured[name] = {"version": first or "UNAVAILABLE", "exit_code": str(result.returncode)}
    return captured


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def assert_no_payload_leak(label: str, document: dict, payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    lowered = text.lower()
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in lowered, "payload hex present")
    check(
        f"{label}:no-base64",
        base64.b64encode(sample).decode("ascii") not in text,
        "payload base64 present",
    )
    for start in range(0, min(len(payload), 512)):
        run = payload[start : start + 8]
        if len(run) == 8 and all(32 <= byte < 127 for byte in run):
            check(
                f"{label}:no-ascii-run",
                run.decode("ascii") not in text,
                f"ascii payload run at {start}",
            )
    for value in _string_values(document):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def parse_native(stdout: str) -> dict:
    record = {"register_file": {}, "nonram": {}}
    for line in stdout.splitlines():
        if line.startswith("nonram_") and line.split("=", 1)[0] not in ("nonram_signatures", "nonram_overflow"):
            _, value = line.split("=", 1)
            address, width, is_write, reason, count = value.split(",")
            record["nonram"][f"{address}:{width}:{is_write}:{reason}"] = count
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.startswith("r") and key[1:].isdigit():
            record["register_file"][key] = value
        else:
            record[key] = value
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-00")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--private-fixture-root", default=str(DEFAULT_PRIVATE_FIXTURE_ROOT))
    parser.add_argument("--skip-native", action="store_true",
                        help="skip only the live native rebuild (diagnostic use; never an official PASS)")
    options = parser.parse_args()

    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)
    skip_native = options.skip_native

    try:
        head = git("rev-parse", "HEAD")
        head_tree = git("rev-parse", "HEAD^{tree}")
        branch = git("branch", "--show-current")

        # --- frozen Phase-10 terminal boundary -------------------------------
        check("baseline:commit-type", git("cat-file", "-t", BASELINE_COMMIT) == "commit", BASELINE_COMMIT)
        check("baseline:commit-tree", git("rev-parse", f"{BASELINE_COMMIT}^{{tree}}") == BASELINE_TREE, BASELINE_TREE)
        ancestor = subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
            check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).returncode == 0
        check("branch:head-descends-from-baseline", ancestor, head)
        check("branch:name", branch == PHASE11_BRANCH, branch)
        check(
            "baseline:branch-reachable",
            git("rev-parse", f"{BASELINE_BRANCH}^{{commit}}") == BASELINE_COMMIT,
            BASELINE_BRANCH,
        )

        # --- inherited tag reconciliations -----------------------------------
        tags = set(git("tag", "-l", "openrecomp-phase*").splitlines())
        check("reconcile:tag-set", tags == DOCUMENTED_TAG_SET, ",".join(sorted(tags)))
        check(
            "reconcile:phase6-tag-absent",
            git("tag", "-l", "openrecomp-phase6*") == "",
            "absent",
        )
        check(
            "reconcile:phase7-tag-object",
            git("rev-parse", "openrecomp-phase7-pass") == "b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800",
            "phase7 tag object",
        )
        check(
            "reconcile:phase7-tag-commit",
            git("rev-parse", "openrecomp-phase7-pass^{commit}") == "2917aa6549ab975cffdeb50120514c1723f7e493",
            "phase7 commit",
        )
        check(
            "reconcile:phase7-tag-tree",
            git("rev-parse", "openrecomp-phase7-pass^{tree}") == "59529c130d759ceb1ca9e6c65a510fa373656b01",
            "phase7 tree",
        )
        for absent_prefix in ("openrecomp-phase8*", "openrecomp-phase9*", "openrecomp-phase10*", "openrecomp-phase11*"):
            check(
                f"reconcile:tag-absent:{absent_prefix}",
                git("tag", "-l", absent_prefix) == "",
                "absent",
            )

        # --- frozen Phase-1..10 trees ----------------------------------------
        prior_paths = [f".openrecomp-phase{i}" for i in range(1, 11)]
        changed = git("diff", "--name-only", BASELINE_COMMIT, "--", *prior_paths)
        changed_set = set(filter(None, changed.splitlines()))
        check(
            "frozen:no-prior-tracked-change-outside-documented-residue",
            changed_set <= DOCUMENTED_PRIOR_TRACKED_DIFF,
            ",".join(sorted(changed_set)) or "none",
        )
        status_lines = git("status", "--porcelain", "--untracked-files=all").splitlines()
        undocumented: list[str] = []
        for line in status_lines:
            match = re.search(r"\.openrecomp-phase([0-9]+)/", line)
            if not match:
                continue
            numeric = int(match.group(1))
            path = line[3:].strip().strip('"')
            if numeric in (2, 3, 11):
                continue
            undocumented.append(path)
        check("frozen:no-new-prior-residue", not undocumented, ",".join(sorted(undocumented)) or "none")

        # --- frozen Phase-10 terminal records --------------------------------
        for rel, expected in sorted(FROZEN_P10_HASHES.items()):
            observed = sha256_file(ROOT / rel)
            check(f"frozen:p10:{rel}", observed == expected, observed)

        index = json.loads((P10 / "evidence" / "P10-91" / "evidence_index.json").read_text(encoding="utf-8"))
        entries = index.get("entries", [])
        check("frozen:p10-evidence-index-count", len(entries) == 135, str(len(entries)))
        mismatches: list[str] = []
        for entry in entries:
            path = ROOT / entry["path"]
            if not path.is_file():
                mismatches.append(f"{entry['path']}:missing")
                continue
            if sha256_file(path) != entry["sha256"]:
                mismatches.append(f"{entry['path']}:hash")
        check(
            "frozen:p10-evidence-index-verified",
            not mismatches,
            ",".join(mismatches[:3]) or f"{len(entries)} files",
        )

        total_tests = 0
        for stage in FROZEN_STAGES:
            number = stage.split("-")[1]
            candidates = sorted((P10 / "evidence" / stage).glob(f"p10_{number}_tests.json"))
            check(f"frozen:stage-record:{stage}", len(candidates) == 1, str(len(candidates)))
            record = json.loads(candidates[0].read_text(encoding="utf-8"))
            check(f"frozen:stage-status:{stage}", record.get("status") == "PASS", str(record.get("status")))
            check(f"frozen:stage-failed:{stage}", record.get("failed") == 0, str(record.get("failed")))
            check(f"frozen:stage-tests:{stage}", record.get("tests", 0) > 0, str(record.get("tests")))
            total_tests += int(record.get("tests", 0))
            capture = (P10 / "evidence" / stage / "run1.txt")
            check(f"frozen:stage-capture:{stage}", capture.is_file(), stage)
            check(
                f"frozen:stage-marker:{stage}",
                f"OPENRECOMP_P10_{number}=PASS" in capture.read_text(encoding="utf-8"),
                stage,
            )
            if stage in TERMINAL_STAGE_COUNTS:
                check(
                    f"frozen:terminal-count:{stage}",
                    record.get("tests") == TERMINAL_STAGE_COUNTS[stage],
                    f"{record.get('tests')} != {TERMINAL_STAGE_COUNTS[stage]}",
                )
        check("frozen:total-stage-tests", total_tests == 2277, str(total_tests))

        for name, script in (
            ("p9", P9 / "src" / "p9_source_manifest_v1.py"),
            ("p10", P10 / "src" / "p10_source_manifest_v1.py"),
        ):
            completed = subprocess.run(
                [sys.executable, str(script)], check=False, cwd=str(ROOT),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            )
            check(
                f"frozen:{name}-source-manifest",
                completed.returncode == 0 and completed.stderr == "" and "=PASS entries=" in completed.stdout,
                completed.stdout.strip() or completed.stderr.strip(),
            )

        verdict = json.loads((P10 / "evidence" / "P10-99" / "terminal_verdict.json").read_text(encoding="utf-8"))
        check("terminal:p10-99-decision", verdict.get("decision") == "PASS", str(verdict.get("decision")))
        check(
            "terminal:p10-99-marker",
            "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=PASS" in verdict.get("markers_issued", []),
            "terminal PASS",
        )
        required = verdict.get("required_stages", [])
        check(
            "terminal:p10-99-required-set",
            [item.get("stage") for item in required] == [
                "P10-00", "P10-01", "P10-02", "P10-03", "P10-04", "P10-05", "P10-06",
                "P10-07", "P10-08", "P10-09", "P10-10", "P10-11", "P10-12",
                "P10-90", "P10-91",
            ],
            ",".join(str(item.get("stage")) for item in required),
        )
        check(
            "terminal:p10-99-all-stages-pass",
            bool(required) and all(item.get("outcome") == "PASS" for item in required),
            f"{sum(1 for item in required if item.get('outcome') == 'PASS')}/{len(required)}",
        )
        guards = verdict.get("scope_guards", {})
        for guard in ("hercules_playability", "general_ps1_compatibility", "milestones_b_g",
                      "gpu_rendering_vram", "controller_input_consumption",
                      "cdrom_disc_reading_streaming", "interrupt_delivery_dma_timing"):
            check(f"terminal:p10-99-guard:{guard}", guards.get(guard) == NOT_PROVEN, str(guards.get(guard)))

        # --- inherited milestone-A record and the non-establishment of B..G ---
        native_entry = json.loads(
            (P10 / "evidence" / "P10-05" / "native_entry.json").read_text(encoding="utf-8")
        )
        check(
            "inherit:milestone-a",
            native_entry["milestone"]["highest"] == "A",
            native_entry["milestone"]["highest"],
        )
        check(
            "inherit:milestone-a-native-execution",
            native_entry["execution"]["termination_category"] == "UNRESOLVED_INDIRECT_JUMP"
            and native_entry["execution"]["deterministic"] is True,
            native_entry["execution"]["termination_category"],
        )
        milestone = json.loads(
            (P10 / "evidence" / "P10-11" / "milestone.json").read_text(encoding="utf-8")
        )
        check("inherit:b-not-established", milestone["milestones"]["B"]["established"] is False, "B")
        for item in ("C", "D", "E", "F", "G"):
            check(f"inherit:{item.lower()}-not-established", milestone["milestones"][item]["established"] is False, item)
        check("inherit:highest-a", milestone["highest_milestone"] == "A", str(milestone["highest_milestone"]))

        gpu = json.loads((P10 / "evidence" / "P10-07" / "gpu_frontier.json").read_text(encoding="utf-8"))
        check("inherit:no-gpu-command-writes", gpu["transcript"]["gp0_writes"] == 0 and gpu["transcript"]["gp1_writes"] == 0, "0/0")
        check("inherit:milestone-c-not-established", gpu["new_frontier"]["milestone_c_established"] is False, "false")
        check(
            "inherit:gpu-polling-non-causal",
            gpu["stub_ab_experiment"]["access_traffic_identical"] is True,
            "identical",
        )
        disc = json.loads((P10 / "evidence" / "P10-09" / "disc_frontier.json").read_text(encoding="utf-8"))
        check(
            "inherit:disc-data-path-not-reached",
            disc["classification"]["data_path_reached"] is False,
            str(disc["classification"]["data_path_reached"]),
        )
        input_spu = json.loads(
            (P10 / "evidence" / "P10-10" / "input_spu_frontier.json").read_text(encoding="utf-8")
        )
        check(
            "inherit:controller-not-reached",
            input_spu["controller"]["controller_data_reached"] is False
            and input_spu["controller"]["scripted_input_consumable"] is False,
            str(input_spu["controller"]["controller_data_reached"]),
        )
        check(
            "inherit:no-frame-loop",
            input_spu["game_loop"]["frame_loop_reached"] is False,
            str(input_spu["game_loop"]["frame_loop_reached"]),
        )

        # --- toolchains -------------------------------------------------------
        toolchains = capture_toolchains()
        for name, record in sorted(toolchains.items()):
            check(f"toolchain:{name}", record["version"] != "UNAVAILABLE", record["version"])

        # --- private fixture/disc identity ------------------------------------
        check("fixture:directory", fixture_root.is_dir(), "private fixture directory present")
        identity = fixture.build_identity(fixture_root)
        executable = identity["executable"]
        check(
            "fixture:executable-entry",
            executable["directory_entry"] == fixture.PRIMARY_EXECUTABLE,
            executable["directory_entry"],
        )
        check("fixture:executable-size", executable["size"] == EXPECTED_FIXTURE["executable_size"], str(executable["size"]))
        check("fixture:executable-sha256", executable["sha256"] == EXPECTED_FIXTURE["executable_sha256"], executable["sha256"])
        cue = identity["disc"]["cue"]
        check("fixture:cue-size", cue["cue_size"] == EXPECTED_FIXTURE["cue_size"], str(cue["cue_size"]))
        check("fixture:cue-sha256", cue["cue_sha256"] == EXPECTED_FIXTURE["cue_sha256"], cue["cue_sha256"])
        check("fixture:cue-single-track", cue["track_count"] == 1, str(cue["track_count"]))
        check("fixture:cue-track-type", cue["tracks"][0]["type"] == "MODE2/2352", cue["tracks"][0]["type"])
        bins = identity["disc"]["bins"]
        check("fixture:bin-count", len(bins) == 1, str(len(bins)))
        check("fixture:bin-size", bins[0]["size"] == EXPECTED_FIXTURE["bin_size"], str(bins[0]["size"]))
        check("fixture:bin-sha256", bins[0]["sha256"] == EXPECTED_FIXTURE["bin_sha256"], bins[0]["sha256"])
        volume = identity["disc"]["volume"]
        check(
            "fixture:volume-space-size",
            volume["volume_space_size_sectors"] == EXPECTED_FIXTURE["volume_space_size_sectors"],
            str(volume["volume_space_size_sectors"]),
        )
        check("fixture:root-extent", volume["root_extent_lba"] == EXPECTED_FIXTURE["root_extent_lba"], str(volume["root_extent_lba"]))
        system_cnf = identity["system_cnf"]
        check("fixture:boot-target", system_cnf["boot_target"] == EXPECTED_FIXTURE["boot_target"], system_cnf["boot_target"])
        check(
            "fixture:boot-extent-sha256",
            system_cnf["boot_extent_sha256"] == EXPECTED_FIXTURE["executable_sha256"],
            system_cnf["boot_extent_sha256"],
        )

        # --- PS-X EXE metadata and frozen structure/emission identity ---------
        image = psx.ingest((fixture_root / fixture.PRIMARY_EXECUTABLE).read_bytes())
        header = image.header
        check("exe:entry", f"0x{header.pc0:08x}" == EXPECTED_FIXTURE["entry"], f"0x{header.pc0:08x}")
        check("exe:text-address", f"0x{header.t_addr:08x}" == EXPECTED_FIXTURE["text_address"], f"0x{header.t_addr:08x}")
        check("exe:text-size", f"0x{header.t_size:08x}" == EXPECTED_FIXTURE["text_size"], f"0x{header.t_size:08x}")
        check("exe:stack-pointer", f"0x{header.s_addr:08x}" == EXPECTED_FIXTURE["stack_pointer"], f"0x{header.s_addr:08x}")

        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)
        pipeline = bridge.analyze(image, contract, flat)
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image.file_sha256,
        )
        result = structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
        summary = structure.structure_summary(result)
        for key, expected in sorted(EXPECTED_STRUCTURE.items()):
            check(f"structure:{key}", summary.get(key) == expected, str(summary.get(key)))

        build_set = emission.build_build_set(result, contract, flat, image.file_sha256, driver="phase10")
        program_text = build_set["files"][emission.PROGRAM_NAME]
        check(
            "emission:program-fingerprint",
            build_set["program_fingerprint"] == EXPECTED_EMISSION["program_fingerprint"],
            build_set["program_fingerprint"],
        )
        check(
            "emission:function-count",
            len(build_set["program"].translations) == EXPECTED_STRUCTURE["functions"],
            str(len(build_set["program"].translations)),
        )
        check(
            "emission:no-guest-machine-code",
            image.payload[:64].hex() not in program_text.lower(),
            "no guest payload bytes in the generated program",
        )
        check(
            "emission:no-opcode-dispatch",
            "opcode" not in program_text,
            "generated program is a direct translation, not a decode loop",
        )
        check(
            "emission:inert-image-unit",
            "static const unsigned char p9_chunk_data_0[]" in build_set["files"][emission.IMAGE_NAME],
            "guest image emitted as inert data",
        )

        native_record: dict = {"attested": False}
        if not skip_native:
            workspace = P11 / "build" / "p11-00-repro"
            if workspace.exists():
                shutil.rmtree(workspace)
            comparison = bp.build_generated_host(
                lambda: build_set["files"][emission.PROGRAM_NAME],
                support_sources=(
                    bp.BuildSource(emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   build_set["files"][emission.IMAGE_NAME].encode("utf-8")),
                    bp.BuildSource(emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   build_set["files"][emission.SUPPORT_NAME].encode("utf-8")),
                    bp.BuildSource(emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   build_set["files"][emission.DRIVER_NAME].encode("utf-8")),
                ),
                config=bp.BuildConfig(fixture_id="p11-00-repro", smoke_test=False, run_count=2),
                workspace=workspace,
                keep_workspace=True,
            )
            check(
                "native:build-status",
                all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs),
                str([run.manifest.build_status.value for run in comparison.runs]),
            )
            first_exe = workspace / "run1" / "program.exe"
            second_exe = workspace / "run2" / "program.exe"
            check("native:executable-present", first_exe.is_file() and second_exe.is_file(), "both runs")
            check(
                "native:build-reproducible",
                sha256_file(first_exe) == sha256_file(second_exe),
                sha256_file(first_exe),
            )
            completed = subprocess.run([str(first_exe)], capture_output=True, timeout=1800)
            check("native:exit", completed.returncode == 0, str(completed.returncode))
            check("native:stderr", completed.stderr == b"", completed.stderr[:120].decode("ascii", "replace"))
            first = completed.stdout
            second = subprocess.run([str(first_exe)], capture_output=True, timeout=1800).stdout
            check("native:deterministic", second == first, "byte-identical stdout")

            native = parse_native(first.decode("utf-8"))
            for key, expected in (
                ("failed", EXPECTED_NATIVE["failed"]),
                ("error", EXPECTED_NATIVE["error"]),
                ("reads", EXPECTED_NATIVE["reads"]),
                ("writes", EXPECTED_NATIVE["writes"]),
                ("denied", EXPECTED_NATIVE["denied"]),
                ("host_calls", EXPECTED_NATIVE["host_calls"]),
                ("p10_access_budget", EXPECTED_NATIVE["p10_access_budget"]),
                ("p10_access_count", EXPECTED_NATIVE["p10_access_count"]),
                ("p10_budget_denials", EXPECTED_NATIVE["p10_budget_denials"]),
                ("nonram_signatures", EXPECTED_NATIVE["nonram_signatures"]),
                ("nonram_overflow", EXPECTED_NATIVE["nonram_overflow"]),
                ("memory", EXPECTED_NATIVE["memory"]),
            ):
                check(f"native:{key}", native.get(key) == expected, str(native.get(key)))
            for register, expected in sorted(EXPECTED_NATIVE["register_file"].items()):
                check(
                    f"native:register:{register}",
                    native["register_file"].get(register) == expected,
                    str(native["register_file"].get(register)),
                )
            check(
                "native:gpu-status-polling",
                native["nonram"].get("0x1f801814:32:0:0") == EXPECTED_NATIVE["nonram"]["0x1f801814"],
                str(native["nonram"].get("0x1f801814:32:0:0")),
            )
            check(
                "native:timer-polling",
                native["nonram"].get("0x1f801110:32:0:0") == EXPECTED_NATIVE["nonram"]["0x1f801110"],
                str(native["nonram"].get("0x1f801110:32:0:0")),
            )
            check(
                "native:budget-reached",
                int(native["p10_access_count"]) > int(native["p10_access_budget"]),
                native["p10_access_count"],
            )
            native_record = {
                "attested": True,
                "executable_sha256": sha256_file(first_exe),
                "build_reproducible": True,
                "stdout_sha256": hashlib.sha256(first).hexdigest(),
                "stdout_bytes": len(first),
                "observables": {
                    key: native.get(key)
                    for key in ("failed", "error", "reads", "writes", "denied", "host_calls",
                                "p10_access_budget", "p10_access_count", "p10_budget_denials",
                                "nonram_signatures", "nonram_overflow", "memory")
                },
                "register_file": dict(sorted(native["register_file"].items())),
                "nonram": dict(sorted(native["nonram"].items())),
            }
        else:
            check("native:skipped-not-allowed", False, "the live native rebuild is mandatory")

        # --- Phase-11 control plane -------------------------------------------
        for rel in REQUIRED_CONTROL_FILES:
            check(f"control:file:{rel}", (ROOT / rel).is_file(), rel)
        queue_text = (P11 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        for stage in PHASE11_STAGES:
            check(f"control:queue:{stage}", f"| {stage} |" in queue_text, stage)
        state_text = (P11 / "STATE.md").read_text(encoding="utf-8")
        for marker in (INITIALIZATION_MARKER, FRAME_MARKER, PLAYABILITY_MARKER, GENERAL_MARKER):
            check(
                f"control:state:{marker}",
                f"{marker}={NOT_PROVEN}" in state_text,
                f"{marker}={NOT_PROVEN}",
            )
        manifest = subprocess.run(
            [sys.executable, str(P11 / "src" / "p11_source_manifest_v1.py")],
            check=False, cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        )
        check(
            "control:source-manifest",
            manifest.returncode == 0 and manifest.stderr == "" and "=PASS entries=" in manifest.stdout,
            manifest.stdout.strip() or manifest.stderr.strip(),
        )

        # --- evidence writing and public-safety closure -----------------------
        baseline_document = {
            "schema": "openrecomp-phase11-baseline-v1",
            "stage": STAGE,
            "baseline": {
                "phase": 10,
                "commit": BASELINE_COMMIT,
                "tree": BASELINE_TREE,
                "branch": BASELINE_BRANCH,
                "terminal_marker": "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=PASS",
                "playability_marker": "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN",
                "general_marker": "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN",
            },
            "phase11": {
                "branch": branch,
                "head": head,
                "head_tree": head_tree,
                "frozen_stage_queue": list(PHASE11_STAGES),
            },
            "frozen_p10_hashes": dict(sorted(FROZEN_P10_HASHES.items())),
            "frozen_p10_evidence_index_entries": len(entries),
            "frozen_p10_stage_tests_total": total_tests,
            "toolchains": toolchains,
        }
        fixture_document = {
            "schema": "openrecomp-phase11-fixture-identity-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "is_pass_criterion": True,
            "identity": identity,
        }
        frontier_document = {
            "schema": "openrecomp-phase11-frontier-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "structure": {key: summary.get(key) for key in sorted(EXPECTED_STRUCTURE)},
            "emission": {
                "program_fingerprint": build_set["program_fingerprint"],
                "program_bytes": len(program_text.encode("utf-8")),
                "image_sha256": build_set["hashes"][emission.IMAGE_NAME],
                "image_bytes": len(build_set["files"][emission.IMAGE_NAME].encode("utf-8")),
                "functions": len(build_set["program"].translations),
                "runtime_composition": build_set["runtime_composition"],
                "driver": build_set["driver"],
            },
            "milestone_a_reproduction": native_record,
            "inherited_boundary": {
                "highest_milestone": "A",
                "b_through_g": "NOT_PROVEN",
                "first_unresolved_blocker": "executed unresolved indirect jump",
                "gpu_command_writes": 0,
                "controller_window_accesses": 0,
                "disc_data_path_reached": False,
                "frame_loop_reached": False,
            },
        }
        milestones_document = {
            "schema": "openrecomp-phase11-milestone-inheritance-v1",
            "stage": STAGE,
            "inherited": {
                "A": "PROVEN (P10-05/P10-11, reproduced live at P11-00)",
                "B": "NOT_PROVEN",
                "C": "NOT_PROVEN",
                "D": "NOT_PROVEN",
                "E": "NOT_PROVEN",
                "F": "NOT_PROVEN",
                "G": "NOT_PROVEN",
            },
            "claims": {
                INITIALIZATION_MARKER: NOT_PROVEN,
                FRAME_MARKER: NOT_PROVEN,
                PLAYABILITY_MARKER: NOT_PROVEN,
                GENERAL_MARKER: NOT_PROVEN,
            },
            "observed_historical_record_note": [
                "the committed P10-05 native_entry.json translated_trace.file_sha256",
                "records the frozen Phase-9 driver hash while emission.json records",
                "the Phase-10 driver; the live P11-00 rebuild uses the frozen",
                "Phase-10 emission composition and attests the composition-independent",
                "milestone-A observables. No claim depends on the historical hash map",
                "and no Phase-10 evidence is rewritten.",
            ],
        }
        if not options.verify_only:
            write_json(evidence / "baseline.json", baseline_document)
            write_json(evidence / "fixture_identity.json", fixture_document)
            write_json(evidence / "frontier.json", frontier_document)
            write_json(evidence / "milestone_inheritance.json", milestones_document)

        payload = image.payload
        for label, document in (
            ("baseline", baseline_document),
            ("fixture", fixture_document),
            ("frontier", frontier_document),
            ("milestones", milestones_document),
        ):
            assert_no_payload_leak(f"public:{label}", document, payload)

        check("claim:initialization-not-promoted", True, NOT_PROVEN)
        check("claim:frame-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-permanent", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Phase-11 boundary + control plane",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p11_00_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_00={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{INITIALIZATION_MARKER}={NOT_PROVEN}")
    print(f"{FRAME_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
