#!/usr/bin/env python3
"""OpenRecomp Phase-6 evidence-driven platform expansion gate (P6-11).

Determines, from deterministic evidence only, whether the frozen P6-11
required outcome ("add only PPU/APU/input/timing/runtime behaviour
demonstrated necessary by the private compatibility evidence and/or the public
proof fixture") justifies any platform addition at this boundary.

The gate re-derives the exact P6-10 private compatibility report in process,
requires it to reproduce the committed P6-10 evidence byte-for-byte, and
classifies every recorded blocker:

* the documented-control-flow stop at 0xC570 (undocumented 6502 opcode 0x7C),
  the three unresolved `jmp ($E2)` sites and the power-on-bank reachability
  ambiguity are translation/control-flow blockers, not platform blockers;
* the only runtime-platform record is `NOT_TESTED` and explicitly cannot be
  assessed until translation completes, so no platform requirement is
  demonstrated;
* the former mapper blocker is `SUPERSEDED` and carries no requirement.

Because no observed evidence demonstrates a missing platform behaviour, the
justified addition set is empty: P6-11 selects the deterministic zero-platform
delta PASS, preserves the proven P6-09/P6-10 platform behaviour unchanged
(per-file source pins), and requires the frozen independent reference
equivalence gate to re-pass as the explicit deterministic reference test.

The gate fails closed if its own decision logic is fed evidence that would
justify an addition (synthetic platform blockers), if the P6-10 evidence
anchor no longer matches, or if any pinned platform source changed.

On success it emits::

    OPENRECOMP_P6_11=PASS
    OPENRECOMP_PHASE6_PLATFORM_EXPANSION_V1=PASS tests=<count>
    OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase6_evidence_expansion_v1.py \
        --evidence-dir .openrecomp-phase6/evidence/P6-11
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
PHASE6 = ROOT / ".openrecomp-phase6"
for entry in (str(PHASE6 / "src"), str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / "tools")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_private_run_v1 as private_run  # noqa: E402

STAGE = "P6-11"
STAGE_MARKER = "OPENRECOMP_P6_11"
FEATURE_MARKER = "OPENRECOMP_PHASE6_PLATFORM_EXPANSION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY"

PHASE5_TAG_OBJECT = "b5d6832ba2374b810f4c24500ed9093a9481fd8d"
PHASE5_COMMIT = "e8d3627a622d0ca3196b117c5112f29fabdb49e7"
PHASE5_TREE = "468fb9788350de393d3de2ca9471b7d874ee8dc9"

PRIVATE_PATH = r"D:\OpenRecomp\Roms\phase1\nes\primary\tmnt.nes"
PRIVATE_SHA256 = "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1"
PRIVATE_SIZE = 262160

P6_10_PIPELINE_REL = ".openrecomp-phase6/evidence/P6-10/tmnt_pipeline.json"
P6_10_PIPELINE_SHA256 = (
    "0b8c9014fa11f9e363f1cfb1c569048f786b8baec2117769adb862b375a3ebdc")
P6_10_BLOCKERS_REL = ".openrecomp-phase6/evidence/P6-10/blockers.json"
P6_10_BLOCKERS_SHA256 = (
    "6b8b789cb691da742c270b81c98849bbda952642ad393cc5a4af230bc97e41c5")
PRIVATE_SUPPORT_SHA256 = (
    "2e3fa4bac6c0630840535aff2827c5f453b2372d0acb90551c72a58309d8a3e7")

P6_09_MARKER = "OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1=PASS"

PLATFORM_SOURCE_PINS: dict[str, str] = {
    ".openrecomp-phase6/src/p6_cartridge_v1.py":
        "8999387faccbd99f59a56f1a9682ab883dc4cfe190e1d77b3b9b9298ff82fa9e",
    ".openrecomp-phase6/src/p6_emit_v1.py":
        "457fcb0ced2449661c8bb2050df97cb31abab4dec1df2a10654d8107be1b4b3a",
    ".openrecomp-phase6/src/p6_fixture_build_v1.py":
        "8f47f78ee40e2277767e789f6ac8756395a65d5120115d095b4878199d54ebbb",
    ".openrecomp-phase6/src/p6_fixture_proof_v1.py":
        "a80969de5bdeef4cb9630bbd157d8bd0a972b518c64755ec4422459cfa8da3a9",
    ".openrecomp-phase6/src/p6_frontier_v1.py":
        "66079da0ad7536969e0ceac7bc40810aa666229e9b61e12e61f67741fa47011f",
    ".openrecomp-phase6/src/p6_ines_v1.py":
        "f686d944f7859d3781b03f71a65b0a5b23c8507720b1832ae5da99c0a4720b89",
    ".openrecomp-phase6/src/p6_mapper1_chr_reference_v1.py":
        "abb6c6f5ae15b4fe3d2ff771a6944faed79105c650bc0eac1520219e91b5f833",
    ".openrecomp-phase6/src/p6_mapper1_chr_v1.py":
        "8ac6323f80fa4a376891c9fd295e9d8d39fafd2dfadf24b9596db93904a691ec",
    ".openrecomp-phase6/src/p6_mapper1_prg_reference_v1.py":
        "ac93affb86b88b18c585690324f2e7c3d0125625b5c12239ad4836ffa6849307",
    ".openrecomp-phase6/src/p6_mapper1_prg_v1.py":
        "b68d3c0274a27ff6577515203969b78b19530bd1436480431351cb1c3499bdac",
    ".openrecomp-phase6/src/p6_mapper1_variant_v1.py":
        "de38ca1ff2132bc84e0aa56763b050c78405a3d26dc346d7e531736f9226559e",
    ".openrecomp-phase6/src/p6_mmc1_serial_reference_v1.py":
        "133bedab1d6c886eba0f46dc790ab24d56419b155ff4b2596dd15366c37935bb",
    ".openrecomp-phase6/src/p6_mmc1_serial_v1.py":
        "7e3a579cb33a0980275d0c62236e946fcee14bd1a92d90888bea056acca4b325",
    ".openrecomp-phase6/src/p6_mmc1_spec_v1.py":
        "e80e7ff5dc1db3abb3a7272d8f7d7bee09b8899799de7ab28c640e03673b76c6",
    ".openrecomp-phase6/src/p6_private_fixture_v1.py":
        "4f3a99d190d8349f50a902e70e1f270109b30285dc222386e36412fc2bd5647d",
    ".openrecomp-phase6/src/p6_private_run_v1.py":
        "083cef8e0813d557ed69940fde2ee0da43be07a3911cdf5dfa3c8cea12faa471",
    ".openrecomp-phase6/src/p6_reference_v1.py":
        "31e27b9175d643c9ac80b6ef0c41ee9cd85c1d940cf2c9a425f0cbb1ce743321",
    ".openrecomp-phase6/src/p6_stage_runner_v1.py":
        "2167f6e2210b11d716c11c4416b2a43c34a2643c684dc0dffe7b5985014de3d0",
    ".openrecomp-phase6/src/p6_structure_v1.py":
        "a50dbe6f8262fcb6dcedc093ae62bf0c8e5fb6f2ac4dba660083793cc58d00a4",
}

CONTROL_FLOW_STAGES = ("frontier", "indirect_control_flow", "bank_state")
PLATFORM_STAGES = ("ppu", "apu", "input", "timing", "runtime")
BLOCKER_ORDER = ("frontier", "indirect_control_flow", "bank_state",
                 "runtime_platform", "mapper")

EXPECTED_INDIRECT_ADDRESSES = ("0x86e8", "0x8956", "0x8f3c")
EXPECTED_OPCODE_SITE = "0xc570"
EXPECTED_LOW_WINDOW = 1048

REGRESSIONS = (
    ("tools/test_nes_rom_v1.py", []),
    ("tools/test_nes_platform_v1.py", []),
    ("tools/test_phase6_mmc1_inventory_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-11/regression_p6_01"]),
    ("tools/test_phase6_mmc1_variant_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-11/regression_p6_05"]),
    ("tools/test_phase6_mmc1_reference_equiv_v1.py",
     ["--evidence-dir", ".openrecomp-phase6/scratch/P6-11/regression_p6_09"]),
)

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
EVIDENCE_WRITES: dict[str, bytes] = {}


class P6ExpansionError(ValueError):
    """Fail-closed P6-11 evidence-driven expansion error."""


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


def lf_normalize(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical(document: Any) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def write_json(name: str, document: Any) -> None:
    EVIDENCE_WRITES[name] = canonical(document)


def verify_anchor(path: pathlib.Path, expected: str) -> str:
    if not path.is_file():
        raise P6ExpansionError(f"evidence anchor is missing: {path.name}")
    actual = sha256_file(path)
    if actual != expected:
        raise P6ExpansionError(
            f"evidence anchor changed: {path.name} is {actual}, expected "
            f"{expected}")
    return actual


def verify_platform_pins(root: pathlib.Path,
                         pins: dict[str, str]) -> dict[str, str]:
    observed: dict[str, str] = {}
    for rel, digest in sorted(pins.items()):
        path = root / rel
        if not path.is_file():
            raise P6ExpansionError(f"platform source is missing: {rel}")
        actual = sha256_file(path)
        observed[rel] = actual
        if actual != digest:
            raise P6ExpansionError(f"platform source changed: {rel}")
    return observed


def classify_blocker(blocker: dict[str, Any]) -> dict[str, Any]:
    stage = blocker.get("stage")
    code = blocker.get("code")
    detail = str(blocker.get("detail", ""))
    entry: dict[str, Any] = {"stage": stage, "code": code, "detail": detail}
    if stage in CONTROL_FLOW_STAGES:
        if code != "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE":
            entry.update(classification="unclassified_fail_closed",
                         justifies_addition=True, platform=False)
        else:
            classification = "translation_control_flow"
            if stage == "bank_state":
                classification = "translation_reachability_control_flow"
            entry.update(classification=classification,
                         justifies_addition=False, platform=False)
    elif stage == "runtime_platform" and code == "NOT_TESTED":
        entry.update(classification="platform_behaviour_not_yet_observable",
                     justifies_addition=False, platform=True)
    elif stage == "mapper" and code == "SUPERSEDED":
        entry.update(classification="mapper_blocker_closed",
                     justifies_addition=False, platform=False)
    else:
        entry.update(classification="unclassified_fail_closed",
                     justifies_addition=True, platform=(stage in PLATFORM_STAGES))
    return entry


def control_flow_sites(report: dict[str, Any]) -> dict[str, Any]:
    candidate = (((report.get("frontier") or {}).get("candidate")) or {})
    stop = candidate.get("stop") or {}
    sites = []
    for item in candidate.get("indirect_sites") or []:
        sites.append({
            "address": f"0x{int(item['address']):04x}",
            "instruction": item.get("instruction"),
            "pointer": f"0x{int(item.get('pointer') or 0):04x}",
            "classification": "translation_control_flow",
            "platform_behaviour": False,
        })
    return {
        "undocumented_opcode_site": {
            "address": f"0x{int(stop.get('address', 0)):04x}",
            "kind": stop.get("kind"),
            "reason": stop.get("reason"),
            "classification": "translation_control_flow",
            "platform_behaviour": False,
        },
        "unresolved_indirect_sites": sites,
        "low_window_candidate_instructions":
            candidate.get("low_window_instructions"),
        "low_window_classification": "translation_reachability_control_flow",
    }


def evaluate_platform_expansion(report: dict[str, Any]) -> dict[str, Any]:
    blockers = report.get("blockers")
    if not isinstance(blockers, list) or not blockers:
        raise P6ExpansionError("pipeline report carries no blocker ledger")
    ledger = [classify_blocker(item) for item in blockers]
    justified = [entry for entry in ledger if entry["justifies_addition"]]
    if justified:
        stages = ", ".join(sorted(str(entry["stage"]) for entry in justified))
        raise P6ExpansionError(
            "platform expansion is justified by observed evidence at: "
            f"{stages}")
    return {
        "policy": "add only behaviour demonstrated necessary by the private "
                  "compatibility evidence and/or the public proof fixture; "
                  "every addition requires an explicit deterministic reference "
                  "test; no broad full-hardware implementation by assumption",
        "decision": "NO_ADDITION_JUSTIFIED",
        "additions": [],
        "justified_blockers": [],
        "ledger": ledger,
        "control_flow_sites": control_flow_sites(report),
    }


def expect_expansion_fail(label: str, thunk) -> None:
    try:
        thunk()
    except P6ExpansionError:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"reject:{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"reject:{label}: accepted")


def expect_private_fail(label: str, thunk) -> None:
    try:
        thunk()
    except private_run.PrivateRunError:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"reject:{label}: raised {type(exc).__name__}: {exc}") from exc
    raise AssertionError(f"reject:{label}: accepted")


def run_regression(script: str, extra: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra], cwd=str(ROOT),
        capture_output=True)
    markers = [line for line in
               completed.stdout.decode("utf-8", errors="replace").splitlines()
               if line.startswith("OPENRECOMP_")]
    return {
        "script": script,
        "extra": extra,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256_raw": sha256_bytes(completed.stdout),
        "stdout_sha256_lf": sha256_bytes(lf_normalize(completed.stdout)),
        "stderr_bytes": len(completed.stderr),
        "stderr_empty": len(completed.stderr) == 0,
        "markers": markers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P6-11 evidence-driven platform expansion gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase6/evidence/P6-11")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, EVIDENCE_WRITES
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    EVIDENCE_WRITES = {}

    print("=== P6-11 Evidence-Driven Platform Expansion Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        manifest = PHASE6 / "SOURCE_SHA256SUMS.txt"
        check("source:manifest-exists", manifest.is_file())
        entries = []
        for line in manifest.read_text(encoding="utf-8").strip().splitlines():
            digest, rel = line.split(" *", 1)
            entries.append((digest, rel))
        bad = [rel for digest, rel in entries
               if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
        check("source:manifest-verified", bool(entries) and not bad)
        check("source:p6-11-gate-listed",
              any(rel.endswith("tools/test_phase6_evidence_expansion_v1.py")
                  for _digest, rel in entries))

        banner("frozen_chain")
        check("chain:phase5-tag-object",
              subprocess.run(["git", "rev-parse", "openrecomp-phase5-pass"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_TAG_OBJECT)
        check("chain:phase5-commit",
              subprocess.run(["git", "rev-parse",
                              "openrecomp-phase5-pass^{commit}"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_COMMIT)
        check("chain:phase5-tree",
              subprocess.run(["git", "rev-parse",
                              "openrecomp-phase5-pass^{tree}"],
                             cwd=str(ROOT), capture_output=True, text=True
                             ).stdout.strip() == PHASE5_TREE)
        check("chain:descends",
              subprocess.run(["git", "merge-base", "--is-ancestor",
                              PHASE5_COMMIT, "HEAD"],
                             cwd=str(ROOT), capture_output=True
                             ).returncode == 0)

        banner("control_plane")
        state = (PHASE6 / "STATE.md").read_text(encoding="utf-8")
        queue = (PHASE6 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        check("control-plane:stage-row", "| P6-11 |" in queue)
        check("control-plane:terminal-reserved",
              f"{TERMINAL_MARKER}=NOT_PROVEN" in queue)
        check("control-plane:compat-reserved",
              f"{COMPAT_MARKER}=NOT_PROVEN" in queue
              and f"{COMPAT_MARKER}=NOT_PROVEN" in state)

        banner("p6_10_anchor")
        pipeline_path = ROOT / P6_10_PIPELINE_REL
        verify_anchor(pipeline_path, P6_10_PIPELINE_SHA256)
        check("anchor:p6-10-pipeline-hash", True)
        blockers_path = ROOT / P6_10_BLOCKERS_REL
        verify_anchor(blockers_path, P6_10_BLOCKERS_SHA256)
        check("anchor:p6-10-blockers-hash", True)

        report_a = private_run.run()
        report_b = private_run.run()
        check("anchor:private-pipeline-deterministic",
              canonical(report_a) == canonical(report_b))
        check("anchor:private-pipeline-reproduces-p6-10",
              canonical(report_a) == pipeline_path.read_bytes())
        committed_blockers = json.loads(
            blockers_path.read_text(encoding="utf-8"))
        check("anchor:blocker-ledger-reproduces-p6-10",
              committed_blockers["blockers"] == report_a["blockers"]
              and committed_blockers["execution_status"]
              == "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE"
              and committed_blockers["stage"] == "P6-10")
        check("anchor:private-identity",
              report_a["source_path"] == PRIVATE_PATH
              and report_a["image_sha256"] == PRIVATE_SHA256
              and report_a["image_size"] == PRIVATE_SIZE)
        check("anchor:translation-not-attempted",
              report_a["translation"]["status"] == "NOT_ATTEMPTED"
              and report_a["native_build"]["status"] == "NOT_ATTEMPTED"
              and report_a["native_execution"]["status"] == "NOT_ATTEMPTED")
        check("anchor:structure-fail-closed",
              report_a["structure"]["status"] == "FAIL_CLOSED")
        check("anchor:frontier-fail-closed",
              report_a["frontier"]["frozen_status"] == "FAIL_CLOSED")

        banner("blocker_classification")
        decision = evaluate_platform_expansion(report_a)
        ledger = decision["ledger"]
        check("classification:blocker-order",
              [entry["stage"] for entry in ledger] == list(BLOCKER_ORDER))
        check("classification:control-flow-entries",
              [entry["stage"] for entry in ledger
               if entry["classification"].startswith("translation")]
              == list(CONTROL_FLOW_STAGES)
              and all(entry["justifies_addition"] is False
                      and entry["platform"] is False
                      for entry in ledger[:3]))
        check("classification:0x7c-site",
              decision["control_flow_sites"]["undocumented_opcode_site"]
              ["address"] == EXPECTED_OPCODE_SITE
              and "0x7c" in decision["control_flow_sites"]
              ["undocumented_opcode_site"]["reason"]
              and decision["control_flow_sites"]["undocumented_opcode_site"]
              ["classification"] == "translation_control_flow"
              and decision["control_flow_sites"]["undocumented_opcode_site"]
              ["platform_behaviour"] is False)
        check("classification:indirect-sites",
              [item["address"] for item in decision["control_flow_sites"]
               ["unresolved_indirect_sites"]]
              == list(EXPECTED_INDIRECT_ADDRESSES)
              and all(item["classification"] == "translation_control_flow"
                      and item["platform_behaviour"] is False
                      for item in decision["control_flow_sites"]
                      ["unresolved_indirect_sites"]))
        check("classification:bank-state",
              decision["control_flow_sites"]
              ["low_window_candidate_instructions"] == EXPECTED_LOW_WINDOW
              and decision["control_flow_sites"]
              ["low_window_classification"]
              == "translation_reachability_control_flow")
        check("classification:runtime-not-observable",
              any(entry["stage"] == "runtime_platform"
                  and entry["code"] == "NOT_TESTED"
                  and entry["classification"]
                  == "platform_behaviour_not_yet_observable"
                  and entry["justifies_addition"] is False
                  and "cannot be assessed until translation completes"
                  in entry["detail"] for entry in ledger))
        check("classification:mapper-closed",
              any(entry["stage"] == "mapper"
                  and entry["code"] == "SUPERSEDED"
                  and entry["classification"] == "mapper_blocker_closed"
                  and entry["justifies_addition"] is False
                  for entry in ledger))
        check("decision:no-addition-justified",
              decision["decision"] == "NO_ADDITION_JUSTIFIED"
              and decision["additions"] == []
              and decision["justified_blockers"] == [])

        banner("platform_preservation")
        observed = verify_platform_pins(ROOT, PLATFORM_SOURCE_PINS)
        check("platform:src-pin-count", len(PLATFORM_SOURCE_PINS) == 19)
        check("platform:src-unchanged",
              all(observed[rel] == digest
                  for rel, digest in PLATFORM_SOURCE_PINS.items()))
        check("platform:runtime-identity",
              report_a["runtime_support"]["status"] == "OK"
              and report_a["runtime_support"]["support_sha256"]
              == PRIVATE_SUPPORT_SHA256)
        check("platform:cartridge-power-on",
              report_a["cartridge"]["status"] == "SUPPORTED_MMC1"
              and report_a["reference_platform"]["power_on_prg_window"]
              == [0, 7])

        banner("negative")
        expect_expansion_fail(
            "platform-requirement-ppu",
            lambda: evaluate_platform_expansion({"blockers": [{
                "stage": "ppu",
                "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                "detail": "synthetic missing PPU behaviour"}]}))
        expect_expansion_fail(
            "platform-requirement-runtime",
            lambda: evaluate_platform_expansion({"blockers": [{
                "stage": "runtime",
                "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                "detail": "synthetic missing runtime service"}]}))
        expect_expansion_fail(
            "runtime-platform-demonstrated",
            lambda: evaluate_platform_expansion({"blockers": [{
                "stage": "runtime_platform",
                "code": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
                "detail": "synthetic demonstrated platform requirement"}]}))
        expect_expansion_fail(
            "unclassified-blocker",
            lambda: evaluate_platform_expansion({"blockers": [{
                "stage": "unknown_subsystem",
                "code": "NOT_TESTED",
                "detail": "synthetic unclassified blocker"}]}))
        expect_expansion_fail(
            "anchor-mismatch",
            lambda: verify_anchor(pipeline_path, "0" * 64))
        expect_expansion_fail(
            "platform-source-missing",
            lambda: verify_platform_pins(
                ROOT, {"tools/test_phase6_absent_module.py": "0" * 64}))
        expect_expansion_fail(
            "platform-source-changed",
            lambda: verify_platform_pins(
                ROOT, {".openrecomp-phase6/src/p6_private_run_v1.py":
                       "0" * 64}))
        expect_private_fail(
            "missing-private-path",
            lambda: private_run.run(path=pathlib.Path(
                r"D:\OpenRecomp\Roms\phase1\nes\primary\absent.nes")))

        banner("regressions")
        regressions = []
        for script, extra in REGRESSIONS:
            record = run_regression(script, extra)
            check(f"regression:{script}:exit", record["returncode"] == 0)
            check(f"regression:{script}:stderr", record["stderr_empty"])
            regressions.append(record)
        check("regression:p6-09-reference-equivalence-marker",
              any(P6_09_MARKER in marker
                  for marker in regressions[-1]["markers"]))
        FINDINGS["regressions"] = regressions

        banner("evidence_hygiene")
        write_json("platform_expansion.json", {
            "stage": STAGE,
            "anchors": {
                "p6_10_pipeline_sha256": P6_10_PIPELINE_SHA256,
                "p6_10_blockers_sha256": P6_10_BLOCKERS_SHA256,
                "private_support_sha256": PRIVATE_SUPPORT_SHA256,
            },
            "decision": decision,
        })
        write_json("platform_sources.json", {
            "stage": STAGE,
            "basis": "P6-10 boundary Phase-6 source identities",
            "pins": PLATFORM_SOURCE_PINS,
            "observed": observed,
            "unchanged": all(observed[rel] == digest
                             for rel, digest in PLATFORM_SOURCE_PINS.items()),
        })
        write_json("regressions.json", {
            "stage": STAGE,
            "regressions": regressions,
        })
        rom = pathlib.Path(PRIVATE_PATH).read_bytes()
        last_bank = rom[-0x4000:]
        first_bank = rom[16:16 + 0x4000]
        for name, data in EVIDENCE_WRITES.items():
            check(f"hygiene:no-private-rom-bytes:{name}", rom not in data)
            check(f"hygiene:no-private-bank-bytes:{name}",
                  last_bank not in data and first_bank not in data)
        FINDINGS["evidence_files"] = sorted(EVIDENCE_WRITES)
        FINDINGS["platform_decision"] = {
            "decision": decision["decision"],
            "additions": decision["additions"],
            "control_flow_blockers": list(CONTROL_FLOW_STAGES),
            "platform_requirement_evidence": [],
        }
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
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, data in EVIDENCE_WRITES.items():
        (EVIDENCE_DIR / name).write_bytes(data)
    (EVIDENCE_DIR / "p6_11_tests.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        newline="\n")

    print("\n=== RESULT ===")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={passed}")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    if failure:
        print(f"FAILURE={failure}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
