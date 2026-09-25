#!/usr/bin/env python3
"""Deterministic P16-04 CD-ROM production integration & A0:0x43 Exec gate."""

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

STAGE = "P16-04"


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

    # 2. Build set composition with CD-ROM sector delivery and P16 BIOS extensions
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
    build_root = ROOT / ".openrecomp-phase16" / "build" / "p16_04"
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
        config=bp.BuildConfig(fixture_id="p16_04", smoke_test=False, run_count=2),
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

    gate.check("failed-zero", t1.get("failed") == 0, f"failed == 0 (got {t1.get('failed')})")
    gate.check("error-empty", t1.get("error") == "", f"error empty (got {t1.get('error')})")

    # CD-ROM sector delivery assertions
    gate.check("cd-read-calls", t1.get("p16_cdrom_read_calls") == 2, f"CD read calls == 2 (got {t1.get('p16_cdrom_read_calls')})")
    gate.check("cd-sectors", t1.get("p16_cdrom_sectors_delivered") == 146, f"CD sectors == 146 (got {t1.get('p16_cdrom_sectors_delivered')})")
    gate.check("cd-bytes", t1.get("p16_cdrom_bytes_delivered") == 299008, f"CD bytes == 299008 (got {t1.get('p16_cdrom_bytes_delivered')})")
    gate.check("cd-no-failures", t1.get("p16_cdrom_read_failures") == 0, "CD read failures == 0")
    gate.check("cd-last-lba", t1.get("p16_cdrom_last_lba") == 88, "CD last LBA == 88")
    gate.check("cd-last-count", t1.get("p16_cdrom_last_count") == 145, "CD last count == 145")

    # A0:0x43 Exec dispatch assertions
    gate.check("exec-calls", t1.get("p16_exec_calls") == 1, f"Exec calls == 1 (got {t1.get('p16_exec_calls')})")
    gate.check("exec-struct", t1.get("p16_exec_struct_addr") == contract.EXEC_STRUCT_ADDR, f"Exec struct addr == 0x{contract.EXEC_STRUCT_ADDR:08x}")
    gate.check("exec-pc0", t1.get("p16_exec_pc0") == contract.TITLE_ENTRY_PC, f"Exec pc0 == 0x{contract.TITLE_ENTRY_PC:08x}")
    gate.check("exec-t-addr", t1.get("p16_exec_t_addr") == contract.TITLE_TEXT_ADDR, f"Exec t_addr == 0x{contract.TITLE_TEXT_ADDR:08x}")
    gate.check("exec-t-size", t1.get("p16_exec_t_size") == contract.TITLE_PAYLOAD_SIZE, f"Exec t_size == {contract.TITLE_PAYLOAD_SIZE}")
    gate.check("exec-sp-addr", t1.get("p16_exec_sp_addr") == contract.TITLE_SP_ADDR, f"Exec sp_addr == 0x{contract.TITLE_SP_ADDR:08x}")
    gate.check("exec-payload-verified", t1.get("p16_exec_payload_verified") == 1, "authentic TITLE overlay payload SHA-256 verified")
    gate.check("exec-first-word", t1.get("p16_exec_first_word") == contract.TITLE_FIRST_INSTR_WORD, f"first word == 0x{contract.TITLE_FIRST_INSTR_WORD:08x}")
    gate.check("rcnt-clear-calls", t1.get("p16_rcnt_clear_calls") == 1, "ChangeClearRCnt calls == 1")

    # 5. Evidence generation
    evidence_doc = {
        "schema": "openrecomp-phase16-cdrom-production-v1",
        "stage": STAGE,
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "telemetry": {
            "p16_exec_calls": t1.get("p16_exec_calls"),
            "p16_exec_struct_addr": f"0x{t1.get('p16_exec_struct_addr', 0):08x}",
            "p16_exec_pc0": f"0x{t1.get('p16_exec_pc0', 0):08x}",
            "p16_exec_t_addr": f"0x{t1.get('p16_exec_t_addr', 0):08x}",
            "p16_exec_t_size": t1.get("p16_exec_t_size"),
            "p16_exec_sp_addr": f"0x{t1.get('p16_exec_sp_addr', 0):08x}",
            "p16_exec_payload_verified": t1.get("p16_exec_payload_verified"),
            "p16_exec_first_word": f"0x{t1.get('p16_exec_first_word', 0):08x}",
            "p16_cdrom_read_calls": t1.get("p16_cdrom_read_calls"),
            "p16_cdrom_sectors_delivered": t1.get("p16_cdrom_sectors_delivered"),
            "p16_cdrom_bytes_delivered": t1.get("p16_cdrom_bytes_delivered"),
            "p16_cdrom_read_failures": t1.get("p16_cdrom_read_failures"),
            "p16_cdrom_last_lba": t1.get("p16_cdrom_last_lba"),
            "p16_cdrom_last_count": t1.get("p16_cdrom_last_count"),
            "p16_rcnt_clear_calls": t1.get("p16_rcnt_clear_calls"),
        },
        "determinism": {
            "dual_runs_identical": run1["stdout"] == run2["stdout"],
            "stderr_empty": run1["stderr_bytes"] == 0,
        },
        "private_fixture_bytes_recorded": "NO",
        "third_party_code_imported": "NO",
    }
    write_json(evidence / "cdrom_production.json", evidence_doc)
    assert_public_safe(gate, "cdrom-production", evidence_doc, b"")

    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase16-result-v1",
        "stage": STAGE,
        "status": "PASS",
        "evidence_class": "REPRESENTATIVE_TEST_RECORD",
        "markers": {
            contract.CDROM_PRODUCTION_INTEGRATION_MARKER: "PASS",
            "OPENRECOMP_P16_04": "PASS",
            contract.INITIALIZATION_MARKER: "NOT_PROVEN",
            contract.FRAME_MARKER: "NOT_PROVEN",
            contract.PLAYABILITY_MARKER: "NOT_PROVEN",
            contract.GENERAL_MARKER: "NOT_PROVEN",
        },
        "next_stage": "P16-05",
    })

    gate.mark(contract.CDROM_PRODUCTION_INTEGRATION_MARKER)
    gate.mark("OPENRECOMP_P16_04")
    gate.mark(contract.INITIALIZATION_MARKER, "NOT_PROVEN")
    gate.mark(contract.FRAME_MARKER, "NOT_PROVEN")
    gate.mark(contract.PLAYABILITY_MARKER, "NOT_PROVEN")
    gate.mark(contract.GENERAL_MARKER, "NOT_PROVEN")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase16/evidence/P16-04"))
