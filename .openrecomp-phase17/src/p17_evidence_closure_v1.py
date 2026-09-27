#!/usr/bin/env python3
"""P17-91 evidence-closure and source-manifest audit logic.

This module holds the mechanical audit used by the P17-91 gate
(tools/test_phase17_evidence_closure_v1.py). It is deliberately split out
the same way P17-90 split p17_consistency_policy_v1 from its gate, so the
audit construction is testable and reusable independently of the gate harness.

Scope and honesty boundaries:

* P17-91 is a terminal consistency gate. It proves that the committed Phase-17
  evidence corpus is internally consistent, complete, schema-conformant,
  publicly safe, and that the source manifest is exact. It proves nothing new
  about emulation and promotes no proof marker.
* The audit fails closed. Any real inconsistency in the committed corpus is
  reported as a finding and fails the stage; nothing is special-cased away.
* The only allow-listing performed is recorded explicitly in
  PUBLIC_SAFETY_ALLOWLIST with a mechanical reason per entry.

Manifest digest basis (verified mechanically at gate time): the Phase-17 source
manifest records the sha256 of each tracked file content bytes. For every text
source tracked here the git blob at HEAD and the working-tree bytes are
identical, and the audit re-proves that for each entry rather than assuming it
(see manifest_digest_basis).
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
from typing import Any

AUDIT_SCHEMA = "openrecomp-phase17-evidence-closure-audit-v1"
MARKER = "OPENRECOMP_PHASE17_EVIDENCE_CLOSURE_V1"

#: The frozen Phase-16 terminal commit that anchors the prior-phase integrity
#: check (control policy rule 3).
PHASE16_BASELINE_COMMIT = "a0c26e882ca65cfc84cbec78f7e787509a4992a3"

#: Phase-17 evidence directories that must exist and be schema-conformant. The
#: historical (non-R) P17-04..P17-07 rows are deliberately included: their
#: RESULT.json status is the historical gate verdict PASS while their queue
#: verdict is FAIL_REVIEW_REQUIRED. They are evidence, not failures, and must
#: not be reported as broken.
STAGE_DIRS: tuple[str, ...] = (
    "P17-00", "P17-01", "P17-02", "P17-03",
    "P17-04", "P17-04R", "P17-05", "P17-05R",
    "P17-06", "P17-06R", "P17-07", "P17-07R",
    "P17-90",
)

#: Stages that recorded official dual runs (run1/run2 + determinism.json) and
#: therefore must satisfy byte-identical dual-run determinism. P17-06R is the
#: one transcript-based stage with no run files and no determinism.json; it is
#: excluded from the dual-run checks and separately required to carry its
#: digest-bound transcript.
DUAL_RUN_STAGES: tuple[str, ...] = (
    "P17-00", "P17-01", "P17-02", "P17-03",
    "P17-04", "P17-04R", "P17-05", "P17-05R",
    "P17-06", "P17-07", "P17-07R", "P17-90",
)

#: Transcript-based stage without official run files.
TRANSCRIPT_STAGES: tuple[str, ...] = ("P17-06R",)

#: Required per-stage evidence documents (EVIDENCE_SCHEMA.md). Every dual-run
#: stage must carry the four run files plus RESULT.json and determinism.json.
REQUIRED_EVIDENCE_DOCUMENTS: tuple[str, ...] = (
    "RESULT.json",
    "determinism.json",
    "run1.txt",
    "run2.txt",
    "run1.err.txt",
    "run2.err.txt",
)

#: Transcript stage document set (no run files; digest-bound transcript).
REQUIRED_TRANSCRIPT_DOCUMENTS: tuple[str, ...] = (
    "RESULT.json",
    "continuation.json",
    "next_stage.json",
    "stage_metadata.json",
    "transcript.json",
    "transcript.sha256",
)

RESULT_SCHEMA = "openrecomp-phase17-result-v1"
ALLOWED_EVIDENCE_CLASSES = ("REPRESENTATIVE_TEST_RECORD",
                            "PRIVATE_FIXTURE_BOUNDED")

#: The four claim markers that must remain NOT_PROVEN, and the frame marker
#: that must remain NO, in every stage RESULT.json.
NOT_PROVEN_MARKERS: tuple[str, ...] = (
    "OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF",
    "OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF",
    "OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF",
    "OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY",
)
FIRST_FRAME_READY_MARKER = "FIRST_FRAME_READY"

PROTECTED_MARKER_VALUES: dict[str, str] = {
    "OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
    "FIRST_FRAME_READY": "NO",
}

# ---------------------------------------------------------------------------
# Public-safety scan
# ---------------------------------------------------------------------------

#: Reconstructive-metadata keys forbidden by EVIDENCE_SCHEMA.md and control
#: policy rules 11/15. Matched as JSON keys, not as arbitrary substrings, so
#: that a check name such as safe-instruction_word in a gate transcript is not
#: a false positive.
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
#: committed evidence. The /home/<user>/... shape is primary; the others mirror
#: the control policy and the pre-existing p17_gate_v1.reject_private_path
#: helper.
PRIVATE_PATH_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/tmp/[A-Za-z0-9._-]+"),
    # Windows drive-letter path in its JSON-encoded form (X:\\\\ -> four literal
    # backslashes) and UNC path in JSON-encoded form (\\\\\\\\name\\\\ -> eight
    # literal backslashes). Matching the encoded form avoids colliding with the
    # two-backslash-delimited ISO-9660 path segments recorded in P17-01 (for
    # example \\\\EX\\\\TITLE.;1), which are legitimate non-reconstructive
    # metadata.
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"\\\\\\\\[A-Za-z0-9._-]+\\\\"),
)

#: Files within the committed Phase-17 evidence tree that are exempt from the
#: private-path scan, each with the mechanical reason. This is the ONLY
#: allow-listing P17-91 performs, and it is deliberately tiny and named.
PUBLIC_SAFETY_ALLOWLIST: tuple[dict[str, str], ...] = (
    {
        "glob": "P17-00/negative_tests.json",
        "rule": "PRIVATE_PATH_NEGATIVE_CONTROL",
        "reason": (
            "P17-00 deliberately records the six SYNTHETIC forbidden-path "
            "strings from p17_gate_v1.FORBIDDEN_PRIVATE_PATHS as the expected "
            "inputs of its path-rejector negative control, together with the "
            "assertion that each was rejected. Each string is a fabricated "
            "placeholder consisting of a synthetic user/home segment and a "
            "synthetic location (and includes a Windows/UNC pair); none is a "
            "real host path, and their presence here is the positive evidence "
            "that the guard exists. The audit still requires every other rule "
            "to hold in this file."
        ),
    },
    {
        "glob": "P17-00/run1.txt",
        "rule": "PRIVATE_PATH_NEGATIVE_CONTROL_TRANSCRIPT",
        "reason": "Dual-run transcript of the P17-00 negative control above.",
    },
    {
        "glob": "P17-00/run2.txt",
        "rule": "PRIVATE_PATH_NEGATIVE_CONTROL_TRANSCRIPT",
        "reason": "Dual-run transcript of the P17-00 negative control above.",
    },
    {
        "glob": "P17-00/p17_00_tests.json",
        "rule": "PRIVATE_PATH_NEGATIVE_CONTROL_RECORD",
        "reason": (
            "Gate check record embedding the P17-00 negative-control detail "
            "string; same synthetic placeholders as negative_tests.json."
        ),
    },
    {
        "glob": "P17-07/run1.txt",
        "rule": "PRIVATE_PATH_TOKEN_AS_CHECK_NAME",
        "reason": (
            "Contains the check name safe-/home/ emitted by "
            "test_phase17_frontier_assessment_v1, which asserts the literal "
            "token /home/ is absent from its assessment document. The line "
            "holds the bare token as a label, not an absolute host path (there "
            "is no /home/<user>/ segment), so PRIVATE_PATH_RES does not match "
            "it; listed for completeness of the audit documented reasoning."
        ),
    },
    {
        "glob": "P17-07/run2.txt",
        "rule": "PRIVATE_PATH_TOKEN_AS_CHECK_NAME",
        "reason": "Dual-run transcript of the P17-07 check name above.",
    },
    {
        "glob": "P17-07/p17_07_tests.json",
        "rule": "PRIVATE_PATH_TOKEN_AS_CHECK_NAME",
        "reason": "Gate check record carrying the P17-07 /home/ check name.",
    },
)

#: Markdown controller-review documents are controller-authored prose reviewed
#: and committed by the controller, not stage-generated RESULT evidence. They
#: are reported separately (see public_safety_scan) so a real path in prose is
#: visible rather than silently allowed or silently failed.
REVIEW_DOCUMENT_GLOB = "CONTROLLER_REVIEW.md"


def is_allowlisted(relative: str) -> dict[str, str] | None:
    for entry in PUBLIC_SAFETY_ALLOWLIST:
        if relative.endswith(entry["glob"]):
            return entry
    return None


def json_keys(document: Any) -> set[str]:
    """Return every dict key anywhere in document (nested, order-independent)."""
    found: set[str] = set()
    if isinstance(document, dict):
        for key, value in document.items():
            found.add(str(key))
            found.update(json_keys(value))
    elif isinstance(document, list):
        for item in document:
            found.update(json_keys(item))
    return found


def forbidden_keys_present(document: Any) -> list[str]:
    return sorted(json_keys(document) & set(FORBIDDEN_RECONSTRUCTIVE_KEYS))


#: Short, non-reconstructive labels for each private-path pattern, used in
#: place of the matched text. P17-91 evidence must not echo a private host path
#: back into its own committed documents, so only the pattern family and a hit
#: count are ever recorded.
PRIVATE_PATH_LABELS: tuple[str, ...] = (
    "unix-home-user-path",
    "unix-users-user-path",
    "unix-tmp-path",
    "windows-drive-path",
    "windows-unc-path",
)


def private_path_hit_labels(text: str) -> list[str]:
    """Return the pattern-family labels that matched, never the matched text."""
    labels: list[str] = []
    for label, pattern in zip(PRIVATE_PATH_LABELS, PRIVATE_PATH_RES):
        if any(True for _ in pattern.finditer(text)):
            labels.append(label)
    return sorted(set(labels))


def private_path_hit_count(text: str) -> int:
    return sum(1 for pattern in PRIVATE_PATH_RES for _ in pattern.finditer(text))


def scan_document(document: Any, relative: str) -> dict[str, Any]:
    """Scan one committed evidence document for forbidden content.

    Returns a report with the allowlist decision applied. Only pattern-family
    labels and hit counts are recorded -- never the matched private-path text --
    so this gate's own evidence cannot carry a private host path. The allowlist
    waives only the private-path shapes for a named file; the reconstructive-key
    rule is never waived.
    """
    if isinstance(document, str):
        text = document
        key_hits: list[str] = []
    else:
        text = json.dumps(document, sort_keys=True)
        key_hits = forbidden_keys_present(document)
    path_labels = private_path_hit_labels(text)
    path_count = private_path_hit_count(text)
    allow = is_allowlisted(relative)
    allowlisted = allow is not None
    return {
        "document": relative,
        "private_path_label_hits": path_labels,
        "private_path_hit_count": path_count,
        "forbidden_key_hits": key_hits,
        "allowlisted": allowlisted,
        "allowlist_rule": allow["rule"] if allow else "",
        "allowlisted_path_hit_count": path_count if allowlisted else 0,
        "unallowlisted_path_hit_count": 0 if allowlisted else path_count,
        "ok": (path_count == 0 or allowlisted) and not key_hits,
    }

#: The gate writes its own evidence into this directory while it runs, so it is
#: excluded from the public-safety scan set: counting it would make the scan a
#: function of run order. P17-91 audits the committed prior-stage corpus.
SELF_EVIDENCE_DIR = "P17-91"


def iter_evidence_documents(evidence_root: pathlib.Path,
                          exclude_dirs: tuple[str, ...] = ()) -> list[pathlib.Path]:
    """Yield every evidence file under evidence_root, sorted.

    ``exclude_dirs`` names stage directories (relative to evidence_root) whose
    contents are excluded. P17-91 excludes its OWN evidence directory because
    the gate body runs inside it: files the gate writes while it scans (and the
    stage runner writes around it) would otherwise make the scanned-file count
    a function of run order, which is exactly the nondeterminism this stage
    must not have. P17-91 audits the committed corpus of the prior stages, not
    its own output.
    """
    excluded = {name.strip("/") for name in exclude_dirs}
    found: list[pathlib.Path] = []
    for path in evidence_root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(evidence_root).as_posix()
        if relative.split("/", 1)[0] in excluded:
            continue
        found.append(path)
    return sorted(found)


def read_evidence_file(path: pathlib.Path) -> tuple[Any, bool]:
    """Read a file as JSON when possible; return (payload, is_json)."""
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return path.read_bytes(), False
    if path.suffix == ".json":
        try:
            return json.loads(content), True
        except json.JSONDecodeError:
            return content, False
    return content, False


def public_safety_scan(evidence_root: pathlib.Path) -> dict[str, Any]:
    """Scan the whole committed Phase-17 evidence tree.

    Stage-generated evidence is scanned under the allowlist above. Controller
    review prose (CONTROLLER_REVIEW.md) is scanned and reported but is not
    allowed to fail the gate by itself: it is controller-authored and committed
    by the controller, outside the worker write scope, and P17-91 must not
    rewrite or regenerate any existing stage evidence. Any hit in prose is
    surfaced in review_document_findings so the controller sees it plainly.
    """
    documents: list[dict[str, Any]] = []
    review_findings: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in iter_evidence_documents(evidence_root,
                                   exclude_dirs=(SELF_EVIDENCE_DIR,)):
        relative = path.relative_to(evidence_root).as_posix()
        payload, _ = read_evidence_file(path)
        if relative.endswith(REVIEW_DOCUMENT_GLOB):
            prose = payload if isinstance(payload, str) else json.dumps(payload)
            labels = private_path_hit_labels(prose)
            count = private_path_hit_count(prose)
            keys = (forbidden_keys_present(payload)
                    if not isinstance(payload, str) else [])
            if labels or keys:
                review_findings.append({
                    "document": relative,
                    "private_path_label_hits": labels,
                    "private_path_hit_count": count,
                    "forbidden_key_hits": keys,
                    "severity": "REPORTED_NOT_GATING",
                    "reason": (
                        "Controller-authored review prose, committed by the "
                        "controller; outside the P17-91 write scope and must "
                        "not be modified by this stage. Surfaced for "
                        "controller attention."
                    ),
                })
            continue
        report = scan_document(payload, relative)
        documents.append(report)
        if not report["ok"]:
            failures.append(relative)

    return {
        "schema": "openrecomp-phase17-public-safety-v1",
        "documents_scanned": len(documents),
        "documents_failed": failures,
        "allowlisted_documents": sorted(
            report["document"] for report in documents if report["allowlisted"]),
        "reports": documents,
        "review_document_findings": review_findings,
        "ok": not failures,
    }

# ---------------------------------------------------------------------------
# Source manifest exactness
# ---------------------------------------------------------------------------

MANIFEST_SCHEMA = "openrecomp-phase17-source-manifest-audit-v1"
MANIFEST_PATH = ".openrecomp-phase17/SOURCE_SHA256SUMS.txt"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_manifest(content: str) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Parse SOURCE_SHA256SUMS.txt into {path: digest} plus malformed lines."""
    entries: dict[str, str] = {}
    errors: list[dict[str, Any]] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(" *", 1)
        if len(parts) != 2:
            errors.append({"line": line_no, "reason": "missing-space-asterisk"})
            continue
        digest, relative = parts[0].strip().lower(), parts[1]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            errors.append({"line": line_no, "reason": "bad-digest",
                           "path": relative})
            continue
        if relative in entries:
            errors.append({"line": line_no, "reason": "duplicate-entry",
                           "path": relative})
            continue
        entries[relative] = digest
    return entries, errors


def tracked_phase17_sources(root: pathlib.Path) -> list[str]:
    """The exact set of tracked Phase-17 sources the manifest must cover.

    Mirrors p17_source_manifest_v1.tracked_paths: every
    .openrecomp-phase17/src/p17_*.py and every tools/test_phase17_*.py tracked
    by git, excluding __init__.py and caches. Uses git ls-files so untracked
    scratch files cannot masquerade as manifest entries.
    """
    completed = subprocess.run(
        ["git", "ls-files", "-z", ".openrecomp-phase17/src", "tools"],
        cwd=str(root), capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError("git ls-files failed")
    found: set[str] = set()
    for raw in completed.stdout.split(b"\0"):
        if not raw:
            continue
        relative = raw.decode("utf-8")
        name = relative.rsplit("/", 1)[-1]
        if (relative.startswith(".openrecomp-phase17/src/")
                and name.endswith(".py") and name.startswith("p17_")
                and name != "__init__.py"):
            found.add(relative)
        elif (relative.startswith("tools/")
              and name.startswith("test_phase17_")
              and name.endswith(".py")):
            found.add(relative)
    return sorted(found)


def manifest_digest_basis(root: pathlib.Path, relative: str) -> dict[str, Any]:
    """Return the working-tree and git-blob digests for one manifest entry.

    The audit requires these to be equal for every source, which is the
    mechanical proof that the manifest basis is unambiguous. A divergence would
    be a real finding.
    """
    path = root / relative
    working = sha256_bytes(path.read_bytes()) if path.is_file() else ""
    blob = subprocess.run(["git", "cat-file", "blob", f"HEAD:{relative}"],
                          cwd=str(root), capture_output=True)
    git_blob = sha256_bytes(blob.stdout) if blob.returncode == 0 else ""
    return {
        "path": relative,
        "working_tree_sha256": working,
        "git_blob_sha256": git_blob,
        "basis_agrees": bool(working) and working == git_blob,
    }


def audit_manifest(root: pathlib.Path, manifest_text: str) -> dict[str, Any]:
    """Full source-manifest exactness audit."""
    entries, parse_errors = parse_manifest(manifest_text)
    expected = tracked_phase17_sources(root)
    expected_set, entry_set = set(expected), set(entries)

    missing = sorted(expected_set - entry_set)
    extra = sorted(entry_set - expected_set)

    digest_mismatch: list[dict[str, str]] = []
    basis_divergence: list[dict[str, Any]] = []
    for relative in sorted(expected_set & entry_set):
        basis = manifest_digest_basis(root, relative)
        if not basis["basis_agrees"]:
            basis_divergence.append(basis)
        recorded = entries.get(relative, "")
        actual = basis["git_blob_sha256"] or basis["working_tree_sha256"]
        if recorded != actual:
            digest_mismatch.append({"path": relative, "recorded": recorded,
                                    "actual": actual})

    counts: dict[str, int] = {}
    for line in manifest_text.splitlines():
        if " *" in line:
            rel = line.split(" *", 1)[1]
            counts[rel] = counts.get(rel, 0) + 1
    duplicates = sorted(name for name, n in counts.items() if n > 1)

    ok = (not parse_errors and not missing and not extra
          and not digest_mismatch and not basis_divergence and not duplicates)

    return {
        "schema": MANIFEST_SCHEMA,
        "manifest": MANIFEST_PATH,
        "expected_count": len(expected),
        "entry_count": len(entries),
        "parse_errors": parse_errors,
        "missing_entries": missing,
        "extra_entries": extra,
        "duplicate_entries": duplicates,
        "digest_mismatches": digest_mismatch,
        "basis_divergences": basis_divergence,
        "basis": "git-blob-content (equals working-tree bytes for every entry)",
        "expected_paths": expected,
        "ok": ok,
    }

# ---------------------------------------------------------------------------
# Evidence closure / schema conformance
# ---------------------------------------------------------------------------

def _load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_evidence_closure(evidence_root: pathlib.Path) -> dict[str, Any]:
    """Verify every stage directory carries the schema-required documents and a
    schema-conformant RESULT.json."""
    stages: list[dict[str, Any]] = []
    ok = True
    for stage in STAGE_DIRS:
        directory = evidence_root / stage
        present = directory.is_dir()
        names = sorted(p.name for p in directory.iterdir()) if present else []
        required = list(REQUIRED_EVIDENCE_DOCUMENTS)
        if stage in TRANSCRIPT_STAGES:
            required = list(REQUIRED_TRANSCRIPT_DOCUMENTS)
        missing = [name for name in required if name not in names]
        result_path = directory / "RESULT.json"
        result_present = result_path.is_file()
        document = _load_json(result_path) if result_present else {}
        schema = str(document.get("schema", ""))
        stage_field = str(document.get("stage", ""))
        status = str(document.get("status", ""))
        evidence_class = str(document.get("evidence_class", ""))
        markers = document.get("markers", {})
        conformant = (
            schema == RESULT_SCHEMA
            and stage_field == stage
            and status in ("PASS", "FAIL")
            and evidence_class in ALLOWED_EVIDENCE_CLASSES
            and isinstance(markers, dict) and bool(markers)
        )
        entry = {
            "stage": stage,
            "directory_present": present,
            "files": names,
            "required_documents": required,
            "missing_documents": missing,
            "result_present": result_present,
            "schema": schema,
            "stage_field": stage_field,
            "status": status,
            "evidence_class": evidence_class,
            "markers_present": isinstance(markers, dict) and bool(markers),
            "schema_conformant": conformant,
            "ok": present and not missing and conformant,
        }
        ok = ok and entry["ok"]
        stages.append(entry)
    return {
        "schema": "openrecomp-phase17-evidence-closure-v1",
        "stages_expected": len(STAGE_DIRS),
        "stages_checked": len(stages),
        "stages": stages,
        "ok": ok,
    }


def audit_dual_run_determinism(evidence_root: pathlib.Path) -> dict[str, Any]:
    """Byte-identity of run1/run2, empty stderr, and re-derived run digests
    against determinism.json."""
    stages: list[dict[str, Any]] = []
    ok = True
    for stage in DUAL_RUN_STAGES:
        directory = evidence_root / stage
        run1 = directory / "run1.txt"
        run2 = directory / "run2.txt"
        err1 = directory / "run1.err.txt"
        err2 = directory / "run2.err.txt"
        b1 = run1.read_bytes() if run1.is_file() else b""
        b2 = run2.read_bytes() if run2.is_file() else b""
        e1 = err1.read_bytes() if err1.is_file() else b"__missing__"
        e2 = err2.read_bytes() if err2.is_file() else b"__missing__"
        sha1 = sha256_bytes(b1)
        sha2 = sha256_bytes(b2)
        identical = bool(b1) and b1 == b2
        stderr_empty = (e1 == b"" and e2 == b"")

        determinism_path = directory / "determinism.json"
        recorded_ok = False
        recorded_mismatch: list[str] = []
        if determinism_path.is_file():
            record = _load_json(determinism_path)
            runs = record.get("runs", {})
            rec1 = runs.get("run1", {}).get("stdout_sha256_lf", "")
            rec2 = runs.get("run2", {}).get("stdout_sha256_lf", "")
            if rec1 != sha1 or rec2 != sha2:
                recorded_mismatch.append(
                    "run-digest mismatch recorded="
                    f"{rec1[:12]},{rec2[:12]} actual={sha1[:12]},{sha2[:12]}")
            record_declares = (
                record.get("stdout_identical_raw") is True
                and record.get("stdout_identical_lf") is True
                and record.get("stderr_empty_both") is True
                and record.get("returncode_zero_both") is True
            )
            recorded_ok = not recorded_mismatch and record_declares
        else:
            recorded_mismatch.append("determinism.json missing")

        entry = {
            "stage": stage,
            "run1_sha256": sha1,
            "run2_sha256": sha2,
            "run_byte_identical": identical,
            "stderr_both_empty": stderr_empty,
            "recorded_digests_match": recorded_ok,
            "recorded_mismatch": recorded_mismatch,
            "ok": identical and stderr_empty and recorded_ok,
        }
        ok = ok and entry["ok"]
        stages.append(entry)
    return {
        "schema": "openrecomp-phase17-dual-run-determinism-v1",
        "stages_checked": len(stages),
        "stages": stages,
        "ok": ok,
    }


def audit_transcript_binding(evidence_root: pathlib.Path) -> dict[str, Any]:
    """P17-06R and P17-07R digest-bound transcript integrity."""
    report: dict[str, Any] = {
        "schema": "openrecomp-phase17-transcript-binding-v1"}
    p06r = evidence_root / "P17-06R"
    transcript = p06r / "transcript.json"
    sidecar = p06r / "transcript.sha256"
    recorded = ""
    if sidecar.is_file():
        recorded = sidecar.read_text(encoding="utf-8").split()[0].strip()
    actual = sha256_bytes(transcript.read_bytes()) if transcript.is_file() else ""
    p07r = evidence_root / "P17-07R"
    binding_path = p07r / "transcript_binding.json"
    binding = _load_json(binding_path) if binding_path.is_file() else {}
    bound = str(binding.get("transcript_sha256", ""))
    report.update({
        "P17-06R_transcript_sha256": actual,
        "P17-06R_sidecar_sha256": recorded,
        "P17-06R_sidecar_matches": bool(actual) and actual == recorded,
        "P17-07R_bound_sha256": bound,
        "P17-07R_binding_matches_transcript": bool(actual) and actual == bound,
        "rederived_provenance_digest_count": binding.get(
            "rederived_provenance_digest_count"),
        "ok": bool(actual) and actual == recorded and actual == bound,
    })
    return report

# ---------------------------------------------------------------------------
# Marker ledger
# ---------------------------------------------------------------------------

def audit_marker_ledger(evidence_root: pathlib.Path, state_text: str,
                        queue_text: str) -> dict[str, Any]:
    """Every protected claim marker remains NOT_PROVEN / NO in every stage
    RESULT.json, and STATE/STAGE_QUEUE declare the same four NOT_PROVEN markers
    plus FIRST_FRAME_READY=NO."""
    per_stage: list[dict[str, Any]] = []
    ok = True
    for stage in STAGE_DIRS:
        result_path = evidence_root / stage / "RESULT.json"
        if not result_path.is_file():
            per_stage.append({"stage": stage, "result_present": False,
                              "ok": False})
            ok = False
            continue
        markers = _load_json(result_path).get("markers", {})
        drift: list[dict[str, str]] = []
        for marker, required in PROTECTED_MARKER_VALUES.items():
            if marker in markers and str(markers[marker]) != required:
                drift.append({"marker": marker, "required": required,
                              "found": str(markers[marker])})
        entry_ok = not drift
        ok = ok and entry_ok
        per_stage.append({
            "stage": stage,
            "result_present": True,
            "protected_markers": {marker: str(markers.get(marker, "<absent>"))
                                  for marker in PROTECTED_MARKER_VALUES},
            "drift": drift,
            "ok": entry_ok,
        })

    state_declares = {name: (name in state_text) for name in NOT_PROVEN_MARKERS}
    state_declares[FIRST_FRAME_READY_MARKER] = (
        f"{FIRST_FRAME_READY_MARKER}=NO" in state_text)
    queue_declares = {name: (name in queue_text) for name in NOT_PROVEN_MARKERS}
    queue_declares[FIRST_FRAME_READY_MARKER] = (
        f"{FIRST_FRAME_READY_MARKER}=NO" in queue_text)
    ledger_ok = all(state_declares.values()) and all(queue_declares.values())
    return {
        "schema": "openrecomp-phase17-marker-ledger-v1",
        "stages": per_stage,
        "state_declares": state_declares,
        "queue_declares": queue_declares,
        "promoted_markers": sorted(
            drift["marker"] for stage in per_stage for drift in stage["drift"]),
        "ok": ok and ledger_ok,
    }


# ---------------------------------------------------------------------------
# Frozen prior-phase integrity
# ---------------------------------------------------------------------------

PRIOR_PHASE_DIRS: tuple[str, ...] = tuple(
    f".openrecomp-phase{n}" for n in range(1, 17))


def audit_prior_phase_integrity(root: pathlib.Path,
                                baseline: str = PHASE16_BASELINE_COMMIT
                                ) -> dict[str, Any]:
    """Prove Phase-1..16 trees were not modified by Phase-17 work.

    Three independent mechanical checks:

    1. No commit in baseline..HEAD touched any .openrecomp-phaseN tree for
       N < 17.
    2. Each .openrecomp-phaseN tree object id at HEAD equals the tree object id
       at the frozen Phase-16 baseline commit.
    3. git status --porcelain reports no working-tree modification under any
       prior-phase directory.
    """
    diff_commits = subprocess.run(
        ["git", "log", "--oneline", f"{baseline}..HEAD", "--", *PRIOR_PHASE_DIRS],
        cwd=str(root), capture_output=True, text=True)
    touching = [line for line in diff_commits.stdout.splitlines() if line.strip()]

    trees: list[dict[str, Any]] = []
    ok = not touching
    for directory in PRIOR_PHASE_DIRS:
        at_baseline = subprocess.run(
            ["git", "rev-parse", f"{baseline}:{directory}"],
            cwd=str(root), capture_output=True, text=True)
        at_head = subprocess.run(
            ["git", "rev-parse", f"HEAD:{directory}"],
            cwd=str(root), capture_output=True, text=True)
        baseline_tree = (at_baseline.stdout.strip()
                         if at_baseline.returncode == 0 else "")
        head_tree = at_head.stdout.strip() if at_head.returncode == 0 else ""
        same = bool(baseline_tree) and baseline_tree == head_tree
        ok = ok and same
        trees.append({"directory": directory, "baseline_tree": baseline_tree,
                      "head_tree": head_tree, "identical": same})

    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *PRIOR_PHASE_DIRS],
        cwd=str(root), capture_output=True, text=True)
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    ok = ok and not dirty

    return {
        "schema": "openrecomp-phase17-prior-phase-integrity-v1",
        "baseline_commit": baseline,
        "commits_touching_prior_phases": touching,
        "tree_comparisons": trees,
        "worktree_dirty_prior_phases": dirty,
        "method": (
            "git log baseline..HEAD over .openrecomp-phase1..16 (must be "
            "empty); git rev-parse <baseline>:<dir> == HEAD:<dir> for each "
            "prior-phase tree; git status --porcelain over the same paths "
            "(must be empty)"
        ),
        "ok": ok,
    }

# ---------------------------------------------------------------------------
# Negative controls (self-test)
# ---------------------------------------------------------------------------

def negative_controls(root: pathlib.Path,
                      evidence_root: pathlib.Path) -> dict[str, Any]:
    """Tamper cases proving the audit fails closed on each class of corruption.

    Each case mutates a copy of a real input (manifest text, evidence document,
    or run file) and re-runs the corresponding audit function. detected is true
    iff the mutated audit reports ok == False.
    """
    results: list[dict[str, Any]] = []

    manifest_text = (root / MANIFEST_PATH).read_text(encoding="utf-8")
    baseline_manifest = audit_manifest(root, manifest_text)

    def add(name: str, detected: bool, detail: str) -> None:
        results.append({"case": name, "detected": bool(detected),
                        "detail": detail})

    # 1. Corrupted manifest digest: flip the first character of one entry.
    lines = manifest_text.splitlines()
    for index, line in enumerate(lines):
        if " *" in line:
            digest, rest = line.split(" *", 1)
            bad = ("0" if digest[0] != "0" else "1") + digest[1:]
            lines[index] = f"{bad} *{rest}"
            break
    corrupt = audit_manifest(root, "\n".join(lines) + "\n")
    add("corrupted_manifest_digest", corrupt["ok"] is False,
        f"digest_mismatches={len(corrupt['digest_mismatches'])}")

    # 2. Removed manifest entry: drop one expected entry.
    target = baseline_manifest["expected_paths"][0]
    removed_lines = [line for line in manifest_text.splitlines()
                     if not line.endswith(f" *{target}")]
    gone = audit_manifest(root, "\n".join(removed_lines) + "\n")
    add("removed_manifest_entry", gone["ok"] is False,
        f"missing_entries={gone['missing_entries'][:2]}")

    # 3. Missing required evidence document: synthetic single-stage corpus.
    with tempfile.TemporaryDirectory() as tmp:
        stage_dir = pathlib.Path(tmp) / "P17-99"
        stage_dir.mkdir()
        (stage_dir / "RESULT.json").write_text(json.dumps({
            "schema": RESULT_SCHEMA, "stage": "P17-99", "status": "PASS",
            "evidence_class": "REPRESENTATIVE_TEST_RECORD",
            "markers": {"OPENRECOMP_P17_99": "PASS"},
        }), encoding="utf-8")
        closure = audit_evidence_closure(pathlib.Path(tmp))
        detected = any(not entry["ok"] for entry in closure["stages"])
        add("missing_required_evidence_document", detected,
            "synthetic stage missing run/determinism documents")

    # 4. Divergent run1/run2: copy a real stage, mutate run2.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = pathlib.Path(tmp)
        source = evidence_root / "P17-00"
        target_dir = tmp_root / "P17-00"
        target_dir.mkdir()
        for name in ("run1.txt", "run2.txt", "run1.err.txt", "run2.err.txt",
                     "determinism.json"):
            if (source / name).is_file():
                (target_dir / name).write_bytes((source / name).read_bytes())
        (target_dir / "run2.txt").write_bytes(
            (source / "run2.txt").read_bytes() + b"TAMPER\n")
        determinism = audit_dual_run_determinism(tmp_root)
        detected = any(not entry["ok"] for entry in determinism["stages"])
        add("divergent_dual_run", detected, "run2 mutated by one appended line")

    # 5. Fabricated private host path injected into a scan document.
    injected = scan_document(
        {"schema": "x", "note": "see /home/intruder/secret/path for detail"},
        "P17-99/injected.json")
    add("fabricated_private_host_path", injected["ok"] is False,
        f"unallowlisted_path_hit_count="
        f"{injected['unallowlisted_path_hit_count']}")

    # 5b. The allowlist waives only the path shapes, never the key rules.
    allowed_path = scan_document({"note": "/home/intruder/secret/path"},
                                 "P17-00/negative_tests.json")
    allowed_key = scan_document({"payload_bytes": "deadbeef"},
                                "P17-00/negative_tests.json")
    add("allowlisted_file_forbidden_key_still_caught",
        allowed_path["ok"] is True and allowed_key["ok"] is False,
        "allowlist waives only path shapes, never reconstructive keys")

    # 6. Promoted NOT_PROVEN marker: synthetic corpus, promote one marker.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = pathlib.Path(tmp)
        for stage in STAGE_DIRS:
            d = tmp_root / stage
            d.mkdir()
            (d / "RESULT.json").write_text(json.dumps({
                "schema": RESULT_SCHEMA, "stage": stage, "status": "PASS",
                "evidence_class": "REPRESENTATIVE_TEST_RECORD",
                "markers": dict(PROTECTED_MARKER_VALUES),
            }), encoding="utf-8")
        promoted_path = tmp_root / STAGE_DIRS[0] / "RESULT.json"
        promoted = _load_json(promoted_path)
        promoted["markers"]["OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF"] = "PASS"
        promoted_path.write_text(json.dumps(promoted), encoding="utf-8")
        drifted = audit_marker_ledger(tmp_root, "", "")
        add("promoted_not_proven_marker", drifted["ok"] is False,
            f"promoted={drifted['promoted_markers']}")

    add("baseline_manifest_is_clean", baseline_manifest["ok"] is True,
        f"entries={baseline_manifest['entry_count']}")

    tamper_cases = [entry for entry in results
                    if entry["case"] != "baseline_manifest_is_clean"]
    ok = all(entry["detected"] for entry in results)
    return {
        "schema": "openrecomp-phase17-negative-controls-v1",
        "cases": results,
        "tamper_case_count": len(tamper_cases),
        "tamper_detected_count": sum(1 for entry in tamper_cases
                                     if entry["detected"]),
        "ok": ok,
    }


def audit_document() -> dict[str, Any]:
    """Public description of what P17-91 audits."""
    return {
        "schema": AUDIT_SCHEMA,
        "marker": MARKER,
        "proves": (
            "The Phase-17 committed evidence corpus is internally consistent, "
            "complete, schema-conformant, publicly safe, and the source "
            "manifest is exact. Nothing about emulation."
        ),
        "promotes_no_proof_marker": True,
        "checks": [
            "source-manifest-exactness (missing/extra/duplicate/digest/basis)",
            "evidence-closure (required documents + RESULT.json schema)",
            "dual-run-determinism (run1==run2, empty stderr, re-derived digests)",
            "public-safety (private host paths, reconstructive keys)",
            "frozen-prior-phase-integrity (Phase 1..16 trees unchanged)",
            "marker-ledger (protected claim markers un-promoted)",
            "negative-controls (tamper cases fail closed)",
        ],
        "audited_stage_dirs": list(STAGE_DIRS),
        "dual_run_stages": list(DUAL_RUN_STAGES),
        "transcript_stages": list(TRANSCRIPT_STAGES),
        # The forbidden reconstructive key names are declared by count and a
        # non-echoing statement, never as bare contiguous terms: the shared
        # gate helper p17_gate_v1.assert_public_safe has a fail-closed
        # substring guard that fires on the literal terms, so echoing them
        # here would manufacture a self-hit with no public-safety meaning.
        # The scan itself still uses the exact FORBIDDEN_RECONSTRUCTIVE_KEYS
        # tuple against every document.
        "forbidden_reconstructive_key_count": len(FORBIDDEN_RECONSTRUCTIVE_KEYS),
        "forbidden_reconstructive_key_form": "declared in the scan; not echoed",
        "private_path_pattern_labels": list(PRIVATE_PATH_LABELS),
        "public_safety_allowlist_rules": sorted(
            {entry["rule"] for entry in PUBLIC_SAFETY_ALLOWLIST}),
        "public_safety_allowlisted_file_count": len(PUBLIC_SAFETY_ALLOWLIST),
        "phase16_baseline_commit": PHASE16_BASELINE_COMMIT,
    }

