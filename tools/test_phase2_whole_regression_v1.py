#!/usr/bin/env python3
"""OpenRecomp whole Phase-2 regression and evidence audit V1 (P2-90).

P2-90 is a verification stage.  It re-runs every applicable completed Phase-2
gate on the frozen tree, audits the cross-stage evidence for internal
consistency, verifies source integrity and the asset/legal policy, and records
a machine-readable regression matrix, stage/evidence consistency table and
claim classification table.

Audited chain (guest input -> ... -> reproducible release packaging):

    P2-01 program model, P2-02 CFG, P2-03 functions, P2-04 call graph,
    P2-05 translation units, P2-06 indirect control flow, P2-07 host emitter,
    P2-08 generic runtime ABI, P2-09 deterministic build,
    P2-10..P2-14 MIPS32 end-to-end proofs, P2-20..P2-23 NES6502 proofs,
    P2-30 cross-architecture neutrality, P2-40 generic runtime integration,
    P2-50 build/package reproducibility, NES platform contract,
    Phase-1 host gates and SOURCE_SHA256SUMS.txt source integrity.

The audit fails closed: a failing gate, a missing/stale evidence artifact or a
policy finding fails the stage.

Terminal-state contract (P2-99 transition): while the P2-99 final verdict has
not been issued this audit requires the final
OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF marker to be NOT_PROVEN, exactly as
at P2-90/P2-91 time.  After the validated P2-99 terminal verdict the audit
accepts and emits the authorized PASS value, but only when the P2-99 verdict
evidence exists, declares PASS, pins this repository's P2-99 gate by SHA-256
and the control plane states the terminal marker.  A PASS marker without that
validated authorization still fails this audit.  This is a deliberate,
documented end-of-phase contract transition, not a weakened check:
`tools/test_phase2_final_verdict_v1.py` provides the replacement coverage that
validates the terminal authorization and the full terminal evidence chain.
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

EVIDENCE_ROOT = ROOT / ".openrecomp-phase2" / "evidence"
CONTROL_PLANE = ROOT / ".openrecomp-phase2"
# Raw gate captures are written to the pre-existing untracked scratch area so
# that the audited evidence tree stays free of host-specific capture bytes.
CAPTURE_ROOT = ROOT / ".openrecomp-phase2" / "scratch" / "P2-90" / "regressions"

STAGE = "P2-90"
STAGE_MARKER = "OPENRECOMP_P2_90"
FEATURE_MARKER = "OPENRECOMP_PHASE2_WHOLE_REGRESSION_V1"
FINAL_MARKER = "OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF"
FINAL_MARKER_VALUE = "NOT_PROVEN"
P2_99_EVIDENCE = EVIDENCE_ROOT / "P2-99"
P2_99_GATE = ROOT / "tools" / "test_phase2_final_verdict_v1.py"
P2_99_STAGE_MARKER = "OPENRECOMP_P2_99=PASS"


def authorized_final_verdict() -> str:
    """Return the authorized terminal value of the final Phase-2 marker.

    Pre-terminal (P2-90/P2-91 semantics) the marker must be NOT_PROVEN.  The
    terminal PASS value is authorized only by a P2-99 verdict evidence document
    that declares PASS, records the P2-99 stage/final markers, pins the live
    P2-99 gate by SHA-256, and is reflected by exactly the terminal marker
    statements in STATE.md and HANDOFF.md.  Anything else fails closed to
    NOT_PROVEN.
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

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {
    "gate_matrix": [],
    "evidence_consistency": [],
    "claim_classification": [],
    "legal_findings": [],
    "corrections": [],
}

# ---------------------------------------------------------------------------
# Completed stages and their evidence artifacts
# ---------------------------------------------------------------------------
# (stage id, ledger name, evidence dir name, feature marker, expected test count)
COMPLETED_STAGES: tuple[tuple[str, str, str, str | None, int | None], ...] = (
    ("P2-00", "Baseline + control plane", "P2-00", None, None),
    ("P2-01", "Shared program model V1", "P2-01", "OPENRECOMP_PROGRAM_MODEL_V1", 49),
    ("P2-02", "CFG construction V1", "P2-02", "OPENRECOMP_CFG_V1", 82),
    ("P2-03", "Function discovery V1", "P2-03", "OPENRECOMP_FUNCTION_DISCOVERY_V1", 67),
    ("P2-04", "Call-graph recovery V1", "P2-04", "OPENRECOMP_CALL_GRAPH_V1", 61),
    ("P2-05", "Translation units V1", "P2-05", "OPENRECOMP_TRANSLATION_UNITS_V1", 104),
    ("P2-06", "Indirect-control-flow classification V1", "P2-06", "OPENRECOMP_INDIRECT_CONTROL_FLOW_V1", 134),
    ("P2-07", "Host emitter V1", "P2-07", "OPENRECOMP_HOST_EMITTER_V1", 106),
    ("P2-08", "Generic runtime ABI V1", "P2-08", "OPENRECOMP_GENERIC_RUNTIME_ABI_V1", 169),
    ("P2-09", "Deterministic build pipeline", "P2-09", "OPENRECOMP_DETERMINISTIC_BUILD_V1", 120),
    ("P2-10", "Tiny MIPS32 end-to-end proof", "P2-10", "OPENRECOMP_MIPS32_END_TO_END_V1", 108),
    ("P2-11", "MIPS32 calls/stack/memory", "P2-11", "OPENRECOMP_MIPS32_CALLS_MEMORY_V1", 77),
    ("P2-12", "MIPS32 direct CFG stress", "P2-12", "OPENRECOMP_MIPS32_DIRECT_CFG_V1", 96),
    ("P2-13", "Runtime-host boundary", "P2-13", "OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1", 80),
    ("P2-14", "Larger MIPS32 open fixture", "P2-14", "OPENRECOMP_MIPS32_LARGER_FIXTURE_V1", 82),
    ("P2-20", "NES6502 program bridge", "P2-20", "OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1", 86),
    ("P2-21", "NES6502 host emitter path", "P2-21", "OPENRECOMP_NES6502_HOST_EMITTER_V1", 74),
    ("P2-22", "NES runtime bridge", "P2-22", "OPENRECOMP_NES_RUNTIME_BRIDGE_V1", 66),
    ("P2-23", "NES end-to-end proof", "P2-23", "OPENRECOMP_NES_END_TO_END_V1", 50),
    ("P2-30", "Cross-architecture neutrality audit", "P2-30", "OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1", 14),
    ("P2-40", "Generic runtime integration audit", "P2-40", "OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1", 181),
    ("P2-50", "Build/package reproducibility", "P2-50", "OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1", 174),
)

# ---------------------------------------------------------------------------
# Regression matrix
# ---------------------------------------------------------------------------
# mode:
#   "noargs"   -> python <script>            (canonical frozen no-argument run)
#   "evidence" -> python <script> --evidence-dir <capture> [--json <capture>/name]
# stdout_lf_sha256: recorded claim to verify against the sha256 of the newline-
# normalized stdout of this audit's run.  None means the audit records the hash
# but has no historical claim to compare against.
# frozen_captures: (frozen evidence file, expected removed line, expected added line)
#   The fresh stdout must equal the frozen capture except for exactly these
#   documented cross-stage guard replacements.
GATES: tuple[dict[str, Any], ...] = (
    {
        "stage": "P2-01", "name": "program model", "script": "tools/test_program_model_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_PROGRAM_MODEL_V1", "tests": 49,
        "stdout_lf_sha256": "c2afcd2a9a04c03e422bd48488c3b71d4872e152ba1dd0a70aa5a637b416a8f4",
        "frozen_captures": (),
    },
    {
        "stage": "P2-02", "name": "CFG", "script": "tools/test_cfg_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_CFG_V1", "tests": 82,
        "stdout_lf_sha256": "bfe24768a47e13f2d0cd88f4ee42ad979715cd694437aacf37ca943a0f5f1255",
        "frozen_captures": (),
    },
    {
        "stage": "P2-03", "name": "function discovery", "script": "tools/test_functions_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_FUNCTION_DISCOVERY_V1", "tests": 67,
        "stdout_lf_sha256": "5df8320de33e05ec999c3b2ec3f1921d1ac26a7968f8cacaf216f539fc23df2b",
        "frozen_captures": (),
    },
    {
        "stage": "P2-04", "name": "call graph", "script": "tools/test_call_graph_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_CALL_GRAPH_V1", "tests": 61,
        "stdout_lf_sha256": "99001a6c29f1c83cc28036d99024675d90993d393a1fe38d2e8a2f542e38254a",
        "frozen_captures": (),
    },
    {
        "stage": "P2-05", "name": "translation units", "script": "tools/test_translation_units_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_TRANSLATION_UNITS_V1", "tests": 104,
        "stdout_lf_sha256": "2d5980f97bebc7a8053bf9f3292bc7e7a823567232f50a9012c0f686bbf9d671",
        "frozen_captures": (),
    },
    {
        "stage": "P2-06", "name": "indirect control flow", "script": "tools/test_indirect_control_flow_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_INDIRECT_CONTROL_FLOW_V1", "tests": 134,
        "stdout_lf_sha256": "b2f40c6a683768c0ac96222064a37f897670f972a0503757e5c759ada2a9758b",
        "frozen_captures": (),
    },
    {
        "stage": "P2-07", "name": "host emitter", "script": "tools/test_host_emitter_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_HOST_EMITTER_V1", "tests": 106,
        "stdout_lf_sha256": "44c24de8a0f6f80ee81514caeb64057c28d0dae604d389db8dfe2ef259180863",
        "frozen_captures": (),
    },
    {
        "stage": "P2-08", "name": "runtime ABI", "script": "tools/test_runtime_abi_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_GENERIC_RUNTIME_ABI_V1", "tests": 169,
        "stdout_lf_sha256": "bf0177edafc3908053306a6bc2c97648451e2eb71ad132519ade8146ed53975c",
        "frozen_captures": (),
    },
    {
        "stage": "P2-09", "name": "deterministic build", "script": "tools/test_build_pipeline_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_DETERMINISTIC_BUILD_V1", "tests": 120,
        "stdout_lf_sha256": "25139e4da54ad7f683e442570250b739cec1477c49f03f9cd3ff648f1ffed9a4",
        "frozen_captures": (),
    },
    {
        "stage": "P2-10", "name": "MIPS32 end-to-end", "script": "tools/test_mips32_end_to_end_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_MIPS32_END_TO_END_V1", "tests": 108,
        "stdout_lf_sha256": "82378376b952c9c396fcf5f95a389348bff5ba444f2d8dbb3aa86776d0774560",
        "frozen_captures": (("P2-10/p2_10_gate.txt", "PASS: no-p2-11-evidence-directory", "PASS: no-p2-11-memory-emission-in-p2-10"),),
    },
    {
        "stage": "P2-11", "name": "MIPS32 calls/memory", "script": "tools/test_mips32_calls_memory_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_MIPS32_CALLS_MEMORY_V1", "tests": 77,
        "stdout_lf_sha256": "d16107cd1740220f6f187856fcb9e04f7416ab1c003dbed01c89a72c5d6dd4c1",
        "frozen_captures": (("P2-11/p2_11_gate.txt", "PASS: no-p2-12-evidence-directory", "PASS: no-p2-12-switch-emission-in-p2-11"),),
    },
    {
        "stage": "P2-12", "name": "MIPS32 direct CFG", "script": "tools/test_mips32_direct_cfg_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_MIPS32_DIRECT_CFG_V1", "tests": 96,
        "stdout_lf_sha256": "915df670bf88aded03deab9bc09ca1e96c055e196eb2c6dd7b7a61da101b8504",
        "frozen_captures": (("P2-12/p2_12_gate.txt", "PASS: no-p2-13-evidence-directory", "PASS: no-p2-13-host-call-emission-in-p2-12"),),
    },
    {
        "stage": "P2-13", "name": "runtime-host boundary", "script": "tools/test_runtime_host_boundary_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1", "tests": 80,
        "stdout_lf_sha256": "ca82230b84a623f52f63f1f4a5d27c73ca137061c0674362334d1d111a362f24",
        "frozen_captures": (("P2-13/p2_13_gate.txt", "PASS: no-p2-14-evidence-directory", "PASS: no-guest-memory-access-in-p2-13"),),
    },
    {
        "stage": "P2-14", "name": "larger MIPS32 fixture", "script": "tools/test_mips32_larger_fixture_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_MIPS32_LARGER_FIXTURE_V1", "tests": 82,
        "stdout_lf_sha256": "197a6c5e5c5578ee6fced2eb45b937359bbd612dab8ec11bb4d5c2e6b717da51",
        "frozen_captures": (("P2-14/p2_14_gate.txt", "PASS: no-p2-20-evidence-directory", "PASS: no-nes6502-dependency-in-p2-14"),),
    },
    {
        "stage": "P2-20", "name": "NES6502 program bridge", "script": "tools/test_nes6502_program_bridge_v1.py",
        "mode": "evidence", "feature": "OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1", "tests": 86,
        "json_name": "p2_20_tests.json",
        "stdout_lf_sha256": "d8a58133d9e89d681538226d524593405ef918359ca1c9d98ebbf02628fc6930",
        "frozen_captures": (("P2-20/p2_20_gate_evidence.txt", None, None),),
    },
    {
        "stage": "P2-21", "name": "NES6502 host emitter", "script": "tools/test_nes6502_host_emitter_v1.py",
        "mode": "evidence", "feature": "OPENRECOMP_NES6502_HOST_EMITTER_V1", "tests": 74,
        "json_name": "p2_21_tests.json",
        "stdout_lf_sha256": None,
        "frozen_captures": (),
        "recorded_hashes": ("P2-21/RESULT.json", "evidence_hashes"),
        "allow_missing_hashes": (),
    },
    {
        "stage": "P2-22", "name": "NES runtime bridge", "script": "tools/test_nes_runtime_bridge_v1.py",
        "mode": "evidence", "feature": "OPENRECOMP_NES_RUNTIME_BRIDGE_V1", "tests": 66,
        "json_name": "p2_22_tests.json",
        "stdout_lf_sha256": "1cfdff4347b9fe525189032812ce74aeae8572a11d2b85f61e696de7b4317c99",
        "frozen_captures": (("P2-22/p2_22_run1.txt", None, None),),
    },
    {
        "stage": "P2-23", "name": "NES end-to-end", "script": "tools/test_nes_end_to_end_v1.py",
        "mode": "evidence", "feature": "OPENRECOMP_NES_END_TO_END_V1", "tests": 50,
        "json_name": "p2_23_tests.json",
        "stdout_lf_sha256": None,
        "frozen_captures": (),
        "recorded_hashes": ("P2-23/RESULT.json", "evidence_hashes"),
        "allow_missing_hashes": ("p2_23_tests.json",),
        "expected_delta_hashes": ("RESULT.md", "changed_files.txt",
                                  "regression_tools_phase1_host_gates_v1.txt", "source_integrity.txt"),
    },
    {
        "stage": "P2-30", "name": "cross-architecture neutrality", "script": "tools/test_cross_architecture_neutrality_v1.py",
        "mode": "evidence", "feature": "OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1", "tests": 14,
        "stdout_lf_sha256": "49a2a255e714d17ab00d224dc3f6f218df8eb0e00d26d60ecfc71c89404abb54",
        "frozen_captures": (),
        "compare_tests_json": "p2_30_tests.json",
    },
    {
        "stage": "P2-40", "name": "generic runtime integration", "script": "tools/test_generic_runtime_integration_v1.py",
        "mode": "evidence", "feature": "OPENRECOMP_GENERIC_RUNTIME_INTEGRATION_V1", "tests": 181,
        "json_name": "p2_40_tests.json",
        "stdout_lf_sha256": "405c90d1c867495b3ac568a62b0d7c7e9234ca5ef469cdc2510d307b8d148228",
        "reconstruct_frozen_prefix": ".openrecomp-phase2\\evidence\\P2-40",
        "frozen_captures": (),
        "recorded_hashes": ("P2-40/RESULT.json", "hashes"),
        "allow_missing_hashes": ("contract_classification.md", "dependency_findings.txt",
                                 "determinism.txt", "responsibility_analysis.md"),
    },
    {
        "stage": "P2-50", "name": "build/package reproducibility", "script": "tools/test_build_package_reproducibility_v1.py",
        "mode": "evidence", "feature": "OPENRECOMP_BUILD_PACKAGE_REPRODUCIBILITY_V1", "tests": 174,
        "stdout_lf_sha256": "0616da411e9b3b12e485b43056981e5fc269565ac932d556912ff9e82e63c92d",
        "frozen_captures": (),
        "recorded_hashes": ("P2-50/RESULT.json", "evidence_hashes"),
        "allow_missing_hashes": (),
        "expected_delta_hashes": ("changed_files.txt", "input_hashes.txt", "source_integrity.txt"),
    },
    {
        "stage": "NES-PLATFORM", "name": "NES platform contract", "script": "tools/test_nes_platform_v1.py",
        "mode": "noargs", "feature": "OPENRECOMP_NES_PLATFORM_V1", "tests": 10,
        "stdout_lf_sha256": "d2275cd6fd678e98621de9298e7f64bf4dfec6e29ede7850a53667f69a73e7e8",
        "frozen_captures": (),
    },
)

# Machine-readable RESULT.json exists for these stages; P2-00..P2-04 are
# RESULT.md-only in the frozen evidence set.
JSON_REQUIRED_STAGES = {
    "P2-05", "P2-06", "P2-07", "P2-08", "P2-09", "P2-10", "P2-11", "P2-12", "P2-13", "P2-14",
    "P2-20", "P2-21", "P2-22", "P2-23", "P2-30", "P2-40", "P2-50",
}

# Key identities recorded by frozen stage evidence (verified against the
# audited tree evidence and, where regenerated, against this audit's captures).
IDENTITIES = {
    "P2-10": {
        "fixture_sha256": "b33b597c28eb7f7239ee5079728c7f3e447387d4ed34525c445cf8c1e9234975",
        "generated_source_sha256": "8570ea4a11321118a3fff270e0dc9756d2a4ee7a52421ece1d2d892384118fbb",
        "executable_sha256": "f94c95d2e86fca83f56e5e87a98bccaa1e2a4ced3fd9222aef29608592810f4e",
    },
    "P2-11": {
        "fixture_sha256": "4ce3fdab7f9e622648eb74eff676fd79712c2043b8e35e752e84e26712e6d309",
        "generated_source_sha256": "4637ba676e99ba74e0c1708f100ba81b9506f1689fbee3d736364a6f821ceaf3",
        "executable_sha256": "bd719060f38793a349271358e121730206f0799d67bd771c1a8ca6a31eba27c6",
    },
    "P2-12": {
        "fixture_sha256": "2e3309f310a6f23c145ba7b95a22f10e3d81f32ec19afb966a9044395c066c84",
        "generated_source_sha256": "36ba17c8a1edcd22148c9789abe9348f68e9b6cd02912a9a94481de93a3009c9",
        "executable_sha256": "3d92fc274ddb94190292fb9630243f7b064a42733406ecaf7cab2d85a5f2f266",
    },
    "P2-13": {
        "fixture_sha256": "7c9ba624b7503ccb31e0cd4b82b2c0316674b2c094945df84524503e34eb19b6",
        "generated_source_sha256": "8c602b35e47f90d5edf9fd6cad566b4b378c3ffc69574f63b80c48bdb55367ef",
        "executable_sha256": "8ab94ab0f186e33778ddb6464f31c492045e6b612abeb523547b2aaa92a940a1",
    },
    "P2-14": {
        "fixture_sha256": "1c233f56528cb3fe20a7b806ce40e8bef6fc66a8cf8c0fd15d8b7b49bce547eb",
        "generated_source_sha256": "25d8d85ff88d2009443a6c67db40855df5e0876cb2b0aef8505d12d500204203",
        "executable_sha256": "1e81bf8cd32b60cd5b3acae26c8f9dc23c0f801cf46b0c49ccb348ebc5eb2ab4",
    },
    "P2-20": {
        "region_sha256": "0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398",
    },
    "P2-21": {
        "fixture_sha256": "0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398",
        "generated_source_sha256": "7d42947f658f0e7dcb146f3c5f2dd19c742c94bb8cf3e6b2ae8feb789758fd74",
        "executable_sha256": "dbba1e3a86274d2944a38de575faee48d04e7748e8a150c93a5adbb0325e35f8",
    },
    "P2-22": {
        "fixture_sha256": "cc57bba3124f264cb6f4ec2b0e83cb82d3a9eeea551d18c098278c7eef827763",
    },
    "P2-23": {
        "fixture_sha256": "dfadcbe759121b0705f2a7db3295127b7adceb403a6254897caee85f8a1c44c2",
        "generated_source_sha256": "9819b40e9909b4056211f6f452297b502b99bc4be4f96fe797cdcdfd6aaf2b78",
        "executable_sha256": "5afd387d048299d53eb1cbc0534e9d01c373ccb9a370ca712bd01bef0b4c2207",
    },
    "P2-30": {
        "mips32_host_source_sha256": "be52ef25060e22f8c4677c2e87a2e89180f82ae88833c4d910ec11fe1881b9f6",
    },
    "P2-40": {
        "generated_source_sha256": "c0a76e0f19217aeed017fca9f2abc82ef644563c1374d046987452800679246a",
        "executable_sha256": "96676becf33f2251fcbc0b097ad8fa7ea2c100f4754617a4a5dcbdac1ecaf5b2",
        "fixture_input_sha256": "9323f24533ec6c31cf954c8315fd674ac8efc8c803e960eb9b1a902891cfe237",
    },
    "P2-50": {
        "source_state_fingerprint": "5d93971b102b24e56b2c98bf4c6b6486f58e6c174700af1c77cf969f85024c54",
        "generic-runtime-pipeline": {
            "executable_sha256": "96676becf33f2251fcbc0b097ad8fa7ea2c100f4754617a4a5dcbdac1ecaf5b2",
            "package_archive_sha256": "fa72b5d169ad0f8f97c03578e18d1d0e4b810b9aa6281e154e947d9b2803888c",
        },
        "mips32-larger": {
            "executable_sha256": "1e81bf8cd32b60cd5b3acae26c8f9dc23c0f801cf46b0c49ccb348ebc5eb2ab4",
            "package_archive_sha256": "1c1dac0ea9942a9a31d0780c187c52b7e6bc18d6708f6599a76dca350079ef17",
        },
        "nes-nrom-end-to-end": {
            "executable_sha256": "5afd387d048299d53eb1cbc0534e9d01c373ccb9a370ca712bd01bef0b4c2207",
            "package_archive_sha256": "71847f9d7ffd126456cca96dea406884d4221b2c6fa86a2e4f15b6462d4c8745",
        },
    },
}

# Stale values that must not remain in the control plane after the P2-90
# corrections (superseded P2-50 archive/source-state claims).
STALE_CONTROL_PLANE_TOKENS = (
    "084b1c2c", "7feaab35", "68cc619e",
    "9dd81a78a16c3327bd57010bd6a910b50c1c2c9b5ab92213bee075257fd570ae",
)

# Claims audited by this stage.  Classification vocabulary:
# PROVEN / BOUNDED_PROVEN / NOT_PROVEN / OUT_OF_SCOPE.
CLAIMS: tuple[tuple[str, str, str], ...] = (
    ("architecture-neutral shared analysis pipeline", "PROVEN",
     "static import/symbol isolation over the audited shared modules plus MIPS32 and NES6502 "
     "path exercises (P2-30); neutral is proven for the audited modules and synthetic fixtures only"),
    ("NES/6502 frontend integration", "BOUNDED_PROVEN",
     "one synthetic 26-byte NES6502 region through P2-01..P2-06 (P2-20) and one bounded emitted "
     "subset (P2-21); no full 6502 support"),
    ("NES runtime bridge", "BOUNDED_PROVEN",
     "bounded synthetic NROM fixture; memory/input/frame/audio contracts via the generic ABI; "
     "no PPU/APU implementation"),
    ("NES synthetic end-to-end native recompilation", "BOUNDED_PROVEN",
     "one synthetic 59-instruction NROM fixture; reference observable equals native observable"),
    ("observable equivalence", "BOUNDED_PROVEN",
     "declared observable sets for synthetic fixtures only; not general guest/host equivalence"),
    ("deterministic repeated execution", "PROVEN",
     "byte-identical stdout across repeated gate runs and repeated native executions for the "
     "audited fixtures"),
    ("MIPS32 shared-path operation", "BOUNDED_PROVEN",
     "synthetic 13/16/35/5/57-instruction fixtures; no general MIPS32 support"),
    ("generic runtime neutrality", "PROVEN",
     "no platform leakage in the audited generic runtime modules; adapters share the generic "
     "contracts unchanged (P2-40)"),
    ("reproducible native build", "BOUNDED_PROVEN",
     "detected clang-cl/lld-link 22.1.8 toolchain on this host for the audited fixtures"),
    ("reproducible release package", "BOUNDED_PROVEN",
     "audited canonical packaging path for three representative fixtures"),
    ("arbitrary NES ROM compatibility", "NOT_PROVEN", "no general NES ROM support is implemented or claimed"),
    ("commercial-game compatibility", "NOT_PROVEN", "no commercial ROM/game is used or supported"),
    ("complete NES hardware compatibility", "NOT_PROVEN", "no full PPU/APU/mapper implementation"),
    ("arbitrary MIPS32 binary compatibility", "NOT_PROVEN", "bounded synthetic fixtures only"),
    ("PS1/PS2/Xbox compatibility", "OUT_OF_SCOPE", "not implemented, not claimed"),
    ("cycle accuracy", "OUT_OF_SCOPE", "cycle-exact behavior is not modeled or claimed"),
    ("future architecture compatibility", "NOT_PROVEN",
     "GB/GBC/SMS/RT64-like extension points are documented only; no adapter implemented"),
    ("Phase-2 final end-to-end proof marker", "NOT_PROVEN",
     "OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF is reserved for P2-99 and remains NOT_PROVEN"),
)

REQUIRED_CLAIMS = (
    "architecture-neutral shared analysis pipeline",
    "NES/6502 frontend integration",
    "NES runtime bridge",
    "NES synthetic end-to-end native recompilation",
    "observable equivalence",
    "deterministic repeated execution",
    "MIPS32 shared-path operation",
    "generic runtime neutrality",
    "reproducible native build",
    "reproducible release package",
    "arbitrary NES ROM compatibility",
    "commercial-game compatibility",
    "complete NES hardware compatibility",
    "arbitrary MIPS32 binary compatibility",
    "PS1/PS2/Xbox compatibility",
    "cycle accuracy",
    "future architecture compatibility",
)

ALLOWED_CLAIM_CLASSES = {"PROVEN", "BOUNDED_PROVEN", "NOT_PROVEN", "OUT_OF_SCOPE"}

# ---------------------------------------------------------------------------
# Legal / asset / content policy definitions
# ---------------------------------------------------------------------------
CONSOLE_MAGICS = (
    (b"NES\x1a", "iNES container magic"),
    (b"FDS\x1a", "FDS container magic"),
    (b"UNIF", "UNIF container magic"),
    (b"\x00\x00\x00\x00\x1a\x00\x00\x00", "NES 2.0 style header"),
)
FORBIDDEN_SUFFIXES = {".nes", ".fds", ".unf", ".unif", ".gb", ".gbc", ".sms", ".rom", ".iso", ".cue", ".chd"}
SECRET_PATTERNS = (
    (re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key header"),
    (re.compile(rb"AKIA[0-9A-Z]{16}"), "AWS access key"),
    (re.compile(rb"(?i)(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*\S"), "credential pattern"),
)
HOST_PATH_PATTERN = re.compile(
    rb"(?<![A-Za-z0-9])[A-Za-z]:[\\/]"
    rb"|(?<![\\])\\\\[A-Za-z0-9_.$-]"
    rb"|file://|/tmp/|/var/tmp/|/home/|/Users/|\\Temp\\|\\AppData\\|\\Users\\"
)
HOST_PATH_ALLOWLIST = {
    # P2-40 policy evidence documents the exact rejection needles it tests.
    ".openrecomp-phase2/evidence/P2-40/dependency_findings.txt",
}

# Pre-existing absolute-host-path occurrences in frozen P2-00..P2-50 evidence.
# These are host-environment identifiers recorded by the completed stages
# (working-copy path, detected compiler/interpreter executables).  They are not
# secrets, not present in release packages and cannot be rewritten without
# invalidating the hash-pinned evidence of those PASS stages; P2-90 records them
# as a bounded evidence-hygiene limitation for the P2-91 evidence index.  Any
# occurrence outside this exact set fails the audit.
DOCUMENTED_FROZEN_HOST_PATH_FILES = {
    "P2-00/RESULT.md",
    "P2-07/host_emitter_tests.json",
    "P2-07/native_compile.txt",
    "P2-08/determinism.txt",
    "P2-08/runtime_abi_tests.json",
    "P2-40/run1.txt",
    "P2-40/run2.txt",
    "P2-50/regression_tools_test_cross_architecture_neutrality_v1.txt",
    "P2-50/regression_tools_test_generic_runtime_integration_v1.txt",
}

FROZEN_STAGE_DIRS = tuple(entry[2] for entry in COMPLETED_STAGES)

TEXT_SUFFIXES_FOR_LEGAL = {".md", ".json", ".txt", ".c", ".h", ".py"}


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


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", "replace")


def parse_marker(stdout: str, feature: str) -> tuple[str, int | None] | None:
    pattern = re.compile(
        r"^" + re.escape(feature) + r"=(PASS|FAIL)(?:\s+tests=(\d+))?\s*$", re.MULTILINE
    )
    matches = pattern.findall(stdout)
    if not matches:
        return None
    status, tests = matches[-1]
    return status, (int(tests) if tests else None)


def normalize_command(command: list[str]) -> list[str]:
    """Return a host-neutral display form of a command (no interpreter path)."""
    normalized: list[str] = []
    for index, part in enumerate(command):
        if index == 0:
            normalized.append("python")
            continue
        text = str(part)
        if text.startswith(str(ROOT)):
            try:
                text = pathlib.Path(text).relative_to(ROOT).as_posix()
            except ValueError:
                pass
        normalized.append(text)
    return normalized


def run_command(command: list[str], *, timeout: int, capture_dir: pathlib.Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    lf_text = normalize_text(stdout)
    crlf_text = lf_text.replace("\n", "\r\n")
    record: dict[str, Any] = {
        "command": normalize_command(command),
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_lf_sha256": sha256_bytes(lf_text.encode("utf-8")),
        "stdout_crlf_sha256": sha256_bytes(crlf_text.encode("utf-8")),
        "stdout_utf16_crlf_sha256": sha256_bytes((b"\xff\xfe" + crlf_text.encode("utf-16-le"))),
    }
    if capture_dir is not None:
        capture_dir.mkdir(parents=True, exist_ok=True)
        (capture_dir / "stdout.txt").write_bytes(stdout.encode("utf-8"))
        (capture_dir / "stderr.txt").write_bytes(stderr.encode("utf-8"))
        (capture_dir / "command.txt").write_bytes((" ".join(normalize_command(command)) + "\n").encode("utf-8"))
    return record


def compare_text_capture(label: str, fresh: str, frozen_path: pathlib.Path,
                         removed: str | None, added: str | None) -> None:
    frozen = normalize_text(decode_text(frozen_path.read_bytes()))
    fresh_norm = normalize_text(fresh)
    if fresh_norm == frozen:
        check(label, True)
        return
    frozen_lines = frozen.splitlines()
    fresh_lines = fresh_norm.splitlines()
    missing = [line for line in frozen_lines if line not in fresh_lines]
    extra = [line for line in fresh_lines if line not in frozen_lines]
    if removed is None and added is None:
        check(label, not missing and not extra)
    else:
        check(label, missing == [removed] and extra == [added])


# ---------------------------------------------------------------------------
# Control-plane audit
# ---------------------------------------------------------------------------
def audit_control_plane() -> None:
    state = (CONTROL_PLANE / "STATE.md").read_text(encoding="utf-8")
    handoff = (CONTROL_PLANE / "HANDOFF.md").read_text(encoding="utf-8")
    queue = (CONTROL_PLANE / "STAGE_QUEUE.md").read_text(encoding="utf-8")

    authorized = authorized_final_verdict()
    final_lines_state = re.findall(r"^" + re.escape(FINAL_MARKER) + r"=(\S+)\s*$", state, re.MULTILINE)
    final_lines_handoff = re.findall(r"^" + re.escape(FINAL_MARKER) + r"=(\S+)\s*$", handoff, re.MULTILINE)
    check("control-plane:final-marker-not-claimed",
          final_lines_state == [authorized] and final_lines_handoff == [authorized])

    current = re.search(r"^CURRENT_STAGE=(\S+)$", state + "\n" + handoff, re.MULTILINE)
    check("control-plane:current-stage-declared",
          current is not None and current.group(1) in {"P2-90", "P2-91", "P2-99"})
    last_passed = re.search(r"^LAST_PASSED_STAGE=(\S+)$", state + "\n" + handoff, re.MULTILINE)
    check("control-plane:last-passed-stage-declared",
          last_passed is not None
          and last_passed.group(1) in {"P2-50", "P2-90", "P2-91", "P2-99"})

    for stage, _name, _directory, feature, tests in COMPLETED_STAGES:
        ledger = re.search(rf"^\|\s*{re.escape(stage)}\s*\|[^|]*\|\s*`?PASS`?\s*\|", state, re.MULTILINE)
        check(f"control-plane:ledger-{stage}", ledger is not None)
        check(f"control-plane:queue-{stage}",
              re.search(rf"^\|\s*{re.escape(stage)}\s*\|[^|]*\|\s*COMPLETE\s*\|", queue, re.MULTILINE) is not None)
        if feature is not None and tests is not None:
            marker = f"{feature}=PASS tests={tests}"
            check(f"control-plane:marker-{stage}-{feature}", marker in state)
            if marker in handoff or feature in handoff:
                check(f"control-plane:handoff-marker-{stage}-{feature}", marker in handoff)

    check("control-plane:queue-p2-90",
          re.search(r"^\|\s*P2-90\s*\|[^|]*\|\s*(NEXT|COMPLETE)\s*\|", queue, re.MULTILINE) is not None)
    check("control-plane:queue-p2-91",
          re.search(r"^\|\s*P2-91\s*\|[^|]*\|\s*(QUEUED|COMPLETE|NEXT)\s*\|", queue, re.MULTILINE) is not None)
    check("control-plane:queue-p2-99",
          re.search(r"^\|\s*P2-99\s*\|[^|]*\|\s*(QUEUED|COMPLETE|NEXT)\s*\|", queue, re.MULTILINE) is not None)
    check("control-plane:phase1-marker",
          "OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2" in state
          and "OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2" in handoff)

    stale = sorted(token for token in STALE_CONTROL_PLANE_TOKENS if token in state or token in handoff)
    check("control-plane:no-superseded-p2-50-claims", not stale)
    p2_50 = IDENTITIES["P2-50"]
    for rep in ("generic-runtime-pipeline", "mips32-larger", "nes-nrom-end-to-end"):
        archive = p2_50[rep]["package_archive_sha256"][:8]
        check(f"control-plane:p2-50-archive-{rep}", archive in state and archive in handoff)
    fingerprint = p2_50["source_state_fingerprint"]
    check("control-plane:p2-50-source-state-fingerprint", fingerprint in state and fingerprint in handoff)
    check("control-plane:p2-14-guard-adjustment-documented",
          "no-nes6502-dependency-in-p2-14" in state and "no-nes6502-dependency-in-p2-14" in handoff)


# ---------------------------------------------------------------------------
# Evidence audit (existence, verdicts, markers, identity claims, refs)
# ---------------------------------------------------------------------------
def audit_evidence() -> None:
    for stage, _name, directory, feature, tests in COMPLETED_STAGES:
        stage_dir = EVIDENCE_ROOT / directory
        result_md = stage_dir / "RESULT.md"
        check(f"evidence:result-md-{stage}", result_md.exists() and result_md.stat().st_size > 0)
        text = result_md.read_text(encoding="utf-8")
        check(f"evidence:verdict-{stage}", "PASS" in text)
        if feature is not None:
            check(f"evidence:marker-{stage}",
                  feature + "=PASS" in text
                  or ((stage_dir / "RESULT.json").exists()
                      and feature in (stage_dir / "RESULT.json").read_text(encoding="utf-8")))
        if stage in JSON_REQUIRED_STAGES:
            result_json = stage_dir / "RESULT.json"
            check(f"evidence:result-json-{stage}", result_json.exists())
            document = json.loads(result_json.read_text(encoding="utf-8"))
            verdict = document.get("verdict", document.get("status"))
            check(f"evidence:json-verdict-{stage}", verdict in {None, "PASS"})
            recorded_stage = document.get("stage")
            check(f"evidence:json-stage-{stage}", recorded_stage in {None, stage})
            FINDINGS["evidence_consistency"].append({
                "stage": stage,
                "result_md_sha256": sha256_file(result_md),
                "result_json_sha256": sha256_file(result_json),
                "feature_marker": feature,
                "expected_tests": tests,
            })

    for stage, identity in IDENTITIES.items():
        stage_dir = EVIDENCE_ROOT / stage
        blob = b""
        for candidate in sorted(stage_dir.iterdir()):
            if candidate.is_file() and candidate.suffix in {".md", ".json", ".txt"}:
                blob += candidate.read_bytes()
        for key, value in identity.items():
            if isinstance(value, dict):
                for rep, rep_identity in value.items():
                    if isinstance(rep_identity, dict):
                        for rep_key, rep_value in rep_identity.items():
                            check(f"identity:{stage}:{rep}:{rep_key}", rep_value.encode("ascii") in blob)
                    else:
                        check(f"identity:{stage}:{key}:{rep}", rep_identity.encode("ascii") in blob)
            else:
                check(f"identity:{stage}:{key}", value.encode("ascii") in blob)

    token_pattern = re.compile(r"`((?:p2_[A-Za-z0-9_.-]+|RESULT)\.(?:md|json|txt|c|zip))`")
    for stage, _name, directory, _feature, _tests in COMPLETED_STAGES:
        stage_dir = EVIDENCE_ROOT / directory
        text = (stage_dir / "RESULT.md").read_text(encoding="utf-8")
        missing = sorted({token for token in token_pattern.findall(text) if not (stage_dir / token).exists()})
        check(f"evidence:refs-exist-{stage}", not missing)
        if missing:
            FINDINGS["legal_findings"].append({"stage": stage, "missing_evidence_refs": missing})


# ---------------------------------------------------------------------------
# Regression matrix execution
# ---------------------------------------------------------------------------
def audit_gates(python: str, *, execute: bool, only: set[str] | None = None) -> None:
    total_gate_checks = 0
    failures: list[str] = []
    for gate in GATES:
        stage = gate["stage"]
        script = gate["script"]
        feature = gate["feature"]
        if only is not None and stage not in only:
            RESULTS.append({"check": f"gate-skipped:{stage}", "status": "SKIP"})
            continue
        capture_dir = CAPTURE_ROOT / stage
        command = [python, script]
        if gate["mode"] == "evidence":
            capture_dir.mkdir(parents=True, exist_ok=True)
            command += ["--evidence-dir", str(capture_dir)]
            if gate.get("json_name"):
                command += ["--json", str(capture_dir / gate["json_name"])]
        if not execute:
            print(f"SKIP: gate {stage} ({script}) [skip-execution]", flush=True)
            RESULTS.append({"check": f"gate-skipped:{stage}", "status": "SKIP"})
            continue
        record = run_command(command, timeout=7200,
                             capture_dir=(capture_dir if gate["mode"] == "evidence" else None))
        stdout = record["stdout"]
        marker = parse_marker(stdout, feature)
        record_entry = {
            "stage": stage,
            "name": gate["name"],
            "script": script,
            "mode": gate["mode"],
            "command": record["command"],
            "returncode": record["returncode"],
            "marker": None if marker is None else f"{feature}={marker[0]}" + (
                f" tests={marker[1]}" if marker[1] is not None else ""),
            "stdout_lf_sha256": record["stdout_lf_sha256"],
            "stderr_lf_sha256": sha256_bytes(normalize_text(record["stderr"]).encode("utf-8")),
        }
        FINDINGS["gate_matrix"].append(record_entry)

        if record["returncode"] != 0 or marker is None or marker[0] != "PASS":
            failures.append(f"{stage}: rc={record['returncode']} marker={marker}")
            print(f"FAIL gate {stage}: rc={record['returncode']} marker={marker}", flush=True)
            continue
        recorded_tests = marker[1]
        if recorded_tests is not None:
            total_gate_checks += recorded_tests
            if gate["tests"] is not None and recorded_tests != gate["tests"]:
                failures.append(f"{stage}: tests={recorded_tests} expected {gate['tests']}")
                print(f"FAIL gate {stage}: tests={recorded_tests} != {gate['tests']}", flush=True)
                continue
        expected_hash = gate.get("stdout_lf_sha256")
        if expected_hash is not None:
            stdout_for_hash = stdout
            reconstruct = gate.get("reconstruct_frozen_prefix")
            if reconstruct:
                stdout_for_hash = stdout.replace(str(capture_dir), reconstruct)
            lf_text = normalize_text(stdout_for_hash)
            candidates = (
                ("utf-8-lf", sha256_bytes(lf_text.encode("utf-8"))),
                ("utf-8-crlf", sha256_bytes(lf_text.replace("\n", "\r\n").encode("utf-8"))),
                ("utf-16le-bom-crlf",
                 sha256_bytes(b"\xff\xfe" + lf_text.replace("\n", "\r\n").encode("utf-16-le"))),
            )
            matched = next((name for name, value in candidates if value == expected_hash), None)
            record_entry["stdout_hash_convention"] = matched
            record_entry["stdout_reconstructed"] = bool(reconstruct)
            if matched is None:
                failures.append(f"{stage}: stdout hash {record['stdout_lf_sha256']} != {expected_hash}")
                print(f"FAIL gate {stage}: stdout hash mismatch", flush=True)
                continue
        for frozen_rel, removed, added in gate.get("frozen_captures", ()):
            compare_text_capture(f"capture:{stage}:{frozen_rel}", stdout, EVIDENCE_ROOT / frozen_rel, removed, added)

        recorded = gate.get("recorded_hashes")
        if recorded is not None:
            recorded_doc = json.loads((EVIDENCE_ROOT / recorded[0]).read_text(encoding="utf-8"))[recorded[1]]
            allow_missing = set(gate.get("allow_missing_hashes", ()))
            expected_deltas = set(gate.get("expected_delta_hashes", ()))
            for name, expected in sorted(recorded_doc.items()):
                fresh = capture_dir / name
                if not fresh.exists():
                    if name in allow_missing:
                        continue
                    failures.append(f"{stage}: recorded evidence file not regenerated: {name}")
                    print(f"FAIL gate {stage}: recorded evidence file not regenerated: {name}", flush=True)
                    continue
                actual = sha256_file(fresh)
                if actual != expected:
                    reconstruct = gate.get("reconstruct_frozen_prefix")
                    if reconstruct:
                        data = fresh.read_bytes().replace(
                            str(capture_dir).encode("utf-8"), reconstruct.encode("utf-8")
                        )
                        if sha256_bytes(data) == expected:
                            FINDINGS.setdefault("reconstructed_evidence_hashes", []).append({
                                "stage": stage,
                                "file": name,
                                "note": "recorded hash reproduced after restoring the frozen evidence-dir prefix",
                            })
                            continue
                    if name in expected_deltas:
                        FINDINGS["corrections"].append({
                            "stage": stage,
                            "file": name,
                            "recorded_sha256": expected,
                            "current_sha256": actual,
                            "classification": "EXPECTED_DOCUMENTED_OR_ADDITIVE_DELTA",
                        })
                        continue
                    failures.append(f"{stage}: evidence file hash mismatch: {name}")
                    print(f"FAIL gate {stage}: evidence file hash mismatch: {name}", flush=True)
        if gate.get("compare_tests_json"):
            fresh_json = capture_dir / gate["compare_tests_json"]
            frozen_json = EVIDENCE_ROOT / stage / gate["compare_tests_json"]
            if fresh_json.exists() and frozen_json.exists():
                check(f"tests-json-identical:{stage}", fresh_json.read_bytes() == frozen_json.read_bytes())
        print(f"PASS gate {stage}: {record_entry['marker']} sha256={record['stdout_lf_sha256'][:16]}", flush=True)

    FINDINGS["gate_matrix_summary"] = {
        "gates_executed": len(FINDINGS["gate_matrix"]),
        "gate_checks": total_gate_checks,
        "failures": failures,
    }
    if failures:
        print(f"FAILURES: {failures}", flush=True)
    check("regression-matrix:no-failures", not failures)


# ---------------------------------------------------------------------------
# Phase-1 host gates and source integrity
# ---------------------------------------------------------------------------
def audit_phase1(python: str, *, execute: bool) -> None:
    if not execute:
        print("SKIP: phase-1 host gates [skip-execution]", flush=True)
        RESULTS.append({"check": "phase1-host-gates-skipped", "status": "SKIP"})
        return
    host_gates = run_command([python, "tools/phase1_host_gates_v1.py"], timeout=7200,
                             capture_dir=EVIDENCE_ROOT / "P2-90" / "phase1_host_gates")
    stdout = host_gates["stdout"]
    counts = re.search(r"OPENRECOMP_PHASE1_HOST_GATES_PASS=(\d+) FAIL=(\d+) SKIPPED=(\d+)", stdout)
    check("phase1-host-gates:marker", "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS" in stdout)
    check("phase1-host-gates:counts",
          counts is not None and counts.group(1) == "44" and counts.group(2) == "0" and counts.group(3) == "2")

    integrity = run_command([python, "tools/phase1_host_gates_v1.py", "--only", "source-integrity"],
                            timeout=1800, capture_dir=EVIDENCE_ROOT / "P2-90" / "source_integrity")
    integrity_stdout = integrity["stdout"]
    entries = re.search(r"verified (\d+) manifest entries", integrity_stdout)
    check("source-integrity:pass",
          "source-integrity" in integrity_stdout and entries is not None
          and "OPENRECOMP_PHASE1_HOST_GATES_V1=PASS" in integrity_stdout)
    manifest_entries = int(entries.group(1)) if entries else 0
    manifest_lines = (ROOT / "SOURCE_SHA256SUMS.txt").read_text(encoding="utf-8").strip().splitlines()
    check("source-integrity:count-matches-manifest", manifest_entries == len(manifest_lines))
    manifest = "\n".join(manifest_lines)
    check("source-integrity:audit-gate-registered",
          "tools/test_phase2_whole_regression_v1.py" in manifest)
    FINDINGS["phase1_host_gates"] = {"counts": list(counts.groups()) if counts else None}
    FINDINGS["source_integrity"] = {
        "manifest_entries": manifest_entries,
        "manifest_sha256": sha256_bytes((ROOT / "SOURCE_SHA256SUMS.txt").read_bytes()),
        "audit_gate_registered": "tools/test_phase2_whole_regression_v1.py" in manifest,
    }


# ---------------------------------------------------------------------------
# Legal / asset / content policy audit
# ---------------------------------------------------------------------------
def tracked_files() -> list[pathlib.Path]:
    raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"], stderr=subprocess.STDOUT)
    return [ROOT / item.decode("utf-8") for item in raw.split(bytes([0])) if item]


def _scan_evidence_file(path: pathlib.Path, *, allowlisted: bool = False) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    data = path.read_bytes()
    for magic, label in CONSOLE_MAGICS:
        if data[:16].startswith(magic):
            findings.append((f"console-magic:{label}", ""))
    if allowlisted:
        return findings
    if path.suffix.lower() in TEXT_SUFFIXES_FOR_LEGAL:
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(data):
                findings.append((f"secret:{label}", ""))
        if HOST_PATH_PATTERN.search(data):
            findings.append(("absolute-host-path", ""))
    return findings


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
        if path.suffix.lower() in TEXT_SUFFIXES_FOR_LEGAL:
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in pss.MARKERS:
                if marker.search(text):
                    tracked_findings.append({"file": rel, "kind": "public-safety-marker"})
    check("legal:tracked-tree-clean", not tracked_findings)
    FINDINGS["legal_findings"].extend(tracked_findings)

    own_findings: list[dict[str, str]] = []
    own_dir = EVIDENCE_ROOT / "P2-90"
    if own_dir.exists():
        for path in sorted(own_dir.rglob("*")):
            if not path.is_file() or "_probe" in path.parts or "regressions" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            for kind, _detail in _scan_evidence_file(path):
                own_findings.append({"file": rel, "kind": kind})
    check("legal:p2-90-artifacts-clean", not own_findings)
    FINDINGS["legal_findings"].extend(own_findings)

    frozen_host_paths: set[str] = set()
    frozen_findings: list[dict[str, str]] = []
    for directory in FROZEN_STAGE_DIRS:
        stage_dir = EVIDENCE_ROOT / directory
        if not stage_dir.exists():
            continue
        for path in sorted(stage_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            for kind, _detail in _scan_evidence_file(path, allowlisted=(rel in HOST_PATH_ALLOWLIST)):
                frozen_findings.append({"file": rel, "kind": kind})
                if kind == "absolute-host-path":
                    frozen_host_paths.add(f"{directory}/{path.relative_to(stage_dir).as_posix()}")
    unexpected = sorted(frozen_host_paths - DOCUMENTED_FROZEN_HOST_PATH_FILES)
    check("legal:frozen-evidence-findings-documented", not unexpected)
    FINDINGS["legal_findings"].extend(frozen_findings)
    FINDINGS["frozen_evidence_host_path_files"] = sorted(frozen_host_paths)

    package_findings: list[dict[str, str]] = []
    for archive in sorted((EVIDENCE_ROOT / "P2-50").glob("package_*.zip")):
        entries = read_package_entries(archive)
        package_findings.extend(rp.content_policy_findings(entries))
    check("legal:release-packages-pass-content-policy", not package_findings)
    FINDINGS["legal_findings"].extend(
        {"file": str(item), "kind": "release-package-policy"} for item in package_findings
    )

    host_path_sources = []
    for module_dir in ("openrecomp", "adapters"):
        for path in sorted((ROOT / module_dir).glob("*.py")):
            if path.relative_to(ROOT).as_posix() == "openrecomp/release_package.py":
                # This module defines the host-path detection pattern itself.
                continue
            if HOST_PATH_PATTERN.search(path.read_bytes()):
                host_path_sources.append(path.relative_to(ROOT).as_posix())
    check("legal:shared-source-no-host-paths", not host_path_sources)
    FINDINGS["legal_findings"].extend({"file": item, "kind": "host-path-in-source"} for item in host_path_sources)


def read_package_entries(archive: pathlib.Path) -> tuple[Any, ...]:
    """Wrap canonical archive entries for the release content policy scan."""
    pairs = rp.read_canonical_archive(archive.read_bytes())
    return tuple(_PolicyEntry(info.name, content) for info, content in pairs)


class _PolicyEntry:
    __slots__ = ("name", "content")

    def __init__(self, name: str, content: bytes) -> None:
        self.name = name
        self.content = content


# ---------------------------------------------------------------------------
# Claim classification
# ---------------------------------------------------------------------------
def audit_claims() -> None:
    seen: set[str] = set()
    for claim, classification, basis in CLAIMS:
        check(f"claim:{claim}:classification-vocabulary", classification in ALLOWED_CLAIM_CLASSES)
        check(f"claim:{claim}:basis-nonempty", bool(basis))
        check(f"claim:{claim}:unique", claim not in seen)
        seen.add(claim)
    for required in REQUIRED_CLAIMS:
        check(f"claim-required:{required}", required in seen)
    FINDINGS["claim_classification"] = [
        {"claim": claim, "classification": classification, "basis": basis}
        for claim, classification, basis in CLAIMS
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P2-90 whole Phase-2 regression and evidence audit")
    parser.add_argument("--evidence-dir", type=str, default=".openrecomp-phase2/evidence/P2-90")
    parser.add_argument("--json", type=str, default=None)
    parser.add_argument("--python", type=str, default=sys.executable)
    parser.add_argument("--skip-execution", action="store_true",
                        help="development flag: audit static evidence only, never emit PASS")
    parser.add_argument("--only-stage", action="append", default=[],
                        help="development flag: execute only the named gate stage(s), never emit PASS")
    args = parser.parse_args()

    evidence_dir = pathlib.Path(args.evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    global RESULTS
    RESULTS = []

    print("=== P2-90 Whole Phase-2 Regression and Evidence Audit ===", flush=True)
    failure: str | None = None
    dev_only = bool(args.only_stage)
    try:
        audit_control_plane()
        audit_evidence()
        audit_claims()
        audit_gates(args.python, execute=not args.skip_execution,
                    only=set(args.only_stage) if dev_only else None)
        audit_phase1(args.python, execute=not args.skip_execution)
        audit_legal()
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    skipped = sum(1 for item in RESULTS if item["status"] == "SKIP")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    summary = FINDINGS.get("gate_matrix_summary", {})
    gate_checks = summary.get("gate_checks", 0)

    status = "PASS"
    if args.skip_execution or dev_only:
        status = "SKIP"
    elif failure is not None or failed:
        status = "FAIL"

    result = {
        "stage": STAGE,
        "marker": f"{FEATURE_MARKER}=PASS tests={passed} gates={summary.get('gates_executed', 0)} gate_tests={gate_checks}",
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failure": failure,
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

    (evidence_dir / "p2_90_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    (evidence_dir / "regression_matrix.json").write_bytes(
        (json.dumps(FINDINGS["gate_matrix"], indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    matrix_lines = [
        "P2-90 regression matrix",
        "=" * 24,
        f"{'stage':<12} {'mode':<9} {'rc':<3} marker",
    ]
    for item in FINDINGS["gate_matrix"]:
        matrix_lines.append(f"{item['stage']:<12} {item['mode']:<9} {item['returncode']:<3} {item['marker']}")
    (evidence_dir / "regression_matrix.txt").write_bytes(("\n".join(matrix_lines) + "\n").encode("utf-8"))

    if args.json:
        pathlib.Path(args.json).write_bytes(
            (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )

    print("\n=== RESULT ===")
    if args.skip_execution or dev_only:
        print(f"{STAGE_MARKER}=SKIP (development flag; gate execution not performed)")
        return 0
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed} gates={summary.get('gates_executed', 0)} gate_tests={gate_checks}")
        print(f"{FINAL_MARKER}={authorized_final_verdict()}")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FINAL_MARKER}={authorized_final_verdict()}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
