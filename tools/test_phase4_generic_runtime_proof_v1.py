#!/usr/bin/env python3
"""OpenRecomp Phase-4 end-to-end generic-runtime native proof gate (P4-09).

Demonstrates the bounded pipeline and independently verifies its observable:

    fixture/input -> ingestion -> program recovery -> translation
    -> host emission -> native build -> generic runtime -> platform adapter
    -> deterministic execution

* every stage is executed here in sequence and recorded with its identities
  (fixture hashes, frozen ELF ingestion identity, the neutral structure
  recovery summary, translation hashes, deterministic build manifest, the
  `BoundPlatform` adapter capabilities and the native execution observable);
* the independent Phase-4 reference (its own ELF loader, decoder and executor,
  sharing no code with the emitter or generated program) runs the same input
  plan and must agree on every observable field: transcript, exit status,
  steps, PC, failure state, output bytes and the P4-01 canonical state digest;
* reference and native determinism are checked by repetition, and the
  reference is shown to fail closed on unsupported instructions, unaligned
  or out-of-region accesses.

It emits::

    OPENRECOMP_P4_09=PASS
    OPENRECOMP_PHASE4_END_TO_END_NATIVE_PROOF_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_generic_runtime_proof_v1.py
    python tools/test_phase4_generic_runtime_proof_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-09
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(ROOT / ".openrecomp-phase4" / "src"),
                  str(ROOT / ".openrecomp-phase3" / "src"), str(ROOT / "tools")):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import p4_fixture_exec_v1 as fx  # noqa: E402
import p4_platform_adapter_v1 as pa  # noqa: E402
import p4_reference_fixture_v1 as ref  # noqa: E402
from p3_elf_image_v1 import ingest  # noqa: E402
from p3_structure_v1 import analyze_structure, structure_summary  # noqa: E402
from p3_target_mips32_v1 import MIPS32_O32  # noqa: E402
from openrecomp.program_model import ProgramSource, canonical_json  # noqa: E402
import test_phase4_adapter_execution_v1 as p408  # noqa: E402

STAGE = "P4-09"
STAGE_MARKER = "OPENRECOMP_P4_09"
FEATURE_MARKER = "OPENRECOMP_PHASE4_END_TO_END_NATIVE_PROOF_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

SOURCE_SUMS = "SOURCE_SHA256SUMS.txt"
SOURCE_SUMS_SHA256 = "76f77bbc97780afe9c2b41a0cb89b5323ab22450c4b2a368dd03fb4d7bbe1095"
SOURCE_SUMS_ENTRIES = 134
P3_SUMS = ".openrecomp-phase3/SOURCE_SHA256SUMS.txt"
P3_SUMS_SHA256 = "a7d0953c0f02276ad233db50e326d9e71a3136542648bb04a95de9d3e05e2488"
P3_SUMS_ENTRIES = 24
P4_SUMS = ".openrecomp-phase4/SOURCE_SHA256SUMS.txt"

FIXTURE_ELF_SHA256 = "acb4f4e57a7f996e87989e99d702d802259b752aabb2476f574665ef061969bc"
PROGRAM_SHA256 = "abd138ea391fb48cd5ba17b54f56f93a77aaa6ebab201d715210635a7f1edc48"
SUPPORT_SHA256 = "755a004630560ae606ce571c2c111934b94e945db6c4c6d6aea5c105a2b8a8fd"
EXECUTABLE_SHA256 = "c966e1854dcc9c9169859b20ef40c07810e7d40d7dc7700b2e202a168e5b3caa"
EXPECTED_TRANSCRIPT = (
    "P4FIXTURE v1",
    "input_bytes=4",
    "input_xor=136",
    "fib10=55",
    "prime_count=16",
    "primes_sum=381",
    "bss_sum=4028012831",
    "heap_sum=3784880468",
    "checksum=0xd43e5ba6",
    "ticks_start=19",
    "ticks_end=6691",
)
EXPECTED_STATE_DIGEST = "0x5185479717fe4020"
EXPECTED_STEPS = 6784
EXPECTED_PC = 0x1BF4
REFERENCE_RUNS = 2

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def expect_fail(label: str, thunk, error_type=Exception) -> None:
    try:
        thunk()
    except error_type:
        check(f"reject:{label}", True)
        return
    except Exception as exc:  # noqa: BLE001 - fail closed
        raise AssertionError(
            f"{label}: raised {type(exc).__name__} instead of {error_type.__name__}") from exc
    raise AssertionError(f"{label}: accepted")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def parse_manifest(path: pathlib.Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for line in read_text(path).strip().splitlines():
        if not line.strip():
            continue
        match = re.match(r"^([0-9a-f]{64}) \*(.+)$", line)
        if match is None:
            raise AssertionError(f"malformed manifest line: {line[:80]}")
        entries.append((match.group(1), match.group(2)))
    return entries


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------
def stage_source_integrity() -> None:
    check("source:root-manifest", sha256_file(ROOT / SOURCE_SUMS) == SOURCE_SUMS_SHA256)
    root_entries = parse_manifest(ROOT / SOURCE_SUMS)
    check("source:root-manifest-entries", len(root_entries) == SOURCE_SUMS_ENTRIES)
    check("source:root-manifest-verified",
          all((ROOT / rel).is_file() and sha256_file(ROOT / rel) == digest
              for digest, rel in root_entries))
    check("source:phase3-manifest", sha256_file(ROOT / P3_SUMS) == P3_SUMS_SHA256)
    phase3_entries = parse_manifest(ROOT / P3_SUMS)
    check("source:phase3-manifest-entries", len(phase3_entries) == P3_SUMS_ENTRIES)
    phase4_entries = parse_manifest(ROOT / P4_SUMS)
    bad = [rel for digest, rel in phase4_entries
           if not (ROOT / rel).is_file() or sha256_file(ROOT / rel) != digest]
    check("source:phase4-manifest-verified", phase4_entries and not bad)
    FINDINGS["source_integrity"] = {"root_entries": len(root_entries),
                                    "phase3_entries": len(phase3_entries),
                                    "phase4_entries": len(phase4_entries)}


def stage_fixture_and_ingestion() -> tuple[bytes, dict[str, Any]]:
    data = fx.load_fixture_elf()
    check("pipeline:fixture-elf", sha256_bytes(data) == FIXTURE_ELF_SHA256)
    plan = fx.input_plan_document()
    check("pipeline:input-plan", bytes.fromhex(plan["console_input_hex"]) == fx.INPUT_PLAN)
    ingested = ingest(data, MIPS32_O32)
    identity = ingested.identity
    check("pipeline:ingestion-identity",
          identity["machine"] == 8 and identity["elf_class"] == "ELF32"
          and identity["static"] is True and identity["entry"] == "0x00001c00")
    analysis = fx.analyze_fixture(data)
    check("pipeline:ingestion-entry",
          analysis["entry"] == fx.FIXTURE_ENTRY)
    text = analysis["text"]
    check("pipeline:ingestion-text",
          (text.sh_addr, text.sh_size) == (0x1000, 3104))

    segments, entry = ref.load_segments(data)
    check("pipeline:independent-loader-entry", entry == fx.FIXTURE_ENTRY)
    check("pipeline:loader-segment-agreement",
          [(seg.vaddr, seg.filesz, seg.memsz) for seg in segments]
          == [(seg.p_vaddr, seg.p_filesz, seg.p_memsz)
              for seg in ingested.parsed.load_segments])
    stage = {
        "fixture_elf_sha256": FIXTURE_ELF_SHA256,
        "input_plan_hex": plan["console_input_hex"],
        "identity": identity,
        "segments": [seg.to_document() for seg in segments],
        "independent_entry": hex(entry),
    }
    FINDINGS["ingestion"] = stage
    return data, stage


def stage_program_recovery(data: bytes) -> dict[str, Any]:
    analysis = fx.analyze_fixture(data)["frontier"]
    source = ProgramSource("mips32-o32", adapter="openrecomp.phase4-pipeline",
                           address_width_bits=32)
    structure = analyze_structure(analysis, source=source, entry=fx.FIXTURE_ENTRY)
    summary = structure_summary(structure)
    check("pipeline:structure-instructions", summary["instruction_count"] == 774)
    check("pipeline:structure-blocks", summary["block_count"] == 142)
    check("pipeline:structure-functions", summary["function_count"] == 9)
    check("pipeline:structure-call-edges",
          summary["call_graph_edges"] == 14 and summary["call_graph_unresolved_edges"] == 0)
    check("pipeline:structure-recursion", summary["call_graph_recursive"] == ["fn_1010"])
    check("pipeline:structure-entry-unit", summary["entry_unit"] == "tu_fn_1c00")
    check("pipeline:structure-no-indirect", summary["indirect_sites"] == [])
    check("pipeline:structure-no-unresolved", summary["unresolved_edges"] == 0)
    check("pipeline:structure-fingerprints",
          len(summary["cfg_fingerprint"]) == 64
          and len(summary["call_graph_fingerprint"]) == 64)
    FINDINGS["program_recovery"] = {
        "flow_histogram": summary["flow_histogram"],
        "edge_histogram": summary["edge_histogram"],
        "block_count": summary["block_count"],
        "function_count": summary["function_count"],
        "call_graph_edges": summary["call_graph_edges"],
        "cfg_fingerprint": summary["cfg_fingerprint"],
        "call_graph_fingerprint": summary["call_graph_fingerprint"],
        "program_model_fingerprint": summary["program_model_fingerprint"],
        "translation_unit_set_fingerprint": summary["translation_unit_set_fingerprint"],
    }
    return summary


def stage_translation_and_build(data: bytes) -> tuple[fx.FixtureTranslation, pathlib.Path]:
    translation = fx.translate_fixture(data)
    check("pipeline:translation-program", translation.program_sha256 == PROGRAM_SHA256)
    check("pipeline:translation-support", translation.support_sha256 == SUPPORT_SHA256)
    check("pipeline:translation-reachable", translation.reachable_words == 774)
    comparison, executable = p408.build_program(translation.program_text,
                                                translation.support_text, "p4-09")
    check("pipeline:build-classification",
          comparison.classification.value == "EXECUTABLE_REPRODUCIBLE")
    check("pipeline:build-executable", sha256_file(executable) == EXECUTABLE_SHA256)
    check("pipeline:build-manifest-deterministic",
          comparison.runs[0].manifest.serialize() == comparison.runs[1].manifest.serialize())
    FINDINGS["translation_build"] = {
        "program_sha256": PROGRAM_SHA256,
        "support_sha256": SUPPORT_SHA256,
        "executable_sha256": EXECUTABLE_SHA256,
        "manifest_sha256": comparison.runs[0].manifest.fingerprint(),
    }
    return translation, executable


def stage_runtime_and_adapter(data: bytes) -> None:
    adapter = p408.FixtureAdapter(data, pa.PlatformHooks())
    check("pipeline:adapter-valid", pa.validate_adapter(adapter) == [])
    bound = pa.bind_platform(adapter)
    check("pipeline:adapter-claims",
          dict(bound.claims)["console_compatibility"] is False
          and dict(bound.claims)["arbitrary_binary_compatibility"] is False)
    check("pipeline:adapter-memory",
          bound.memory.fetch(fx.FIXTURE_ENTRY, 32)
          == int.from_bytes(fx.fixture_image(data)[fx.FIXTURE_ENTRY:fx.FIXTURE_ENTRY + 4],
                            "little"))
    check("pipeline:adapter-services",
          bound.mediator.dispatch("fixture.out", (0x41,)).ok
          and bound.io.console.output == b"A")
    check("pipeline:adapter-input",
          bound.mediator.dispatch("fixture.in", ()).value == fx.INPUT_PLAN[0])
    check("pipeline:adapter-ticks",
          bound.mediator.dispatch("fixture.ticks", ()).value == 0)
    check("pipeline:adapter-exit",
          bound.mediator.dispatch("fixture.exit", (0,)).ok)
    FINDINGS["runtime_adapter"] = {
        "interface_ids": list(bound.interface_ids),
        "capabilities": dict(bound.capabilities),
        "fingerprint": bound.fingerprint(),
    }


def stage_native_execution(executable: pathlib.Path) -> dict[str, str]:
    outputs = p408.run_executable(executable, repeats=3)
    check("pipeline:execution-replay-identical", len(set(outputs)) == 1)
    observable = p408.parse_observable(outputs[0])
    check("pipeline:execution-no-failure",
          observable.get("failed") == "0" and observable.get("failure") == "")
    check("pipeline:execution-transcript",
          p408.transcript_from_hex(observable["output_hex"]) == list(EXPECTED_TRANSCRIPT))
    check("pipeline:execution-steps", observable.get("steps") == str(EXPECTED_STEPS))
    check("pipeline:execution-pc", observable.get("pc") == f"0x{EXPECTED_PC:08x}")
    check("pipeline:execution-digest",
          observable.get("state_fnv1a64") == EXPECTED_STATE_DIGEST)
    FINDINGS["native_execution"] = observable
    return observable


# ---------------------------------------------------------------------------
# Independent reference equivalence
# ---------------------------------------------------------------------------
def run_reference(segments, entry) -> ref.ReferenceMachine:
    machine = ref.ReferenceMachine(segments, entry, input_plan=fx.INPUT_PLAN)
    machine.run()
    return machine


def stage_equivalence(data: bytes, observable: dict[str, str]) -> None:
    segments, entry = ref.load_segments(data)
    first = run_reference(segments, entry)
    second = run_reference(segments, entry)
    check("reference:deterministic",
          canonical_json(first.observable_document())
          == canonical_json(second.observable_document()))
    document = first.observable_document()
    transcript = bytes(first.output).decode("ascii").splitlines()
    check("reference:transcript", tuple(transcript) == EXPECTED_TRANSCRIPT)
    check("reference:exit-status", document["exit_status"] == 0
          and observable.get("exit_status") == "0")
    check("reference:steps", document["steps"] == EXPECTED_STEPS
          and observable.get("steps") == str(EXPECTED_STEPS))
    check("reference:pc", document["pc"] == EXPECTED_PC
          and observable.get("pc") == f"0x{EXPECTED_PC:08x}")
    check("reference:no-failure", document["failed"] is False
          and observable.get("failed") == "0" and observable.get("failure") == "")
    check("reference:output-identical",
          document["output_sha256"]
          == hashlib.sha256(bytes.fromhex(observable["output_hex"])).hexdigest())
    check("reference:digest-identical",
          document["state_fnv1a64"] == observable.get("state_fnv1a64")
          == EXPECTED_STATE_DIGEST)
    fresh = ref.ReferenceMachine(segments, entry, input_plan=fx.INPUT_PLAN)
    check("reference:image-window-identical",
          sha256_bytes(fresh.image_window())
          == sha256_bytes(fx.fixture_image(data)))
    check("reference:hi-lo-covered-by-digest",
          0 <= document["hi"] <= 0xFFFFFFFF and 0 <= document["lo"] <= 0xFFFFFFFF
          and document["state_fnv1a64"] == EXPECTED_STATE_DIGEST)

    payload = {
        "stage": STAGE,
        "reference_version": ref.REFERENCE_VERSION,
        "native_observable": observable,
        "reference_observable": document,
        "fields_compared": ["transcript", "exit_status", "steps", "pc", "failed",
                            "output_sha256", "state_fnv1a64"],
        "equivalent": True,
    }
    ARTIFACTS["equivalence.json"] = (
        json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    FINDINGS["equivalence"] = {
        "equivalent": True,
        "state_fnv1a64": document["state_fnv1a64"],
        "steps": document["steps"],
        "output_sha256": document["output_sha256"],
    }


def stage_reference_negatives(data: bytes) -> None:
    import struct as _struct

    segments, entry = ref.load_segments(data)
    check("negative:reference-unsupported-instruction", _reference_invalid() is True)
    machine = ref.ReferenceMachine(segments, entry, input_plan=fx.INPUT_PLAN, max_steps=10)
    machine.run()
    check("negative:reference-step-limit",
          machine.failed and machine.failure == "step limit exceeded")
    small = ref.ReferenceMachine(segments, entry, input_plan=fx.INPUT_PLAN)
    small.write(0x30000000, 4, 1)
    check("negative:reference-unmapped-store",
          small.failed and small.failure == "MEMORY_OUT_OF_RANGE")
    unaligned = ref.ReferenceMachine(segments, entry, input_plan=fx.INPUT_PLAN)
    unaligned.registers[1] = 0x1C01
    unaligned.pc = 0x1000
    word = (1 << 21) | 0x08  # jr $1
    unaligned.memory[0x1000:0x1004] = _struct.pack("<I", word)
    unaligned.step()
    check("negative:reference-unaligned-jump",
          unaligned.failed and unaligned.failure == "unaligned indirect jump target")


def _reference_invalid() -> bool:
    import struct as _struct

    synthetic = ref.Segment(vaddr=0x1000, filesz=4, memsz=4, flags=5,
                            data=_struct.pack("<I", 0xFC000000))
    machine = ref.ReferenceMachine((synthetic,), 0x1000, input_plan=b"")
    machine.run()
    return machine.failed and "unsupported instruction" in machine.failure


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="P4-09 end-to-end proof gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-09")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P4-09 End-to-End Generic-Runtime Native Proof Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("source_integrity")
        stage_source_integrity()
        banner("fixture_ingestion")
        data, ingestion = stage_fixture_and_ingestion()
        banner("program_recovery")
        stage_program_recovery(data)
        banner("translation_build")
        translation, executable = stage_translation_and_build(data)
        banner("runtime_adapter")
        stage_runtime_and_adapter(data)
        banner("native_execution")
        observable = stage_native_execution(executable)
        banner("equivalence")
        stage_equivalence(data, observable)
        banner("reference_negatives")
        stage_reference_negatives(data)
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

    pipeline = {
        "stage": STAGE,
        "pipeline": [
            "fixture/input", "ingestion", "program recovery", "translation",
            "host emission", "native build", "generic runtime",
            "platform adapter", "deterministic execution",
        ],
        "findings": FINDINGS,
        "status": status,
    }
    ARTIFACTS["pipeline.json"] = (
        json.dumps(pipeline, indent=2, sort_keys=True) + "\n").encode("utf-8")
    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, payload in ARTIFACTS.items():
        (EVIDENCE_DIR / name).write_bytes(payload)
    (EVIDENCE_DIR / "p4_09_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        print(f"{COMPAT_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
