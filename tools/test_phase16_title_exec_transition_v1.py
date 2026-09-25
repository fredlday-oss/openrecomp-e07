#!/usr/bin/env python3
"""Deterministic P16-06 Exec transition proof to 0x800380A0 gate."""

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
import p15_trace_v1 as trace  # noqa: E402
from tools import test_phase11_gpu_v1 as p11_05  # noqa: E402

import p16_analysis_v1 as analysis16  # noqa: E402
import p16_contracts_v1 as contract  # noqa: E402
import p16_emission_v1 as emission16  # noqa: E402
from p16_gate_v1 import assert_public_safe, run_stage, write_json  # noqa: E402
import p16_surface_v1 as surface16  # noqa: E402
import p16_transition_v1 as transition16  # noqa: E402

STAGE = "P16-06"


def parse_telemetry(stdout_bytes: bytes) -> dict[str, Any]:
    telemetry: dict[str, Any] = {}
    for line in stdout_bytes.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if val.isdigit():
                telemetry[key] = int(val)
            elif val.startswith("0x"):
                try:
                    telemetry[key] = int(val, 16)
                except ValueError:
                    telemetry[key] = val
            else:
                telemetry[key] = val
    return telemetry


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    fixture_root = ROOT / "fixtures" / "psx" / "hercules"
    if not fixture_root.is_dir():
        fixture_root = ROOT.parents[1] / "fixtures" / "psx" / "hercules"
    disc_path = fixture_root / "Disney's Hercules Action Game (USA).bin"
    gate.check("disc-present", disc_path.is_file(), "authentic disc image present")

    # 1. Structural analysis with Phase 16 services and internal targets
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

    # 2. Build set composition with exec_transition=True
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
        exec_transition=True,
    )
    gate.check("build-set-files", len(build_set["files"]) == 4, "build set has all 4 C source units")

    # 3. Native host compilation (dual runs for deterministic comparison)
    build_root = ROOT / ".openrecomp-phase16" / "build" / "p16_06"
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
        config=bp.BuildConfig(fixture_id="p16_06", smoke_test=False, run_count=2),
        workspace=build_root,
        keep_workspace=True,
    )
    gate.check("run1-build-ok", comparison.runs[0].manifest.build_status == bp.BuildStatus.OK, "run1 built OK")
    gate.check("run2-build-ok", comparison.runs[1].manifest.build_status == bp.BuildStatus.OK, "run2 built OK")

    executables = [build_root / f"run{index}" / "program.exe" for index in range(1, 3)]

    # 4. Deterministic native execution
    run1 = trace.run_program(executables[0], budget=p11_05.ACCESS_BUDGET, block_budget=surface16.FRONTIER_BLOCK_BUDGET)
    run2 = trace.run_program(executables[1], budget=p11_05.ACCESS_BUDGET, block_budget=surface16.FRONTIER_BLOCK_BUDGET)

    gate.check("run1-rc-zero", run1["returncode"] == 0, f"run1 returncode 0 (got {run1['returncode']})")
    gate.check("run2-rc-zero", run2["returncode"] == 0, f"run2 returncode 0 (got {run2['returncode']})")
    gate.check("run1-stderr-empty", run1["stderr_bytes"] == 0, "run1 stderr empty")
    gate.check("run2-stderr-empty", run2["stderr_bytes"] == 0, "run2 stderr empty")
    gate.check("dual-run-stdout-identical", run1["stdout"] == run2["stdout"], "dual runs byte-identical")

    t1 = parse_telemetry(run1["stdout"])

    # 5. Verify Exec transition telemetry
    for label, cond, msg in transition16.verify_transition_telemetry(t1):
        gate.check(label, cond, msg)

    # 6. Verify CD-ROM telemetry integrity
    gate.check("cd-read-calls", t1.get("p16_cdrom_read_calls") == 2, f"CD read calls == 2 (got {t1.get('p16_cdrom_read_calls')})")
    gate.check("cd-sectors", t1.get("p16_cdrom_sectors_delivered") == 146, f"CD sectors == 146 (got {t1.get('p16_cdrom_sectors_delivered')})")
    gate.check("cd-bytes", t1.get("p16_cdrom_bytes_delivered") == 299008, f"CD bytes == 299008 (got {t1.get('p16_cdrom_bytes_delivered')})")
    gate.check("cd-failures-zero", t1.get("p16_cdrom_read_failures") == 0, "CD read failures == 0")

    # 7. Evidence generation
    evidence_doc = {
        "schema": "openrecomp-phase16-title-exec-transition-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "transition_proof": {
            "exec_struct_addr": f"0x{t1.get('p16_exec_struct_addr', 0):08x}",
            "exec_pc0": f"0x{t1.get('p16_exec_pc0', 0):08x}",
            "exec_sp_addr": f"0x{t1.get('p16_exec_sp_addr', 0):08x}",
            "exec_payload_verified": t1.get("p16_exec_payload_verified"),
            "transition_dispatched": t1.get("p16_transition_dispatched"),
            "transition_target": f"0x{t1.get('p16_transition_target', 0):08x}",
            "transition_sp": f"0x{t1.get('p16_transition_sp', 0):08x}",
            "title_entry_called": t1.get("p16_title_entry_called"),
            "title_initial_gp": f"0x{t1.get('p16_title_initial_gp', 0):08x}",
            "title_heap_start": f"0x{t1.get('p16_title_heap_start', 0):08x}",
            "title_heap_size": f"0x{t1.get('p16_title_heap_size', 0):08x}",
            "title_cfg_param1": f"0x{t1.get('p16_title_cfg_param1', 0):08x}",
            "title_cfg_param2": f"0x{t1.get('p16_title_cfg_param2', 0):08x}",
            "title_main_reached": t1.get("p16_title_main_reached"),
            "title_main_target": f"0x{t1.get('p16_title_main_target', 0):08x}",
        },
        "determinism": {
            "dual_runs_identical": run1["stdout"] == run2["stdout"],
            "stderr_empty": run1["stderr_bytes"] == 0,
        },
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "title_exec_transition.json", evidence_doc)
    assert_public_safe(gate, "title-exec-transition", evidence_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.TITLE_EXEC_TRANSITION_MARKER: "PASS",
            "OPENRECOMP_P16_06": "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P16-07",
    })

    gate.mark(contract.TITLE_EXEC_TRANSITION_MARKER)
    gate.mark("OPENRECOMP_P16_06")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-06"))
