#!/usr/bin/env python3
"""P17-99 terminal Phase-17 closure logic.

This module holds the mechanical terminal-verdict construction used by the
P17-99 gate (tools/test_phase17_terminal_closure_v1.py). It is split out the
same way P17-90 split p17_consistency_policy_v1 and P17-91 split
p17_evidence_closure_v1 from their gates, so the closure construction is
readable and independently re-runnable.

Scope and honesty boundaries:

* P17-99 is the terminal Phase-17 verdict. It proves the complete Phase-17
  stage chain is internally consistent and terminally closed: every stage
  PASS, the certified provenance chain intact, stage markers consistent,
  evidence manifest consistent, deterministic dual runs, no private-path
  leakage, clean repository, no Phase 1..16 evidence modification, no stale
  REVIEW_REQUIRED for a clause that is now satisfied, and an exact
  HEAD/tree binding.
* It promotes NO proof marker. FIRST_FRAME_READY stays NO and the four
  claim markers stay NOT_PROVEN, exactly as committed. A Phase-17 terminal
  PASS does not promote any broader claim.
* The only allow-listing performed is the one already named and bounded in
  p17_evidence_closure_v1.PUBLIC_SAFETY_ALLOWLIST; this module introduces no
  new allow-listing.
* The running-attestation (repository-cleanliness and HEAD/tree binding)
  is emitted by the gate under the stage_runner's two official runs and is
  recorded in P17-99/official_runs.json, not committed here as a single run.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any

CLOSURE_SCHEMA = "openrecomp-phase17-terminal-closure-v1"
MARKER = "OPENRECOMP_PHASE17_TERMINAL_V1"
STAGE_MARKER = "OPENRECOMP_P17_99"

#: The controller HEAD/tree the P17-99 worker branched from. The terminal
#: closure reproduces this exact binding and records it; any divergence is a
#: real finding.
BASE_COMMIT = "b1bace7c6c39403c49b9168a880082b91b168553"
BASE_TREE = "920e3b785fda92d027f783ee50b82d578e82c01a"

#: The frozen Phase-16 terminal commit that anchors prior-phase integrity.
PHASE16_BASELINE_COMMIT = "a0c26e882ca65cfc84cbec78f7e787509a4992a3"

#: The complete authoritative Phase-17 stage chain, in order.
STAGE_CHAIN: tuple[str, ...] = (
    "P17-00", "P17-01", "P17-02", "P17-03",
    "P17-04R", "P17-05R", "P17-06R", "P17-07R",
    "P17-90", "P17-91",
)

#: The mandatory stage markers. Each must appear with value PASS in the named
#: stage's RESULT.json.
STAGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("P17-00", "OPENRECOMP_P17_00"),
    ("P17-01", "OPENRECOMP_PHASE17_TITLE_INGESTION_V1"),
    ("P17-02", "OPENRECOMP_PHASE17_TITLE_IR_CONTRACT_V1"),
    ("P17-03", "OPENRECOMP_PHASE17_FRONTIER_RECONCILIATION_V1"),
    ("P17-04R", "OPENRECOMP_P17_04R"),
    ("P17-05R", "OPENRECOMP_P17_05R"),
    ("P17-06R", "OPENRECOMP_P17_06R"),
    ("P17-07R", "OPENRECOMP_P17_07R"),
    ("P17-90", "OPENRECOMP_P17_90"),
    ("P17-91", "OPENRECOMP_P17_91"),
)

#: Historical next_stage aliases. The committed P17-03 RESULT.json recorded
#: next_stage "P17-04" (the pre-review-revision row); the authoritative chain
#: continues at P17-04R, which is the reviewed and integrated replacement of
#: that row. This is an alias, not a divergence: P17-04 is preserved as
#: historical evidence and P17-04R is its reviewed successor.
NEXT_STAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "P17-03": ("P17-04",),
}

#: The four claim markers that must remain NOT_PROVEN, plus the frame marker.
PROTECTED_MARKERS: dict[str, str] = {
    "OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF": "NOT_PROVEN",
    "OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY": "NOT_PROVEN",
    "FIRST_FRAME_READY": "NO",
}

#: Certified provenance chain (stage -> certifying commit). P17-00..P17-03 and
#: P17-07R have no single certifying commit recorded; they are verified through
#: their committed evidence and the ancestry chain instead.
PROVENANCE_CHAIN: tuple[tuple[str, str], ...] = (
    ("P17-04R", "0ab4e7eb2ed4393cec7f61a79705d2c44bbc4441"),
    ("P17-05R", "b18fd4bee216b3133f667de82c4e0c92d917c127"),
    ("P17-06R", "2701415223dd182a40cf257c849952a6ce63ee08"),
    ("P17-07R", "b553f70163fbd660252a3fcdaa77eee672af0f48"),
    ("P17-90", "53528956b3276e8bc3f954dc141049bb7ab7c74b"),
    ("P17-91", "84e3e8ae19bcab79ef819e937d1b1361f5628b0c"),
)

#: All Phase-17 stage evidence directories that must exist and be closed.
EVIDENCE_STAGE_DIRS: tuple[str, ...] = (
    "P17-00", "P17-01", "P17-02", "P17-03",
    "P17-04", "P17-04R", "P17-05", "P17-05R",
    "P17-06", "P17-06R", "P17-07", "P17-07R",
    "P17-90", "P17-91",
)

#: Prior-phase directories whose trees must be byte-identical to the frozen
#: Phase-16 baseline commit.
PRIOR_PHASE_DIRS: tuple[str, ...] = tuple(
    f".openrecomp-phase{n}" for n in range(1, 17))

#: The clause whose stale REVIEW_REQUIRED stop must be cleared by P17-99.
REVIEW_REQUIRED_MARKER = ".openrecomp-phase17/REVIEW_REQUIRED.md"

#: Stage directories covered by the public-safety scan (the committed corpus).
#: P17-99's own directory is excluded while the gate runs for the same reason
#: P17-91 excluded its own: counting its own output would make the scan order
#: dependent.
SCAN_STAGES: tuple[str, ...] = EVIDENCE_STAGE_DIRS

#: Stage marker tokens and the canonical terminal token. A marker is
#: syntactically clean iff it is OPENRECOMP_<TOKEN>=<VALUE> with a single "=".
MARKER_TOKEN_RE = re.compile(r"^OPENRECOMP_[A-Z0-9_]+$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          text=True)


def _load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. Stage chain closure
# ---------------------------------------------------------------------------

def audit_stage_chain(evidence_root: pathlib.Path) -> dict[str, Any]:
    """Every chained stage RESULT.json is PASS, carries its required marker
    with value PASS, and records the expected next_stage link."""
    entries: list[dict[str, Any]] = []
    ok = True
    for index, stage in enumerate(STAGE_CHAIN):
        path = evidence_root / stage / "RESULT.json"
        present = path.is_file()
        document = _load_json(path) if present else {}
        markers = document.get("markers", {}) if isinstance(document, dict) else {}
        status = str(document.get("status", "")) if present else ""
        stage_field = str(document.get("stage", "")) if present else ""
        required = [marker for owner, marker in STAGE_MARKERS if owner == stage]
        marker_values = {marker: str(markers.get(marker, "<absent>"))
                         for marker in required}
        markers_ok = all(value == "PASS" for value in marker_values.values())
        expected_next = STAGE_CHAIN[index + 1] if index + 1 < len(STAGE_CHAIN) else None
        recorded_next = document.get("next_stage") if present else None
        accepted_next = {expected_next} | set(NEXT_STAGE_ALIASES.get(stage, ()))
        next_ok = (expected_next is None) or (recorded_next in accepted_next)
        entry_ok = (present and status == "PASS" and stage_field == stage
                    and markers_ok and next_ok)
        ok = ok and entry_ok
        entries.append({
            "stage": stage,
            "result_present": present,
            "status": status,
            "stage_field_matches": stage_field == stage,
            "required_markers": marker_values,
            "markers_ok": markers_ok,
            "expected_next_stage": expected_next,
            "recorded_next_stage": recorded_next,
            "next_stage_ok": next_ok,
            "ok": entry_ok,
        })
    return {
        "schema": "openrecomp-phase17-terminal-stage-chain-v1",
        "chain_length": len(STAGE_CHAIN),
        "stages": entries,
        "ok": ok,
    }


# ---------------------------------------------------------------------------
# 2. Prior-phase integrity (no Phase 1..16 modification)
# ---------------------------------------------------------------------------

def audit_prior_phase_integrity(root: pathlib.Path,
                                baseline: str = PHASE16_BASELINE_COMMIT
                                ) -> dict[str, Any]:
    """Phase-1..16 trees are unmodified relative to the frozen baseline."""
    touched = git(root, "log", "--oneline", f"{baseline}..HEAD", "--",
                  *PRIOR_PHASE_DIRS).stdout.splitlines()
    touching = [line for line in touched if line.strip()]
    trees: list[dict[str, Any]] = []
    ok = not touching
    for directory in PRIOR_PHASE_DIRS:
        at_base = git(root, "rev-parse", f"{baseline}:{directory}")
        at_head = git(root, "rev-parse", f"HEAD:{directory}")
        base_tree = at_base.stdout.strip() if at_base.returncode == 0 else ""
        head_tree = at_head.stdout.strip() if at_head.returncode == 0 else ""
        same = bool(base_tree) and base_tree == head_tree
        ok = ok and same
        trees.append({"directory": directory, "baseline_tree": base_tree,
                      "head_tree": head_tree, "identical": same})
    dirty = [line for line in git(root, "status", "--porcelain", "--",
                                  *PRIOR_PHASE_DIRS).stdout.splitlines()
             if line.strip()]
    ok = ok and not dirty
    return {
        "schema": "openrecomp-phase17-terminal-prior-phase-integrity-v1",
        "baseline_commit": baseline,
        "commits_touching_prior_phases": touching,
        "tree_comparisons": trees,
        "worktree_dirty_prior_phases": dirty,
        "method": (
            "git log baseline..HEAD over .openrecomp-phase1..16 must be empty; "
            "git rev-parse <baseline>:<dir> == HEAD:<dir> for each prior-phase "
            "tree; git status --porcelain over the same paths must be empty"
        ),
        "ok": ok,
    }


# ---------------------------------------------------------------------------
# 3. Certified provenance chain
# ---------------------------------------------------------------------------

def audit_provenance_chain(root: pathlib.Path,
                           base_commit: str = BASE_COMMIT) -> dict[str, Any]:
    """Each certified stage commit is a real ancestor of the base commit."""
    entries: list[dict[str, Any]] = []
    ok = True
    for stage, commit in PROVENANCE_CHAIN:
        resolved = git(root, "rev-parse", f"{commit}^{{commit}}")
        ancestor = git(root, "merge-base", "--is-ancestor", commit, base_commit)
        resolved_ok = (resolved.returncode == 0
                       and resolved.stdout.strip().startswith(commit))
        ancestor_ok = ancestor.returncode == 0
        entry_ok = resolved_ok and ancestor_ok
        ok = ok and entry_ok
        entries.append({
            "stage": stage,
            "certifying_commit": commit,
            "resolves": resolved_ok,
            "ancestor_of_base": ancestor_ok,
            "ok": entry_ok,
        })
    return {
        "schema": "openrecomp-phase17-terminal-provenance-chain-v1",
        "base_commit": base_commit,
        "certified_stages": entries,
        "ok": ok,
    }


# ---------------------------------------------------------------------------
# 4. Evidence manifest consistency
# ---------------------------------------------------------------------------

MANIFEST_PATH = ".openrecomp-phase17/SOURCE_SHA256SUMS.txt"


def audit_manifest_consistency(root: pathlib.Path) -> dict[str, Any]:
    """The committed source manifest matches the tracked Phase-17 sources."""
    manifest = root / MANIFEST_PATH
    text = manifest.read_text(encoding="utf-8") if manifest.is_file() else ""
    recorded: dict[str, str] = {}
    parse_errors: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split(" *", 1)
        if len(parts) != 2:
            parse_errors.append({"line": line_no, "reason": "missing-space-asterisk"})
            continue
        digest, relative = parts[0].strip().lower(), parts[1]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            parse_errors.append({"line": line_no, "reason": "bad-digest",
                                 "path": relative})
            continue
        recorded[relative] = digest

    listing = git(root, "ls-files", "-z", ".openrecomp-phase17/src", "tools")
    expected: set[str] = set()
    for raw in listing.stdout.split(chr(0)):
        if not raw:
            continue
        relative = raw
        name = relative.rsplit("/", 1)[-1]
        if (relative.startswith(".openrecomp-phase17/src/")
                and name.endswith(".py") and name.startswith("p17_")
                and name != "__init__.py"):
            expected.add(relative)
        elif (relative.startswith("tools/")
              and name.startswith("test_phase17_") and name.endswith(".py")):
            expected.add(relative)

    missing = sorted(expected - set(recorded))
    extra = sorted(set(recorded) - expected)
    mismatches: list[dict[str, str]] = []
    for relative in sorted(expected & set(recorded)):
        path = root / relative
        actual = sha256_bytes(path.read_bytes()) if path.is_file() else ""
        if actual != recorded[relative]:
            mismatches.append({"path": relative,
                               "recorded": recorded[relative],
                               "actual": actual})
    ok = not parse_errors and not missing and not extra and not mismatches
    return {
        "schema": "openrecomp-phase17-terminal-manifest-consistency-v1",
        "manifest": MANIFEST_PATH,
        "expected_count": len(expected),
        "entry_count": len(recorded),
        "parse_errors": parse_errors,
        "missing_entries": missing,
        "extra_entries": extra,
        "digest_mismatches": mismatches,
        "ok": ok,
    }


# ---------------------------------------------------------------------------
# 5. Marker ledger (no unsupported proof promotion)
# ---------------------------------------------------------------------------

def audit_marker_ledger(evidence_root: pathlib.Path, state_text: str,
                        queue_text: str, review_text: str) -> dict[str, Any]:
    """Every protected claim marker stays NOT_PROVEN/NO across all stages."""
    per_stage: list[dict[str, Any]] = []
    ok = True
    for stage in EVIDENCE_STAGE_DIRS:
        path = evidence_root / stage / "RESULT.json"
        if not path.is_file():
            per_stage.append({"stage": stage, "result_present": False, "ok": False})
            ok = False
            continue
        markers = _load_json(path).get("markers", {})
        drift: list[dict[str, str]] = []
        for marker, required in PROTECTED_MARKERS.items():
            if marker in markers and str(markers[marker]) != required:
                drift.append({"marker": marker, "required": required,
                              "found": str(markers[marker])})
        entry_ok = not drift
        ok = ok and entry_ok
        per_stage.append({
            "stage": stage,
            "result_present": True,
            "protected_markers": {marker: str(markers.get(marker, "<absent>"))
                                  for marker in PROTECTED_MARKERS},
            "drift": drift,
            "ok": entry_ok,
        })

    def declares(text: str) -> dict[str, bool]:
        found = {}
        for marker in PROTECTED_MARKERS:
            if marker == "FIRST_FRAME_READY":
                found[marker] = (marker + "=NO") in text
            else:
                found[marker] = marker in text
        return found

    state_declares = declares(state_text)
    queue_declares = declares(queue_text)
    review_declares = declares(review_text)
    ledger_ok = all(state_declares.values()) and all(queue_declares.values())
    return {
        "schema": "openrecomp-phase17-terminal-marker-ledger-v1",
        "stages": per_stage,
        "state_declares": state_declares,
        "queue_declares": queue_declares,
        "review_required_declares": review_declares,
        "promoted_markers": sorted(
            drift["marker"] for stage in per_stage for drift in stage["drift"]),
        "ok": ok and ledger_ok,
    }


# ---------------------------------------------------------------------------
# 6. REVIEW_REQUIRED terminal consistency
# ---------------------------------------------------------------------------

def audit_review_required(review_text: str) -> dict[str, Any]:
    """The historical P17-04..P17-07 review stop is cleared and the only
    remaining stop is the (now satisfied) P17-99 terminal gate."""
    normalized = " ".join(review_text.split())
    p17_90 = ("P17-90 was independently reviewed" in normalized
              and "integrated" in normalized)
    p17_91 = "P17-91 was independently reviewed" in normalized
    remaining = "remaining fail-closed stop covers P17-99" in normalized
    cleared = p17_90 and p17_91 and remaining
    stale = "The required next action is human review and redesign" in normalized
    return {
        "schema": "openrecomp-phase17-terminal-review-required-v1",
        "p17_90_reviewed_and_integrated": p17_90,
        "p17_91_reviewed_and_integrated": p17_91,
        "remaining_stop_is_p17_99": remaining,
        "historical_review_stop_cleared": cleared,
        "stale_required_next_action_present": stale,
        "ok": cleared and not stale,
    }


# ---------------------------------------------------------------------------
# 7. Terminal binding
# ---------------------------------------------------------------------------

def audit_terminal_binding(root: pathlib.Path, head: str, tree: str,
                           base_commit: str = BASE_COMMIT,
                           base_tree: str = BASE_TREE) -> dict[str, Any]:
    """The working tree binding is exact and internally consistent."""
    base_is_commit = git(root, "cat-file", "-t", base_commit).stdout.strip() == "commit"
    base_tree_of_commit = git(root, "rev-parse", f"{base_commit}^{{tree}}").stdout.strip()
    base_tree_matches = base_tree_of_commit == base_tree
    head_is_commit = git(root, "cat-file", "-t", head).stdout.strip() == "commit"
    head_tree_of_commit = git(root, "rev-parse", f"{head}^{{tree}}").stdout.strip()
    head_tree_matches = head_tree_of_commit == tree
    ok = (base_is_commit and base_tree_matches and head_is_commit
          and head_tree_matches)
    return {
        "schema": "openrecomp-phase17-terminal-binding-v1",
        "base_commit": base_commit,
        "base_tree": base_tree,
        "base_commit_is_commit": base_is_commit,
        "base_tree_matches": base_tree_matches,
        "head": head,
        "head_tree": tree,
        "head_is_commit": head_is_commit,
        "head_tree_matches": head_tree_matches,
        "ok": ok,
    }


# ---------------------------------------------------------------------------
# 8. Marker syntax
# ---------------------------------------------------------------------------

def audit_marker_syntax(texts: dict[str, str]) -> dict[str, Any]:
    """No malformed marker token: multi-equals or promoted NOT_PROVEN."""
    problems: list[dict[str, str]] = []
    checked = 0
    for name, text in texts.items():
        for line in text.splitlines():
            if not line.startswith("OPENRECOMP_"):
                continue
            checked += 1
            if line.count("=") != 1:
                problems.append({"document": name, "line": line,
                                 "reason": "multi-equals"})
                continue
            token, value = line.split("=", 1)
            if not MARKER_TOKEN_RE.match(token):
                problems.append({"document": name, "line": line,
                                 "reason": "bad-token"})
            if "NOT_PROVEN=PASS" in line or "=PASS=PASS" in line:
                problems.append({"document": name, "line": line,
                                 "reason": "promoted-marker"})
    return {
        "schema": "openrecomp-phase17-terminal-marker-syntax-v1",
        "lines_checked": checked,
        "problems": problems,
        "ok": not problems,
    }
