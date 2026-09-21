#!/usr/bin/env python3
"""OpenRecomp Phase-10 Hercules BIOS/service frontier gate (P10-04).

The gate classifies the reachable BIOS/service calls of the private Hercules
frontier from the frozen frontier records and the completed Phase-10 structure:

* a bounded backwards slice resolves indirect-call target registers;
* the three reachable ``jalr`` sites whose target register is a constant equal
  to the BIOS ``B0`` vector base are classified as BIOS vector calls with the
  function index taken from the constant written to ``$t1`` in the call delay
  slot (``0x56`` and ``0x57``);
* the other nineteen indirect-call targets are proven non-constant (the target
  register is written by a memory load) or explicitly unresolved (the bounded
  window crosses a control-flow boundary); nothing is guessed;
* the Phase-9 typed service boundary is reused unchanged; every observed BIOS
  service stays ``implemented: false`` and ``fail-closed``, and no BIOS
  semantics is invented;
* synthetic fixtures cover the accepted resolvable forms and every fail-closed
  form, including a native run of a BIOS-vector-call fixture and of a fixture
  that reads the low BIOS table window.

On success it emits::

    OPENRECOMP_P10_04=PASS
    OPENRECOMP_PHASE10_BIOS_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_bios_v1.py
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

import p9_bios_boundary_v1 as p9_bios  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402
import p10_bios_boundary_v1 as bios  # noqa: E402
import p10_emission_v1 as emission  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P10-04"
FEATURE_MARKER = "OPENRECOMP_PHASE10_BIOS_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

EXPECTED = {
    "site_count": 22,
    "bios_calls": 3,
    "bios_functions": ["ps1.bios.B0.56", "ps1.bios.B0.57"],
    "b0_55": 0,
    "b0_56": 1,
    "b0_57": 2,
    "unresolved": 19,
    "resolved_internal": 0,
    "memory_loaded_targets": 13,
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


def analyze_words(words: list[int]) -> tuple[object, dict, bytes, object]:
    return fixture_gate.structure_fixture(words)


def classify(words: list[int]) -> tuple[dict, object]:
    image, contract, flat, result = analyze_words(words)
    analysis_source = fixture_gate.bridge.analyze(image, contract, flat).analysis
    entries = frozenset(function.entry_address for function in result.discovery.functions)
    return bios.classify_calls(analysis_source, function_entries=entries), result


def bios_call_fixture(vector: int, index: int, *, high: bool = False) -> list[int]:
    a = fixture_gate.Assembler()
    if high:
        a.i("lui", rt=10, imm=0x8000)
        a.i("addiu", rs=10, rt=10, imm=vector)
    else:
        a.i("addiu", rs=0, rt=10, imm=vector)
    a.r("jalr", rs=10, rd=31)
    a.i("addiu", rs=0, rt=9, imm=index)
    a.r("jr", rs=31)
    a.nop()
    return a.finish()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-04")
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()

    try:
        # --- synthetic accepted forms ---------------------------------------
        classification, _ = classify(bios_call_fixture(0xB0, 0x56))
        check("synthetic:b0-sites", classification["site_count"] == 1, str(classification["site_count"]))
        site = classification["sites"][0]
        check("synthetic:b0-class", site["classification"] == bios.CLASS_BIOS_VECTOR_CALL, site["classification"])
        check("synthetic:b0-target", site["target"] == "0x000000b0", str(site["target"]))
        check("synthetic:b0-vector", site["vector"] == "B0", str(site["vector"]))
        check("synthetic:b0-index", site["function_index"] == 0x56, str(site["function_index"]))
        check("synthetic:b0-service", site["service_id"] == "ps1.bios.B0.56", str(site["service_id"]))
        check("synthetic:b0-disposition", site["disposition"] == "FAIL_CLOSED", site["disposition"])

        for name, vector, index in (("A0", 0xA0, 0x00), ("B0", 0xB0, 0x13), ("C0", 0xC0, 0x07)):
            synthetic, _ = classify(bios_call_fixture(vector, index))
            entry = synthetic["sites"][0]
            check(f"synthetic:vector-{name}", entry["vector"] == name, str(entry["vector"]))
            check(f"synthetic:vector-{name}:index", entry["function_index"] == index, str(entry["function_index"]))

        high, _ = classify(bios_call_fixture(0xB0, 0x56, high=True))
        check("synthetic:high-target", high["sites"][0]["target"] == "0x800000b0", str(high["sites"][0]["target"]))
        check("synthetic:high-vector", high["sites"][0]["vector"] == "B0", str(high["sites"][0]["vector"]))

        # no constant index in the delay slot -> classified, but no service id
        a = fixture_gate.Assembler()
        a.i("addiu", rs=0, rt=10, imm=0xB0)
        a.r("jalr", rs=10, rd=31)
        a.nop()
        a.r("jr", rs=31)
        a.nop()
        no_index, _ = classify(a.finish())
        entry = no_index["sites"][0]
        check("synthetic:no-index-class", entry["classification"] == bios.CLASS_BIOS_VECTOR_CALL, entry["classification"])
        check("synthetic:no-index-none", entry["function_index"] is None, str(entry["function_index"]))
        check("synthetic:no-index-service", entry["service_id"] is None, str(entry["service_id"]))

        # --- synthetic fail-closed forms -------------------------------------
        # constant target outside the image
        a = fixture_gate.Assembler()
        a.i("addiu", rs=0, rt=10, imm=0x0100)
        a.r("jalr", rs=10, rd=31)
        a.nop()
        a.r("jr", rs=31)
        a.nop()
        outside, _ = classify(a.finish())
        entry = outside["sites"][0]
        check("synthetic:outside-class", entry["classification"] == bios.CLASS_UNRESOLVED_CONSTANT_TARGET, entry["classification"])
        check("synthetic:outside-target", entry["target"] == "0x00000100", str(entry["target"]))
        check("synthetic:outside-disposition", entry["disposition"] == "FAIL_CLOSED", entry["disposition"])

        # constant target that is a known internal function entry
        image, contract, flat, result = analyze_words(bios_call_fixture(0xB0, 0x56))
        entries = sorted(function.entry_address for function in result.discovery.functions)
        internal_target = entries[0]
        a = fixture_gate.Assembler()
        a.i("lui", rt=10, imm=(internal_target >> 16) & 0xFFFF)
        a.i("ori", rs=10, rt=10, imm=internal_target & 0xFFFF)
        a.r("jalr", rs=10, rd=31)
        a.nop()
        a.r("jr", rs=31)
        a.nop()
        internal, internal_result = classify(a.finish())
        entry = internal["sites"][0]
        check("synthetic:internal-class", entry["classification"] == bios.CLASS_RESOLVED_INTERNAL_CALL, entry["classification"])
        check(
            "synthetic:internal-target",
            entry["target"] == f"0x{internal_target:08x}",
            f"{entry['target']} != 0x{internal_target:08x}",
        )
        check("synthetic:internal-disposition", entry["disposition"] == "EXACT_TARGET", entry["disposition"])
        check(
            "synthetic:internal-evidence-targets",
            internal["resolved_evidence_targets"] == [internal_target],
            str(internal["resolved_evidence_targets"]),
        )

        # non-constant target (loaded from memory)
        a = fixture_gate.Assembler()
        a.i("lui", rt=1, imm=0x8003)
        a.i("lw", rs=1, rt=10, imm=0)
        a.r("jalr", rs=10, rd=31)
        a.nop()
        a.r("jr", rs=31)
        a.nop()
        loaded, _ = classify(a.finish())
        entry = loaded["sites"][0]
        check("synthetic:loaded-class", entry["classification"] == bios.CLASS_INDIRECT_TARGET_UNRESOLVED, entry["classification"])
        check("synthetic:loaded-target", entry["target"] is None, str(entry["target"]))
        check(
            "synthetic:loaded-evidence",
            any("slice-writer:lw" in item for item in entry["evidence"]),
            ",".join(entry["evidence"]),
        )

        # --- Phase-9 boundary reused unchanged -------------------------------
        p9_boundary = p9_bios.default_boundary().as_dict()
        check("p9:vector-count", len(p9_boundary["services"]) == 3, str(len(p9_boundary["services"])))
        check(
            "p9:no-service-implemented",
            all(service["implemented"] is False for service in p9_boundary["services"]),
            "none implemented",
        )
        check("p9:fail-closed-policy", p9_boundary["unknown_service_policy"] == "fail-closed", p9_boundary["unknown_service_policy"])

        # --- Hercules frontier ------------------------------------------------
        private_path = ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
        check("private:present", private_path.is_file(), "private fixture present")
        if private_path.is_file():
            private_image = psx.ingest(private_path.read_bytes())
            private_contract = memory_map.build_contract(private_image)
            private_flat = memory_map.flat_image(private_image)
            private_pipeline = bridge.analyze(private_image, private_contract, private_flat)
            private_source = ProgramSource(
                "mips32-bounded-v1",
                adapter="adapters.mips32",
                address_width_bits=32,
                endianness="little",
                input_sha256=private_image.file_sha256,
            )
            private_result = structure.analyze_structure(
                private_pipeline.analysis, source=private_source, entry=private_image.header.pc0
            )
            private_entries = frozenset(
                function.entry_address for function in private_result.discovery.functions
            )
            private_classification = bios.classify_calls(
                private_pipeline.analysis, function_entries=private_entries
            )
            check(
                "private:site-count",
                private_classification["site_count"] == EXPECTED["site_count"],
                str(private_classification["site_count"]),
            )
            check(
                "private:histogram",
                private_classification["histogram"]
                == {"BIOS_VECTOR_CALL": EXPECTED["bios_calls"], "INDIRECT_TARGET_UNRESOLVED": EXPECTED["unresolved"]},
                json.dumps(private_classification["histogram"], sort_keys=True),
            )
            check(
                "private:bios-functions",
                private_classification["bios_functions"] == EXPECTED["bios_functions"],
                ",".join(private_classification["bios_functions"]),
            )
            index_histogram: dict[str, int] = {}
            for site in private_classification["bios_calls"]:
                key = f"0x{site['function_index']:02x}" if site["function_index"] is not None else "none"
                index_histogram[key] = index_histogram.get(key, 0) + 1
            check(
                "private:bios-index-histogram",
                index_histogram == {"0x56": EXPECTED["b0_56"], "0x57": EXPECTED["b0_57"]},
                json.dumps(index_histogram, sort_keys=True),
            )
            check(
                "private:bios-targets",
                {site["target"] for site in private_classification["bios_calls"]} == {"0x000000b0"},
                "B0 vector base",
            )
            check(
                "private:no-bios-implemented",
                all(site["disposition"] == "FAIL_CLOSED" for site in private_classification["bios_calls"]),
                "fail closed",
            )
            memory_loaded = sum(
                1
                for site in private_classification["sites"]
                if site["classification"] == bios.CLASS_INDIRECT_TARGET_UNRESOLVED
                and any("slice-writer:lw" in item for item in site["evidence"])
            )
            check(
                "private:memory-loaded-targets",
                memory_loaded == EXPECTED["memory_loaded_targets"],
                str(memory_loaded),
            )
            check(
                "private:resolved-internal",
                private_classification["resolved_internal_call_count"] == EXPECTED["resolved_internal"],
                str(private_classification["resolved_internal_call_count"]),
            )
            boundary = bios.typed_boundary(private_classification)
            check("private:boundary-observed", boundary["observed_service_count"] == 2, str(boundary["observed_service_count"]))
            check(
                "private:boundary-unimplemented",
                all(service["implemented"] is False for service in boundary["observed_services"]),
                "none implemented",
            )
            check("private:boundary-no-image", boundary["bios_image"] == "none", boundary["bios_image"])
            check("private:semantics-undetermined", boundary["semantics_determined"] is False, "false")

            write_json(
                evidence / "bios_classification.json",
                {
                    "schema": "openrecomp-phase10-bios-classification-v1",
                    "stage": STAGE,
                    "label": "hercules-private-fixture",
                    "is_pass_criterion": False,
                    "identity": private_image.identity(),
                    "classification": private_classification,
                    "boundary": boundary,
                    "p9_boundary_reused": p9_boundary,
                    "blocks_required": [
                        "no BIOS image is loaded, executed or emulated",
                        "no BIOS function semantics is determined from the function index",
                        "every observed BIOS service remains fail-closed",
                    ],
                },
            )

        # --- native fail-closed behaviour -------------------------------------
        negatives = (
            ("bios-vector-call", bios_call_fixture(0xB0, 0x56)),
            ("bios-table-read", [
                builder.i_type("lui", rt=1, imm=0x0000),
                builder.i_type("lw", rs=1, rt=10, imm=0xB0),
                builder.r_type("jalr", rs=10, rd=31),
                builder.nop(),
                builder.r_type("jr", rs=31),
                builder.nop(),
            ]),
        )
        negative_records = []
        for name, words in negatives:
            image, contract, flat, result = analyze_words(words)
            build_set = emission.build_build_set(result, contract, flat, image.file_sha256)
            workspace = ROOT / ".openrecomp-phase10" / "build" / f"p10-04-negative-{name}"
            if workspace.exists():
                shutil.rmtree(workspace)
            build = bp.build_generated_host(
                lambda: build_set["files"][emission.PROGRAM_NAME],
                support_sources=(
                    bp.BuildSource(emission.IMAGE_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   build_set["files"][emission.IMAGE_NAME].encode("utf-8")),
                    bp.BuildSource(emission.SUPPORT_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   build_set["files"][emission.SUPPORT_NAME].encode("utf-8")),
                    bp.BuildSource(emission.DRIVER_NAME, bp.BuildArtifactKind.RUNTIME_SUPPORT_SOURCE,
                                   build_set["files"][emission.DRIVER_NAME].encode("utf-8")),
                ),
                config=bp.BuildConfig(fixture_id=f"p10-04-{name}", smoke_test=False, run_count=2),
                workspace=workspace,
                keep_workspace=True,
            )
            check(
                f"native:{name}:build",
                all(run.manifest.build_status is bp.BuildStatus.OK for run in build.runs),
                str([run.manifest.build_status.value for run in build.runs]),
            )
            completed = subprocess.run(
                [str(workspace / "run1" / "program.exe")], capture_output=True, timeout=600
            )
            native = fixture_gate.parse_native(completed.stdout.decode("utf-8"))
            check(f"native:{name}:fail-closed", native.get("failed") == "1", str(native.get("failed")))
            negative_records.append(
                {
                    "name": name,
                    "failed": native.get("failed"),
                    "error": native.get("error"),
                    "denied": native.get("denied"),
                }
            )
        write_json(
            evidence / "bios_native_negatives.json",
            {
                "schema": "openrecomp-phase10-bios-native-negatives-v1",
                "stage": STAGE,
                "negatives": negative_records,
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
        "stage_name": "Hercules BIOS frontier",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_04_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_04={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
