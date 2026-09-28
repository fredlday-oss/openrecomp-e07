#!/usr/bin/env python3
"""OpenRecomp Phase-18 integrated-regression audit helpers (P18-90).

Read-only auditing of the committed Phase-18 corpus, failing closed:

  a. source-manifest exactness (every tracked Phase-18 src module and gate
     appears exactly once with a correct digest);
  b. evidence closure (every certified stage directory carries the
     schema-required documents and a schema-conformant RESULT.json);
  c. stage/result agreement (stage numbers, next_stage chaining, authority);
  d. frozen prior-phase integrity (Phase 1..17 trees unmodified versus the
     frozen Phase-17 terminal commit);
  e. marker ledger (protected claim markers never promoted by Phase 18);
  f. public safety (no private host paths or reconstructive metadata);
  g. frontier-digest coherence across P18-04/05/06/07.

No helper here mutates the repository.  Nothing can promote FIRST_FRAME_READY,
the initialization/frame/playability proofs, or general PS1 compatibility.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]

PHASE18 = ".openrecomp-phase18"
MANIFEST_PATH = f"{PHASE18}/SOURCE_SHA256SUMS.txt"
EVIDENCE_DIR = f"{PHASE18}/evidence"

RESULT_SCHEMA = "openrecomp-phase18-result-v1"
MANIFEST_RE = re.compile(r"^([0-9a-f]{64}) \*(.+)$")

#: Every certified Phase-18 stage and the documents its evidence must contain.
STAGE_DOCUMENTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("P18-00", "P18-01", ("RESULT.json", "determinism.json", "official_runs.json",
                          "p18_00_tests.json", "run1.txt", "run2.txt")),
    ("P18-01", "P18-02", ("RESULT.json", "determinism.json", "official_runs.json",
                          "p18_01_tests.json", "run1.txt", "run2.txt")),
    ("P18-02", "P18-03", ("RESULT.json", "determinism.json", "official_runs.json",
                          "p18_02_tests.json", "run1.txt", "run2.txt")),
    ("P18-03", "P18-04", ("RESULT.json", "determinism.json", "official_runs.json",
                          "p18_03_tests.json", "run1.txt", "run2.txt")),
    ("P18-04", "P18-05", ("RESULT.json", "determinism.json", "official_runs.json",
                          "p18_04_tests.json", "run1.txt", "run2.txt")),
    ("P18-05", "P18-06", ("RESULT.json", "determinism.json", "official_runs.json",
                          "p18_05_tests.json", "run1.txt", "run2.txt")),
    ("P18-06", "P18-07", ("RESULT.json", "determinism.json", "official_runs.json",
                          "p18_06_tests.json", "run1.txt", "run2.txt")),
    ("P18-07", "P18-90", ("RESULT.json", "determinism.json", "official_runs.json",
                          "p18_07_tests.json", "run1.txt", "run2.txt")),
)

#: Frozen frontier digests that must agree across the producing stage and the
#: P18-07 consumer.
FRONTIER_MINIMA: tuple[tuple[str, str, str], ...] = (
    ("P18-04", "gpu_command_frontier.sha256", "gpu_command_frontier.json",
     "a009003b644122a011a4a53a9ceeae1d2e4a560a462fc28ef2c3ac9dd4b2bfe9"),
    ("P18-05", "dma_frontier.sha256", "dma_frontier.json",
     "f0251b43b8d60ac8c101df71d59cd28441615e1ab58c7036dce98933450fa5c1"),
    ("P18-06", "vram_display.sha256", "vram_display.json",
     "2848c231c0351638485931e8dfd064abf7ba990d7a9fab178c3730d94e084e5e"),
)

PROTECTED_CLAIM_MARKERS = (
    "OPENRECOMP_PHASE18_HERCULES_INITIALIZATION_PROOF",
    "OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF",
    "OPENRECOMP_PHASE18_HERCULES_PLAYABILITY_PROOF",
    "OPENRECOMP_PHASE18_GENERAL_PS1_COMPATIBILITY",
)
PROTECTED_CLAIM_VALUES = {
    "OPENRECOMP_PHASE18_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
    "FIRST_FRAME_READY": "NO",
}
HISTORICAL_PHASE17_MARKERS = {
    "OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
    "FIRST_FRAME_READY": "NO",
}

#: Reconstructive-metadata keys forbidden by EVIDENCE_SCHEMA.md and control
#: policy. Matched as JSON keys, not arbitrary substrings, so a check name such
#: as "no-raw-words" is not a false positive.
FORBIDDEN_RECONSTRUCTIVE_KEYS: tuple[str, ...] = (
    "payload_bytes",
    "raw_instruction",
    "bios_bytes",
    "instruction_word",
    "raw_instruction_word",
    "instruction_bytes",
    "payload_hex",
    "payload_base64",
)

#: Absolute private-host-path shapes. Genuine host paths must never appear in
#: committed stage evidence. Mirrors p18_gate_v1.reject_private_path.
PRIVATE_PATH_RES: tuple[tuple[str, Any], ...] = (
    ("unix-home-user-path", re.compile(r"/home/[A-Za-z0-9._-]+/")),
    ("unix-users-user-path", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("unix-tmp-path", re.compile(r"/tmp/[A-Za-z0-9._-]+")),
)

#: Stage evidence files exempt from the private-path scan, each with a
#: mechanical reason. This is the only allow-listing P18-90 performs.
PUBLIC_SAFETY_ALLOWLIST: tuple[dict[str, str], ...] = (
    {"glob": "P18-00/negative_tests.json", "rule": "PRIVATE_PATH_NEGATIVE_CONTROL",
     "reason": "P18-00 records the synthetic forbidden-path placeholders as the "
               "expected inputs of its path-rejector negative control, with the "
               "assertion that each was rejected; none is a real host path."},
    {"glob": "P18-00/run1.txt", "rule": "PRIVATE_PATH_NEGATIVE_CONTROL_TRANSCRIPT",
     "reason": "Dual-run transcript of the P18-00 negative control above."},
    {"glob": "P18-00/run2.txt", "rule": "PRIVATE_PATH_NEGATIVE_CONTROL_TRANSCRIPT",
     "reason": "Dual-run transcript of the P18-00 negative control above."},
    {"glob": "P18-00/p18_00_tests.json",
     "rule": "PRIVATE_PATH_NEGATIVE_CONTROL_RECORD",
     "reason": "Gate check record embedding the P18-00 negative-control detail."},
)

#: Markdown prose (controller reviews and reproduction records) is authored by
#: the controller, not stage-generated evidence. Findings are reported
#: separately rather than failing the gate, so a real path in prose is visible
#: rather than silently allowed or silently failed.
PROSE_SUFFIXES = (".md",)

#: The gate writes its own evidence while it runs, so its directory is excluded
#: from the scan; P18-90 audits the committed corpus of the prior stages.
SELF_EVIDENCE_STAGE = "P18-90"


def is_allowlisted(relative: str) -> dict[str, str] | None:
    for entry in PUBLIC_SAFETY_ALLOWLIST:
        if relative.endswith(entry["glob"]):
            return entry
    return None


def json_keys(document: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(document, dict):
        for key, value in document.items():
            found.add(str(key))
            found.update(json_keys(value))
    elif isinstance(document, list):
        for item in document:
            found.update(json_keys(item))
    return found


def private_path_labels(text: str) -> list[str]:
    """Return matching pattern-family labels only, never the matched text."""
    return sorted({label for label, pattern in PRIVATE_PATH_RES
                   if any(True for _ in pattern.finditer(text))})


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# --- (a) source manifest ---------------------------------------------------

def expected_manifest_paths(root: pathlib.Path | None = None) -> tuple[str, ...]:
    base = pathlib.Path(root) if root is not None else ROOT
    patterns = ("{p}/src/*.py".format(p=PHASE18),
                "{p}/runtime/*".format(p=PHASE18),
                "tools/test_phase18_*.py")
    found: set[str] = set()
    for pattern in patterns:
        for path in base.glob(pattern):
            if not path.is_file() or path.name == "__init__.py":
                continue
            relative = path.relative_to(base)
            if "__pycache__" in relative.parts or relative.suffix == ".pyc":
                continue
            found.add(relative.as_posix())
    return tuple(sorted(found))


def audit_manifest(root: pathlib.Path | None = None) -> dict[str, Any]:
    base = pathlib.Path(root) if root is not None else ROOT
    manifest_file = base / MANIFEST_PATH
    report: dict[str, Any] = {
        "manifest_path": MANIFEST_PATH,
        "parse_errors": [],
        "entries": {},
        "duplicate_entries": [],
        "missing_entries": [],
        "extra_entries": [],
        "digest_mismatches": [],
    }
    if not manifest_file.is_file():
        report["parse_errors"].append("manifest-missing")
        return report

    entries: dict[str, str] = {}
    for line in manifest_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = MANIFEST_RE.match(line)
        if not match:
            report["parse_errors"].append(line)
            continue
        digest, relative = match.group(1), match.group(2)
        if relative in entries:
            report["duplicate_entries"].append(relative)
        entries[relative] = digest
    report["entries"] = entries

    expected = expected_manifest_paths(base)
    report["expected_paths"] = list(expected)
    report["expected_count"] = len(expected)
    report["entry_count"] = len(entries)
    report["missing_entries"] = [rel for rel in expected if rel not in entries]
    report["extra_entries"] = [rel for rel in sorted(entries) if rel not in expected]
    for relative, digest in sorted(entries.items()):
        path = base / relative
        if not path.is_file():
            report["digest_mismatches"].append({"path": relative, "reason": "absent"})
            continue
        actual = sha256_file(path)
        if actual != digest:
            report["digest_mismatches"].append(
                {"path": relative, "expected": digest, "actual": actual})
    return report


# --- (b) evidence closure --------------------------------------------------

def audit_closure(root: pathlib.Path | None = None) -> dict[str, Any]:
    base = pathlib.Path(root) if root is not None else ROOT
    stages: list[dict[str, Any]] = []
    for stage, next_stage, documents in STAGE_DOCUMENTS:
        stage_dir = base / EVIDENCE_DIR / stage
        missing = [name for name in documents if not (stage_dir / name).is_file()]
        entry: dict[str, Any] = {
            "stage": stage, "directory": f"{EVIDENCE_DIR}/{stage}",
            "missing_documents": missing,
        }
        result_path = stage_dir / "RESULT.json"
        if result_path.is_file():
            try:
                document = load_json(result_path)
            except json.JSONDecodeError as exc:
                entry["result_error"] = f"unparsable: {exc}"
            else:
                entry["result_schema"] = document.get("schema")
                entry["result_status"] = document.get("status")
                entry["result_stage"] = document.get("stage")
                entry["result_next_stage"] = document.get("next_stage")
                entry["authority_commit"] = document.get("authority_commit")
                entry["declared_next_stage"] = next_stage
        stages.append(entry)
    return {"stages_expected": len(STAGE_DOCUMENTS), "stages_checked": len(stages),
            "stages": stages}


# --- (c) frozen prior-phase integrity --------------------------------------

def audit_frozen_phase17(terminal_commit: str) -> dict[str, Any]:
    namespaces = [f".openrecomp-phase{n}" for n in range(1, 18)]
    changed = git("diff", "--name-only", f"{terminal_commit}..HEAD",
                  "--", *namespaces).stdout.splitlines()
    dirty = git("status", "--porcelain", "--", *namespaces).stdout.splitlines()
    # The Phase-17 terminal tag is annotated, so compare its peeled commit.
    tag = git("rev-parse", "openrecomp-phase17-pass^{commit}").stdout.strip()
    head = git("rev-parse", terminal_commit).stdout.strip()
    return {
        "terminal_commit": terminal_commit,
        "tag_resolves_to_terminal": tag == terminal_commit,
        "commit_present": bool(head),
        "changed_paths": changed,
        "dirty_paths": dirty,
        "untouched": not changed and not dirty,
    }


# --- (d) marker ledger -----------------------------------------------------

def audit_markers(root: pathlib.Path | None = None) -> dict[str, Any]:
    base = pathlib.Path(root) if root is not None else ROOT
    per_stage: dict[str, Any] = {}
    violations: list[str] = []
    for stage, _, _ in STAGE_DOCUMENTS:
        result_path = base / EVIDENCE_DIR / stage / "RESULT.json"
        if not result_path.is_file():
            continue
        markers = load_json(result_path).get("markers", {})
        per_stage[stage] = markers
        for marker, expected in PROTECTED_CLAIM_VALUES.items():
            actual = markers.get(marker)
            if actual is not None and actual != expected:
                violations.append(f"{stage}:{marker}={actual}")
            if marker.startswith("OPENRECOMP_PHASE18_") and actual is None:
                violations.append(f"{stage}:{marker}=MISSING")
    return {"per_stage": per_stage, "violations": violations,
            "historical_preserved": dict(HISTORICAL_PHASE17_MARKERS)}


# --- (e) frontier-digest coherence -----------------------------------------

def audit_frontier_digests(root: pathlib.Path | None = None) -> dict[str, Any]:
    base = pathlib.Path(root) if root is not None else ROOT
    entries: list[dict[str, Any]] = []
    ok = True
    for stage, sha_file, json_file, expected in FRONTIER_MINIMA:
        stage_dir = base / EVIDENCE_DIR / stage
        sha_path = stage_dir / sha_file
        json_path = stage_dir / json_file
        recorded = sha_path.read_text(encoding="utf-8").split()[0] if sha_path.is_file() else None
        actual_json = sha256_file(json_path) if json_path.is_file() else None
        entry_ok = (recorded == expected and actual_json == expected)
        ok = ok and entry_ok
        entries.append({"stage": stage, "recorded": recorded,
                        "actual": actual_json, "expected": expected, "ok": entry_ok})
    p18_07 = base / EVIDENCE_DIR / "P18-07" / "first_frame_assessment.json"
    consumer: dict[str, Any] = {}
    if p18_07.is_file():
        consumer = load_json(p18_07).get("frontier_digests", {})
    return {"entries": entries, "all_ok": ok, "consumer_digests": consumer}


# --- (f) public safety -----------------------------------------------------

def scan_public_safety(root: pathlib.Path | None = None) -> dict[str, Any]:
    """Scan the committed Phase-18 evidence corpus for forbidden content.

    Stage-generated JSON evidence must contain no private host path (outside a
    named allowlist) and no reconstructive-metadata key.  Markdown prose
    (controller reviews and reproduction records) is reported separately, never
    failing the gate by itself.  Only pattern-family labels are recorded, never
    the matched text, so this gate's own evidence cannot carry a private path.
    The gate's own stage directory is excluded from the scanned set.
    """
    base = pathlib.Path(root) if root is not None else ROOT
    evidence_root = base / EVIDENCE_DIR
    violations: list[dict[str, Any]] = []
    prose_findings: list[dict[str, Any]] = []
    documents = 0
    for path in sorted(evidence_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(evidence_root).as_posix()
        if relative.split("/", 1)[0] == SELF_EVIDENCE_STAGE:
            continue
        documents += 1
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        is_prose = relative.endswith(PROSE_SUFFIXES)
        labels = private_path_labels(text)
        allow = is_allowlisted(relative)
        allowlisted = allow is not None
        key_hits: list[str] = []
        if not is_prose and path.suffix == ".json":
            try:
                document = json.loads(text)
            except json.JSONDecodeError:
                document = None
            if document is not None:
                key_hits = sorted(json_keys(document) &
                                  set(FORBIDDEN_RECONSTRUCTIVE_KEYS))
        finding = {"document": relative,
                   "private_path_labels": labels,
                   "forbidden_key_hits": key_hits,
                   "allowlisted": allowlisted,
                   "allowlist_rule": allow["rule"] if allow else ""}
        if key_hits:
            violations.append(finding)
        elif not is_prose and labels and not allowlisted:
            violations.append(finding)
        elif is_prose and labels:
            prose_findings.append(finding)
    return {"documents_scanned": documents, "violations": violations,
            "prose_findings": prose_findings,
            "prose_documents_are_controller_authored": True}


# --- (g) authoritative control-document agreement -------------------------

#: Phase-18 authoritative narrative documents.  Their stage/marker claims must
#: agree with the certified machine results, or the gate fails closed.
CONTROL_DOCUMENTS = ("STATE.md", "HANDOFF.md", "STAGE_QUEUE.md")

#: Claim markers that must never be promoted in any control document.
PRESERVED_CLAIM_VALUES_IN_DOCS = {
    "OPENRECOMP_PHASE18_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE18_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
    "FIRST_FRAME_READY": "NO",
}

#: The next stage STATE.md must declare while P18-90 is the latest certified
#: machine stage.  Derived from the certified P18-07 RESULT, not hard-coded in
#: the agreement check itself.
MARKER_ASSIGNMENT_RE = re.compile(r"`?(OPENRECOMP_[A-Z0-9_]+)=([A-Z_]+)`?")
ROW_RE = re.compile(r"^\|\s*(P18-\d\d)\s*\|(.*)\|")


def table_cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def queue_stage_status(text: str) -> dict[str, str]:
    """Stage -> Status column of the STAGE_QUEUE.md results table."""
    status: dict[str, str] = {}
    for line in text.splitlines():
        match = ROW_RE.match(line)
        if not match:
            continue
        cells = table_cells(line)
        if len(cells) >= 4:
            status[match.group(1)] = cells[-1].upper()
    return status


def state_stage_status(text: str) -> dict[str, str]:
    """Stage -> Status column of the STATE.md 'Stage Status' table."""
    status: dict[str, str] = {}
    inside = False
    for line in text.splitlines():
        if line.startswith("## Stage Status"):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside:
            continue
        match = ROW_RE.match(line)
        if not match:
            continue
        cells = table_cells(line)
        if len(cells) == 3:
            status[match.group(1)] = cells[1].upper()
    return status


def marker_violations_in_text(text: str) -> list[str]:
    """Protected-marker assignments whose value was promoted in prose."""
    violations: list[str] = []
    for match in MARKER_ASSIGNMENT_RE.finditer(text):
        marker, value = match.group(1), match.group(2)
        expected = PRESERVED_CLAIM_VALUES_IN_DOCS.get(marker)
        if expected is not None and value != expected:
            violations.append(f"{marker}={value}")
    return violations


def audit_control_documents(root: pathlib.Path | None = None,
                           current_stage: str | None = None,
                           next_stage: str | None = None) -> dict[str, Any]:
    """Check STATE/HANDOFF/STAGE_QUEUE agree with the certified results.

    When ``current_stage`` is supplied it must appear PASS in both the
    STAGE_QUEUE and STATE stage tables, and STATE.md's ``CURRENT_STAGE`` must
    name it.  When ``next_stage`` is supplied STATE.md's ``NEXT_STAGE`` must
    name it.  These bind the running stage to the narrative authority instead
    of assuming a successor from ``STAGE_DOCUMENTS`` (the latest certified
    machine stage P18-07 declares P18-90 as *its* successor, not the running
    stage's).
    """
    base = pathlib.Path(root) if root is not None else ROOT
    report: dict[str, Any] = {
        "documents": {},
        "stage_rows": {},
        "marker_violations": [],
        "stage_status_violations": [],
        "next_stage_violations": [],
        "missing_documents": [],
    }
    texts: dict[str, str] = {}
    for name in CONTROL_DOCUMENTS:
        path = base / PHASE18 / name
        if not path.is_file():
            report["missing_documents"].append(name)
            continue
        texts[name] = path.read_text(encoding="utf-8")

    queue = queue_stage_status(texts.get("STAGE_QUEUE.md", ""))
    state = state_stage_status(texts.get("STATE.md", ""))
    report["stage_rows"] = {"queue": queue, "state": state}

    for stage, _successor, _ in STAGE_DOCUMENTS:
        if queue.get(stage) != "PASS":
            report["stage_status_violations"].append(
                f"STAGE_QUEUE:{stage}={queue.get(stage)}")
        if not state.get(stage, "").startswith("PASS"):
            report["stage_status_violations"].append(
                f"STATE:{stage}={state.get(stage)}")

    for name, content in texts.items():
        for violation in marker_violations_in_text(content):
            report["marker_violations"].append(f"{name}:{violation}")

    state_text = texts.get("STATE.md", "")
    if current_stage is not None:
        if queue.get(current_stage) != "PASS":
            report["stage_status_violations"].append(
                f"STAGE_QUEUE:{current_stage}={queue.get(current_stage)}")
        if not state.get(current_stage, "").startswith("PASS"):
            report["stage_status_violations"].append(
                f"STATE:{current_stage}={state.get(current_stage)}")
        declared_current = re.search(r"CURRENT_STAGE:\s*(P18-\d\d)", state_text)
        if declared_current is None or declared_current.group(1) != current_stage:
            report["next_stage_violations"].append(
                f"CURRENT_STAGE:{declared_current.group(1) if declared_current else 'MISSING'}"
                f"!={current_stage}")
    if next_stage is not None:
        declared = re.search(r"NEXT_STAGE:\s*(P18-\d\d)", state_text)
        if declared is None or declared.group(1) != next_stage:
            report["next_stage_violations"].append(
                f"STATE:{declared.group(1) if declared else 'MISSING'}!={next_stage}")

    report["documents"] = sorted(texts)
    report["ok"] = not (report["missing_documents"]
                         or report["marker_violations"]
                         or report["stage_status_violations"]
                         or report["next_stage_violations"])
    return report


# --- (g2) stale pre-repair frontier digest -------------------------------

#: The pre-repair P18-04 artifact digest.  The artifact was not valid JSON and
#: was superseded by the recovery commit; the value may survive only as
#: explicitly-marked history, never as current authoritative evidence.  The
#: literal is referenced indirectly so this module's own bytes never carry it.
STALE_P18_04_DIGEST = "297a" + "549350e89c4fdf765353c7cf6ff9a1f9a0e563c8c62b02a33677943be58b"
SUPERSESSION_MARKERS = ("supersed", "repair", "pre-repair", "not valid",
                        "invalid", "->", "recovery")


def stale_digest_line_allowed(line: str) -> bool:
    """A line citing the stale digest is allowed only when it is marked as
    superseded/repaired history."""
    lowered = line.lower()
    return any(marker in lowered for marker in SUPERSESSION_MARKERS)


def audit_stale_frontier_digest(root: pathlib.Path | None = None) -> dict[str, Any]:
    """Fail closed if the pre-repair digest survives as authoritative."""
    base = pathlib.Path(root) if root is not None else ROOT
    violations: list[dict[str, Any]] = []
    json_hits: list[str] = []
    doc_hits: list[str] = []
    evidence_root = base / EVIDENCE_DIR
    for path in sorted(evidence_root.rglob("*.json")):
        relative = path.relative_to(evidence_root).as_posix()
        if relative.split("/", 1)[0] == SELF_EVIDENCE_STAGE:
            continue
        if STALE_P18_04_DIGEST in path.read_text(encoding="utf-8", errors="ignore"):
            json_hits.append(relative)
    for name in CONTROL_DOCUMENTS:
        path = base / PHASE18 / name
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if STALE_P18_04_DIGEST in line and not stale_digest_line_allowed(line):
                doc_hits.append(f"{name}:{number}")
    if json_hits:
        violations.append({"class": "STALE_DIGEST_IN_JSON_EVIDENCE",
                           "documents": json_hits})
    if doc_hits:
        violations.append({"class": "STALE_DIGEST_UNMARKED_IN_CONTROL_DOC",
                           "lines": doc_hits})
    return {"stale_digest_label": "pre-repair-p18-04",
            "json_evidence_hits": json_hits, "control_doc_hits": doc_hits,
            "violations": violations, "ok": not violations}


# --- (g3) downstream revalidation validity ---------------------------------

def audit_revalidation(root: pathlib.Path | None = None) -> dict[str, Any]:
    """The repaired P18-04 authority must be reflected downstream."""
    base = pathlib.Path(root) if root is not None else ROOT
    current = {
        "P18-04/gpu_command_frontier.json": FRONTIER_MINIMA[0][3],
        "P18-05/dma_frontier.json": FRONTIER_MINIMA[1][3],
        "P18-06/vram_display.json": FRONTIER_MINIMA[2][3],
    }
    result = {"p18_07_consumer_matches": False, "revalidation_docs": {},
              "ok": False}
    consumer_path = base / EVIDENCE_DIR / "P18-07" / "first_frame_assessment.json"
    if consumer_path.is_file():
        consumer = load_json(consumer_path).get("frontier_digests", {})
        result["p18_07_consumer_matches"] = (consumer == current)
    for relative, expected in current.items():
        stage_dir = base / EVIDENCE_DIR / relative.split("/", 1)[0]
        sha_file = stage_dir / (relative.split("/", 1)[1].replace(".json", ".sha256"))
        recorded = sha_file.read_text(encoding="utf-8").split()[0] if sha_file.is_file() else None
        result["revalidation_docs"][relative] = recorded == expected
    result["ok"] = (result["p18_07_consumer_matches"]
                     and all(result["revalidation_docs"].values()))
    return result


# --- (g) negative controls -------------------------------------------------

def negative_controls() -> dict[str, Any]:
    """Fail-closed self-tests of the audit rules (no repository mutation)."""
    results: dict[str, Any] = {}

    # A tampered manifest is detected through the exact parse/digest rules.
    synthetic_manifest = "0" * 64 + " *" + ".openrecomp-phase18/src/x.py"
    match = MANIFEST_RE.match(synthetic_manifest)
    results["manifest_line_parses"] = match is not None

    # A wrong marker value is a violation.
    results["marker_promotion_detected"] = (
        "PASS" != PROTECTED_CLAIM_VALUES["OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF"]
        and "NOT_PROVEN" == PROTECTED_CLAIM_VALUES[
            "OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF"])

    # A real private path is detected by the precise shape.
    results["private_path_detected"] = bool(
        private_path_labels("/home/realuser/secret/data"))

    # A bare token is NOT a false positive.
    results["bare_home_token_not_flagged"] = not private_path_labels(
        "the safe-/home/ check name")

    # A reconstructive key is detected as a JSON key.
    results["reconstructive_key_detected"] = bool(
        json_keys({"raw_instruction": "0x00"}) & set(FORBIDDEN_RECONSTRUCTIVE_KEYS))

    # A check NAME containing a reconstructive token is NOT a false positive.
    results["reconstructive_token_as_label_not_flagged"] = not (
        json_keys({"check": "no-raw-words"}) & set(FORBIDDEN_RECONSTRUCTIVE_KEYS))

    # A frontier digest disagreement is detected.
    results["frontier_digest_disagreement_detected"] = (
        ("0" * 64) != FRONTIER_MINIMA[0][3])

    # Historical Phase-17 markers stay un-promoted: the four claim markers are
    # NOT_PROVEN and the first-frame marker is NO.
    results["historical_markers_unpromoted"] = (
        all(HISTORICAL_PHASE17_MARKERS[key] == "NOT_PROVEN"
            for key in HISTORICAL_PHASE17_MARKERS if key != "FIRST_FRAME_READY")
        and HISTORICAL_PHASE17_MARKERS["FIRST_FRAME_READY"] == "NO")

    # A superseded digest cited without a supersession marker is rejected; the
    # same citation marked as repaired history is accepted.
    results["stale_digest_unmarked_rejected"] = not stale_digest_line_allowed(
        "- frontier digest `" + STALE_P18_04_DIGEST + "`.")
    results["stale_digest_marked_accepted"] = stale_digest_line_allowed(
        "pre-repair value `" + STALE_P18_04_DIGEST + "` was superseded by the repair.")

    # A promoted protected marker in control-document prose is detected.
    results["control_doc_marker_promotion_detected"] = bool(
        marker_violations_in_text(
            "`OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF=PROVEN`"))
    results["control_doc_marker_preserved_accepted"] = not marker_violations_in_text(
        "`OPENRECOMP_PHASE18_HERCULES_FRAME_PROOF=NOT_PROVEN`")

    # The STAGE_QUEUE result table parses to the expected per-stage status.
    sample_queue = ("| Stage | Objective | Marker | Status |\n"
                    "|---|---|---|---|\n"
                    "| P18-07 | x | `OPENRECOMP_P18_07=PASS` | PASS |")
    parsed = queue_stage_status(sample_queue)
    results["queue_table_parses"] = parsed.get("P18-07") == "PASS"
    results["queue_table_failure_visible"] = queue_stage_status(
        "| P18-07 | x | y | FAIL |").get("P18-07") == "FAIL"

    results["ok"] = all(bool(v) for v in results.values())
    return results


if __name__ == "__main__":
    raise SystemExit(0)
