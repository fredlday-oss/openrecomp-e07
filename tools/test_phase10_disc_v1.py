#!/usr/bin/env python3
"""OpenRecomp Phase-10 disc / CD-ROM / streaming frontier gate (P10-09).

The gate uses the already verified CUE as the authoritative private disc source
and classifies the CD-ROM behaviour that the dynamic Hercules path actually
reaches:

* the disc identity is re-verified against the `P10-00` record (CUE and BIN
  identities discovered from the fixture directory, never assumed; track
  layout; ISO9660 boot relationship; executable/disc consistency);
* the deterministic CD-ROM register transcript is classified exactly by
  register and direction, and every command byte is classified with the
  audited Phase-9 CD-ROM command table;
* the disc data path is assessed: whether any sector read, ISO9660 access, file
  open/read, overlay load, resource load, streaming or XA operation is reached;
* the requirement record follows the evidence: register-level traffic is
  served by the Phase-9 boundary, unknown commands fail closed, and no disc
  data behaviour is implemented because none is reached;
* public synthetic fixtures prove a known command is served, an unknown command
  fails closed, and a data-port read returns the boundary's contract stub
  (never disc bytes).

On success it emits::

    OPENRECOMP_P10_09=PASS
    OPENRECOMP_PHASE10_DISC_FRONTIER_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_disc_v1.py
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

import p9_cdrom_boundary_v1 as cdrom  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_disc_frontier_v1 as disc  # noqa: E402
import p10_emission_v1 as emission  # noqa: E402
import p10_fixture_identity_v1 as fixture  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P10-09"
FEATURE_MARKER = "OPENRECOMP_PHASE10_DISC_FRONTIER_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

EXPECTED_IDENTITY = {
    "executable_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
    "executable_size": 129024,
    "cue_sha256": "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2",
    "cue_size": 101,
    "bin_sha256": "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365",
    "bin_size": 409452624,
    "boot_target": "SLUS_005.29",
    "track_type": "MODE2/2352",
    "volume_space_size_sectors": 174087,
    "root_extent_lba": 22,
}

EXPECTED = {
    "events": 38,
    "index_status_writes": 15,
    "parameter_writes": 8,
    "command_writes": 10,
    "command_known": 9,
    "command_unknown": 1,
    "interrupt_enable_reads": 2,
    "interrupt_enable_writes": 3,
    "unknown_command": 0x80,
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


def cdrom_write_fixture(value: int, register_offset: int) -> list[int]:
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=0x1F80)
    a.i("ori", rs=8, rt=8, imm=0x1800 + register_offset)
    a.i("ori", rs=0, rt=9, imm=value)
    a.i("sb", rs=8, rt=9, imm=0)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def cdrom_read_fixture(register_offset: int) -> list[int]:
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=0x1F80)
    a.i("ori", rs=8, rt=8, imm=0x1800 + register_offset)
    a.i("lbu", rs=8, rt=10, imm=0)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-09")
    parser.add_argument("--fixture-root", default=str(FIXTURE_ROOT))
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()
    fixture_root = pathlib.Path(args.fixture_root)

    try:
        # --- disc identity re-verification (CUE is authoritative) -------------
        check("fixture:directory", fixture_root.is_dir(), "private fixture directory present")
        identity = fixture.build_identity(fixture_root)
        executable = identity["executable"]
        cue = identity["disc"]["cue"]
        bins = identity["disc"]["bins"]
        volume = identity["disc"]["volume"]
        system_cnf = identity["system_cnf"]
        check("fixture:executable-sha", executable["sha256"] == EXPECTED_IDENTITY["executable_sha256"], executable["sha256"])
        check("fixture:executable-size", executable["size"] == EXPECTED_IDENTITY["executable_size"], str(executable["size"]))
        check("fixture:cue-sha", cue["cue_sha256"] == EXPECTED_IDENTITY["cue_sha256"], cue["cue_sha256"])
        check("fixture:cue-size", cue["cue_size"] == EXPECTED_IDENTITY["cue_size"], str(cue["cue_size"]))
        check("fixture:bin-sha", bins[0]["sha256"] == EXPECTED_IDENTITY["bin_sha256"], bins[0]["sha256"])
        check("fixture:bin-size", bins[0]["size"] == EXPECTED_IDENTITY["bin_size"], str(bins[0]["size"]))
        check("fixture:track-type", cue["tracks"][0]["type"] == EXPECTED_IDENTITY["track_type"], cue["tracks"][0]["type"])
        check("fixture:index1", cue["tracks"][0]["index1_msf"] == [0, 0, 0], str(cue["tracks"][0]["index1_msf"]))
        check("fixture:volume-size", volume["volume_space_size_sectors"] == EXPECTED_IDENTITY["volume_space_size_sectors"], str(volume["volume_space_size_sectors"]))
        check("fixture:root-extent", volume["root_extent_lba"] == EXPECTED_IDENTITY["root_extent_lba"], str(volume["root_extent_lba"]))
        check("fixture:boot-target", system_cnf["boot_target"] == EXPECTED_IDENTITY["boot_target"], system_cnf["boot_target"])
        check(
            "fixture:boot-extent-matches-executable",
            system_cnf["boot_extent_sha256"] == EXPECTED_IDENTITY["executable_sha256"],
            system_cnf["boot_extent_sha256"],
        )

        # --- audited command table -------------------------------------------
        check("commands:documented-table", len(cdrom.COMMAND_CLASSES) == 32, str(len(cdrom.COMMAND_CLASSES)))
        check("commands:0x80-unknown", cdrom.COMMAND_CLASSES.get(0x80) is None, "0x80 not documented")
        check("commands:read-command", cdrom.COMMAND_CLASSES[0x06] == "READ_N", cdrom.COMMAND_CLASSES[0x06])

        # --- private dynamic frontier ----------------------------------------
        private_path = fixture_root / "SLUS_005.29"
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
        stdout, build_status = build_and_run(build_set, ROOT / ".openrecomp-phase10" / "build" / "p10-09")
        check("build:status", build_status == "OK,OK", build_status)
        native = fixture_gate.parse_native(stdout)
        cdrom_events = disc.parse_events(stdout) if hasattr(disc, "parse_events") else None
        if cdrom_events is None:
            from tools import test_phase10_gpu_v1 as gpu_gate  # local import to avoid a cycle
            cdrom_events = gpu_gate.frontier.parse_events(stdout, "cdrom")
        check("native:cdrom-events", len(cdrom_events) == EXPECTED["events"], str(len(cdrom_events)))
        classification = disc.classify_events(cdrom_events)
        registers = classification["register_histogram"]
        check(
            "native:index-status-writes",
            registers.get("INDEX_STATUS", {}).get("write") == EXPECTED["index_status_writes"],
            json.dumps(registers, sort_keys=True),
        )
        check(
            "native:parameter-writes",
            registers.get("PARAMETER", {}).get("write") == EXPECTED["parameter_writes"],
            json.dumps(registers, sort_keys=True),
        )
        check(
            "native:command-writes",
            registers.get("COMMAND", {}).get("write") == EXPECTED["command_writes"],
            json.dumps(registers, sort_keys=True),
        )
        check(
            "native:interrupt-enable",
            registers.get("INTERRUPT_ENABLE", {}).get("read") == EXPECTED["interrupt_enable_reads"]
            and registers.get("INTERRUPT_ENABLE", {}).get("write") == EXPECTED["interrupt_enable_writes"],
            json.dumps(registers, sort_keys=True),
        )
        command = classification["command_classification"]
        check("native:command-total", command["command_count"] == EXPECTED["command_writes"], str(command["command_count"]))
        check(
            "native:unknown-command",
            command["unknown_commands"] == [EXPECTED["unknown_command"]],
            str(command["unknown_commands"]),
        )
        check("native:known-command-count", command["command_count"] - command["unknown_command_count"] == EXPECTED["command_known"], str(command["command_count"]))
        check("native:blockers", len(classification["blockers"]) == 1, json.dumps(classification["blockers"], sort_keys=True))
        check("native:data-path-not-reached", classification["data_path_reached"] is False, json.dumps(classification["data_path"], sort_keys=True))
        check("native:disc-image-unused", classification["disc_image_used"] == "none", classification["disc_image_used"])
        check("native:not-failed-on-cdrom", native.get("failed") == "1" and native.get("error") == "unresolved indirect jump", str(native.get("error")))

        requirement_record = disc.requirements(classification)
        check("requirements:no-new-implementation", requirement_record["implemented_at_phase10"] == [], "none")
        check("requirements:data-path-not-implemented", requirement_record["data_path_implemented"] is False, "false")
        check(
            "requirements:unknown-fail-closed",
            requirement_record["unknown_command_disposition"] == "NOT_IMPLEMENTED_FAIL_CLOSED",
            requirement_record["unknown_command_disposition"],
        )
        check(
            "requirements:cue-role",
            "authoritative disc entry point" in requirement_record["cue_role"],
            requirement_record["cue_role"],
        )

        # --- public synthetic fixtures ----------------------------------------
        synthetics = []
        for name, words, expect_failed in (
            ("known-command-setmode", cdrom_write_fixture(0x0E, 1), "0"),
            ("known-command-readn", cdrom_write_fixture(0x06, 1), "0"),
            ("unknown-command-0x80", cdrom_write_fixture(0x80, 1), "1"),
        ):
            synthetic_image, synthetic_contract, synthetic_flat, synthetic_result = fixture_gate.structure_fixture(words)
            synthetic_set = emission.build_build_set(
                synthetic_result, synthetic_contract, synthetic_flat, synthetic_image.file_sha256, driver="phase10"
            )
            synthetic_stdout, synthetic_status = build_and_run(
                synthetic_set, ROOT / ".openrecomp-phase10" / "build" / f"p10-09-{name}"
            )
            check(f"synthetic:{name}:build", synthetic_status == "OK,OK", synthetic_status)
            synthetic_native = fixture_gate.parse_native(synthetic_stdout)
            check(f"synthetic:{name}:failed", synthetic_native.get("failed") == expect_failed, str(synthetic_native.get("failed")))
            synthetics.append(
                {
                    "name": name,
                    "failed": synthetic_native.get("failed"),
                    "error": synthetic_native.get("error"),
                    "denied": synthetic_native.get("denied"),
                }
            )
        # data-port read returns the boundary contract stub, never disc bytes
        read_words = cdrom_read_fixture(2)
        read_image, read_contract, read_flat, read_result = fixture_gate.structure_fixture(read_words)
        read_set = emission.build_build_set(
            read_result, read_contract, read_flat, read_image.file_sha256, driver="phase10"
        )
        read_stdout, read_status = build_and_run(read_set, ROOT / ".openrecomp-phase10" / "build" / "p10-09-data-read")
        check("synthetic:data-read:build", read_status == "OK,OK", read_status)
        read_native = fixture_gate.parse_native(read_stdout)
        check("synthetic:data-read:not-failed", read_native.get("failed") == "0", str(read_native.get("failed")))
        check(
            "synthetic:data-read:stub-value",
            read_native.get("register_file", {}).get("r10") == "0x00000000",
            str(read_native.get("register_file", {}).get("r10")),
        )
        check("synthetic:data-read:no-disc-bytes", read_native.get("denied") == "0", str(read_native.get("denied")))

        write_json(
            evidence / "disc_frontier.json",
            {
                "schema": "openrecomp-phase10-disc-frontier-v1",
                "stage": STAGE,
                "label": "hercules-private-fixture",
                "is_pass_criterion": False,
                "disc_identity": {
                    "cue": cue,
                    "bins": bins,
                    "volume": volume,
                    "system_cnf": system_cnf,
                    "executable": executable,
                },
                "disc_identity_sha256": fixture.identity_digest(identity),
                "classification": classification,
                "requirements": requirement_record,
                "synthetic_fixtures": synthetics,
                "synthetic_data_read": {
                    "words": [f"0x{word:08x}" for word in read_words],
                    "failed": read_native.get("failed"),
                    "register_r10": read_native.get("register_file", {}).get("r10"),
                    "denied": read_native.get("denied"),
                },
                "prohibitions": [
                    "no disc bytes, sectors, file contents or reconstructed disc data are read or committed",
                    "the CUE is never hard-coded: it is discovered from the fixture directory",
                    "no host filesystem behaviour is substituted for PS1 CD behaviour",
                    "unknown CD-ROM commands remain fail-closed",
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
        "stage_name": "Disc / CD-ROM / streaming frontier",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_09_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_09={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
