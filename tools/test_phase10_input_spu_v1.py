#!/usr/bin/env python3
"""OpenRecomp Phase-10 controller / SPU / game-loop frontier gate (P10-10).

Classifies the controller, SPU and frame/event-loop behaviour that the dynamic
Hercules path actually reaches, and proves the deterministic scripted-input
contract with a public synthetic fixture:

* the controller data port is never touched by the private path, so no scripted
  input can be consumed yet - recorded as an explicit not-reached disposition
  rather than implemented speculatively;
* the reached SPU traffic is configuration-only (volume/control writes and two
  register reads); no RAM transfer and no audio output requirement is reachable;
* no frame or event loop is reached: the reached loop is a served busy-poll loop
  (GPU status and timer counter read exactly one-to-one);
* a public synthetic fixture proves the scripted deterministic input contract
  (a button pattern written to the controller data port is read back
  unchanged), and a second one proves SPU configuration writes are served.

On success it emits::

    OPENRECOMP_P10_10=PASS
    OPENRECOMP_PHASE10_INPUT_SPU_FRONTIER_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_input_spu_v1.py
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_input_timer_v1 as input_timer  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_emission_v1 as emission  # noqa: E402
import p10_input_spu_frontier_v1 as frontier  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
import p10_timing_frontier_v1 as timing  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P10-10"
FEATURE_MARKER = "OPENRECOMP_PHASE10_INPUT_SPU_FRONTIER_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

EXPECTED = {
    "timer_counter_reads": 109035,
    "interrupt_port_accesses": 1,
    "controller_accesses": 0,
    "spu_events": 5,
    "spu_ram_transfers": 0,
    "input_events_capped": 65536,
    "failed": "1",
    "error": "unresolved indirect jump",
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_and_run(build_set: dict, workspace: pathlib.Path) -> tuple[str, str]:
    if workspace.exists():
        shutil.rmtree(workspace)
    comparison = bp.build_generated_host(
        lambda: build_set["files"][emission.PROGRAM_NAME],
        support_sources=(
            bp.BuildSource(emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][emission.IMAGE_NAME].encode("utf-8")),
            bp.BuildSource(emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][emission.SUPPORT_NAME].encode("utf-8")),
            bp.BuildSource(emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                           build_set["files"][emission.DRIVER_NAME].encode("utf-8")),
        ),
        config=bp.BuildConfig(fixture_id=workspace.name, smoke_test=False, run_count=2),
        workspace=workspace,
        keep_workspace=True,
    )
    statuses = [run.manifest.build_status.value for run in comparison.runs]
    executable = workspace / "run1" / "program.exe"
    completed = subprocess.run([str(executable)], capture_output=True, timeout=5400)
    return completed.stdout.decode("utf-8", "replace"), ",".join(statuses)


def scripted_input_fixture(pattern: int = 0xC1F3) -> list[int]:
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=(input_timer.JOY_DATA >> 16) & 0xFFFF)
    a.i("ori", rs=8, rt=8, imm=input_timer.JOY_DATA & 0xFFFF)
    a.i("ori", rs=0, rt=9, imm=pattern)
    a.i("sh", rs=8, rt=9, imm=0)
    a.i("lhu", rs=8, rt=10, imm=0)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def spu_config_fixture() -> list[int]:
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=0x1F80)
    a.i("ori", rs=8, rt=8, imm=0x1DB0)
    a.i("ori", rs=0, rt=9, imm=0x3FFF)
    a.i("sh", rs=8, rt=9, imm=0)
    a.i("sh", rs=8, rt=9, imm=2)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-10")
    parser.add_argument("--private-fixture",
                        default=str(ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"))
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()
    private_path = pathlib.Path(args.private_fixture)

    try:
        check("private:present", private_path.is_file(), "private fixture present")
        image = psx.ingest(private_path.read_bytes())
        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)
        pipeline = bridge.analyze(image, contract, flat)
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image.file_sha256,
        )
        result = structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
        build_set = emission.build_build_set(result, contract, flat, image.file_sha256, driver="phase10")
        stdout, build_status = build_and_run(build_set, ROOT / ".openrecomp-phase10" / "build" / "p10-10")
        check("build:status", build_status == "OK,OK", build_status)
        native = fixture_gate.parse_native(stdout)
        log = timing.parse_nonram_log(stdout)
        spu_events = [
            {
                "service": 3,
                "direction": int(parts[1]),
                "width_bits": int(parts[2]),
                "flags": int(parts[3]),
                "address": int(parts[4], 16),
                "value": int(parts[5], 16),
            }
            for parts in (
                line.split("=", 1)[1].split(",")
                for line in stdout.splitlines()
                if line.startswith("ev_spu_")
            )
        ]

        controller = frontier.classify_controller(log)
        spu_classification = frontier.classify_spu(spu_events)
        loop = frontier.classify_game_loop(controller, spu_classification)

        check("controller:not-reached", controller["controller_data_reached"] is False, "false")
        check(
            "controller:not-consumable",
            controller["scripted_input_consumable"] is False,
            "no scripted input can be consumed",
        )
        check("controller:zero-accesses", controller["class_counts"].get("controller", 0) == EXPECTED["controller_accesses"], json.dumps(controller["class_counts"], sort_keys=True))
        check(
            "controller:timer-reads",
            controller["timer_counter_reads"] == EXPECTED["timer_counter_reads"],
            str(controller["timer_counter_reads"]),
        )
        check(
            "controller:interrupt-accesses",
            controller["interrupt_port_accesses"] == EXPECTED["interrupt_port_accesses"],
            str(controller["interrupt_port_accesses"]),
        )
        check("native:input-events-capped", native.get("input_events") == str(EXPECTED["input_events_capped"]), str(native.get("input_events")))
        check("native:failed", native.get("failed") == EXPECTED["failed"], str(native.get("failed")))
        check("native:error", native.get("error") == EXPECTED["error"], str(native.get("error")))

        check("spu:event-count", spu_classification["event_count"] == EXPECTED["spu_events"], str(spu_classification["event_count"]))
        check("spu:no-ram-transfer", spu_classification["ram_transfer_accesses"] == EXPECTED["spu_ram_transfers"], str(spu_classification["ram_transfer_accesses"]))
        check("spu:no-blocked", all(not entry["blocked"] for entry in spu_classification["accesses"]), json.dumps(spu_classification["accesses"], sort_keys=True))
        check("spu:audio-not-required", spu_classification["audio_required"] is False, "false")
        check(
            "spu:classes",
            spu_classification["class_counts"] == {"spu_cd_audio": 4, "spu_control": 1},
            json.dumps(spu_classification["class_counts"], sort_keys=True),
        )
        check(
            "spu:value-classes",
            sorted({entry["value_class"] for entry in spu_classification["accesses"]})
            == ["control_enable_cd_audio_and_transfer", "volume_max", "zero"],
            json.dumps(spu_classification["accesses"], sort_keys=True),
        )
        check(
            "spu:cd-audio-volumes",
            sum(1 for entry in spu_classification["accesses"] if entry["value_class"] == "volume_max") == 2,
            json.dumps(spu_classification["accesses"], sort_keys=True),
        )

        check("loop:no-frame-loop", loop["frame_loop_reached"] is False, "false")
        check("loop:no-vsync-wait", loop["vsync_or_interrupt_wait_reached"] is False, "false")
        check("loop:busy-poll-served", loop["busy_poll_served"] is True, "true")
        check("loop:no-interrupt-progress", loop["interrupt_driven_progress_required"] is False, "false")

        requirement_record = frontier.requirements(controller, spu_classification, loop)
        check("requirements:no-new-implementation", requirement_record["implemented_at_phase10"] == [], "none")
        check(
            "requirements:scripted-input-not-reached",
            requirement_record["dispositions"][0]["disposition"] == "NOT_REACHED_BY_THE_PRIVATE_FRONTIER",
            requirement_record["dispositions"][0]["disposition"],
        )
        check(
            "requirements:spu-served",
            requirement_record["dispositions"][1]["disposition"] == "SERVED_NO_AUDIO_OUTPUT_REQUIRED",
            requirement_record["dispositions"][1]["disposition"],
        )

        # --- public synthetic fixtures ----------------------------------------
        scripted_words = scripted_input_fixture()
        scripted_image, scripted_contract, scripted_flat, scripted_result = fixture_gate.structure_fixture(scripted_words)
        scripted_set = emission.build_build_set(
            scripted_result, scripted_contract, scripted_flat, scripted_image.file_sha256, driver="phase10"
        )
        scripted_stdout, scripted_status = build_and_run(
            scripted_set, ROOT / ".openrecomp-phase10" / "build" / "p10-10-scripted-input"
        )
        check("synthetic:scripted:build", scripted_status == "OK,OK", scripted_status)
        scripted_native = fixture_gate.parse_native(scripted_stdout)
        check("synthetic:scripted:not-failed", scripted_native.get("failed") == "0", str(scripted_native.get("failed")))
        check(
            "synthetic:scripted:readback",
            scripted_native.get("register_file", {}).get("r10") == "0x0000c1f3",
            str(scripted_native.get("register_file", {}).get("r10")),
        )
        scripted_fields = timing.parse_scalar_fields(scripted_stdout)
        check("synthetic:scripted:no-denial", scripted_fields.get("denied") == "0", str(scripted_fields.get("denied")))
        scripted_spu = [
            line.split("=", 1)[1]
            for line in scripted_stdout.splitlines()
            if line.startswith("ev_spu_")
        ]
        check("synthetic:scripted:no-spu-events", scripted_spu == [], str(scripted_spu))

        spu_words = spu_config_fixture()
        spu_image, spu_contract, spu_flat, spu_result = fixture_gate.structure_fixture(spu_words)
        spu_set = emission.build_build_set(
            spu_result, spu_contract, spu_flat, spu_image.file_sha256, driver="phase10"
        )
        spu_stdout, spu_status = build_and_run(spu_set, ROOT / ".openrecomp-phase10" / "build" / "p10-10-spu")
        check("synthetic:spu:build", spu_status == "OK,OK", spu_status)
        spu_native = fixture_gate.parse_native(spu_stdout)
        check("synthetic:spu:not-failed", spu_native.get("failed") == "0", str(spu_native.get("failed")))
        check("synthetic:spu:events", spu_native.get("spu_events") == "2", str(spu_native.get("spu_events")))
        check("synthetic:spu:denied", spu_native.get("denied") == "0", str(spu_native.get("denied")))

        write_json(
            evidence / "input_spu_frontier.json",
            {
                "schema": "openrecomp-phase10-input-spu-frontier-v1",
                "stage": STAGE,
                "label": "hercules-private-fixture",
                "is_pass_criterion": False,
                "identity": image.identity(),
                "controller": controller,
                "spu": spu_classification,
                "game_loop": loop,
                "requirements": requirement_record,
                "synthetic_scripted_input": {
                    "words": [f"0x{word:08x}" for word in scripted_words],
                    "pattern": "0xc1f3",
                    "read_back": scripted_native.get("register_file", {}).get("r10"),
                    "failed": scripted_native.get("failed"),
                    "denied": scripted_fields.get("denied"),
                },
                "synthetic_spu_config": {
                    "words": [f"0x{word:08x}" for word in spu_words],
                    "spu_events": spu_native.get("spu_events"),
                    "failed": spu_native.get("failed"),
                    "denied": spu_native.get("denied"),
                },
                "limitations": [
                    "the per-device transcript prefix is capped, so input-event address histograms come from the exact non-RAM log instead",
                    "no frame loop is reached, so no frame-level observable exists yet",
                ],
            },
        )

        check("claim:native-execution-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-not-promoted", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Controller / SPU / game-loop frontier",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_10_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_10={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
