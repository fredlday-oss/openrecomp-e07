#!/usr/bin/env python3
"""Deterministic P16-05 TITLE load causal proof (controlled ablation) gate."""

from __future__ import annotations

import pathlib
import shutil
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src", ".openrecomp-phase13/src",
              ".openrecomp-phase14/src", ".openrecomp-phase15/src",
              ".openrecomp-phase16/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from openrecomp import build_pipeline as bp  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

import p16_analysis_v1 as analysis16  # noqa: E402
import p16_causality_v1 as causality16  # noqa: E402
import p16_contracts_v1 as contract  # noqa: E402
import p16_emission_v1 as emission16  # noqa: E402
from p16_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p16_surface_v1 as surface16  # noqa: E402

STAGE = "P16-05"


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    fixture_root = ROOT / "fixtures" / "psx" / "hercules"
    if not fixture_root.is_dir():
        fixture_root = ROOT.parents[1] / "fixtures" / "psx" / "hercules"
    disc_path = fixture_root / "Disney's Hercules Action Game (USA).bin"
    gate.check("disc-present", disc_path.is_file(), "authentic disc image present")

    # 1. Structural analysis
    private = analysis16.build_phase16_private(
        fixture_root,
        extra_a0=surface16.EXTRA_A0,
        extra_c0=surface16.EXTRA_C0,
        extra_b0=surface16.EXTRA_B0,
        p14_b0=surface16.P14_B0,
        p14_a0=surface16.P14_A0,
        p15_a0=surface16.P15_A0,
        p15_b0=surface16.P15_B0,
        internal_targets=surface16.INTERNAL_TARGETS,
    )
    gate.check("analysis-ok", "image" in private and "result_b" in private, "private analysis produced")

    # 2. Build set composition
    build_set = emission16.build_build_set(
        private["result_b"],
        private["base"],
        private["contract"],
        private["flat"],
        private["image"].file_sha256,
        disc_path=disc_path,
        sites=private["sites_b"],
        trace=True,
        guarded_resolved_indirect=True,
        extra_a0=surface16.EXTRA_A0,
        extra_c0=surface16.EXTRA_C0,
        extra_b0=surface16.EXTRA_B0,
        p14_b0=surface16.P14_B0,
        p14_a0=surface16.P14_A0,
        p15_a0=surface16.P15_A0,
        p15_b0=surface16.P15_B0,
    )
    gate.check("build-set-files", len(build_set["files"]) == 4, "build set has all 4 C source units")

    # 3. Native host compilation (dual runs for deterministic comparison)
    build_root = ROOT / ".openrecomp-phase16" / "build" / "p16_05"
    if build_root.exists():
        shutil.rmtree(build_root, ignore_errors=True)
    comparison = bp.build_generated_host(
        lambda: build_set["files"][emission16.PROGRAM_NAME],
        support_sources=tuple(
            bp.BuildSource(
                source_name,
                bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                build_set["files"][source_name].encode("utf-8"),
            )
            for source_name in (emission16.IMAGE_NAME, emission16.SUPPORT_NAME, emission16.DRIVER_NAME)
        ),
        config=bp.BuildConfig(fixture_id="p16_05", smoke_test=False, run_count=2),
        workspace=build_root,
        keep_workspace=True,
    )
    gate.check("run1-build-ok", comparison.runs[0].manifest.build_status == bp.BuildStatus.OK, "run1 built OK")
    gate.check("run2-build-ok", comparison.runs[1].manifest.build_status == bp.BuildStatus.OK, "run2 built OK")

    executables = [build_root / f"run{index}" / "program.exe" for index in range(1, 3)]

    # 4. Execute Baseline and Controlled Ablations on Run 1 and Run 2
    runs_records: dict[str, dict[str, Any]] = {"run1": {}, "run2": {}}

    for run_key, exe in zip(("run1", "run2"), executables):
        for ablation in causality16.ALL_ABLATIONS:
            res = causality16.run_ablation(
                exe,
                budget=p11_05.ACCESS_BUDGET,
                block_budget=surface16.FRONTIER_BLOCK_BUDGET,
                ablation=ablation,
            )
            runs_records[run_key][ablation] = res

    # 5. Dual run determinism assertions across all ablations
    for ablation in causality16.ALL_ABLATIONS:
        r1 = runs_records["run1"][ablation]
        r2 = runs_records["run2"][ablation]
        gate.check(f"determinism:{ablation}:rc-zero", r1["returncode"] == 0 and r2["returncode"] == 0, f"rc 0 for {ablation}")
        gate.check(f"determinism:{ablation}:stderr-empty", r1["stderr_bytes"] == 0 and r2["stderr_bytes"] == 0, f"stderr empty for {ablation}")
        gate.check(f"determinism:{ablation}:stdout-identical", r1["stdout"] == r2["stdout"], f"stdout identical for {ablation}")

    # 6. Verify Baseline
    base_t = runs_records["run1"][causality16.ABLATION_NONE]["telemetry"]
    for label, cond, msg in causality16.verify_baseline(base_t):
        gate.check(label, cond, msg)

    # 7. Verify Ablation 1: NULL_DISC (missing disc / sector delivery absent)
    null_t = runs_records["run1"][causality16.ABLATION_NULL_DISC]["telemetry"]
    for label, cond, msg in causality16.verify_null_disc_ablation(null_t):
        gate.check(label, cond, msg)

    # 8. Verify Ablation 2: CORRUPT_SYNC (sector sync header validation active)
    sync_t = runs_records["run1"][causality16.ABLATION_CORRUPT_SYNC]["telemetry"]
    for label, cond, msg in causality16.verify_corrupt_sync_ablation(sync_t):
        gate.check(label, cond, msg)

    # 9. Verify Ablation 3: ZERO_PAYLOAD (authentic fixture bytes required)
    zero_t = runs_records["run1"][causality16.ABLATION_ZERO_PAYLOAD]["telemetry"]
    for label, cond, msg in causality16.verify_zero_payload_ablation(zero_t):
        gate.check(label, cond, msg)

    # 10. Differential Causal Proof Assertions
    gate.check(
        "causality:cd-delivery-necessary-for-exec",
        base_t.get("p16_exec_calls") == 1 and null_t.get("p16_exec_calls") == 0,
        "CD sector delivery is causally necessary to reach A0:0x43 Exec",
    )
    gate.check(
        "causality:sync-validation-necessary-for-exec",
        base_t.get("p16_exec_calls") == 1 and sync_t.get("p16_exec_calls") == 0,
        "Mode 2 Form 1 sync pattern validation is causally necessary to reach A0:0x43 Exec",
    )
    gate.check(
        "causality:authentic-sectors-necessary-for-payload-verification",
        base_t.get("p16_exec_payload_verified") == 1 and zero_t.get("p16_exec_payload_verified") == 0,
        "Authentic disc bytes are causally necessary for TITLE payload SHA-256 verification",
    )
    gate.check(
        "causality:authentic-sectors-necessary-for-first-instruction",
        base_t.get("p16_exec_first_word") == contract.TITLE_FIRST_INSTR_WORD and zero_t.get("p16_exec_first_word") == 0,
        "Authentic disc bytes are causally necessary for valid TITLE entry instruction",
    )

    # 11. Evidence generation
    evidence_doc = {
        "schema": "openrecomp-phase16-title-load-causality-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "ablations": {
            "baseline": {
                "ablation_mode": causality16.ABLATION_NONE,
                "failed": base_t.get("failed"),
                "error": base_t.get("error"),
                "cdrom_read_calls": base_t.get("p16_cdrom_read_calls"),
                "cdrom_sectors_delivered": base_t.get("p16_cdrom_sectors_delivered"),
                "cdrom_bytes_delivered": base_t.get("p16_cdrom_bytes_delivered"),
                "cdrom_read_failures": base_t.get("p16_cdrom_read_failures"),
                "exec_calls": base_t.get("p16_exec_calls"),
                "exec_pc0": f"0x{base_t.get('p16_exec_pc0', 0):08x}",
                "exec_payload_verified": base_t.get("p16_exec_payload_verified"),
                "exec_first_word": f"0x{base_t.get('p16_exec_first_word', 0):08x}",
            },
            "null_disc": {
                "ablation_mode": causality16.ABLATION_NULL_DISC,
                "failed": null_t.get("failed"),
                "error": null_t.get("error"),
                "cdrom_read_calls": null_t.get("p16_cdrom_read_calls"),
                "cdrom_sectors_delivered": null_t.get("p16_cdrom_sectors_delivered"),
                "cdrom_bytes_delivered": null_t.get("p16_cdrom_bytes_delivered"),
                "cdrom_read_failures": null_t.get("p16_cdrom_read_failures"),
                "exec_calls": null_t.get("p16_exec_calls"),
                "exec_payload_verified": null_t.get("p16_exec_payload_verified"),
            },
            "corrupt_sync": {
                "ablation_mode": causality16.ABLATION_CORRUPT_SYNC,
                "failed": sync_t.get("failed"),
                "error": sync_t.get("error"),
                "cdrom_read_calls": sync_t.get("p16_cdrom_read_calls"),
                "cdrom_sectors_delivered": sync_t.get("p16_cdrom_sectors_delivered"),
                "cdrom_bytes_delivered": sync_t.get("p16_cdrom_bytes_delivered"),
                "cdrom_read_failures": sync_t.get("p16_cdrom_read_failures"),
                "exec_calls": sync_t.get("p16_exec_calls"),
                "exec_payload_verified": sync_t.get("p16_exec_payload_verified"),
            },
            "zero_payload": {
                "ablation_mode": causality16.ABLATION_ZERO_PAYLOAD,
                "failed": zero_t.get("failed"),
                "error": zero_t.get("error"),
                "cdrom_read_calls": zero_t.get("p16_cdrom_read_calls"),
                "cdrom_sectors_delivered": zero_t.get("p16_cdrom_sectors_delivered"),
                "cdrom_bytes_delivered": zero_t.get("p16_cdrom_bytes_delivered"),
                "cdrom_read_failures": zero_t.get("p16_cdrom_read_failures"),
                "exec_calls": zero_t.get("p16_exec_calls"),
                "exec_pc0": f"0x{zero_t.get('p16_exec_pc0', 0):08x}",
                "exec_payload_verified": zero_t.get("p16_exec_payload_verified"),
                "exec_first_word": f"0x{zero_t.get('p16_exec_first_word', 0):08x}",
            },
        },
        "causal_proofs": {
            "cd_delivery_required_for_exec": True,
            "sync_validation_active": True,
            "authentic_sectors_required_for_payload": True,
        },
        "determinism": {
            ablation: {
                "dual_runs_identical": (runs_records["run1"][ablation]["stdout"] == runs_records["run2"][ablation]["stdout"]),
                "stderr_empty": (runs_records["run1"][ablation]["stderr_bytes"] == 0),
            }
            for ablation in causality16.ALL_ABLATIONS
        },
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "title_load_causality.json", evidence_doc)
    assert_public_safe(gate, "title-load-causality", evidence_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.TITLE_LOAD_CAUSALITY_MARKER: "PASS",
            "OPENRECOMP_P16_05": "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P16-06",
    })

    gate.mark(contract.TITLE_LOAD_CAUSALITY_MARKER)
    gate.mark("OPENRECOMP_P16_05")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-05"))
