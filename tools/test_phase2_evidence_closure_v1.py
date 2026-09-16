#!/usr/bin/env python3
"""OpenRecomp Phase-2 evidence index, limitations and final-claim closure V1 (P2-91).

P2-91 is a closure/documentation/evidence stage.  It does not add architecture
features and does not broaden compatibility claims.  The deterministic gate
verifies:

* the authoritative Phase-2 evidence index covers every completed stage
  (P2-00, P2-01..P2-14, P2-20..P2-23, P2-30, P2-40, P2-50, P2-90) and every
  indexed evidence reference resolves to an existing artifact;
* the limitations document bounds every major claim and the claim matrix maps
  every public-facing claim to its supporting evidence with consistent
  terminology;
* the nine frozen host-path occurrences identified by P2-90 are classified,
  hash-pinned and left unmodified, and no new absolute local-host path appears
  in portable Phase-2 evidence, control-plane narrative or release artifacts;
* the P2-90 whole-project regression still passes (captured by
  ``--run-regression`` and re-validated on every run);
* the final Phase-2 verdict marker is NOT_PROVEN before P2-99 and carries the
  authorized PASS value after the validated P2-99 terminal verdict; a PASS
  marker without that validation still fails the closure audit.

Terminal-state contract (P2-99 transition): while the P2-99 final verdict has
not been issued this gate requires the final marker to remain ``NOT_PROVEN``
exactly as at P2-91 time.  After the validated P2-99 terminal verdict the gate
accepts the terminal ``PASS`` value in the control plane, the P2-99-owned
evidence and the three authoritative P2-91 closure documents, and it expects
the ``Phase-2 final end-to-end proof marker`` claim to be reclassified as
``PROVEN`` at its documented boundary.  The transition is authorized only by a
P2-99 verdict evidence document that declares PASS, records the stage/final
markers and pins the live P2-99 gate by SHA-256; the replacement coverage for
the pre-terminal invariants lives in ``tools/test_phase2_final_verdict_v1.py``.

The gate never asserts the final proof marker on its own.
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

EVIDENCE_ROOT = ROOT / ".openrecomp-phase2" / "evidence"
CONTROL_PLANE = ROOT / ".openrecomp-phase2"
EVIDENCE_DIR = EVIDENCE_ROOT / "P2-91"

STAGE = "P2-91"
STAGE_MARKER = "OPENRECOMP_P2_91"
FEATURE_MARKER = "OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1"
FINAL_MARKER = "OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF"
FINAL_MARKER_VALUE = "NOT_PROVEN"
P2_99_EVIDENCE = EVIDENCE_ROOT / "P2-99"
P2_99_GATE = ROOT / "tools" / "test_phase2_final_verdict_v1.py"
P2_99_STAGE_MARKER = "OPENRECOMP_P2_99=PASS"
FINAL_CLAIM_KEY = "Phase-2 final end-to-end proof marker"

P2_90_RECORDED_STDOUT_SHA256 = "74e9eadaf0e17ca4a97790e4239f40883cc745cd9817c172f7fa6e2663ce1ee7"
P2_90_MANIFEST_SHA256 = "1bf21db59bf11f4ff19d60bbe4e37afd8e4b8ca5f1391296d882c1149cc08fca"
P2_91_MANIFEST_SHA256 = "05180decf8bd835062dfc7b840dcc71893eae3789d7e27baaf57322c3371f144"
# P2-91-time hashes of the two closure/regression gates whose bytes are
# refreshed by the P2-99 terminal transition (recorded in the P2-91 manifest).
P2_91_RECORDED_GATE_HASHES = {
    "tools/test_phase2_whole_regression_v1.py":
        "5832a0aaf0dd470f7bfdff093d09be371ab03fcfb66d45d2a9844a7cceb090ef",
    "tools/test_phase2_evidence_closure_v1.py":
        "adf61b0a74bff3f57f359ecf03e010fe70eae1c5752f9cae8e3c5fea4df675fc",
}
P2_99_ADDED_MANIFEST_ENTRY = "tools/test_phase2_final_verdict_v1.py"

# Authoritative closure documents that carry the terminal-verdict addendum after
# P2-99; an authorized final-PASS statement in these files must name P2-99.
TERMINAL_DOC_SCOPE = {
    "P2-91/PHASE2_EVIDENCE_INDEX.md",
    "P2-91/PHASE2_LIMITATIONS.md",
    "P2-91/PHASE2_CLAIM_MATRIX.md",
}


def authorized_final_verdict() -> str:
    """Return the authorized terminal value of the final Phase-2 marker.

    Pre-terminal the marker must be NOT_PROVEN.  The terminal PASS value is
    authorized only by a P2-99 verdict evidence document that declares PASS,
    records the stage/final markers, pins the live P2-99 gate by SHA-256 and is
    reflected by the terminal marker statements in STATE.md and HANDOFF.md.
    Anything else fails closed to NOT_PROVEN.
    """
    try:
        result = json.loads((P2_99_EVIDENCE / "RESULT.json").read_text(encoding="utf-8"))
        state = (CONTROL_PLANE / "STATE.md").read_text(encoding="utf-8")
        handoff = (CONTROL_PLANE / "HANDOFF.md").read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 - fail closed
        return FINAL_MARKER_VALUE
    if result.get("verdict") != "PASS":
        return FINAL_MARKER_VALUE
    markers = result.get("markers") or {}
    if markers.get("stage") != P2_99_STAGE_MARKER:
        return FINAL_MARKER_VALUE
    if markers.get("final") != f"{FINAL_MARKER}=PASS":
        return FINAL_MARKER_VALUE
    if not P2_99_GATE.is_file() or result.get("gate_sha256") != sha256_bytes(P2_99_GATE.read_bytes()):
        return FINAL_MARKER_VALUE
    for text in (state, handoff):
        if re.search(r"^" + re.escape(P2_99_STAGE_MARKER) + r"\s*$", text, re.MULTILINE) is None:
            return FINAL_MARKER_VALUE
        if re.search(r"^" + re.escape(FINAL_MARKER) + r"=PASS\s*$", text, re.MULTILINE) is None:
            return FINAL_MARKER_VALUE
    return "PASS"
P2_90_RECORDED_CAPTURE = "P2-90/p2_90_run1.txt"
P2_90_GATE = "tools/test_phase2_whole_regression_v1.py"
P2_90_CAPTURE_REL = pathlib.PurePosixPath("p2_90_rerun")
P2_90_RUN_STDOUT = "p2_90_rerun.txt"

# Frozen P2-90-owned capture files that the nested P2-90 audit rewrites as a
# side effect (its phase-1 capture path is hard-coded).  P2-91 preserves their
# bytes around the official rerun and records the preservation proof.
P2_90_PRESERVED_FILES = (
    "phase1_host_gates/command.txt",
    "phase1_host_gates/stderr.txt",
    "phase1_host_gates/stdout.txt",
    "source_integrity/command.txt",
    "source_integrity/stderr.txt",
    "source_integrity/stdout.txt",
)

# ---------------------------------------------------------------------------
# Canonical stage tables (reused from the P2-90 audit where it owns the value)
# ---------------------------------------------------------------------------
# (stage id, ledger name, expected gate marker, expected check count)
STAGES: tuple[tuple[str, str, str, int | None], ...] = tuple(
    (stage, name, f"{feature}=PASS tests={tests}" if feature else "n/a", tests)
    for stage, name, _directory, feature, tests in p2_90.COMPLETED_STAGES
) + (
    ("P2-90", "Whole-project regression", "OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361", 361),
)

INDEX_ARTIFACTS = {
    "index_md": ("PHASE2_EVIDENCE_INDEX.md", "PHASE2_EVIDENCE_INDEX"),
    "index_json": ("PHASE2_EVIDENCE_INDEX.json", None),
    "limitations": ("PHASE2_LIMITATIONS.md", "PHASE2_LIMITATIONS"),
    "claim_matrix": ("PHASE2_CLAIM_MATRIX.md", "PHASE2_CLAIM_MATRIX"),
    "host_path_audit": ("host_path_audit.md", "HOST_PATH_AUDIT"),
    "host_path_register": ("host_path_occurrences.json", None),
    "capture_preservation": ("p2_90_capture_preservation.json", None),
    "rerun_summary": ("p2_90_rerun.json", None),
}

INDEX_FIELD_LABELS = (
    "PASS marker",
    "Gate marker",
    "Test/check count",
    "Evidence directory",
    "Principal RESULT",
    "Fixture/input identity",
    "Generated/executable/package identity",
    "Deterministic-run identity",
    "Claim boundary",
)

# Extra stage identities curated by P2-91 (stage-time records).  Every token is
# independently re-verified against the frozen stage evidence by this gate.
INDEX_IDENTITY_TOKENS: dict[str, tuple[str, ...]] = {
    "P2-00": ("dc063ef0a3ab0bce4eb98a3ba82ba53be10ba8fcf286629ceaf7f5e9f6ba6d68",),
    "P2-01": (
        "c52847e67a35e8890bc1e9e2c7c474e2e8dfe7bce567190018b459fb8645b9df",
        "sample_nes_call.program.json",
    ),
    "P2-02": (
        "483df98e4ecb6a64441d22692ddcd54777ec52956dc041dae44242cb32886e70",
        "sample_cfg.json",
    ),
    "P2-03": (
        "05218d8d1db991e2ff93679340490d59dcea24add7c3c8d2faee0bf26cbe39a8",
        "sample_functions.discovery.json",
    ),
    "P2-04": (
        "ee4602245dfad5301385b958826dca112c0b600d7e418a37954d39172ea9b374",
        "sample_call_graph.json",
    ),
    "P2-05": ("7209c6ff6bc40d131af0e04eae3c48d48d785ce864de46d0e406d81dbdbbc24a",),
    "P2-06": ("866d290a59228e5bd01f5bc026d2a2b1ca5558e28e9165b2dea42e00464d72a2",),
    "P2-07": ("fb6e6e2c6ba660a5c3df75602a59c0501bf86ca53e0371e4942c0c76108c45d5",),
    "P2-08": ("3c0abaf52efa534b2dc639efceb15cd6e5aa17a4ec218d5515b1160f260809a8",),
    "P2-09": (
        "db055b5cd622a7ef188901ef8da65898e2dac0cacb03c0ee2fb6caeec5b3e273",
        "b75d7656517de8a75c5730fa22b7ea69dff9292be20a6f73d0bd49cf64705e24",
        "de03764e429a6e31d46037c72cd08db126fab18f2838b037b8ecee7deea81368",
    ),
    "P2-20": (
        "0dfbf094", "2924881e", "7b83a827", "e99dce4b", "d0062fed", "67113cc1",
    ),
    "P2-22": ("4ae725be384b991c58d5e072930603b93c72c939df89c18f07749ae5c3db7b5c",),
    "P2-30": ("be52ef25060e22f8c4677c2e87a2e89180f82ae88833c4d910ec11fe1881b9f6",),
    "P2-90": (P2_90_RECORDED_STDOUT_SHA256,),
}

# ---------------------------------------------------------------------------
# Host-path policy
# ---------------------------------------------------------------------------
# The nine pre-existing absolute-host-path occurrences identified by P2-90
# (P2-90/corrections_report.md C4).  None may be rewritten: six are pinned by
# frozen PASS-stage hashes / recorded stdout claims, and all nine are historical
# host-environment identifiers (not secrets, not console content, absent from
# every release package).  Each entry pins the frozen file bytes so the closure
# audit detects any later modification.
FROZEN_HOST_PATH_FILES: dict[str, dict[str, Any]] = {
    "P2-00/RESULT.md": {
        "sha256": "74e0d86d5004313db7f9200f84d345f75fb5308a2bf9fba2218d32d68aecc651",
        "occurrence": "baseline working-copy path row",
        "class": "FROZEN_HISTORICAL_EVIDENCE",
        "pinning": "frozen P2-00 baseline RESULT (no direct hash pin)",
    },
    "P2-07/host_emitter_tests.json": {
        "sha256": "eae4a00e1fc28cabcfe8296c5110412f843eb4c4116e6377d2d44ed0d520b5c1",
        "occurrence": "detected native compiler executable path",
        "class": "FROZEN_HASH_PINNED_EVIDENCE",
        "pinning": "P2-07/RESULT.json artifacts_sha256, P2-07/determinism.txt",
    },
    "P2-07/native_compile.txt": {
        "sha256": "96f80ec6d271f5a282f345a5449f174ef702895365ddcca0c28b6f38f507b028",
        "occurrence": "detected native compiler executable path (raw capture)",
        "class": "FROZEN_HISTORICAL_EVIDENCE",
        "pinning": "frozen raw capture (no direct hash pin); portable derivative provided",
    },
    "P2-08/determinism.txt": {
        "sha256": "f5903884e47c8a9cd928bc075206046249efaea0155b2bfd5be164ea498e28b3",
        "occurrence": "detected native compiler executable path (raw capture)",
        "class": "FROZEN_HISTORICAL_EVIDENCE",
        "pinning": "frozen raw capture (no direct hash pin); portable derivative provided",
    },
    "P2-08/runtime_abi_tests.json": {
        "sha256": "88f304beed3e675b198873002c81528964520761163152450184c63d12e6e3b7",
        "occurrence": "detected native compiler executable path",
        "class": "FROZEN_HASH_PINNED_EVIDENCE",
        "pinning": "P2-08/RESULT.json artifacts_sha256, P2-08/changed_files.txt",
    },
    "P2-40/run1.txt": {
        "sha256": "405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228",
        "occurrence": "interpreter path in captured gate stdout (recorded determinism run)",
        "class": "FROZEN_HASH_PINNED_EVIDENCE",
        "pinning": "P2-40/RESULT.json gate_stdout_sha256, RESULT.md, determinism.txt",
    },
    "P2-40/run2.txt": {
        "sha256": "405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228",
        "occurrence": "interpreter path in captured gate stdout (recorded determinism run)",
        "class": "FROZEN_HASH_PINNED_EVIDENCE",
        "pinning": "P2-40/RESULT.json gate_stdout_sha256, RESULT.md, determinism.txt",
    },
    "P2-50/regression_tools_test_cross_architecture_neutrality_v1.txt": {
        "sha256": "8a6c311b2464070a2ea0320b2c49277307e94d3a9d55c8034cf69009bd5c5a95",
        "occurrence": "interpreter path in nested regression capture",
        "class": "FROZEN_HASH_PINNED_EVIDENCE",
        "pinning": "P2-50/RESULT.json evidence_hashes; re-verified by the P2-90 audit",
    },
    "P2-50/regression_tools_test_generic_runtime_integration_v1.txt": {
        "sha256": "78555f99defe8d54e3301f531ea50f9421aa5950fa3d933006dd16d6a473951d",
        "occurrence": "interpreter path in nested regression capture",
        "class": "FROZEN_HASH_PINNED_EVIDENCE",
        "pinning": "P2-50/RESULT.json evidence_hashes; re-verified by the P2-90 audit",
    },
}

# Pre-existing Phase-2 control-plane installer metadata (not evidence): the
# P2-00 installer recorded its own project root/prompt path.  Out of the
# portable-evidence scope, pinned so any later change is detected.
CONTROL_PLANE_INSTALLER_METADATA = (
    ".openrecomp-phase2/INSTALL_INFO.txt",
    ".openrecomp-phase2/P2_00_START_PROMPT.txt",
)

# Directories excluded from the portable-evidence host-path guard: they are
# pre-existing untracked raw capture/backup residue by design (the P2-90 audit
# writes raw gate captures there and never treats them as evidence).
HOST_PATH_SCAN_EXCLUDED_PARTS = {"scratch", "backups"}

# ---------------------------------------------------------------------------
# Limitations / claim-matrix vocabulary
# ---------------------------------------------------------------------------
# The authoritative claim keys used by PHASE2_LIMITATIONS.md and
# PHASE2_CLAIM_MATRIX.md.  The eighteen P2-90 claims keep their exact identifiers
# and classifications; five closure claims are added (P2-91 decision recorded in
# PHASE2_CLAIM_MATRIX.md).
CLAIM_CLASSIFICATIONS: dict[str, str] = {
    "architecture-neutral shared analysis pipeline": "PROVEN",
    "deterministic ProgramModel/CFG/function/call-graph/translation pipeline": "PROVEN",
    "NES/6502 frontend integration": "BOUNDED_PROVEN",
    "NES runtime bridge": "BOUNDED_PROVEN",
    "NES synthetic end-to-end native recompilation": "BOUNDED_PROVEN",
    "observable equivalence": "BOUNDED_PROVEN",
    "deterministic repeated execution": "PROVEN",
    "MIPS32 shared-path operation": "BOUNDED_PROVEN",
    "generic runtime neutrality": "PROVEN",
    "fail-closed unsupported-service behavior": "BOUNDED_PROVEN",
    "reproducible native build": "BOUNDED_PROVEN",
    "reproducible release package": "BOUNDED_PROVEN",
    "provenance and legal-asset policy enforcement": "PROVEN",
    "arbitrary NES ROM compatibility": "NOT_PROVEN",
    "commercial-game compatibility": "NOT_PROVEN",
    "complete NES hardware compatibility": "NOT_PROVEN",
    "arbitrary mapper support": "NOT_PROVEN",
    "cycle accuracy": "OUT_OF_SCOPE",
    "arbitrary MIPS32 binary compatibility": "NOT_PROVEN",
    "PS1/PS2/Xbox compatibility": "OUT_OF_SCOPE",
    "future architecture compatibility": "NOT_PROVEN",
    "production-ready universal console runtime": "NOT_PROVEN",
    "Phase-2 final end-to-end proof marker": "NOT_PROVEN",
}

NEW_CLAIM_KEYS = (
    "deterministic ProgramModel/CFG/function/call-graph/translation pipeline",
    "fail-closed unsupported-service behavior",
    "provenance and legal-asset policy enforcement",
    "arbitrary mapper support",
    "production-ready universal console runtime",
)

PROVEN_KEYS = tuple(
    key for key, value in CLAIM_CLASSIFICATIONS.items() if value in {"PROVEN", "BOUNDED_PROVEN"}
)
UNPROVEN_KEYS = tuple(
    key for key, value in CLAIM_CLASSIFICATIONS.items() if value in {"NOT_PROVEN", "OUT_OF_SCOPE"}
)

NEGATION_PATTERN = re.compile(r"\bnot\b|\bnever\b|unclaimed|reserved|does not|do not", re.IGNORECASE)

HOST_PATH_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    rb"|(?<![\\])\\\\[A-Za-z0-9_.$-]"
    rb"|file://|/tmp/|/var/tmp/|/home/|/Users/|\\Temp\\|\\AppData\\|\\Users\\"
)

CONSOLE_MAGICS = p2_90.CONSOLE_MAGICS
FORBIDDEN_SUFFIXES = p2_90.FORBIDDEN_SUFFIXES

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {
    "stage_index": [],
    "host_path_findings": [],
    "legal_findings": [],
    "claim_matrix": [],
    "limitations": [],
    "premature_verdict_findings": [],
    "p2_90_rerun": {},
}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n")


def read_text(path: pathlib.Path) -> str:
    return normalize_text(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Static closure audit
# ---------------------------------------------------------------------------
def audit_artifacts(require_capture: bool = True) -> None:
    for key, (name, marker) in INDEX_ARTIFACTS.items():
        if not require_capture and key in {"capture_preservation", "rerun_summary"}:
            continue
        path = EVIDENCE_DIR / name
        check(f"artifacts:present:{key}", path.exists() and path.stat().st_size > 0)
        if marker is not None:
            check(f"artifacts:marker:{key}", marker in read_text(path))


def parse_index(markdown: str) -> dict[str, dict[str, str]]:
    stages: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in markdown.splitlines():
        heading = re.match(r"^###\s+(P2-[0-9]+)\s+—\s+(.+)$", line)
        if heading:
            current = heading.group(1)
            stages[current] = {"__name__": heading.group(2).strip()}
            continue
        if current is None:
            continue
        field = re.match(r"^-\s+([^:]+):\s*(.*)$", line)
        if field:
            stages[current][field.group(1).strip()] = field.group(2).strip()
    return stages


def identity_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            tokens |= identity_tokens(item)
    elif isinstance(value, str):
        tokens.add(value)
    return tokens


def token_in_evidence(stage: str, token: str) -> bool:
    stage_dir = EVIDENCE_ROOT / stage
    if not stage_dir.exists():
        return False
    for suffix in (".md", ".json", ".txt", ".c"):
        for path in sorted(stage_dir.rglob(f"*{suffix}")):
            if not path.is_file():
                continue
            if token.encode("ascii", "ignore") in path.read_bytes():
                return True
    return False


def resolve_refs(markdown: str) -> dict[str, Any]:
    pattern = re.compile(
        r"`((?:\.openrecomp-phase2|openrecomp|tools|schema|adapters)/[A-Za-z0-9_./-]+)`"
    )
    missing: list[str] = []
    resolved: list[str] = []
    for ref in sorted(set(pattern.findall(markdown))):
        if (ROOT / ref).exists():
            resolved.append(ref)
        else:
            missing.append(ref)
    return {"resolved": resolved, "missing": missing}


def audit_index() -> None:
    md = read_text(EVIDENCE_DIR / "PHASE2_EVIDENCE_INDEX.md")
    document = json.loads((EVIDENCE_DIR / "PHASE2_EVIDENCE_INDEX.json").read_text(encoding="utf-8"))
    records = {item["stage"]: item for item in document["stages"]}
    parsed = parse_index(md)

    check("index:coverage-complete", {stage for stage, *_ in STAGES} == set(parsed))
    check("index:json-coverage-complete", {stage for stage, *_ in STAGES} == set(records))

    for stage, name, gate_marker, tests in STAGES:
        section = parsed.get(stage)
        check(f"index:stage-{stage}", section is not None)
        missing = [label for label in INDEX_FIELD_LABELS if label not in section]
        check(f"index:stage-{stage}:fields", not missing)
        check(f"index:stage-{stage}:name", name.lower() in section["__name__"].lower())
        check(f"index:stage-{stage}:pass-marker",
              f"OPENRECOMP_{stage.replace('-', '_')}=PASS" in section["PASS marker"])
        check(f"index:stage-{stage}:gate-marker", gate_marker in section["Gate marker"])
        if tests is not None:
            check(f"index:stage-{stage}:count", f"`{tests}`" in section["Test/check count"])
        else:
            check(f"index:stage-{stage}:count", "n/a" in section["Test/check count"].lower())
        check(f"index:stage-{stage}:evidence-dir",
              f".openrecomp-phase2/evidence/{stage}/" in section["Evidence directory"])
        check(f"index:stage-{stage}:result",
              f".openrecomp-phase2/evidence/{stage}/RESULT.md" in section["Principal RESULT"])
        check(f"index:stage-{stage}:result-exists",
              (EVIDENCE_ROOT / stage / "RESULT.md").exists())

        expected_tokens = set(INDEX_IDENTITY_TOKENS.get(stage, ()))
        if stage in p2_90.IDENTITIES:
            expected_tokens |= identity_tokens(p2_90.IDENTITIES[stage])
        blob = " ".join(section.values())
        for token in sorted(expected_tokens):
            check(f"index:stage-{stage}:identity:{token[:16]}", token in blob)
            check(f"index:stage-{stage}:identity-in-evidence:{token[:16]}",
                  token_in_evidence(stage, token))

        record = records.get(stage)
        check(f"index:json-{stage}", record is not None)
        check(f"index:json-{stage}:gate-marker", gate_marker in str(record.get("gate_marker")))
        check(f"index:json-{stage}:count", record.get("check_count") == tests)
        check(f"index:json-{stage}:evidence-dir",
              record.get("evidence_directory") == f".openrecomp-phase2/evidence/{stage}/")
        check(f"index:json-{stage}:result",
              record.get("principal_result") == f".openrecomp-phase2/evidence/{stage}/RESULT.md")
        for field_name in ("fixture_input_identity", "generated_executable_package_identity",
                           "deterministic_run_identity", "claim_boundary"):
            check(f"index:json-{stage}:{field_name}",
                  isinstance(record.get(field_name), str) and len(record[field_name]) > 0)
        for token in sorted(expected_tokens):
            check(f"index:json-{stage}:identity:{token[:16]}",
                  token in json.dumps(record, sort_keys=True))

        FINDINGS["stage_index"].append({
            "stage": stage,
            "name": name,
            "gate_marker": gate_marker,
            "check_count": tests,
            "evidence_directory": f".openrecomp-phase2/evidence/{stage}/",
            "principal_result": f".openrecomp-phase2/evidence/{stage}/RESULT.md",
            "identity_tokens_verified": sorted(expected_tokens),
        })

    refs = resolve_refs(md)
    check("index:refs-resolve", refs["missing"] == [])
    FINDINGS["index_refs"] = refs


# ---------------------------------------------------------------------------
# Limitations audit
# ---------------------------------------------------------------------------
def audit_limitations() -> None:
    text = read_text(EVIDENCE_DIR / "PHASE2_LIMITATIONS.md")
    authorized = authorized_final_verdict()
    check("limitations:proven-heading", "PROVEN / BOUNDED_PROVEN" in text)
    check("limitations:unproven-heading", "NOT_PROVEN / OUT_OF_SCOPE" in text)
    check("limitations:final-marker-statement",
          FINAL_MARKER in text and authorized in text and "P2-99" in text
          and (authorized == FINAL_MARKER_VALUE or f"{FINAL_MARKER}=PASS" in text))
    expected = effective_claim_classifications()
    for key, classification in expected.items():
        if classification in {"PROVEN", "BOUNDED_PROVEN"}:
            check(f"limitations:proven:{key}", f"`{key}`" in text)
    for key, classification in expected.items():
        if classification in {"NOT_PROVEN", "OUT_OF_SCOPE"}:
            check(f"limitations:unproven:{key}", f"`{key}`" in text)
    check("limitations:no-final-pass-claim",
          not premature_pass_claims(text, allow_authorized=authorized == "PASS"))
    refs = resolve_refs(text)
    check("limitations:refs-resolve", refs["missing"] == [])
    FINDINGS["limitations"] = {
        "proven_keys": [key for key, value in expected.items() if value in {"PROVEN", "BOUNDED_PROVEN"}],
        "unproven_keys": [key for key, value in expected.items() if value in {"NOT_PROVEN", "OUT_OF_SCOPE"}],
    }


# ---------------------------------------------------------------------------
# Claim-matrix audit
# ---------------------------------------------------------------------------
def audit_claim_matrix() -> None:
    text = read_text(EVIDENCE_DIR / "PHASE2_CLAIM_MATRIX.md")
    authorized = authorized_final_verdict()
    expected = effective_claim_classifications()
    check("claim-matrix:final-marker-statement",
          FINAL_MARKER in text and authorized in text and "P2-99" in text
          and (authorized == FINAL_MARKER_VALUE or f"{FINAL_MARKER}=PASS" in text))
    check("claim-matrix:no-final-pass-claim",
          not premature_pass_claims(text, allow_authorized=authorized == "PASS"))
    rows: dict[str, str] = {}
    for line in text.splitlines():
        row = re.match(r"^\|\s*`([^`]+)`\s*\|\s*`?([A-Z_]+)`?\s*\|", line)
        if row:
            rows[row.group(1)] = row.group(2)
    for claim, classification, _basis in p2_90.CLAIMS:
        expected_class = expected.get(claim, classification)
        check(f"claim-matrix:p2-90:{claim}", rows.get(claim) == expected_class)
    for claim in NEW_CLAIM_KEYS:
        check(f"claim-matrix:new:{claim}", rows.get(claim) == expected[claim])
    for claim, classification in rows.items():
        check(f"claim-matrix:vocabulary:{claim}",
              classification in {"PROVEN", "BOUNDED_PROVEN", "NOT_PROVEN", "OUT_OF_SCOPE"})
    check("claim-matrix:key-coverage", set(expected) == set(rows))
    for key, classification in expected.items():
        if classification in {"PROVEN", "BOUNDED_PROVEN"}:
            check(f"claim-matrix:proven-section:{key}", f"`{key}`" in text)
    for key, classification in expected.items():
        if classification in {"NOT_PROVEN", "OUT_OF_SCOPE"}:
            check(f"claim-matrix:unproven-section:{key}", f"`{key}`" in text)
    refs = resolve_refs(text)
    check("claim-matrix:refs-resolve", refs["missing"] == [])
    FINDINGS["claim_matrix"] = [
        {"claim": claim, "classification": classification} for claim, classification in sorted(rows.items())
    ]


# ---------------------------------------------------------------------------
# Premature-verdict audit
# ---------------------------------------------------------------------------
def premature_pass_claims(text: str, *, allow_authorized: bool = False) -> list[str]:
    """Return un-negated final-PASS marker statements.

    ``allow_authorized`` permits occurrences whose surrounding window names the
    P2-99 terminal verdict; it is used only when the P2-99 verdict evidence is
    present and validated, and only for the terminal control-plane marker
    statements and the three P2-91 closure documents that carry the addendum.
    """
    findings: list[str] = []
    lines = text.splitlines()
    needle = f"{FINAL_MARKER}=PASS"
    for index, line in enumerate(lines):
        if needle not in line:
            continue
        window = " ".join(lines[max(0, index - 1): index + 3])
        if NEGATION_PATTERN.search(window):
            continue
        if allow_authorized and ("P2-99" in window or "P2_99" in window):
            continue
        findings.append(line.strip())
    return findings


def effective_claim_classifications() -> dict[str, str]:
    """Claim classifications valid for the current (pre/terminal) state."""
    mapping = dict(CLAIM_CLASSIFICATIONS)
    if authorized_final_verdict() == "PASS":
        mapping[FINAL_CLAIM_KEY] = "PROVEN"
    return mapping


def parse_manifest(lines: list[str]) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in lines:
        digest, separator, path = line.partition(" *")
        if separator:
            entries[path.strip()] = digest.strip()
    return entries


def audit_premature_verdict() -> None:
    authorized = authorized_final_verdict()
    for name in ("PHASE2_EVIDENCE_INDEX.md", "PHASE2_LIMITATIONS.md",
                 "PHASE2_CLAIM_MATRIX.md", "host_path_audit.md"):
        text = read_text(EVIDENCE_DIR / name)
        check(f"premature-verdict:{name}",
              not premature_pass_claims(text, allow_authorized=authorized == "PASS"))

    state = read_text(CONTROL_PLANE / "STATE.md")
    handoff = read_text(CONTROL_PLANE / "HANDOFF.md")
    queue = read_text(CONTROL_PLANE / "STAGE_QUEUE.md")
    state_lines = re.findall(r"^" + re.escape(FINAL_MARKER) + r"=(\S+)\s*$", state, re.MULTILINE)
    handoff_lines = re.findall(r"^" + re.escape(FINAL_MARKER) + r"=(\S+)\s*$", handoff, re.MULTILINE)
    check("premature-verdict:state-not-proven", state_lines == [authorized])
    check("premature-verdict:handoff-not-proven", handoff_lines == [authorized])
    check("premature-verdict:queue-reserves-p2-99",
          re.search(r"^\|\s*P2-99\s*\|[^|]*\|\s*(QUEUED|NEXT|COMPLETE)\s*\|", queue, re.MULTILINE) is not None
          and "Final verdict" in queue)
    check("premature-verdict:queue-p2-91",
          re.search(r"^\|\s*P2-91\s*\|[^|]*\|\s*(NEXT|COMPLETE)\s*\|", queue, re.MULTILINE) is not None)

    findings: list[str] = []
    if authorized != "PASS":
        for label, text in (("STATE.md", state), ("HANDOFF.md", handoff)):
            findings.extend(f"{label}: {item}" for item in premature_pass_claims(text))
    for path in sorted(EVIDENCE_ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        if "/scratch/" in rel:
            continue
        evidence_rel = path.relative_to(EVIDENCE_ROOT).as_posix()
        if authorized == "PASS" and evidence_rel.startswith("P2-99/"):
            # The validated P2-99 verdict evidence is the authorized claim site;
            # the P2-99 gate separately validates its bounded-claim content.
            continue
        allow = authorized == "PASS" and evidence_rel in TERMINAL_DOC_SCOPE
        findings.extend(f"{rel}: {item}" for item in premature_pass_claims(
            path.read_text(encoding="utf-8", errors="replace"), allow_authorized=allow))
    check("premature-verdict:no-unnegated-pass-marker", not findings)
    FINDINGS["premature_verdict_findings"] = findings


# ---------------------------------------------------------------------------
# Host-path recurrence audit
# ---------------------------------------------------------------------------
def iter_host_path_scope() -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for path in sorted(CONTROL_PLANE.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        parts = pathlib.PurePosixPath(rel).parts
        if len(parts) >= 2 and parts[1] in HOST_PATH_SCAN_EXCLUDED_PARTS:
            continue
        paths.append(path)
    for path in sorted((ROOT / "openrecomp").rglob("*.py")):
        if path.relative_to(ROOT).as_posix() == "openrecomp/release_package.py":
            continue
        paths.append(path)
    for path in sorted((ROOT / "adapters").rglob("*.py")):
        paths.append(path)
    return paths


def audit_host_paths() -> None:
    register = json.loads((EVIDENCE_DIR / "host_path_occurrences.json").read_text(encoding="utf-8"))
    entries = {item["file"]: item for item in register["files"]}
    check("host-path:register-complete", set(entries) == set(FROZEN_HOST_PATH_FILES))

    for rel, expected in FROZEN_HOST_PATH_FILES.items():
        path = EVIDENCE_ROOT / rel
        check(f"host-path:frozen-exists:{rel}", path.exists())
        check(f"host-path:frozen-sha256:{rel}", sha256_file(path) == expected["sha256"])
        check(f"host-path:frozen-still-detected:{rel}",
              bool(HOST_PATH_PATTERN.search(path.read_bytes())))
        entry = entries.get(rel, {})
        check(f"host-path:register-class:{rel}", entry.get("class") == expected["class"])
        check(f"host-path:register-pinning:{rel}", bool(entry.get("pinning")))
        check(f"host-path:register-sha256:{rel}", entry.get("sha256") == expected["sha256"])
        check(f"host-path:register-resolution:{rel}", bool(entry.get("resolution")))
        FINDINGS["host_path_findings"].append({
            "file": f".openrecomp-phase2/evidence/{rel}",
            "class": expected["class"],
            "sha256": expected["sha256"],
            "resolution": entry.get("resolution"),
        })

    installer_map = {item["file"]: item for item in register.get("control_plane_metadata", [])}
    check("host-path:control-plane-metadata-documented",
          set(installer_map) == set(CONTROL_PLANE_INSTALLER_METADATA))
    for rel in CONTROL_PLANE_INSTALLER_METADATA:
        path = ROOT / rel
        check(f"host-path:control-plane-metadata-exists:{rel}", path.exists())
        check(f"host-path:control-plane-metadata-sha256:{rel}",
              installer_map.get(rel, {}).get("sha256") == sha256_file(path))
        check(f"host-path:control-plane-metadata-detected:{rel}",
              bool(HOST_PATH_PATTERN.search(path.read_bytes())))

    frozen_rels = {f".openrecomp-phase2/evidence/{item}" for item in FROZEN_HOST_PATH_FILES}
    unexpected: list[str] = []
    for path in iter_host_path_scope():
        rel = path.relative_to(ROOT).as_posix()
        if rel in frozen_rels or rel in CONTROL_PLANE_INSTALLER_METADATA:
            continue
        if HOST_PATH_PATTERN.search(path.read_bytes()):
            unexpected.append(rel)
    check("host-path:no-new-occurrences", not unexpected)
    FINDINGS["host_path_findings"].extend({"file": item, "kind": "unexpected-host-path"} for item in unexpected)

    own_findings: list[str] = []
    for path in sorted(EVIDENCE_DIR.rglob("*")):
        if not path.is_file():
            continue
        if HOST_PATH_PATTERN.search(path.read_bytes()):
            own_findings.append(path.relative_to(ROOT).as_posix())
    check("host-path:p2-91-artifacts-clean", not own_findings)
    FINDINGS["host_path_findings"].extend({"file": item, "kind": "p2-91-host-path"} for item in own_findings)

    package_findings: list[str] = []
    for archive in sorted((EVIDENCE_ROOT / "P2-50").glob("package_*.zip")):
        pairs = rp.read_canonical_archive(archive.read_bytes())
        entries_policy = tuple(p2_90._PolicyEntry(info.name, content) for info, content in pairs)
        for item in rp.content_policy_findings(entries_policy):
            package_findings.append(f"{archive.name}: {item}")
    check("host-path:release-packages-clean", not package_findings)
    FINDINGS["host_path_findings"].extend({"file": item, "kind": "release-package-policy"} for item in package_findings)


# ---------------------------------------------------------------------------
# Legal / content policy audit
# ---------------------------------------------------------------------------
def tracked_files() -> list[pathlib.Path]:
    raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"], stderr=subprocess.STDOUT)
    return [ROOT / item.decode("utf-8") for item in raw.split(bytes([0])) if item]


def audit_legal() -> None:
    tracked_findings: list[dict[str, str]] = []
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            tracked_findings.append({"file": rel, "kind": "console-asset-suffix"})
            continue
        if not path.exists():
            tracked_findings.append({"file": rel, "kind": "tracked-file-missing"})
            continue
        head = path.read_bytes()[:16]
        for magic, label in CONSOLE_MAGICS:
            if head.startswith(magic):
                tracked_findings.append({"file": rel, "kind": f"console-magic:{label}"})
        if path.suffix.lower() in {".md", ".json", ".txt", ".c", ".h", ".py"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in pss.MARKERS:
                if marker.search(text):
                    tracked_findings.append({"file": rel, "kind": "public-safety-marker"})
    check("legal:tracked-tree-clean", not tracked_findings)
    FINDINGS["legal_findings"].extend(tracked_findings)

    for archive in sorted((EVIDENCE_ROOT / "P2-50").glob("package_*.zip")):
        pairs = rp.read_canonical_archive(archive.read_bytes())
        entries_policy = tuple(p2_90._PolicyEntry(info.name, content) for info, content in pairs)
        findings = rp.content_policy_findings(entries_policy)
        check(f"legal:release-package-policy:{archive.name}", not findings)
        FINDINGS["legal_findings"].extend(
            {"file": f"{archive.name}:{item}", "kind": "release-package-policy"} for item in findings
        )

    audit_host_paths()


# ---------------------------------------------------------------------------
# Source integrity
# ---------------------------------------------------------------------------
def audit_source_integrity(python: str) -> None:
    completed = subprocess.run(
        [python, "tools/phase1_host_gates_v1.py", "--only", "source-integrity"],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600,
    )
    stdout = completed.stdout or ""
    entries = re.search(r"verified (\d+) manifest entries", stdout)
    check("source-integrity:pass",
          completed.returncode == 0 and "source-integrity" in stdout and entries is not None)
    manifest_lines = (ROOT / "SOURCE_SHA256SUMS.txt").read_text(encoding="utf-8").strip().splitlines()
    check("source-integrity:count-matches-manifest",
          entries is not None and int(entries.group(1)) == len(manifest_lines))
    manifest = "\n".join(manifest_lines)
    check("source-integrity:closure-gate-registered", "tools/test_phase2_evidence_closure_v1.py" in manifest)
    # The manifest must reproduce both historical manifests exactly: removing the
    # P2-99 gate entry and restoring the P2-91-recorded terminal-gate hashes must
    # reproduce the P2-91 manifest, and removing the closure-gate entry from that
    # must reproduce the P2-90 manifest.  This holds before the P2-99 terminal
    # transition (the reconstruction is the identity) and after it, so no
    # unauthorized manifest line can be added, removed or changed in either state.
    current = parse_manifest(manifest_lines)
    reconstructed = dict(current)
    reconstructed.pop(P2_99_ADDED_MANIFEST_ENTRY, None)
    for relative, recorded in P2_91_RECORDED_GATE_HASHES.items():
        reconstructed[relative] = recorded
    rebuilt = sorted(f"{digest} *{path}" for path, digest in reconstructed.items())
    p2_91_ok = sha256_bytes(("\n".join(rebuilt) + "\n").encode("utf-8")) == P2_91_MANIFEST_SHA256
    without_closure = [line for line in rebuilt if "tools/test_phase2_evidence_closure_v1.py" not in line]
    p2_90_ok = sha256_bytes(("\n".join(without_closure) + "\n").encode("utf-8")) == P2_90_MANIFEST_SHA256
    check("source-integrity:manifest-delta-additive-only", p2_91_ok and p2_90_ok)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "source_integrity.txt").write_bytes(
        ("command: python tools/phase1_host_gates_v1.py --only source-integrity\n"
         + normalize_text(stdout)).encode("utf-8")
    )
    FINDINGS["source_integrity"] = {
        "manifest_entries": len(manifest_lines),
        "manifest_sha256": sha256_file(ROOT / "SOURCE_SHA256SUMS.txt"),
        "stdout_sha256": sha256_bytes(normalize_text(stdout).encode("utf-8")),
    }


# ---------------------------------------------------------------------------
# P2-90 whole-regression rerun capture
# ---------------------------------------------------------------------------
def run_p2_90_regression(python: str) -> None:
    capture_dir = EVIDENCE_DIR / P2_90_CAPTURE_REL
    capture_dir.mkdir(parents=True, exist_ok=True)
    frozen_dir = EVIDENCE_ROOT / "P2-90"
    snapshot = {rel: (frozen_dir / rel).read_bytes() for rel in P2_90_PRESERVED_FILES}
    completed = subprocess.run(
        [python, P2_90_GATE, "--evidence-dir", str(capture_dir)],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=21600,
    )
    stdout = normalize_text(completed.stdout or "")
    (EVIDENCE_DIR / P2_90_RUN_STDOUT).write_bytes(stdout.encode("utf-8"))
    fresh = {rel: (frozen_dir / rel).read_bytes() for rel in P2_90_PRESERVED_FILES}
    for rel in ("phase1_host_gates/stdout.txt", "source_integrity/stdout.txt"):
        (capture_dir / f"frozen_{rel.replace('/', '_')}").write_bytes(fresh[rel])
    for rel, data in snapshot.items():
        (frozen_dir / rel).write_bytes(data)
    restored = {rel: sha256_file(frozen_dir / rel) for rel in P2_90_PRESERVED_FILES}
    preservation = {
        "frozen_files": {
            rel: {
                "before_sha256": sha256_bytes(snapshot[rel]),
                "after_regression_sha256": sha256_bytes(fresh[rel]),
                "restored_sha256": restored[rel],
                "restored_byte_identical_to_before": restored[rel] == sha256_bytes(snapshot[rel]),
            }
            for rel in P2_90_PRESERVED_FILES
        },
        "returncode": completed.returncode,
        "stdout_lf_sha256": sha256_bytes(stdout.encode("utf-8")),
        "stderr_empty": not (completed.stderr or "").strip(),
    }
    (EVIDENCE_DIR / "p2_90_capture_preservation.json").write_bytes(
        (json.dumps(preservation, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    lines = [
        "P2-90 frozen capture preservation around the P2-91 regression rerun",
        "===================================================================",
    ]
    for rel in P2_90_PRESERVED_FILES:
        item = preservation["frozen_files"][rel]
        lines.append(f"{rel}: before={item['before_sha256'][:16]} regen={item['after_regression_sha256'][:16]} "
                     f"restored={item['restored_sha256'][:16]} byte_identical={item['restored_byte_identical_to_before']}")
    (EVIDENCE_DIR / "p2_90_capture_preservation.txt").write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    check("p2-90-rerun:executed", completed.returncode == 0)
    check("p2-90-rerun:preserved", all(
        item["restored_byte_identical_to_before"] for item in preservation["frozen_files"].values()))


def write_rerun_summary() -> None:
    stdout = normalize_text((EVIDENCE_DIR / P2_90_RUN_STDOUT).read_text(encoding="utf-8"))
    capture_dir = EVIDENCE_DIR / P2_90_CAPTURE_REL
    document = json.loads((capture_dir / "p2_90_tests.json").read_text(encoding="utf-8"))
    matrix = json.loads((capture_dir / "regression_matrix.json").read_text(encoding="utf-8"))
    preservation = json.loads((EVIDENCE_DIR / "p2_90_capture_preservation.json").read_text(encoding="utf-8"))
    frozen_capture = EVIDENCE_ROOT / P2_90_RECORDED_CAPTURE
    frozen_text = normalize_text(frozen_capture.read_text(encoding="utf-8"))
    summary = {
        "stage": p2_90.STAGE,
        "status": document.get("status"),
        "marker": "OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990",
        "audit_checks": document.get("passed"),
        "gates": len(matrix),
        "gate_checks": document.get("findings", {}).get("gate_matrix_summary", {}).get("gate_checks"),
        "stdout_content_sha256_lf": sha256_bytes(stdout.encode("utf-8")),
        "stdout_content_identical_to_frozen_capture": stdout == frozen_text,
        "p2_90_recorded_capture": P2_90_RECORDED_CAPTURE,
        "p2_90_recorded_capture_sha256": sha256_file(frozen_capture),
        "p2_90_recorded_capture_sha256_matches_record": (
            sha256_file(frozen_capture) == P2_90_RECORDED_STDOUT_SHA256),
        "frozen_captures_preserved": all(
            item.get("restored_byte_identical_to_before") is True
            for item in preservation.get("frozen_files", {}).values()
        ),
        "final_marker": f"{FINAL_MARKER}={FINAL_MARKER_VALUE}",
    }
    (EVIDENCE_DIR / "p2_90_rerun.json").write_bytes(
        (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )


def audit_p2_90_rerun_capture() -> None:
    stdout_path = EVIDENCE_DIR / P2_90_RUN_STDOUT
    check("p2-90-rerun:capture-exists", stdout_path.exists())
    stdout = normalize_text(stdout_path.read_text(encoding="utf-8"))
    check("p2-90-rerun:stage-marker", f"{p2_90.STAGE_MARKER}=PASS" in stdout)
    check("p2-90-rerun:gate-marker",
          "OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1=PASS tests=361 gates=22 gate_tests=1990" in stdout)
    check("p2-90-rerun:final-marker", f"{FINAL_MARKER}={FINAL_MARKER_VALUE}" in stdout)
    check("p2-90-rerun:no-failures", "FAIL:" not in stdout)
    lf_hash = sha256_bytes(stdout.encode("utf-8"))
    frozen_capture = EVIDENCE_ROOT / P2_90_RECORDED_CAPTURE
    frozen_text = normalize_text(frozen_capture.read_text(encoding="utf-8"))
    check("p2-90-rerun:stdout-content-identical", stdout == frozen_text)
    check("p2-90-rerun:stdout-hash", sha256_file(frozen_capture) == P2_90_RECORDED_STDOUT_SHA256)

    capture_dir = EVIDENCE_DIR / P2_90_CAPTURE_REL
    summary = json.loads((EVIDENCE_DIR / "p2_90_rerun.json").read_text(encoding="utf-8"))
    check("p2-90-rerun:summary-stage", summary.get("stage") == p2_90.STAGE)
    check("p2-90-rerun:summary-marker", summary.get("status") == "PASS")
    check("p2-90-rerun:summary-tests", summary.get("gate_checks") == 1990)
    check("p2-90-rerun:summary-gates", summary.get("gates") == 22)
    check("p2-90-rerun:summary-audit-checks", summary.get("audit_checks") == 361)
    check("p2-90-rerun:summary-stdout-hash", summary.get("stdout_content_sha256_lf") == lf_hash)
    check("p2-90-rerun:summary-content-match",
          summary.get("stdout_content_identical_to_frozen_capture") is True)
    check("p2-90-rerun:summary-recorded-capture-hash",
          summary.get("p2_90_recorded_capture_sha256") == P2_90_RECORDED_STDOUT_SHA256)
    check("p2-90-rerun:summary-frozen-preserved", summary.get("frozen_captures_preserved") is True)

    tests_json = capture_dir / "p2_90_tests.json"
    check("p2-90-rerun:tests-json-exists", tests_json.exists())
    document = json.loads(tests_json.read_text(encoding="utf-8"))
    check("p2-90-rerun:tests-json-pass",
          document.get("status") == "PASS" and document.get("passed") == 361 and document.get("failed") == 0)
    matrix_path = capture_dir / "regression_matrix.json"
    check("p2-90-rerun:matrix-exists", matrix_path.exists())
    matrix_doc = json.loads(matrix_path.read_text(encoding="utf-8"))
    check("p2-90-rerun:matrix-gates", len(matrix_doc) == 22)
    check("p2-90-rerun:matrix-all-pass",
          all("=PASS" in item.get("marker", "") for item in matrix_doc))

    preservation = json.loads((EVIDENCE_DIR / "p2_90_capture_preservation.json").read_text(encoding="utf-8"))
    check("p2-90-rerun:preservation-recorded",
          set(preservation.get("frozen_files", {})) == set(P2_90_PRESERVED_FILES))
    for rel, item in preservation["frozen_files"].items():
        check(f"p2-90-rerun:preserved-restored:{rel}",
              item.get("restored_byte_identical_to_before") is True)
        check(f"p2-90-rerun:currently-frozen:{rel}",
              sha256_file(EVIDENCE_ROOT / "P2-90" / rel) == item.get("before_sha256"))

    source_integrity_capture = capture_dir / "frozen_source_integrity_stdout.txt"
    check("p2-90-rerun:source-integrity-capture", source_integrity_capture.exists())
    entries = re.search(r"verified (\d+) manifest entries",
                        source_integrity_capture.read_text(encoding="utf-8", errors="replace"))
    manifest_lines = (ROOT / "SOURCE_SHA256SUMS.txt").read_text(encoding="utf-8").strip().splitlines()
    current_manifest = parse_manifest(manifest_lines)
    expected_live = (
        (int(entries.group(1)) if entries else -1)
        + (1 if P2_99_ADDED_MANIFEST_ENTRY in current_manifest else 0)
    )
    check("p2-90-rerun:source-integrity-count",
          entries is not None and len(manifest_lines) == expected_live)

    phase1_capture = capture_dir / "frozen_phase1_host_gates_stdout.txt"
    check("p2-90-rerun:phase1-capture", phase1_capture.exists())
    phase1_text = phase1_capture.read_text(encoding="utf-8", errors="replace")
    check("p2-90-rerun:phase1-counts",
          "OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2" in phase1_text)

    FINDINGS["p2_90_rerun"] = {
        "stdout_content_sha256_lf": lf_hash,
        "p2_90_recorded_capture_sha256": sha256_file(frozen_capture),
        "stdout_content_identical_to_frozen_capture": stdout == frozen_text,
        "audit_checks": summary.get("audit_checks"),
        "gates": summary.get("gates"),
        "gate_checks": summary.get("gate_checks"),
        "frozen_captures_preserved": summary.get("frozen_captures_preserved"),
    }


# ---------------------------------------------------------------------------
# Terminology / control-plane consistency audit
# ---------------------------------------------------------------------------
def audit_terminology() -> None:
    state = read_text(CONTROL_PLANE / "STATE.md")
    handoff = read_text(CONTROL_PLANE / "HANDOFF.md")
    queue = read_text(CONTROL_PLANE / "STAGE_QUEUE.md")

    for stage, _name, gate_marker, _tests in STAGES:
        if gate_marker == "n/a":
            check(f"terminology:state-ledger:{stage}",
                  re.search(rf"^\|\s*{re.escape(stage)}\s*\|[^|]*\|\s*`?PASS`?\s*\|", state, re.MULTILINE) is not None)
            continue
        check(f"terminology:state-gate-marker:{stage}", gate_marker in state or gate_marker.split(" tests=")[0] in state)
    p2_91_closed = ("OPENRECOMP_P2_91=PASS" in state and "OPENRECOMP_P2_91=PASS" in handoff
                    and "OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS" in state
                    and "OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1=PASS" in handoff)
    p2_91_active = (re.search(r"^CURRENT_STAGE=P2-91\s*$", state, re.MULTILINE) is not None
                    or re.search(r"^CURRENT_STAGE=P2-91\s*$", handoff, re.MULTILINE) is not None)
    check("terminology:p2-91-consistent", p2_91_closed or p2_91_active)
    for stage, _name, _gate_marker, _tests in STAGES:
        check(f"terminology:queue-{stage}",
              re.search(rf"^\|\s*{re.escape(stage)}\s*\|[^|]*\|\s*(COMPLETE|NEXT)\s*\|", queue, re.MULTILINE) is not None)
    check("terminology:queue-p2-91-and-p2-99",
          re.search(r"^\|\s*P2-91\s*\|[^|]*\|\s*(NEXT|COMPLETE)\s*\|", queue, re.MULTILINE) is not None
          and re.search(r"^\|\s*P2-99\s*\|[^|]*\|\s*(QUEUED|NEXT|COMPLETE)\s*\|", queue, re.MULTILINE) is not None)
    check("terminology:index-json-stage-names",
          all(item["name"].lower() in name.lower() or name.lower() in item["name"].lower()
              for (stage, name, _g, _t), item in zip(STAGES, FINDINGS["stage_index"])))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P2-91 Phase-2 evidence, limitations and final-claim closure")
    parser.add_argument("--evidence-dir", type=str, default=".openrecomp-phase2/evidence/P2-91")
    parser.add_argument("--json", type=str, default=None)
    parser.add_argument("--python", type=str, default=sys.executable)
    parser.add_argument("--run-regression", action="store_true",
                        help="execute the P2-90 whole-project regression rerun and refresh the capture")
    parser.add_argument("--skip-regression", action="store_true",
                        help="development flag: audit static closure artifacts only, never emit PASS")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []

    print("=== P2-91 Phase-2 Evidence, Limitations and Final-Claim Closure ===", flush=True)
    failure: str | None = None
    try:
        if args.run_regression:
            run_p2_90_regression(args.python)
        if not args.skip_regression:
            write_rerun_summary()
        audit_artifacts(require_capture=not args.skip_regression)
        audit_index()
        audit_limitations()
        audit_claim_matrix()
        audit_terminology()
        audit_premature_verdict()
        if not args.skip_regression:
            audit_p2_90_rerun_capture()
        audit_source_integrity(args.python)
        audit_legal()
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure is not None or failed else "PASS"
    if args.skip_regression:
        status = "SKIP"

    result = {
        "stage": STAGE,
        "stage_name": "OPENRECOMP_PHASE2_EVIDENCE_CLOSURE_V1",
        "marker": f"{FEATURE_MARKER}=PASS tests={passed}",
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "failure": failure,
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

    (EVIDENCE_DIR / "p2_91_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    (EVIDENCE_DIR / "legal_policy_audit.json").write_bytes(
        (json.dumps({
            "host_path_findings": FINDINGS["host_path_findings"],
            "legal_findings": FINDINGS["legal_findings"],
            "premature_verdict_findings": FINDINGS["premature_verdict_findings"],
        }, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    if args.json:
        pathlib.Path(args.json).write_bytes(
            (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )

    print("\n=== RESULT ===")
    if args.skip_regression:
        print(f"{STAGE_MARKER}=SKIP (development flag; regression capture not validated)")
        return 0
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{FINAL_MARKER}={authorized_final_verdict()}")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FINAL_MARKER}={authorized_final_verdict()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
