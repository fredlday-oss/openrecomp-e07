#!/usr/bin/env python3
"""OpenRecomp Phase-10 GPU command execution frontier gate (P10-07).

The gate advances the GPU frontier from the P10-06 dynamic discovery:

* the Phase-10 observable transcript is captured from a deterministic run of the
  private executable (default access budget, additive Phase-10 driver);
* reads and writes are separated before classification, so a status value is
  never mistaken for a command;
* every GPU access class is recorded exactly: port, direction, width, value
  class, unknown-command count, blocked events, transfer classes, DMA-controller
  traffic and the explicit absence of modelled VRAM state;
* the audited Phase-9 GPU boundary is the single source of truth for the
  command-class table (independent classifier vectors are re-checked here);
* public synthetic fixtures prove that a known command is served and recorded
  and that an unknown command fails closed;
* the status-read contract stub is aligned with the audited Phase-9 boundary
  constant and justified by an A/B comparison showing that the recorded access
  traffic is identical with and without it;
* the new frontier and the first remaining blocker are recorded explicitly,
  including the bounded-execution limitation discovered while probing ordering.

On success it emits::

    OPENRECOMP_P10_07=PASS
    OPENRECOMP_PHASE10_GPU_FRONTIER_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_gpu_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
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

import p9_gpu_boundary_v1 as gpu  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_emission_v1 as emission  # noqa: E402
import p10_gpu_frontier_v1 as frontier  # noqa: E402
import p10_runtime_v1 as runtime  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P10-07"
FEATURE_MARKER = "OPENRECOMP_PHASE10_GPU_FRONTIER_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

P10_05_RECORD = ".openrecomp-phase10/evidence/P10-05/native_entry.json"
P10_05_RECORD_SHA256 = "ef7b834293e4e5ff1067c78154ccbbeac218276bea1375000bd380e3cb6c05e9"

EXPECTED = {
    "gpu_events": runtime.EVENT_CAPACITY,
    "gpu_reads": runtime.EVENT_CAPACITY,
    "gpu_writes": 0,
    "unknown_commands": 0,
    "blocked_gpu_events": 0,
    "denied": 11,
    "status_stub": f"0x{runtime.GPU_READ_STUB:08x}",
    "termination": "UNRESOLVED_INDIRECT_JUMP",
    "budget_reached": True,
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


def build_and_run(build_set: dict, workspace: pathlib.Path, *, arguments: tuple[str, ...] = ()) -> tuple[str, str]:
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
    completed = subprocess.run([str(executable), *arguments], capture_output=True, timeout=5400)
    return completed.stdout.decode("utf-8", "replace"), ",".join(statuses)


def synthetic_words(command: int, *, read_status: bool) -> list[int]:
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=0x1F80)
    a.i("ori", rs=8, rt=8, imm=0x1810)
    a.i("lui", rt=9, imm=(command >> 16) & 0xFFFF)
    a.i("ori", rs=9, rt=9, imm=command & 0xFFFF)
    a.i("sw", rs=8, rt=9, imm=0)
    if read_status:
        a.i("ori", rs=8, rt=8, imm=0x4)
        a.i("lw", rs=8, rt=10, imm=0)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-07")
    parser.add_argument("--private-fixture",
                        default=str(ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"))
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()
    private_path = pathlib.Path(args.private_fixture)

    try:
        # --- independent classifier vectors (audited Phase-9 boundary) --------
        classifier_vector = {
            "gp0_known": gpu.classify_gp0(0x28000000),
            "gp0_transfer": gpu.classify_gp0(0xA0000000),
            "gp0_unknown": gpu.classify_gp0(0x1F000000),
            "gp1_known": gpu.classify_gp1(0x00000000),
            "gp1_display": gpu.classify_gp1(0x08000000),
            "gp1_unknown": gpu.classify_gp1(0x1F000000),
        }
        check("vectors:gp0-polygon", classifier_vector["gp0_known"]["class"] == "POLYGON", str(classifier_vector["gp0_known"]))
        check("vectors:gp0-transfer", classifier_vector["gp0_transfer"]["class"] == "CPU_TO_VRAM_COPY", str(classifier_vector["gp0_transfer"]))
        check("vectors:gp0-unknown", classifier_vector["gp0_unknown"]["known"] is False, str(classifier_vector["gp0_unknown"]))
        check("vectors:gp1-reset", classifier_vector["gp1_known"]["class"] == "RESET_GPU", str(classifier_vector["gp1_known"]))
        check("vectors:gp1-unknown", classifier_vector["gp1_unknown"]["known"] is False, str(classifier_vector["gp1_unknown"]))
        check(
            "vectors:transfer-set",
            frontier.TRANSFER_CLASSES == {"CPU_TO_VRAM_COPY", "VRAM_TO_VRAM_COPY", "VRAM_TO_CPU_COPY"},
            ",".join(sorted(frontier.TRANSFER_CLASSES)),
        )
        check(
            "vectors:stub-matches-boundary",
            runtime.GPU_READ_STUB == gpu.GPUSTAT_STUB,
            f"0x{runtime.GPU_READ_STUB:08x}",
        )

        # --- private frontier transcript --------------------------------------
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
        document = emission.emission_document(build_set)
        check(
            "emission:runtime-substitutions",
            document["runtime_composition"]["substitution_count"] == len(runtime.SUBSTITUTIONS),
            str(document["runtime_composition"]["substitution_count"]),
        )
        check(
            "emission:gpu-stub-exposed",
            document["gpu_status_read_stub"] == EXPECTED["status_stub"],
            document["gpu_status_read_stub"],
        )
        check(
            "emission:event-capacity",
            document["event_transcript_capacity"] == runtime.EVENT_CAPACITY,
            str(document["event_transcript_capacity"]),
        )

        stdout, build_status = build_and_run(build_set, ROOT / ".openrecomp-phase10" / "build" / "p10-07")
        check("build:status", build_status == "OK,OK", build_status)
        native = fixture_gate.parse_native(stdout)
        gpu_events = frontier.parse_events(stdout, "gpu")
        input_events = frontier.parse_events(stdout, "input")
        cdrom_events = frontier.parse_events(stdout, "cdrom")
        spu_events = frontier.parse_events(stdout, "spu")
        transcript = frontier.classify_gpu_events(gpu_events)

        check("native:gpu-events", transcript["event_count"] == EXPECTED["gpu_events"], str(transcript["event_count"]))
        check("native:gpu-reads", transcript["reads"] == EXPECTED["gpu_reads"], str(transcript["reads"]))
        check("native:gpu-writes", transcript["writes"] == EXPECTED["gpu_writes"], str(transcript["writes"]))
        check("native:no-gp0-writes", transcript["gp0_writes"] == 0, str(transcript["gp0_writes"]))
        check("native:no-gp1-writes", transcript["gp1_writes"] == 0, str(transcript["gp1_writes"]))
        check("native:no-unknown-commands", transcript["unknown_command_count"] == EXPECTED["unknown_commands"], str(transcript["unknown_command_count"]))
        check("native:no-blocked-gpu-events", transcript["blocked_event_count"] == EXPECTED["blocked_gpu_events"], str(transcript["blocked_event_count"]))
        check(
            "native:gpu-address",
            transcript["address_histogram"] == {"0x1f801814": EXPECTED["gpu_reads"]},
            json.dumps(transcript["address_histogram"], sort_keys=True),
        )
        check("native:gpu-width", transcript["width_histogram"] == {"32": EXPECTED["gpu_reads"]}, json.dumps(transcript["width_histogram"], sort_keys=True))
        check(
            "native:status-value",
            transcript["status_read_values"] == {EXPECTED["status_stub"]: EXPECTED["gpu_reads"]},
            json.dumps(transcript["status_read_values"], sort_keys=True),
        )
        check(
            "native:empty-write-classes",
            transcript["command_class_histogram"] == {} and transcript["distinct_write_values"] == 0,
            json.dumps(transcript["command_class_histogram"], sort_keys=True),
        )
        check("native:no-transfer-class", transcript["transfer_class_count"] == 0, str(transcript["transfer_class_count"]))
        check("native:dma-not-observed", transcript["dma_controller_traffic"] == "not_observed", transcript["dma_controller_traffic"])
        check("native:vram-not-modelled", transcript["vram_state"] == "not_modelled_by_the_phase9_boundary", transcript["vram_state"])
        check("native:no-provenance", "not observable" in transcript["provenance"], transcript["provenance"])
        check("native:denied", native.get("denied") == str(EXPECTED["denied"]), str(native.get("denied")))
        check("native:termination", (native.get("error") or "") == "unresolved indirect jump", str(native.get("error")))
        check("native:budget-reached", int(native.get("p10_budget_denials", "0")) > 0, str(native.get("p10_budget_denials")))
        check("native:first-failure", native.get("failed") == "1", str(native.get("failed")))
        check("native:accessible-stub-value", native.get("p10_access_budget") == "2000000", str(native.get("p10_access_budget")))
        check("native:no-spu-growth", len(spu_events) == 5, str(len(spu_events)))
        check("native:no-cdrom-growth", len(cdrom_events) == 38, str(len(cdrom_events)))

        denial_attribution = {
            "input_blocker_events": sum(1 for event in input_events if event["flags"] == frontier.FLAG_BLOCKER),
            "cdrom_blocker_events": sum(1 for event in cdrom_events if event["flags"] == frontier.FLAG_BLOCKER),
            "spu_blocker_events": sum(1 for event in spu_events if event["flags"] == frontier.FLAG_BLOCKER),
            "gpu_blocker_events": transcript["blocked_event_count"],
        }
        denial_attribution["recorded_blocker_total"] = sum(denial_attribution.values())
        denial_attribution["unrecorded_denials"] = EXPECTED["denied"] - denial_attribution["recorded_blocker_total"]
        check(
            "native:denial-attribution",
            denial_attribution["recorded_blocker_total"] <= EXPECTED["denied"],
            json.dumps(denial_attribution, sort_keys=True),
        )
        check("native:gpu-denials", denial_attribution["gpu_blocker_events"] == 0, str(denial_attribution["gpu_blocker_events"]))

        # --- A/B status-stub experiment ---------------------------------------
        record_path = ROOT / P10_05_RECORD
        check("ab:record-present", record_path.is_file(), P10_05_RECORD)
        record_bytes = record_path.read_bytes()
        check(
            "ab:record-identity",
            hashlib.sha256(record_bytes).hexdigest() == P10_05_RECORD_SHA256,
            hashlib.sha256(record_bytes).hexdigest(),
        )
        without_stub = json.loads(record_bytes.decode("utf-8"))["execution"]
        with_stub = {
            "reads": int(native.get("reads", "0")),
            "writes": int(native.get("writes", "0")),
            "denied": int(native.get("denied", "0")),
            "access_count": int(native.get("p10_access_count", "0")),
            "budget_denials": int(native.get("p10_budget_denials", "0")),
            "error": native.get("error"),
        }
        experiment = frontier.stub_ab_experiment(without_stub, with_stub)
        check(
            "ab:access-traffic-identical",
            experiment["access_traffic_identical"] is True,
            json.dumps(experiment["differences"], sort_keys=True),
        )
        check("ab:no-error-difference", "error" not in experiment["differences"], json.dumps(experiment["differences"], sort_keys=True))

        # --- synthetic native fixtures ----------------------------------------
        negatives = []
        positives = []
        for name, command, read_status, expect_failed in (
            ("known-gp0-nop", 0x00000000, True, "0"),
            ("known-gp0-polygon", 0x28000000, True, "0"),
            ("unknown-gp0", 0x1F000000, False, "1"),
        ):
            words = synthetic_words(command, read_status=read_status)
            synthetic_image, synthetic_contract, synthetic_flat, synthetic_result = fixture_gate.structure_fixture(words)
            synthetic_set = emission.build_build_set(
                synthetic_result, synthetic_contract, synthetic_flat, synthetic_image.file_sha256, driver="phase10"
            )
            synthetic_stdout, synthetic_status = build_and_run(
                synthetic_set, ROOT / ".openrecomp-phase10" / "build" / f"p10-07-{name}"
            )
            check(f"synthetic:{name}:build", synthetic_status == "OK,OK", synthetic_status)
            synthetic_native = fixture_gate.parse_native(synthetic_stdout)
            check(f"synthetic:{name}:failed", synthetic_native.get("failed") == expect_failed, str(synthetic_native.get("failed")))
            synthetic_events = frontier.parse_events(synthetic_stdout, "gpu")
            synthetic_transcript = frontier.classify_gpu_events(synthetic_events)
            record = {
                "name": name,
                "failed": synthetic_native.get("failed"),
                "error": synthetic_native.get("error"),
                "denied": synthetic_native.get("denied"),
                "gpu_events": synthetic_transcript["event_count"],
                "writes": synthetic_transcript["writes"],
                "reads": synthetic_transcript["reads"],
                "histogram": synthetic_transcript["command_class_histogram"],
                "unknown": synthetic_transcript["unknown_command_count"],
            }
            if expect_failed == "1":
                check(f"synthetic:{name}:denied", synthetic_native.get("denied") == "1", str(synthetic_native.get("denied")))
                check(f"synthetic:{name}:blocked", synthetic_transcript["blocked_event_count"] == 1, str(synthetic_transcript["blocked_event_count"]))
                check(f"synthetic:{name}:unknown", synthetic_transcript["unknown_command_count"] == 1, str(synthetic_transcript["unknown_command_count"]))
                negatives.append(record)
            else:
                check(f"synthetic:{name}:denied", synthetic_native.get("denied") == "0", str(synthetic_native.get("denied")))
                check(f"synthetic:{name}:write-class", synthetic_transcript["writes"] == 1, str(synthetic_transcript["writes"]))
                check(
                    f"synthetic:{name}:class",
                    synthetic_transcript["command_class_histogram"]
                    == {gpu.classify_gp0(command)["class"]: 1},
                    json.dumps(synthetic_transcript["command_class_histogram"], sort_keys=True),
                )
                positives.append(record)

        write_json(
            evidence / "gpu_frontier.json",
            {
                "schema": "openrecomp-phase10-gpu-frontier-v1",
                "stage": STAGE,
                "label": "hercules-private-fixture",
                "is_pass_criterion": False,
                "identity": image.identity(),
                "runtime_composition": document["runtime_composition"],
                "gpu_status_read_stub": document["gpu_status_read_stub"],
                "event_transcript_capacity": document["event_transcript_capacity"],
                "phase9_event_transcript_capacity": document["phase9_event_transcript_capacity"],
                "transcript": {
                    key: value for key, value in transcript.items() if key != "status_read_values"
                },
                "status_reads": transcript["status_read_values"],
                "denial_attribution": denial_attribution,
                "classifier_vectors": classifier_vector,
                "stub_ab_experiment": experiment,
                "synthetic_positive": positives,
                "synthetic_negative": negatives,
                "implemented_subset": [
                    {
                        "operation": "GP1 status read (0x1f801814 read)",
                        "behaviour": "returns the audited Phase-9 boundary contract stub",
                        "stub_value": document["gpu_status_read_stub"],
                        "hardware_accuracy": "contract stub, not hardware accurate",
                        "justification": "the frozen Phase-9 runtime returned 0, contradicting its own audited boundary constant; the A/B comparison shows the recorded access traffic is identical either way",
                    }
                ],
                "not_implemented": [
                    "GP0 command execution or VRAM state",
                    "GP1 display/DMA/timer control state",
                    "any rendering, framebuffer or VRAM digest",
                    "any DMA-controller behaviour",
                ],
                "new_frontier": {
                    "gpu_command_stream_reached": False,
                    "gpu_operations_reached": "GP1 status polling only",
                    "gpu_side_blocker": None,
                    "first_recorded_failure": "executed unresolved indirect jump",
                    "budget_reached": True,
                    "first_remaining_blocker": (
                        "the executed unresolved indirect jump (control flow), which precedes any "
                        "GPU command write; the GPU is not the blocker"
                    ),
                    "milestone_c_established": False,
                    "milestone_statement": (
                        "GP1 status polling is reached and served, but no GP0/GP1 command stream is "
                        "reached, so milestone C is NOT established"
                    ),
                },
                "limitations": [
                    transcript["provenance"],
                    "per-device transcripts are printed as separate blocks, so cross-device ordering is not observable",
                    "the transcript is capped at the configured capacity and the GPU/controller streams saturate it",
                    "the deterministic access budget bounds memory accesses, not execution: a guest loop that performs no memory access after truncation cannot be interrupted (observed as a hang while probing ordering at a smaller budget)",
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
        "stage_name": "GPU command execution frontier",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_07_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_07={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
