#!/usr/bin/env python3
"""OpenRecomp Phase-10 interrupt / DMA / timing frontier gate (P10-08).

The gate classifies the interrupt, DMA and timing behaviour that the private
Hercules run actually reaches, using the deterministic non-RAM access log added
at this stage:

* every non-RAM access signature is classified against the audited Phase-9 port
  ranges and accounted for: served device accesses, platform denials, or budget
  denials;
* the denial reconciliation is exact: platform denials plus budget denials equal
  the runtime's denied counter, so no denial stays unattributed (the `P10-07`
  open item of 9 unattributed denials is closed here);
* the deterministic virtual-time abstraction is recorded explicitly and proven
  by a public synthetic fixture (the counter advances by one per read and wraps
  at 16 bits), with no cycle-accuracy claim;
* the interrupt-mask read, the DMA channel-2 configuration write and the
  memory-control delay writes are classified and left fail-closed, with the
  evidence showing that none of them is proven required for progress;
* the bounded-execution limitation (the access budget bounds accesses, not
  execution) is recorded with its observed trigger.

On success it emits::

    OPENRECOMP_P10_08=PASS
    OPENRECOMP_PHASE10_TIMING_FRONTIER_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_timing_v1.py
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

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_emission_v1 as emission  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
import p10_timing_frontier_v1 as timing  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P10-08"
FEATURE_MARKER = "OPENRECOMP_PHASE10_TIMING_FRONTIER_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

EXPECTED_SIGNATURES = (
    ("0x1f801074", 16, "read", 0, 1),
    ("0x1f8010a8", 32, "write", 0, 1),
    ("0x00000000", 8, "write", 0, 1),
    ("0x1f801800", 8, "write", 0, 15),
    ("0x1f801803", 8, "read", 0, 2),
    ("0x1f801803", 8, "write", 0, 3),
    ("0x1f801020", 32, "write", 0, 2),
    ("0x1f801db8", 16, "read", 0, 1),
    ("0x1f801dba", 16, "read", 0, 1),
    ("0x1f801db0", 16, "write", 0, 1),
    ("0x1f801db2", 16, "write", 0, 1),
    ("0x1f801daa", 16, "write", 0, 1),
    ("0x1f801802", 8, "write", 0, 8),
    ("0x1f801801", 8, "write", 0, 10),
    ("0x1f801814", 32, "read", 0, 109035),
    ("0x1f801110", 32, "read", 0, 109035),
    ("0x14802000", 32, "read", 1, 1),
)

EXPECTED = {
    "signatures": 17,
    "read_cap_observations": 65536,
    "served_observations": 218112,
    "platform_denial_observations": 6,
    "budget_denials": 5,
    "denied": 11,
    "termination": "unresolved indirect jump",
    "gp1_reads": 109035,
    "timer1_reads": 109035,
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


def timer_fixture() -> list[int]:
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=0x1F80)
    a.i("ori", rs=8, rt=8, imm=0x1100)
    a.i("lw", rs=8, rt=9, imm=0)
    a.i("lw", rs=8, rt=10, imm=0)
    a.i("lw", rs=8, rt=11, imm=0)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def probe_fixture(address: int, *, is_write: bool, width_bits: int = 32) -> list[int]:
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=(address >> 16) & 0xFFFF)
    a.i("ori", rs=8, rt=8, imm=address & 0xFFFF)
    if is_write:
        a.i("ori", rs=9, rt=0, imm=1)
        a.i("sw", rs=8, rt=9, imm=0)
    else:
        if width_bits == 32:
            a.i("lw", rs=8, rt=10, imm=0)
        else:
            a.i("lhu", rs=8, rt=10, imm=0)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-08")
    parser.add_argument("--private-fixture",
                        default=str(ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"))
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()
    private_path = pathlib.Path(args.private_fixture)

    try:
        # --- the audited ranges and the timing abstraction --------------------
        check("ranges:audited", len(timing.AUDITED_RANGES) == 8, str(len(timing.AUDITED_RANGES)))
        abstraction = timing.TIMING_ABSTRACTION
        check("timing:read-driven", "read-driven" in abstraction["resolution"], abstraction["resolution"])
        check("timing:no-cycle-accuracy", abstraction["cycle_accuracy"] == "not claimed", abstraction["cycle_accuracy"])
        check("timing:no-wall-clock", abstraction["wall_clock_dependency"] == "none", abstraction["wall_clock_dependency"])

        # --- private frontier -------------------------------------------------
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
            document["runtime_composition"]["substitution_count"] == len(emission.p10_runtime.SUBSTITUTIONS),
            str(document["runtime_composition"]["substitution_count"]),
        )

        stdout, build_status = build_and_run(build_set, ROOT / ".openrecomp-phase10" / "build" / "p10-08")
        check("build:status", build_status == "OK,OK", build_status)
        native = fixture_gate.parse_native(stdout)
        log = timing.parse_nonram_log(stdout)
        fields = timing.parse_scalar_fields(stdout)
        check("native:signature-count", len(log) == EXPECTED["signatures"], str(len(log)))
        check("native:log-not-truncated", fields.get("nonram_overflow") == "0", str(fields.get("nonram_overflow")))

        observed = []
        for entry in log:
            observed.append(
                (
                    f"0x{entry['address']:08x}",
                    entry["width_bits"],
                    "write" if entry["is_write"] else "read",
                    entry["reason"],
                    entry["count"],
                )
            )
        check("native:signatures", tuple(observed) == EXPECTED_SIGNATURES, json.dumps(observed))
        check(
            "native:gpu-timer-pairing",
            dict(log[-3].items())["count"] == EXPECTED["gp1_reads"] and log[-2]["count"] == EXPECTED["timer1_reads"],
            f"{log[-3]['count']}/{log[-2]['count']}",
        )

        classification = timing.classify(log, stdout)
        check(
            "native:reconciliation",
            classification["reconciliation"]["matches"] is True,
            json.dumps(classification["reconciliation"], sort_keys=True),
        )
        check(
            "native:platform-denials",
            classification["reconciliation"]["platform_denial_observations"] == EXPECTED["platform_denial_observations"],
            str(classification["reconciliation"]["platform_denial_observations"]),
        )
        check(
            "native:budget-denials",
            classification["reconciliation"]["budget_denials"] == EXPECTED["budget_denials"],
            str(classification["reconciliation"]["budget_denials"]),
        )
        check(
            "native:denied-total",
            classification["reconciliation"]["reported_denied"] == EXPECTED["denied"],
            str(classification["reconciliation"]["reported_denied"]),
        )
        denied_classes = {entry["classification"] for entry in classification["denied"]}
        check(
            "native:denied-classes",
            denied_classes
            == {"OUTSIDE_AUDITED_RANGES", "AUDITED_INTERRUPT_BLOCKED", "AUDITED_CDROM_BLOCKED", "BUDGET_DENIED"},
            ",".join(sorted(denied_classes)),
        )
        check(
            "native:logged-budget-subset",
            classification["reconciliation"]["logged_budget_subset_of_counter"] is True,
            json.dumps(classification["reconciliation"], sort_keys=True),
        )
        check(
            "native:blocked-addresses",
            classification["blocked_addresses"] == {"0x1f801074": 1, "0x1f801801": 1},
            json.dumps(classification["blocked_addresses"], sort_keys=True),
        )
        check(
            "native:served-observations",
            classification["served_observations"] == EXPECTED["served_observations"],
            str(classification["served_observations"]),
        )
        check("native:termination", classification["first_failure"] == EXPECTED["termination"], str(classification["first_failure"]))
        check("native:budget-reached", classification["access_count"] > classification["read_budget"], f"{classification['access_count']} > {classification['read_budget']}")

        requirement_record = timing.requirements(classification)
        check(
            "requirements:no-new-implementation",
            requirement_record["implemented_at_phase10"] == [],
            "none",
        )
        check(
            "requirements:all-fail-closed",
            all(
                item.get("disposition") == "NOT_IMPLEMENTED_FAIL_CLOSED"
                for item in requirement_record["dispositions"]
                if item.get("required") is False and item["interaction"] != "corrupted pointer read"
            ),
            json.dumps(requirement_record["dispositions"], sort_keys=True)[:200],
        )
        check(
            "requirements:timer-required",
            any(item["interaction"] == "timer counter reads" and item["required"] is True for item in requirement_record["dispositions"]),
            "timer counter reads are required and already served",
        )
        check(
            "requirements:dma-not-ready",
            "VRAM" in json.dumps(requirement_record["dispositions"]),
            "the DMA disposition records the VRAM dependency",
        )

        # --- public synthetic fixtures ---------------------------------------
        timer_words = timer_fixture()
        timer_image, timer_contract, timer_flat, timer_result = fixture_gate.structure_fixture(timer_words)
        timer_set = emission.build_build_set(
            timer_result, timer_contract, timer_flat, timer_image.file_sha256, driver="phase10"
        )
        timer_stdout, timer_status = build_and_run(timer_set, ROOT / ".openrecomp-phase10" / "build" / "p10-08-timer")
        check("synthetic:timer:build", timer_status == "OK,OK", timer_status)
        timer_native = fixture_gate.parse_native(timer_stdout)
        check("synthetic:timer:not-failed", timer_native.get("failed") == "0", str(timer_native.get("failed")))
        registers = timer_native.get("register_file", {})
        first = int(registers.get("r09", "0"), 16)
        second = int(registers.get("r10", "0"), 16)
        third = int(registers.get("r11", "0"), 16)
        check(
            "synthetic:timer:monotone",
            second == (first + 1) & 0xFFFF and third == (second + 1) & 0xFFFF,
            f"{first:#06x} {second:#06x} {third:#06x}",
        )
        check("synthetic:timer:first-tick", first == 0, f"{first:#06x}")
        timer_transcript = timing.parse_scalar_fields(timer_stdout)
        check("synthetic:timer:no-denial", timer_transcript.get("denied") == "0", str(timer_transcript.get("denied")))

        negatives = []
        for name, address, is_write in (
            ("interrupt-mask-read", 0x1F801074, False),
            ("dma-channel2-write", 0x1F8010A8, True),
            ("memory-control-delay-write", 0x1F801020, True),
        ):
            words = probe_fixture(address, is_write=is_write)
            probe_image, probe_contract, probe_flat, probe_result = fixture_gate.structure_fixture(words)
            probe_set = emission.build_build_set(
                probe_result, probe_contract, probe_flat, probe_image.file_sha256, driver="phase10"
            )
            probe_stdout, probe_status = build_and_run(
                probe_set, ROOT / ".openrecomp-phase10" / "build" / f"p10-08-{name}"
            )
            check(f"synthetic:{name}:build", probe_status == "OK,OK", probe_status)
            probe_native = fixture_gate.parse_native(probe_stdout)
            check(f"synthetic:{name}:fail-closed", probe_native.get("failed") == "1", str(probe_native.get("failed")))
            check(f"synthetic:{name}:denied", probe_native.get("denied") == "1", str(probe_native.get("denied")))
            negatives.append(
                {
                    "name": name,
                    "address": f"0x{address:08x}",
                    "direction": "write" if is_write else "read",
                    "failed": probe_native.get("failed"),
                    "denied": probe_native.get("denied"),
                    "error": probe_native.get("error"),
                }
            )

        write_json(
            evidence / "timing_frontier.json",
            {
                "schema": "openrecomp-phase10-timing-frontier-v1",
                "stage": STAGE,
                "label": "hercules-private-fixture",
                "is_pass_criterion": False,
                "identity": image.identity(),
                "runtime_composition": document["runtime_composition"],
                "nonram_log_capacity": emission.p10_runtime.NONRAM_LOG_CAPACITY,
                "classification": classification,
                "requirements": requirement_record,
                "synthetic_timer_fixture": {
                    "words": [f"0x{word:08x}" for word in timer_words],
                    "ticks_observed": [first, second, third],
                    "failed": timer_native.get("failed"),
                    "denied": timer_transcript.get("denied"),
                },
                "synthetic_negatives": negatives,
                "bounded_execution": {
                    "access_budget": classification["read_budget"],
                    "access_count": classification["access_count"],
                    "budget_denials": classification["reconciliation"]["budget_denials"],
                    "limitation": (
                        "the deterministic access budget bounds memory accesses, not execution: a "
                        "post-truncation guest loop that performs no memory access cannot be "
                        "interrupted. Observed as a hang while probing ordering at a smaller budget "
                        "during P10-07 reconnaissance. Every official gate therefore runs with the "
                        "default budget and a bounded host timeout."
                    ),
                    "hardening_owner": "P10-12",
                },
                "timing_abstraction": abstraction,
            },
        )

        check("claim:native-execution-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-not-promoted", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except timing.TimingFrontierError as exc:
        RESULTS.append({"check": "gate:timing-error", "status": "FAIL", "detail": f"{exc.code}: {exc.detail}"})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Interrupt / DMA / timing frontier",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_08_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_08={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
