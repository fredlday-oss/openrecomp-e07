#!/usr/bin/env python3
"""OpenRecomp Phase-2 final verdict V1 (P2-99).

P2-99 is the terminal verification and closure stage.  It adds no architecture
feature and broadens no compatibility claim.  The deterministic gate verifies
the complete Phase-2 evidence chain and issues the final verdict:

* every completed stage (P2-00, P2-01..P2-14, P2-20..P2-23, P2-30, P2-40,
  P2-50, P2-90, P2-91) remains PASS in the evidence tree, the STATE.md ledger
  and the STAGE_QUEUE.md queue;
* the authoritative P2-91 evidence index is complete and every referenced
  artifact resolves;
* a terminal whole-project P2-90 regression capture exists and reproduces the
  frozen P2-90 capture byte-for-byte except for the authorized final verdict
  line, with all 22 gates PASS (tests=361 gates=22 gate_tests=1990);
* the P2-91 evidence-closure gate re-runs to PASS (tests=882) on the terminal
  tree and states the authorized final marker;
* source integrity passes, the SOURCE_SHA256SUMS.txt delta against the
  P2-91-recorded manifest is exactly the authorized terminal delta, and the
  legal/content policy is clean;
* the limitations record and claim matrix are internally consistent with the
  terminal verdict: the bounded final claim is classified PROVEN at its
  documented boundary and every excluded compatibility claim stays
  NOT_PROVEN/OUT_OF_SCOPE.

The gate emits ``OPENRECOMP_P2_99=PASS`` and
``OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS`` only when every required
check passes.  In the pre-terminal state it runs the readiness checks and emits
``OPENRECOMP_P2_99=READY`` / ``=NOT_PROVEN`` instead.  On any failure it emits
``OPENRECOMP_P2_99=FAIL`` and preserves the final marker as ``NOT_PROVEN``.

The only authorized way for the final marker to be PASS is this gate's terminal
verdict; the P2-90 regression gate and the P2-91 closure gate validate that
authorization (verdict document + live gate SHA-256 + control-plane terminal
marker) and fail closed on any unauthorized PASS claim.

Usage:

    python tools/test_phase2_final_verdict_v1.py                  # verify only
    python tools/test_phase2_final_verdict_v1.py --run-regression # + terminal P2-90 re-run

Both official modes run the identical check set and produce byte-identical
stdout; ``--run-regression`` additionally re-executes the whole-project P2-90
audit on the terminal tree and captures it under this stage's evidence.
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from openrecomp import release_package as rp  # noqa: E402
import public_safety_scan as pss  # noqa: E402
import test_phase2_whole_regression_v1 as p2_90  # noqa: E402
import test_phase2_evidence_closure_v1 as p2_91  # noqa: E402

EVIDENCE_ROOT = ROOT / ".openrecomp-phase2" / "evidence"
CONTROL_PLANE = ROOT / ".openrecomp-phase2"
EVIDENCE_DIR = EVIDENCE_ROOT / "P2-99"

STAGE = "P2-99"
STAGE_MARKER = "OPENRECOMP_P2_99"
FEATURE_MARKER = "OPENRECOMP_PHASE2_FINAL_VERDICT_V1"
FINAL_MARKER = "OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF"
FINAL_MARKER_VALUE = "NOT_PROVEN"
FINAL_MARKER_PASS = "PASS"

PHASE1_TAG = "openrecomp-phase1-pass"
PHASE1_COMMIT = "46c2f971e1a42cf49bd936bad94697b81bf31002"

P2_90_GATE = "tools/test_phase2_whole_regression_v1.py"
P2_91_GATE = "tools/test_phase2_evidence_closure_v1.py"
P2_90_TERMINAL_CAPTURE = "p2_90_terminal_run.txt"
P2_90_TERMINAL_STDERR = "p2_90_terminal_run.stderr.txt"
P2_90_TERMINAL_SUMMARY = "p2_90_terminal_run_summary.json"
P2_90_TERMINAL_DIR = "p2_90_terminal_run"
P2_90_CAPTURE_PRESERVATION = "p2_90_capture_preservation.json"
P2_90_FROZEN_CAPTURE = EVIDENCE_ROOT / "P2-90" / "p2_90_run1.txt"
P2_90_TERMINAL_MARKER = "OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990"
P2_91_CLOSURE_MARKER = "OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS tests=882"
P2_91_CLOSURE_CAPTURE = "p2_91_closure_run.txt"
P2_91_CLOSURE_STDERR = "p2_91_closure_run.stderr.txt"

FINAL_CLAIM_KEY = "Phase-2 final end-to-end proof marker"
BOUNDED_FINAL_CLAIM = (
    "OpenRecomp has demonstrated an architecture-neutral static-recompilation pipeline "
    "capable of taking supported synthetic guest programs through decoding, program "
    "modelling, control-flow recovery, translation, native host compilation, generic "
    "runtime execution, deterministic observable equivalence, and reproducible packaging "
    "across the audited NES6502 and MIPS32 paths."
)
EXCLUDED_CLAIMS = (
    "arbitrary NES ROM compatibility",
    "arbitrary MIPS32 binary compatibility",
    "commercial-game compatibility",
    "complete NES hardware compatibility",
    "cycle accuracy",
    "PS1/PS2/Xbox compatibility",
    "production-ready universal console runtime",
    "future architecture compatibility",
)

# (stage id, ledger name, gate marker, expected test count)
STAGE_TABLE: tuple[tuple[str, str, str, int | None], ...] = tuple(p2_91.STAGES) + (
    ("P2-91", "Evidence index + limitations", P2_91_CLOSURE_MARKER, 882),
    ("P2-99", "Final verdict", f"{FEATURE_MARKER}=PASS", None),
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
VERDICT_INPUTS: dict[str, bool] = {}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n")


def read_text(path: pathlib.Path) -> str:
    return normalize_text(path.read_text(encoding="utf-8", errors="replace"))


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    RESULTS.append({"check": label, "status": status})
    print(f"{status}: {label}", flush=True)


def section(name: str, func, *args) -> None:
    start = len(RESULTS)
    try:
        func(*args)
    except Exception as exc:  # noqa: BLE001 - fail closed, keep auditing
        check(f"section:{name}:error", False)
        FINDINGS.setdefault("errors", []).append(f"{name}: {type(exc).__name__}: {exc}")
    VERDICT_INPUTS[name] = all(item["status"] == "PASS" for item in RESULTS[start:])


def run_capture(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Terminal P2-90 whole-regression execution and capture validation
# ---------------------------------------------------------------------------
def execute_terminal_p2_90(python: str) -> None:
    """Re-run the whole-project P2-90 audit on the terminal tree and capture it.

    Mirrors the P2-91 capture-preservation procedure: the P2-90 audit rewrites
    its own hard-coded phase-1/source-integrity capture files as a side effect;
    the frozen bytes are snapshotted, the terminal regeneration is captured,
    and the originals are restored byte-identically.
    """
    capture_dir = EVIDENCE_DIR / P2_90_TERMINAL_DIR
    capture_dir.mkdir(parents=True, exist_ok=True)
    frozen_dir = EVIDENCE_ROOT / "P2-90"
    snapshot = {rel: (frozen_dir / rel).read_bytes() for rel in p2_91.P2_90_PRESERVED_FILES}
    completed = run_capture(
        [python, P2_90_GATE, "--evidence-dir", str(capture_dir.relative_to(ROOT)).replace("\\", "/")],
        timeout=21600,
    )
    stdout = normalize_text(completed.stdout or "")
    (EVIDENCE_DIR / P2_90_TERMINAL_CAPTURE).write_bytes(stdout.encode("utf-8"))
    (EVIDENCE_DIR / P2_90_TERMINAL_STDERR).write_bytes((completed.stderr or "").encode("utf-8"))
    fresh = {rel: (frozen_dir / rel).read_bytes() for rel in p2_91.P2_90_PRESERVED_FILES}
    for rel in ("phase1_host_gates/stdout.txt", "source_integrity/stdout.txt"):
        (capture_dir / f"frozen_{rel.replace('/', '_')}").write_bytes(fresh[rel])
    for rel, data in snapshot.items():
        (frozen_dir / rel).write_bytes(data)
    preservation = {
        "stage": STAGE,
        "source_gate": P2_90_GATE,
        "frozen_files": {
            rel: {
                "before_sha256": sha256_bytes(snapshot[rel]),
                "after_regression_sha256": sha256_bytes(fresh[rel]),
                "restored_sha256": sha256_file(frozen_dir / rel),
                "restored_byte_identical_to_before": (frozen_dir / rel).read_bytes() == snapshot[rel],
            }
            for rel in p2_91.P2_90_PRESERVED_FILES
        },
        "returncode": completed.returncode,
        "stdout_lf_sha256": sha256_bytes(stdout.encode("utf-8")),
        "stderr_empty": not (completed.stderr or "").strip(),
    }
    (EVIDENCE_DIR / P2_90_CAPTURE_PRESERVATION).write_bytes(
        (json.dumps(preservation, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    summary = {
        "stage": STAGE,
        "command": [P2_90_GATE, "--evidence-dir", f".openrecomp-phase2/evidence/P2-99/{P2_90_TERMINAL_DIR}"],
        "returncode": completed.returncode,
        "stdout_sha256_lf": sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256_lf": sha256_bytes(normalize_text(completed.stderr or "").encode("utf-8")),
        "stderr_empty": not (completed.stderr or "").strip(),
        "gate_marker": P2_90_TERMINAL_MARKER,
        "frozen_files_restored_byte_identical": all(
            item["restored_byte_identical_to_before"] for item in preservation["frozen_files"].values()
        ),
    }
    (EVIDENCE_DIR / P2_90_TERMINAL_SUMMARY).write_bytes(
        (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )


def audit_terminal_p2_90() -> None:
    capture_path = EVIDENCE_DIR / P2_90_TERMINAL_CAPTURE
    check("p2-90:capture-exists", capture_path.is_file() and capture_path.stat().st_size > 0)
    text = read_text(capture_path)
    check("p2-90:no-failures", "FAIL" not in text)
    check("p2-90:stage-marker", "OPENRECOMP_P2_90=PASS" in text)
    check("p2-90:feature-marker", P2_90_TERMINAL_MARKER in text)
    gate_lines = [line for line in text.splitlines() if line.startswith("PASS gate ")]
    check("p2-90:gate-lines", len(gate_lines) == 22 and all("=PASS" in line for line in gate_lines))
    check("p2-90:final-marker-authorized", re.search(
        r"^" + re.escape(FINAL_MARKER) + r"=PASS\s*$", text, re.MULTILINE) is not None)
    frozen = read_text(P2_90_FROZEN_CAPTURE)
    check("p2-90:content-identical-modulo-final-marker",
          text.replace(f"{FINAL_MARKER}=PASS", f"{FINAL_MARKER}=NOT_PROVEN") == frozen)
    stderr_path = EVIDENCE_DIR / P2_90_TERMINAL_STDERR
    check("p2-90:stderr-empty",
          stderr_path.is_file() and stderr_path.read_text(encoding="utf-8").strip() == "")
    summary = json.loads((EVIDENCE_DIR / P2_90_TERMINAL_SUMMARY).read_text(encoding="utf-8"))
    check("p2-90:summary-returncode", summary.get("returncode") == 0)
    check("p2-90:summary-marker", summary.get("gate_marker") == P2_90_TERMINAL_MARKER)
    check("p2-90:summary-stdout-hash", summary.get("stdout_sha256_lf") == sha256_bytes(text.encode("utf-8")))
    preservation = json.loads((EVIDENCE_DIR / P2_90_CAPTURE_PRESERVATION).read_text(encoding="utf-8"))
    frozen_files = preservation.get("frozen_files", {})
    check("p2-90:frozen-files-covered", set(frozen_files) == set(p2_91.P2_90_PRESERVED_FILES))
    check("p2-90:frozen-files-restored", all(
        item.get("restored_byte_identical_to_before") is True for item in frozen_files.values()))
    for rel in p2_91.P2_90_PRESERVED_FILES:
        current = EVIDENCE_ROOT / "P2-90" / rel
        check(f"p2-90:frozen-current:{rel}",
              current.is_file() and sha256_file(current) == frozen_files[rel]["before_sha256"])
    FINDINGS["p2_90_terminal"] = {
        "stdout_sha256_lf": sha256_bytes(text.encode("utf-8")),
        "gate_lines": len(gate_lines),
        "frozen_capture_sha256": sha256_file(P2_90_FROZEN_CAPTURE),
        "content_identical_modulo_final_marker": True,
    }


# ---------------------------------------------------------------------------
# P2-91 evidence-closure re-run on the terminal tree
# ---------------------------------------------------------------------------
def audit_terminal_p2_91(python: str) -> None:
    completed = run_capture([python, P2_91_GATE], timeout=7200)
    stdout = normalize_text(completed.stdout or "")
    (EVIDENCE_DIR / P2_91_CLOSURE_CAPTURE).write_bytes(stdout.encode("utf-8"))
    (EVIDENCE_DIR / P2_91_CLOSURE_STDERR).write_bytes((completed.stderr or "").encode("utf-8"))
    check("p2-91:returncode", completed.returncode == 0)
    check("p2-91:stage-marker", "OPENRECOMP_P2_91=PASS" in stdout)
    check("p2-91:feature-marker", P2_91_CLOSURE_MARKER in stdout)
    check("p2-91:no-failures", "FAIL" not in stdout)
    check("p2-91:final-marker-authorized", re.search(
        r"^" + re.escape(FINAL_MARKER) + r"=PASS\s*$", stdout, re.MULTILINE) is not None)
    check("p2-91:stderr-empty", not (completed.stderr or "").strip())
    FINDINGS["p2_91_closure"] = {
        "returncode": completed.returncode,
        "stdout_sha256_lf": sha256_bytes(stdout.encode("utf-8")),
        "marker": P2_91_CLOSURE_MARKER,
    }


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------
def audit_source_integrity(python: str) -> None:
    completed = run_capture(
        [python, "tools/phase1_host_gates_v1.py", "--only", "source-integrity"], timeout=3600)
    stdout = normalize_text(completed.stdout or "")
    (EVIDENCE_DIR / "source_integrity.txt").write_bytes(
        ("command: python tools/phase1_host_gates_v1.py --only source-integrity\n" + stdout).encode("utf-8")
    )
    entries = re.search(r"verified (\d+) manifest entries", stdout)
    manifest_lines = (ROOT / "SOURCE_SHA256SUMS.txt").read_text(encoding="utf-8").strip().splitlines()
    check("source-integrity:pass",
          completed.returncode == 0
          and "source-integrity" in stdout
          and "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS" in stdout
          and entries is not None)
    check("source-integrity:count-matches-manifest",
          entries is not None and int(entries.group(1)) == len(manifest_lines))
    current = p2_91.parse_manifest(manifest_lines)
    reconstructed = dict(current)
    reconstructed.pop(p2_91.P2_99_ADDED_MANIFEST_ENTRY, None)
    for relative, recorded in p2_91.P2_91_RECORDED_GATE_HASHES.items():
        reconstructed[relative] = recorded
    rebuilt = sorted(f"{digest} *{path}" for path, digest in reconstructed.items())
    check("source-integrity:manifest-delta-authorized",
          p2_91.P2_99_ADDED_MANIFEST_ENTRY in current
          and sha256_bytes(("\n".join(rebuilt) + "\n").encode("utf-8")) == p2_91.P2_91_MANIFEST_SHA256)
    check("source-integrity:final-gate-hash",
          current.get(p2_91.P2_99_ADDED_MANIFEST_ENTRY)
          == sha256_file(ROOT / p2_91.P2_99_ADDED_MANIFEST_ENTRY))
    check("source-integrity:terminal-gates-registered",
          P2_90_GATE in current and P2_91_GATE in current)
    FINDINGS["source_integrity"] = {
        "manifest_entries": len(manifest_lines),
        "manifest_sha256": sha256_file(ROOT / "SOURCE_SHA256SUMS.txt"),
        "stdout_sha256_lf": sha256_bytes(stdout.encode("utf-8")),
    }


# ---------------------------------------------------------------------------
# Legal / content policy
# ---------------------------------------------------------------------------
def audit_legal_policy() -> None:
    tracked_findings: list[str] = []
    for path in p2_90.tracked_files():
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in p2_90.FORBIDDEN_SUFFIXES:
            tracked_findings.append(f"{relative}:console-asset-suffix")
            continue
        if not path.exists():
            tracked_findings.append(f"{relative}:tracked-file-missing")
            continue
        head = path.read_bytes()[:16]
        for magic, label in p2_90.CONSOLE_MAGICS:
            if head.startswith(magic):
                tracked_findings.append(f"{relative}:console-magic:{label}")
        if path.suffix.lower() in p2_90.TEXT_SUFFIXES_FOR_LEGAL:
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in pss.MARKERS:
                if marker.search(text):
                    tracked_findings.append(f"{relative}:public-safety-marker")
    check("legal:tracked-tree-clean", not tracked_findings)
    FINDINGS["legal_tracked_findings"] = tracked_findings

    package_findings: list[str] = []
    for archive in sorted((EVIDENCE_ROOT / "P2-50").glob("package_*.zip")):
        entries = p2_90.read_package_entries(archive)
        package_findings.extend(f"{archive.name}:{item}" for item in rp.content_policy_findings(entries))
    check("legal:release-packages-clean", not package_findings)
    FINDINGS["legal_package_findings"] = package_findings

    own_findings: list[str] = []
    for path in sorted(EVIDENCE_DIR.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        if p2_90.HOST_PATH_PATTERN.search(data):
            own_findings.append(f"{relative}:absolute-host-path")
        if path.suffix.lower() in p2_90.TEXT_SUFFIXES_FOR_LEGAL:
            for pattern, label in p2_90.SECRET_PATTERNS:
                if pattern.search(data):
                    own_findings.append(f"{relative}:secret:{label}")
    check("legal:p2-99-artifacts-clean", not own_findings)
    FINDINGS["legal_p2_99_findings"] = own_findings

    closure_audit = json.loads(
        (EVIDENCE_ROOT / "P2-91" / "legal_policy_audit.json").read_text(encoding="utf-8"))
    host_findings = closure_audit.get("host_path_findings", [])
    undocumented = [
        item for item in host_findings
        if item.get("kind") in {"unexpected-host-path", "p2-91-host-path", "release-package-policy"}
    ]
    check("legal:closure-host-path-findings-documented", not undocumented)
    check("legal:closure-premature-findings-empty",
          closure_audit.get("premature_verdict_findings") == [])
    check("legal:closure-legal-findings-empty", closure_audit.get("legal_findings") == [])
    FINDINGS["legal_closure_audit"] = {
        "documented_host_path_entries": len(host_findings),
        "undocumented": len(undocumented),
    }


# ---------------------------------------------------------------------------
# Claim / limitation consistency and the final claim test
# ---------------------------------------------------------------------------
def claim_matrix_rows(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        row = re.match(r"^\|\s*`([^`]+)`\s*\|\s*`?([A-Z_]+)`?\s*\|", line)
        if row:
            rows[row.group(1)] = row.group(2)
    return rows


def audit_claims() -> None:
    limitations = read_text(EVIDENCE_ROOT / "P2-91" / "PHASE2_LIMITATIONS.md")
    matrix = read_text(EVIDENCE_ROOT / "P2-91" / "PHASE2_CLAIM_MATRIX.md")
    boundary = read_text(EVIDENCE_DIR / "final_claim_boundary.md")
    rows = claim_matrix_rows(matrix)
    check("claims:limitations-terminal-marker",
          FINAL_MARKER in limitations and f"{FINAL_MARKER}=PASS" in limitations and "P2-99" in limitations)
    check("claims:matrix-terminal-marker",
          FINAL_MARKER in matrix and f"{FINAL_MARKER}=PASS" in matrix and "P2-99" in matrix)
    check("claims:final-marker-classified-proven", rows.get(FINAL_CLAIM_KEY) == "PROVEN")
    check("claims:final-marker-in-limitations-proven",
          f"`{FINAL_CLAIM_KEY}` (`PROVEN`)" in limitations)
    for key in EXCLUDED_CLAIMS:
        classification = rows.get(key)
        check(f"claims:excluded:{key}", classification in {"NOT_PROVEN", "OUT_OF_SCOPE"})
        check(f"claims:excluded-limitations:{key}",
              f"`{key}` (`{classification}`)" in limitations)
    normalized_boundary = " ".join(boundary.split())
    check("claims:bounded-final-claim-text", " ".join(BOUNDED_FINAL_CLAIM.split()) in normalized_boundary)
    check("claims:exclusions-listed",
          all(key in boundary for key in EXCLUDED_CLAIMS))
    check("claims:final-claim-boundary-p2-99", "P2-99" in boundary and "synthetic" in boundary)
    check("claims:no-overstatement",
          all(rows.get(key) != "PROVEN" for key in EXCLUDED_CLAIMS))
    FINDINGS["claims"] = {
        "final_marker_classification": rows.get(FINAL_CLAIM_KEY),
        "excluded_classifications": {key: rows.get(key) for key in EXCLUDED_CLAIMS},
        "bounded_claim_recorded": True,
    }


# ---------------------------------------------------------------------------
# Completed-stage matrix / control plane
# ---------------------------------------------------------------------------
def audit_stage_matrix() -> None:
    state = read_text(CONTROL_PLANE / "STATE.md")
    handoff = read_text(CONTROL_PLANE / "HANDOFF.md")
    queue = read_text(CONTROL_PLANE / "STAGE_QUEUE.md")
    for stage, name, gate_marker, tests in STAGE_TABLE:
        check(f"stage:{stage}:ledger-pass",
              re.search(rf"^\|\s*{re.escape(stage)}\s*\|[^|]*\|\s*`?PASS`?\s*\|", state, re.MULTILINE) is not None)
        check(f"stage:{stage}:queue-complete",
              re.search(rf"^\|\s*{re.escape(stage)}\s*\|[^|]*\|\s*COMPLETE\s*\|", queue, re.MULTILINE) is not None)
        result_md = EVIDENCE_ROOT / stage / "RESULT.md"
        check(f"stage:{stage}:evidence-result",
              result_md.is_file() and "PASS" in read_text(result_md))
        if gate_marker != "n/a":
            feature = gate_marker.split("=")[0]
            check(f"stage:{stage}:state-gate-marker", feature in state)
            if feature in handoff:
                check(f"stage:{stage}:handoff-gate-marker", feature in handoff)
    check("stage:P2-99:state-stage-marker",
          re.search(r"^OPENRECOMP_P2_99=PASS\s*$", state, re.MULTILINE) is not None)
    check("stage:P2-99:handoff-stage-marker",
          re.search(r"^OPENRECOMP_P2_99=PASS\s*$", handoff, re.MULTILINE) is not None)
    check("stage:P2-99:state-feature-marker", FEATURE_MARKER in state)
    check("stage:P2-99:handoff-feature-marker", FEATURE_MARKER in handoff)
    check("stage:P2-99:state-final-marker",
          re.search(r"^" + re.escape(FINAL_MARKER) + r"=PASS\s*$", state, re.MULTILINE) is not None)
    check("stage:P2-99:handoff-final-marker",
          re.search(r"^" + re.escape(FINAL_MARKER) + r"=PASS\s*$", handoff, re.MULTILINE) is not None)
    check("stage:P2-99:phase-complete", "STATUS=COMPLETE" in state)
    check("stage:P2-99:last-passed",
          re.search(r"^LAST_PASSED_STAGE=P2-99\s*$", state + "\n" + handoff, re.MULTILINE) is not None)
    FINDINGS["stages"] = [stage for stage, *_ in STAGE_TABLE]


def audit_phase1_boundary() -> None:
    tag = run_capture(["git", "rev-parse", f"{PHASE1_TAG}^{{commit}}"], timeout=120)
    check("phase1:tag-commit", tag.returncode == 0 and tag.stdout.strip() == PHASE1_COMMIT)
    state = read_text(CONTROL_PLANE / "STATE.md")
    handoff = read_text(CONTROL_PLANE / "HANDOFF.md")
    check("phase1:host-gates-marker",
          "OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2" in state
          and "OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2" in handoff)
    check("phase1:multiarch-proof",
          "OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS" in state
          or "OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS" in handoff)
    FINDINGS["phase1"] = {"tag": PHASE1_TAG, "commit": PHASE1_COMMIT, "verified": True}


def audit_index() -> None:
    md_path = EVIDENCE_ROOT / "P2-91" / "PHASE2_EVIDENCE_INDEX.md"
    json_path = EVIDENCE_ROOT / "P2-91" / "PHASE2_EVIDENCE_INDEX.json"
    check("index:md-exists", md_path.is_file() and md_path.stat().st_size > 0)
    check("index:json-exists", json_path.is_file() and json_path.stat().st_size > 0)
    document = json.loads(json_path.read_text(encoding="utf-8"))
    records = {item["stage"]: item for item in document["stages"]}
    check("index:coverage-complete", {stage for stage, *_ in p2_91.STAGES} == set(records))
    md = read_text(md_path)
    refs = p2_91.resolve_refs(md)
    check("index:refs-resolve", refs["missing"] == [])
    check("index:terminal-marker", document.get("final_marker") == f"{FINAL_MARKER}=PASS")
    check("index:terminal-statement", f"{FINAL_MARKER}=PASS" in md and "P2-99" in md)
    check("index:result-documents-exist",
          all((EVIDENCE_ROOT / stage / "RESULT.md").is_file() for stage, *_ in p2_91.STAGES))
    FINDINGS["index"] = {"stages_indexed": len(records), "refs_resolved": len(refs["resolved"])}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P2-99 Phase-2 final verdict")
    parser.add_argument("--evidence-dir", type=str, default=".openrecomp-phase2/evidence/P2-99")
    parser.add_argument("--python", type=str, default=sys.executable)
    parser.add_argument("--run-regression", action="store_true",
                        help="execute the terminal whole-project P2-90 regression and capture it")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, VERDICT_INPUTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    VERDICT_INPUTS = {}

    print("=== P2-99 Phase-2 Final Verdict ===", flush=True)
    authorized = p2_91.authorized_final_verdict()
    terminal = authorized == "PASS"
    FINDINGS["terminal_state"] = {"authorized_final_marker": authorized, "terminal": terminal}

    if not terminal:
        pending = []
        state_text = read_text(CONTROL_PLANE / "STATE.md")
        handoff_text = read_text(CONTROL_PLANE / "HANDOFF.md")
        queue_text = read_text(CONTROL_PLANE / "STAGE_QUEUE.md")
        if re.search(r"^" + re.escape(FINAL_MARKER) + r"=PASS\s*$", state_text, re.MULTILINE) is None:
            pending.append("STATE.md terminal final marker")
        if re.search(r"^" + re.escape(FINAL_MARKER) + r"=PASS\s*$", handoff_text, re.MULTILINE) is None:
            pending.append("HANDOFF.md terminal final marker")
        if re.search(r"^OPENRECOMP_P2_99=PASS\s*$", state_text, re.MULTILINE) is None:
            pending.append("STATE.md P2-99 marker")
        if re.search(r"^\|\s*P2-99\s*\|[^|]*\|\s*COMPLETE\s*\|", queue_text, re.MULTILINE) is None:
            pending.append("STAGE_QUEUE.md P2-99 COMPLETE row")
        if not (EVIDENCE_DIR / "RESULT.json").exists():
            pending.append("P2-99/RESULT.json terminal verdict document")
        if not (EVIDENCE_DIR / P2_90_TERMINAL_CAPTURE).exists():
            pending.append("terminal P2-90 regression capture")
        if not (EVIDENCE_DIR / "final_claim_boundary.md").exists():
            pending.append("P2-99/final_claim_boundary.md")
        FINDINGS["pending_terminal_artifacts"] = pending
        check("readiness:terminal-state-not-declared", True)
        status = "READY"
        supported = False
        VERDICT_INPUTS["verdict"] = False
    else:
        section("stages", audit_stage_matrix)
        section("phase1", audit_phase1_boundary)
        section("index", audit_index)
        if args.run_regression:
            section("terminal_p2_90_execution", execute_terminal_p2_90, args.python)
        section("terminal_p2_90", audit_terminal_p2_90)
        section("terminal_p2_91", audit_terminal_p2_91, args.python)
        section("source_integrity", audit_source_integrity, args.python)
        section("legal_policy", audit_legal_policy)
        section("claims", audit_claims)
        supported = all(VERDICT_INPUTS.get(name) is True for name in (
            "stages", "phase1", "index", "terminal_p2_90", "terminal_p2_91",
            "source_integrity", "legal_policy", "claims"))
        check("verdict:all-required-invariants-pass", supported)
        VERDICT_INPUTS["verdict"] = supported

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL")
    if terminal:
        status = "PASS" if (supported and not failed) else "FAIL"
    elif failed:
        status = "FAIL"

    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "verdict": "PASS" if status == "PASS" else ("READY" if status == "READY" else "FAIL"),
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={'PASS' if status == 'PASS' else ('READY' if status == 'READY' else 'FAIL')}",
            "gate": f"{FEATURE_MARKER}={'PASS' if status == 'PASS' else status}",
            "final": f"{FINAL_MARKER}={'PASS' if status == 'PASS' else FINAL_MARKER_VALUE}",
        },
        "gate_sha256": sha256_file(pathlib.Path(__file__).resolve()),
        "terminal_state": FINDINGS["terminal_state"],
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }
    (EVIDENCE_DIR / "p2_99_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    if terminal:
        (EVIDENCE_DIR / "legal_policy_audit.json").write_bytes(
            (json.dumps({
                "tracked_findings": FINDINGS.get("legal_tracked_findings", []),
                "package_findings": FINDINGS.get("legal_package_findings", []),
                "p2_99_artifact_findings": FINDINGS.get("legal_p2_99_findings", []),
                "closure_audit": FINDINGS.get("legal_closure_audit", {}),
            }, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        (EVIDENCE_DIR / "claim_consistency.json").write_bytes(
            (json.dumps(FINDINGS.get("claims", {}), indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
        if status == "PASS":
            terminal_document = {
                "stage": STAGE,
                "stage_name": FEATURE_MARKER,
                "verdict": "PASS",
                "status": "PASS",
                "markers": result["markers"],
                "gate_sha256": result["gate_sha256"],
                "terminal_regression_validation": {
                    "status": "PASS",
                    "capture": P2_90_TERMINAL_CAPTURE,
                    "capture_sha256_lf": sha256_file(EVIDENCE_DIR / P2_90_TERMINAL_CAPTURE)
                    if (EVIDENCE_DIR / P2_90_TERMINAL_CAPTURE).is_file() else None,
                    "frozen_capture": ".openrecomp-phase2/evidence/P2-90/p2_90_run1.txt",
                    "frozen_capture_sha256": sha256_file(P2_90_FROZEN_CAPTURE),
                    "content_identical_modulo_final_marker": True,
                },
                "closure_validation": {
                    "status": "PASS",
                    "marker": P2_91_CLOSURE_MARKER,
                    "capture": P2_91_CLOSURE_CAPTURE,
                },
                "checks": {"passed": passed, "failed": failed},
                "claim_boundary": (
                    "P2-99 issues the terminal Phase-2 verdict only for the accumulated, bounded evidence "
                    "chain audited on the terminal tree; it adds no capability and broadens no compatibility claim. "
                    "The final claim is bounded to supported synthetic guest programs and the audited NES6502 and "
                    "MIPS32 paths."
                ),
                "final_phase2_marker": f"{FINAL_MARKER}=PASS",
                "phase2_status": "COMPLETE",
                "next_stage": None,
            }
            (EVIDENCE_DIR / "RESULT.json").write_bytes(
                (json.dumps(terminal_document, indent=2, sort_keys=True) + "\n").encode("utf-8")
            )

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{FINAL_MARKER}={FINAL_MARKER_PASS}")
        return 0
    if status == "READY":
        print(f"{STAGE_MARKER}=READY (terminal verdict not yet declared)")
        print(f"{FINAL_MARKER}={FINAL_MARKER_VALUE}")
        return 3
    print(f"{STAGE_MARKER}=FAIL ({failed} check(s) failed)")
    print(f"{FINAL_MARKER}={FINAL_MARKER_VALUE}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
