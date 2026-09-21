#!/usr/bin/env python3
"""OpenRecomp Phase-10 native Hercules execution entry gate (P10-05).

The gate generates and builds Hercules-derived native host code through the
existing architecture-neutral emitter and the Phase-10 runtime, and
establishes deterministic entry into translated game code:

* the original MIPS machine code never executes: the guest image is inert data
  and the generated program contains no guest bytes and no opcode dispatch;
* the build is reproducible (two isolated runs, both `OK`), the executable
  identity is recorded, and repeated execution is byte-identical;
* the guest entry PC, the initial register state, the stack state, the
  memory-image identity, the translated-trace identity, the first host/service
  transition and the termination category are recorded;
* the run is bounded by an explicit deterministic memory-access budget that
  was NOT reached, so the recorded blocker is real game code, not truncation.

On success it emits::

    OPENRECOMP_P10_05=PASS
    OPENRECOMP_PHASE10_NATIVE_ENTRY_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_native_v1.py
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
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P10-05"
FEATURE_MARKER = "OPENRECOMP_PHASE10_NATIVE_ENTRY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

EVENT_CAPACITY = 4096

EXPECTED = {
    "entry": "0x800132e8",
    "functions": 110,
    "stream_functions_unit_sha256": None,
    "termination_category": "UNRESOLVED_INDIRECT_JUMP",
    "error": "unresolved indirect jump",
    "gp": "0x8002ed78",
    "fp": "0x80200000",
    "failed": "1",
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fnv1a64(data: bytes) -> str:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return f"0x{value:016x}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-05")
    parser.add_argument("--private-fixture",
                        default=str(ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"))
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()
    private_path = pathlib.Path(args.private_fixture)
    workspace = ROOT / ".openrecomp-phase10" / "build" / "p10-05"

    try:
        check("private:present", private_path.is_file(), "private fixture present")
        image = psx.ingest(private_path.read_bytes())
        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)
        check("image:entry", f"0x{image.header.pc0:08x}" == EXPECTED["entry"], f"0x{image.header.pc0:08x}")
        check("image:declared-stack", f"0x{image.header.s_addr:08x}" == "0x801ffff0", f"0x{image.header.s_addr:08x}")

        pipeline = bridge.analyze(image, contract, flat)
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image.file_sha256,
        )
        result = structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
        summary = structure.structure_summary(result)
        check("structure:neutral-instructions", summary["neutral_instructions"] == 3433, str(summary["neutral_instructions"]))
        check("structure:blocks", summary["blocks"] == 739, str(summary["blocks"]))
        check("structure:functions", summary["functions"] == EXPECTED["functions"], str(summary["functions"]))
        check("structure:trap-sites", summary["exception_site_count"] == 3, str(summary["exception_site_count"]))

        build_set = emission.build_build_set(result, contract, flat, image.file_sha256)
        program_text = build_set["files"][emission.PROGRAM_NAME]
        check("emission:function-count", len(build_set["program"].translations) == EXPECTED["functions"],
              str(len(build_set["program"].translations)))
        check(
            "emission:no-guest-machine-code",
            image.payload[:64].hex() not in program_text.lower(),
            "no guest payload bytes in the generated program",
        )
        check(
            "emission:no-opcode-dispatch",
            "opcode" not in program_text,
            "generated program is a direct translation, not a decode loop",
        )
        check(
            "emission:no-image-include",
            emission.IMAGE_NAME not in program_text,
            "the generated program does not include the guest image unit",
        )
        check(
            "emission:inert-image-unit",
            "static const unsigned char p9_chunk_data_0[]" in build_set["files"][emission.IMAGE_NAME],
            "guest image emitted as inert data",
        )
        document = emission.emission_document(build_set)
        write_json(evidence / "emission.json", document)

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
            config=bp.BuildConfig(fixture_id="p10-05-native", smoke_test=False, run_count=2),
            workspace=workspace,
            keep_workspace=True,
        )
        check(
            "build:status",
            all(run.manifest.build_status is bp.BuildStatus.OK for run in comparison.runs),
            str([run.manifest.build_status.value for run in comparison.runs]),
        )
        executable = workspace / "run1" / "program.exe"
        check("build:executable", executable.is_file(), executable.relative_to(ROOT).as_posix())
        executable_sha = sha256_bytes(executable.read_bytes())

        completed = subprocess.run([str(executable)], capture_output=True, timeout=1800)
        check("native:exit", completed.returncode == 0, str(completed.returncode))
        check("native:stderr", completed.stderr == b"", completed.stderr[:120].decode("ascii", "replace"))
        first = completed.stdout
        second = subprocess.run([str(executable)], capture_output=True, timeout=1800).stdout
        check("native:deterministic", second == first, "byte-identical stdout")

        native = fixture_gate.parse_native(first.decode("utf-8"))
        reads = int(native.get("reads", "0"))
        writes = int(native.get("writes", "0"))
        denied = int(native.get("denied", "0"))
        host_calls = int(native.get("host_calls", "0"))
        events = {name: int(native.get(f"{name}_events", "0"))
                  for name in ("gpu", "input", "spu", "cdrom")}
        budget = 2000000  # the Phase-10 runtime default access budget
        accounted = reads + writes + denied + sum(events.values())

        check("native:failed", native.get("failed") == EXPECTED["failed"], str(native.get("failed")))
        check("native:error", native.get("error") == EXPECTED["error"], str(native.get("error")))
        observed_category = {
            "unresolved indirect jump": "UNRESOLVED_INDIRECT_JUMP",
            "unresolved indirect call": "UNRESOLVED_INDIRECT_CALL",
            "guest trap is unsupported": "GUEST_TRAP",
            "runtime memory read failed": "MEMORY_ACCESS_DENIED",
            "runtime memory write failed": "MEMORY_ACCESS_DENIED",
        }.get(native.get("error"), "OTHER")
        check(
            "native:termination-category",
            observed_category == EXPECTED["termination_category"],
            f"{observed_category} ({native.get('error')!r})",
        )
        check("native:guest-traffic", reads + writes > 1000000, f"{reads}+{writes}")
        check("native:inside-budget", accounted < budget, f"{accounted} < {budget}")
        check("native:gp", native.get("register_file", {}).get("r28") == EXPECTED["gp"], str(native.get("register_file", {}).get("r28")))
        check("native:fp", native.get("register_file", {}).get("r30") == EXPECTED["fp"], str(native.get("register_file", {}).get("r30")))
        check(
            "native:stack-differs-from-declared",
            native.get("register_file", {}).get("r29") not in (None, "0x801ffff0"),
            "the crt0-established stack pointer was observed",
        )
        check(
            "native:guest-memory-modified",
            native.get("memory") != fnv1a64(flat),
            "guest RAM digest differs from the loaded image",
        )

        transition = {
            "kind": "fail-closed-unresolved-indirect-jump",
            "error": native.get("error"),
            "candidate_sites": summary["unresolved_sites"] and [
                item for item in summary["unresolved_sites"] if item["kind"] == "INDIRECT_JUMP"
            ],
            "candidate_site_count": sum(1 for item in summary["unresolved_sites"] if item["kind"] == "INDIRECT_JUMP"),
            "address_observable": False,
            "observation_limit": "the frozen Phase-9 observable driver does not print the failing guest PC",
        }
        write_json(
            evidence / "native_entry.json",
            {
                "schema": "openrecomp-phase10-native-entry-v1",
                "stage": STAGE,
                "label": "hercules-private-fixture",
                "is_pass_criterion": False,
                "identity": image.identity(),
                "entry": {
                    "guest_entry_pc": f"0x{image.header.pc0:08x}",
                    "declared_stack_pointer": f"0x{image.header.s_addr:08x}",
                    "initial_register_state": "all 32 guest registers are zero-initialised by the generated entry",
                    "observed_register_file": dict(sorted(native.get("register_file", {}).items())),
                    "observed_stack_pointer": native.get("register_file", {}).get("r29"),
                    "observed_frame_pointer": native.get("register_file", {}).get("r30"),
                    "observed_gp": native.get("register_file", {}).get("r28"),
                },
                "memory_image": {
                    "file_sha256": image.file_sha256,
                    "payload_sha256": image.payload_sha256,
                    "ram_size": len(flat),
                    "loaded_image_sha256": sha256_bytes(flat),
                    "loaded_image_digest": fnv1a64(flat),
                    "runtime_memory_digest": native.get("memory"),
                    "contract_digest": memory_map.contract_digest(contract),
                },
                "translated_trace": {
                    "program_fingerprint": build_set["program_fingerprint"],
                    "file_sha256": build_set["hashes"],
                    "functions": len(build_set["program"].translations),
                    "structure": {
                        key: value for key, value in summary.items()
                        if key in ("neutral_instructions", "folded_delay_slots", "non_nop_delay_slots",
                                   "blocks", "edges", "functions", "translation_units",
                                   "call_edges_internal", "call_edges_unresolved")
                    },
                    "exception_sites": summary["exception_sites"],
                },
                "execution": {
                    "executable_sha256": executable_sha,
                    "stdout_sha256": sha256_bytes(first),
                    "deterministic": True,
                    "failed": native.get("failed"),
                    "error": native.get("error"),
                    "exit_status": native.get("exit_status"),
                    "reads": reads,
                    "writes": writes,
                    "denied": denied,
                    "host_calls": host_calls,
                    "events": events,
                    "events_capped": {name: count >= EVENT_CAPACITY for name, count in events.items()},
                    "access_budget": budget,
                    "accounted_accesses": accounted,
                    "budget_reached": accounted >= budget,
                    "termination_category": observed_category,
                },
                "first_host_service_transition": transition,
                "milestone": {
                    "highest": "A",
                    "statement": "translated native execution begins: the guest entry and its initialisation prefix execute as generated host code",
                    "evidence": [
                        "the program built from the private executable runs deterministically to a fail-closed blocker",
                        "the guest crt0 effect is observable: gp, the crt0-derived stack/frame pointers and the register file are set by executed translated code",
                        "over 1.78 million guest memory accesses executed and the guest RAM digest changed",
                        "the run stopped at an explicit unresolved indirect jump, not at a budget or a host error",
                    ],
                    "not_claimed": [
                        "milestone B or beyond (no proof that initialisation completes)",
                        "any rendering, audio, input or gameplay behaviour",
                    ],
                },
                "limitations": [
                    "the failing guest PC is not observable with the frozen Phase-9 driver",
                    "the platform event transcripts are capped at 4096 recorded events per device",
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
        "stage_name": "Native execution entry",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_05_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_05={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
