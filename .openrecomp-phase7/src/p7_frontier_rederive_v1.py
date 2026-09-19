#!/usr/bin/env python3
"""Phase-7 private TMNT frontier re-derivation (P7-01).

Re-derives the frozen Phase-6 private TMNT compatibility frontier from scratch
on the live private image (metadata/hash/derived-classification only, never
ROM bytes) through the frozen Phase-6 pipeline and the frozen Phase-6
ROM-to-native workflow, then requires the re-derived classifications to be
exactly equal to the committed Phase-6 records:

- `.openrecomp-phase6/evidence/P6-10/tmnt_pipeline.json` (sha256
  `0b8c9014...`),
- `.openrecomp-phase6/evidence/P6-10/blockers.json` (sha256 `6b8b789c...`),
- `.openrecomp-phase6/evidence/P6-13/frontier_record.json` (sha256
  `e49a0b34...`),
- `.openrecomp-phase6/evidence/P6-13/private_workflow.json` (sha256
  `07ce9a55...`),
- `.openrecomp-phase6/evidence/P6-12/blockers.json` (sha256 `b5cb9ef4...`).

No translation changes are made here. No ROM bytes are returned, stored,
echoed or written to evidence.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "tools"),
              str(ROOT / ".openrecomp-phase5" / "src"),
              str(ROOT / ".openrecomp-phase6" / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import p6_emit_v1 as emit_module  # noqa: E402
import p6_private_fixture_v1 as private_fixture  # noqa: E402
import p6_private_run_v1 as private_run  # noqa: E402
import p6_workflow_v1 as workflow  # noqa: E402

P6_10_PIPELINE_REL = ".openrecomp-phase6/evidence/P6-10/tmnt_pipeline.json"
P6_10_PIPELINE_SHA256 = "0b8c9014fa11f9e363f1cfb1c569048f786b8baec2117769adb862b375a3ebdc"
P6_10_BLOCKERS_REL = ".openrecomp-phase6/evidence/P6-10/blockers.json"
P6_10_BLOCKERS_SHA256 = "6b8b789cb691da742c270b81c98849bbda952642ad393cc5a4af230bc97e41c5"
P6_12_BLOCKERS_REL = ".openrecomp-phase6/evidence/P6-12/blockers.json"
P6_12_BLOCKERS_SHA256 = "b5cb9ef40625195baef160717ae15647091d6b6b0a13c2f24b9c8dab5c4ea579"
P6_13_FRONTIER_REL = ".openrecomp-phase6/evidence/P6-13/frontier_record.json"
P6_13_FRONTIER_SHA256 = "e49a0b3422d6a65b5b50ce820db5c9f9d02ef3662aa114f5287db3a8232bf484"
P6_13_WORKFLOW_REL = ".openrecomp-phase6/evidence/P6-13/private_workflow.json"
P6_13_WORKFLOW_SHA256 = "07ce9a558582ed1178b08ff158e2bff41ce9939e0416aaf07fb0dc64f180dd0e"

PRIVATE_SUPPORT_SHA256 = (
    "2e3fa4bac6c0630840535aff2827c5f453b2372d0acb90551c72a58309d8a3e7")
PRIVATE_IMAGE_SHA256 = (
    "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1")
PRIVATE_SIZE = 262160

EXPECTED_CANDIDATE = {
    "instructions": 1250,
    "bytes": 2711,
    "low_window_instructions": 1048,
    "fixed_window_instructions": 202,
    "distinct_opcode_forms": 42,
    "pending_at_stop": 11,
    "truncated": False,
}
EXPECTED_STOP = {
    "address": 0xC570,
    "kind": "undocumented_opcode",
    "reason": "0xc570: undocumented 6502 opcode 0x7c",
    "predecessor": {"address": 0xC56D, "instruction": "jsr"},
}
EXPECTED_INDIRECT_SITES = (
    {"address": 0x86E8, "instruction": "jmp", "pointer": 0xE2},
    {"address": 0x8956, "instruction": "jmp", "pointer": 0xE2},
    {"address": 0x8F3C, "instruction": "jmp", "pointer": 0xE2},
)
EXPECTED_BLOCKER_CLASSES = (
    "unsupported_opcode",
    "unresolved_indirect_control_flow",
    "bank_state_unresolved",
    "platform_runtime_not_tested",
)
EXPECTED_BLOCKER_STAGES = (
    "opcode_frontier",
    "indirect_control_flow",
    "bank_state",
    "runtime_platform",
)


class P7FrontierError(ValueError):
    """Fail-closed P7-01 re-derivation error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(document: Any) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def _read_committed(rel: str, expected_sha256: str) -> dict[str, Any]:
    path = ROOT / rel
    if not path.is_file():
        raise P7FrontierError(f"committed Phase-6 record is missing: {rel}")
    data = path.read_bytes()
    if sha256_bytes(data) != expected_sha256:
        raise P7FrontierError(f"committed Phase-6 record changed: {rel}")
    return json.loads(data.decode("utf-8"))


def _project_pipeline(document: dict[str, Any]) -> dict[str, Any]:
    candidate = document["frontier"]["candidate"]
    keys = ("instructions", "bytes", "low_window_instructions",
            "fixed_window_instructions", "low_window_range",
            "distinct_opcode_forms", "opcode_histogram", "indirect_sites",
            "interrupt_sites", "dynamic_returns", "outside_targets",
            "pending_at_stop", "stop", "truncated")
    return {
        "ingestion": document["ingestion"],
        "container": document["container"],
        "mapper": document["mapper"],
        "submapper": document["submapper"],
        "mirroring": document["mirroring"],
        "prg_bytes": document["prg_bytes"],
        "chr_bytes": document["chr_bytes"],
        "chr_is_ram": document["chr_is_ram"],
        "battery": document["battery"],
        "trainer_bytes": document["trainer_bytes"],
        "four_screen": document["four_screen"],
        "prg_sha256": document["prg_sha256"],
        "chr_sha256": document["chr_sha256"],
        "vectors": document["vectors"],
        "vectors_source": document["vectors_source"],
        "cartridge": document["cartridge"],
        "reference_platform": document["reference_platform"],
        "frontier": {
            "frozen_status": document["frontier"]["frozen_status"],
            "frozen_error": document["frontier"]["frozen_error"],
            "candidate": {key: candidate[key] for key in keys},
        },
        "structure": document["structure"],
        "translation": document["translation"],
        "native_build": document["native_build"],
        "native_execution": document["native_execution"],
        "runtime_support_sha256": document["runtime_support"]["support_sha256"],
        "preserved_phase5_boundary": document["preserved_phase5_boundary"],
        "blockers": document["blockers"],
    }


def _project_workflow(document: dict[str, Any]) -> dict[str, Any]:
    keys = ("status", "stop_reason", "inventory", "mapper_platform",
            "frontier", "opcode_frontier", "indirect_control_flow",
            "translation", "generated_sources", "native_build",
            "native_execution", "platform_runtime", "public_claim")
    return {key: document[key] for key in keys}


def _frontier_record(report: dict[str, Any]) -> dict[str, Any]:
    platform = report["mapper_platform"]
    frontier = report["frontier"]
    return {
        "ingestion_result": "SUPPORTED_MMC1",
        "mapper_state": {
            "status": platform["status"],
            "variant": platform["variant"]["status"],
            "power_on_prg_window":
                platform["cartridge"]["power_on_prg_window"],
            "power_on_registers":
                platform["cartridge"]["power_on_registers"],
        },
        "reachable_static_frontier": {
            "documented_status": frontier["documented_status"],
            "documented_error": frontier["documented_error"],
            "candidate": frontier["candidate"],
        },
        "opcode_frontier": report["opcode_frontier"],
        "indirect_control_flow_frontier": report["indirect_control_flow"],
        "translation_progress": report["translation"]["status"],
        "generated_source_progress": report["generated_sources"]["status"],
        "native_build_progress": report["native_build"]["status"],
        "native_execution_progress": report["native_execution"]["status"],
        "runtime_platform_progress": report["platform_runtime"]["status"],
        "stop_reasons": report["blockers"],
        "stop_reason": report["stop_reason"],
        "native_execution_reached": False,
        "interactive_behaviour_reached": False,
    }


def rederive(path: pathlib.Path | str = private_fixture.PRIVATE_ROM,
             workspace: pathlib.Path | str | None = None) -> dict[str, Any]:
    location = pathlib.Path(path)
    if not location.is_file():
        raise P7FrontierError("private compatibility fixture is not present")

    p6_10 = _read_committed(P6_10_PIPELINE_REL, P6_10_PIPELINE_SHA256)
    p6_10_blockers = _read_committed(P6_10_BLOCKERS_REL, P6_10_BLOCKERS_SHA256)
    p6_12_blockers = _read_committed(P6_12_BLOCKERS_REL, P6_12_BLOCKERS_SHA256)
    p6_13_frontier = _read_committed(P6_13_FRONTIER_REL, P6_13_FRONTIER_SHA256)
    p6_13_workflow = _read_committed(P6_13_WORKFLOW_REL, P6_13_WORKFLOW_SHA256)

    try:
        pipeline = private_run.run(location)
    except Exception as exc:  # noqa: BLE001 - deterministic fail-closed wrapper
        raise P7FrontierError(
            f"pipeline re-derivation failed: {type(exc).__name__}: {exc}") from exc
    try:
        report = workflow.run(location, build=True, workspace=workspace)
    except Exception as exc:  # noqa: BLE001 - deterministic fail-closed wrapper
        raise P7FrontierError(
            f"workflow re-derivation failed: {type(exc).__name__}: {exc}") from exc

    pipeline_projection = _project_pipeline(pipeline)
    committed_pipeline_projection = _project_pipeline(p6_10)
    workflow_projection = _project_workflow(report)
    committed_workflow_projection = _project_workflow(p6_13_workflow["report"])
    record = _frontier_record(report)
    committed_record = {key: value for key, value in p6_13_frontier.items()
                        if key != "stage"}

    candidate = report["frontier"]["candidate"]
    stop = candidate.get("stop") or {}
    blockers = report["blockers"]
    opcode_frontier = report["opcode_frontier"]
    indirect = report["indirect_control_flow"]

    metadata = {
        "rom_sha256": report["input"]["image_sha256"],
        "prg_size": report["inventory"]["prg_bytes"],
        "chr_size": report["inventory"]["chr_bytes"],
        "prg_banks": report["mapper_platform"]["classification"]["prg_banks_16k"],
        "chr_banks": report["mapper_platform"]["classification"]["chr_banks_8k"],
    }
    support = emit_module.emit_support(location.read_bytes(), metadata,
                                       workflow.DEFAULT_PLAN)
    support_sha256 = sha256_bytes(support.encode("utf-8"))
    del support

    comparisons = {
        "pipeline_projection_equal":
            canonical(pipeline_projection)
            == canonical(committed_pipeline_projection),
        "workflow_projection_equal":
            canonical(workflow_projection)
            == canonical(committed_workflow_projection),
        "frontier_record_equal": canonical(record) == canonical(committed_record),
        "p6_10_blockers_equal": pipeline["blockers"] == p6_10_blockers["blockers"],
        "p6_12_private_blockers_equal":
            blockers == p6_12_blockers["private_image"]
            and report["stop_reason"] == p6_12_blockers["private_stop_reason"],
        "runtime_support_identity": support_sha256 == PRIVATE_SUPPORT_SHA256,
        "image_identity":
            report["input"]["image_sha256"] == PRIVATE_IMAGE_SHA256
            and report["input"]["image_size"] == PRIVATE_SIZE,
        "mapper_blocker_superseded":
            report["mapper_platform"]["status"] == "SUPPORTED_MMC1"
            and not any(item["classification"].startswith("mapper_")
                        for item in blockers)
            and any(item["code"] == "SUPERSEDED"
                    and item["stage"] == "mapper"
                    for item in pipeline["blockers"]),
    }
    if not all(comparisons.values()):
        failed = sorted(name for name, value in comparisons.items() if not value)
        raise P7FrontierError(
            "re-derived classifications differ from the frozen Phase-6 "
            "records: " + ", ".join(failed))

    return {
        "stage": "P7-01",
        "classification": "PRIVATE_LOCAL_COMPATIBILITY_FIXTURE",
        "image_sha256": report["input"]["image_sha256"],
        "image_size": report["input"]["image_size"],
        "ingestion_result": report["mapper_platform"]["status"],
        "mapper_platform_status": report["mapper_platform"]["status"],
        "mapper_variant_status": report["mapper_platform"]["variant"]["status"],
        "power_on_registers":
            report["mapper_platform"]["cartridge"]["power_on_registers"],
        "power_on_prg_window":
            report["mapper_platform"]["cartridge"]["power_on_prg_window"],
        "prg_ram_enabled":
            report["mapper_platform"]["cartridge"]["prg_ram_enabled"],
        "reachable_static_frontier": record["reachable_static_frontier"],
        "opcode_frontier": opcode_frontier,
        "indirect_control_flow_frontier": indirect,
        "stop": stop,
        "blockers": blockers,
        "translation_progress": report["translation"]["status"],
        "generated_source_progress": report["generated_sources"]["status"],
        "native_build_progress": report["native_build"]["status"],
        "native_execution_progress": report["native_execution"]["status"],
        "runtime_platform_progress": report["platform_runtime"]["status"],
        "runtime_support_sha256": support_sha256,
        "comparisons": comparisons,
        "pipeline_projection_sha256": sha256_bytes(
            canonical(pipeline_projection).encode("utf-8")),
        "workflow_projection_sha256": sha256_bytes(
            canonical(workflow_projection).encode("utf-8")),
        "frontier_record_sha256": sha256_bytes(
            canonical(record).encode("utf-8")),
        "public_claim": "none; private local analysis must not enter the public "
                        "package",
    }


__all__ = [
    "EXPECTED_BLOCKER_CLASSES",
    "EXPECTED_BLOCKER_STAGES",
    "EXPECTED_CANDIDATE",
    "EXPECTED_INDIRECT_SITES",
    "EXPECTED_STOP",
    "P7FrontierError",
    "PRIVATE_IMAGE_SHA256",
    "PRIVATE_SIZE",
    "PRIVATE_SUPPORT_SHA256",
    "rederive",
]
