#!/usr/bin/env python3
"""OpenRecomp Phase-10 structure reconciliation gate (P10-02).

The gate reconciles the frozen Phase-9 ``CONTROL_WITHOUT_DELAY_SLOT`` failure
without manufacturing a delay slot:

* the cause is BREAK/SYSCALL control semantics: ``break`` and ``syscall`` are
  exception-raising instructions and therefore carry no delay slot, while the
  frozen Phase-8 bridge requires one for every ``control_flow`` record;
* the additive Phase-10 bridge maps an ``external-trap`` record to the shared
  neutral ``InstructionFlow.TRAP`` (no successor, no delay slot, no fabricated
  fall-through) and reuses the frozen Phase-8 delay-slot validation, delay-slot
  folding and the shared ProgramModel/CFG/functions/call-graph/units/
  indirect-control layers unchanged;
* for a trap-free fixture the Phase-10 bridge produces a byte-identical
  structure summary to the frozen Phase-8 bridge;
* the frozen Phase-8 module is unchanged and the frozen P9-11 gate still fails
  closed with ``CONTROL_WITHOUT_DELAY_SLOT``;
* every genuine delay-slot violation still fails closed
  (``CONTROL_WITHOUT_DELAY_SLOT``, ``TARGET_INTO_DELAY_SLOT``,
  ``TRAP_WITH_DELAY_SLOT``, malformed trap records);
* the Hercules structure now completes, and the new exact frontier is recorded.

On success it emits::

    OPENRECOMP_P10_02=PASS
    OPENRECOMP_PHASE10_STRUCTURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_structure_v1.py
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p8_structure_v1 as p8  # noqa: E402
import p8_mips32_semantics_v1 as p8_semantics  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402
import p10_structure_v1 as structure  # noqa: E402
from openrecomp.program_model import InstructionFlow, ProgramSource  # noqa: E402

STAGE = "P10-02"
FEATURE_MARKER = "OPENRECOMP_PHASE10_STRUCTURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

BASELINE_COMMIT = "08c639d9032a364163f2985432744be420d402eb"
DEFAULT_PRIVATE_FIXTURE = ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"

EXPECTED = {
    "reachable_words": 4068,
    "neutral_instructions": 3433,
    "folded_delay_slots": 635,
    "non_nop_delay_slots": 328,
    "blocks": 739,
    "edges": 889,
    "functions": 110,
    "translation_units": 110,
    "call_edges_internal": 209,
    "call_edges_unresolved": 22,
    "unsupported_indirect_sites": 40,
    "exception_site_count": 3,
    "first_unresolved_indirect_site": 0x80013E7C,
    "first_unresolved_indirect_op": "jr",
    "first_unruled_semantic_site": 0x80011A60,
    "first_unruled_semantic_op": "sh",
    "unruled_op_types": 24,
    "unruled_instruction_count": 286,
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


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def _assert_no_payload_leak(label: str, document: dict, payload: bytes) -> None:
    import base64

    text = json.dumps(document, sort_keys=True)
    lowered = text.lower()
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in lowered, "payload hex present")
    check(
        f"{label}:no-base64",
        base64.b64encode(sample).decode("ascii") not in text,
        "payload base64 present",
    )
    for start in range(0, min(len(payload), 512)):
        run = payload[start : start + 8]
        if len(run) == 8 and all(32 <= byte < 127 for byte in run):
            check(
                f"{label}:no-ascii-run",
                run.decode("ascii") not in text,
                f"ascii payload run at {start}",
            )
            break
    for value in _string_values(document):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def synthetic(words: list[int]):
    data = builder.build_from_words(words)
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    analysis = bridge.analyze(image, contract, flat).analysis
    source = ProgramSource(
        "mips32-bounded-v1",
        adapter="adapters.mips32",
        address_width_bits=32,
        endianness="little",
        input_sha256=image.file_sha256,
    )
    return image, analysis, source


def manual_analysis(records: list[dict], reachable: list[int], delay_slots: list[dict], entry: int):
    return {
        "records": records,
        "reachable_addresses": sorted(reachable),
        "delay_slots": delay_slots,
        "entry": entry,
    }


def record(address: int, op: str, word: int, **overrides) -> dict:
    base = {
        "address": address,
        "op": op,
        "word": word,
        "decode_class": "SUPPORTED",
        "control_flow": False,
        "terminator": None,
        "delay_slot": False,
        "target": None,
        "operands": {},
        "exception_transfer": False,
        "reachability": "REACHABLE",
    }
    base.update(overrides)
    return base


def expect_error(label: str, expected_code: str, analysis: dict, source: ProgramSource, entry: int) -> None:
    observed = None
    try:
        structure.analyze_structure(analysis, source=source, entry=entry)
    except p8.P8StructureError as exc:
        observed = exc.code
    check(f"negative:{label}", observed == expected_code, str(observed))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-02")
    parser.add_argument("--private-fixture", default=str(DEFAULT_PRIVATE_FIXTURE))
    parser.add_argument("--cache-dir", default=".openrecomp-phase10/cache")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    private_path = pathlib.Path(options.private_fixture)
    cache = (ROOT / options.cache_dir).resolve()
    cache.mkdir(parents=True, exist_ok=True)

    try:
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256="0" * 64,
        )

        # --- Public synthetic: trap fixture reconciles ---
        trap_words = [
            builder.i_type("beq", 0, 0, 4),
            builder.nop(),
            builder.j_type("jal", 0x80010018),
            builder.i_type("addiu", 4, 4, 1),
            builder.break_(1),
            builder.syscall(0),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        image, analysis, source_trap = synthetic(trap_words)
        result = structure.analyze_structure(analysis, source=source_trap, entry=image.header.pc0)
        summary = structure.structure_summary(result)
        check("synthetic:structure-completes", summary["neutral_instructions"] == 5, str(summary["neutral_instructions"]))
        check("synthetic:trap-count", summary["exception_site_count"] == 2, str(summary["exception_site_count"]))
        check(
            "synthetic:flow-histogram",
            summary["flow_histogram"].get("TRAP") == 2,
            json.dumps(summary["flow_histogram"], sort_keys=True),
        )
        trap_addresses = result.trap_addresses()
        check("synthetic:trap-addresses", trap_addresses == (0x80010010, 0x80010014), str(trap_addresses))
        by_address = {instruction.address: instruction for instruction in result.cfg.instructions}
        for site in trap_addresses:
            instruction = by_address[site]
            check(f"synthetic:trap-flow:0x{site:08x}", instruction.flow is InstructionFlow.TRAP, instruction.flow.value)
            check(f"synthetic:trap-not-unresolved:0x{site:08x}", instruction.unresolved is False, "false")
            check(f"synthetic:trap-no-target:0x{site:08x}", instruction.direct_target is None, "none")
            check(f"synthetic:trap-no-delay-slot:0x{site:08x}", instruction.metadata.get("delay_slot") is None, "none")
            check(
                f"synthetic:trap-metadata:0x{site:08x}",
                (instruction.metadata.get("exception") or {}).get("handling") == "explicit-trap-terminator",
                json.dumps(instruction.metadata.get("exception"), sort_keys=True),
            )
        trap_blocks = [
            block for block in result.cfg.blocks
            if block.terminal is not None and block.terminal.flow is InstructionFlow.TRAP
        ]
        check("synthetic:trap-blocks", len(trap_blocks) == 2, str(len(trap_blocks)))
        for block in trap_blocks:
            check(f"synthetic:trap-no-successor:{block.id}", block.successors == (), "no successor")
        check("synthetic:no-unresolved-sites", summary["unresolved_sites"] == [], "none")

        # --- Public synthetic: the extension is additive for trap-free code ---
        trap_free = [
            builder.i_type("beq", 0, 0, 4),
            builder.nop(),
            builder.j_type("jal", 0x80010018),
            builder.i_type("addiu", 4, 4, 1),
            builder.i_type("addiu", 5, 0, 0),
            builder.i_type("addiu", 6, 0, 0),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        image_free, analysis_free, source_free = synthetic(trap_free)
        p8_result = p8.analyze_structure(analysis_free, source=source_free, entry=image_free.header.pc0)
        p10_result = structure.analyze_structure(analysis_free, source=source_free, entry=image_free.header.pc0)
        p8_summary = p8.structure_summary(p8_result)
        p10_summary = structure.structure_summary(p10_result)
        for key in ("neutral_instructions", "folded_delay_slots", "blocks", "edges", "functions",
                    "translation_units", "call_edges_internal", "call_edges_unresolved",
                    "cfg_fingerprint", "discovery_fingerprint", "call_graph_fingerprint",
                    "units_fingerprint", "program_model_fingerprint"):
            check(
                f"additive:{key}",
                p8_summary[key] == p10_summary[key],
                f"{p8_summary[key]} != {p10_summary[key]}",
            )
        check("additive:trap-count-zero", p10_summary["exception_site_count"] == 0, str(p10_summary["exception_site_count"]))
        check("additive:no-neutral-address-drift", p10_result.neutral_addresses == p8_result.neutral_addresses, "identical")

        # --- Fail-closed negatives ---
        j_word = builder.j_type("j", 0x80010010)
        control_no_slot = manual_analysis(
            [
                record(0x80010000, "j", j_word, control_flow=True, terminator="jump", target=0x80010010,
                       operands={"target": 0x80010010}),
                record(0x80010010, "nop", 0),
            ],
            [0x80010000, 0x80010010],
            [],
            0x80010000,
        )
        expect_error("control-without-delay-slot", "CONTROL_WITHOUT_DELAY_SLOT", control_no_slot, source, 0x80010000)

        trap_with_slot = manual_analysis(
            [
                record(0x80010000, "break", builder.break_(1), control_flow=True, terminator="external-trap",
                       delay_slot=True, exception_transfer=True, decode_class="RECOGNIZED_UNSUPPORTED",
                       operands={"code": 1}),
                record(0x80010004, "nop", 0),
            ],
            [0x80010000, 0x80010004],
            [{"owner": 0x80010000, "delay": 0x80010004}],
            0x80010000,
        )
        expect_error("trap-with-delay-slot", "TRAP_WITH_DELAY_SLOT", trap_with_slot, source, 0x80010000)

        target_into_slot = manual_analysis(
            [
                record(0x80010000, "j", builder.j_type("j", 0x80010010), control_flow=True, terminator="jump",
                       delay_slot=True, target=0x80010010, operands={"target": 0x80010010}),
                record(0x80010004, "nop", 0),
                record(0x80010010, "beq", builder.i_type("beq", 0, 0, 0), control_flow=True,
                       terminator="conditional-branch", delay_slot=True, target=0x80010004,
                       operands={"rs": 0, "rt": 0, "target": 0x80010004}),
                record(0x80010014, "nop", 0),
            ],
            [0x80010000, 0x80010004, 0x80010010, 0x80010014],
            [{"owner": 0x80010000, "delay": 0x80010004}, {"owner": 0x80010010, "delay": 0x80010014}],
            0x80010000,
        )
        expect_error("target-into-delay-slot", "TARGET_INTO_DELAY_SLOT", target_into_slot, source, 0x80010000)

        malformed_trap = manual_analysis(
            [
                record(0x80010000, "break", builder.break_(1), control_flow=True, terminator="external-trap",
                       exception_transfer=True, decode_class="RECOGNIZED_UNSUPPORTED", operands={"code": 2}),
            ],
            [0x80010000],
            [],
            0x80010000,
        )
        expect_error("malformed-trap-code", "TRAP_CODE_OUT_OF_RANGE", malformed_trap, source, 0x80010000)

        trap_in_slot = manual_analysis(
            [
                record(0x80010000, "jal", builder.j_type("jal", 0x80010010), control_flow=True,
                       terminator="direct-call", delay_slot=True, target=0x80010010,
                       operands={"target": 0x80010010}),
                record(0x80010004, "break", builder.break_(1), control_flow=True, terminator="external-trap",
                       exception_transfer=True, decode_class="RECOGNIZED_UNSUPPORTED", operands={"code": 1}),
                record(0x80010010, "nop", 0),
            ],
            [0x80010000, 0x80010004, 0x80010010],
            [{"owner": 0x80010000, "delay": 0x80010004}],
            0x80010000,
        )
        expect_error("trap-in-delay-slot", "DELAY_SLOT_IS_CONTROL", trap_in_slot, source, 0x80010000)

        # --- Frozen Phase-8 behaviour must still fail closed, unchanged ---
        frozen_diff = git("diff", "--name-only", BASELINE_COMMIT, "--", ".openrecomp-phase8", ".openrecomp-phase9")
        check("frozen:phase8-phase9-unchanged", frozen_diff == "", frozen_diff or "none")
        frozen_gate = subprocess.run(
            [sys.executable, "tools/test_phase9_hercules_v1.py",
             "--evidence-dir", ".openrecomp-phase10/cache/p9_11_dependency"],
            cwd=str(ROOT),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        check(
            "frozen:p9-11-gate-passes",
            frozen_gate.returncode == 0 and "OPENRECOMP_P9_11=PASS" in frozen_gate.stdout,
            f"rc={frozen_gate.returncode}",
        )
        check(
            "frozen:p9-11-still-fails-closed",
            "PASS: private:structure-fail-closed" in frozen_gate.stdout,
            "CONTROL_WITHOUT_DELAY_SLOT preserved",
        )
        phase9_status = git("status", "--porcelain", "--untracked-files=all", "--", ".openrecomp-phase9")
        check("frozen:phase9-evidence-untouched", phase9_status == "", phase9_status or "none")

        # --- Hercules: the structure now completes ---
        check("private:present", private_path.is_file(), "private fixture present")
        record_document: dict = {
            "schema": "openrecomp-phase10-structure-reconciliation-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "is_pass_criterion": False,
            "cause": "BREAK/SYSCALL control semantics: exception-raising instructions carry no delay slot",
            "resolution": "additive exception-aware bridge maps external-trap records to InstructionFlow.TRAP",
            "frozen_module_modified": False,
        }
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
            private_summary = structure.structure_summary(private_result)
            check("private:structure-completes", private_summary is not None, "structure available")
            for key in ("neutral_instructions", "folded_delay_slots", "non_nop_delay_slots", "blocks",
                        "edges", "functions", "translation_units", "call_edges_internal",
                        "call_edges_unresolved", "exception_site_count"):
                check(
                    f"private:{key}",
                    private_summary[key] == EXPECTED[key],
                    f"{private_summary[key]} != {EXPECTED[key]}",
                )
            unresolved = private_summary["unresolved_sites"]
            check("private:unresolved-site-count", len(unresolved) == EXPECTED["unsupported_indirect_sites"], str(len(unresolved)))
            first_indirect = unresolved[0]
            check(
                "private:first-indirect-site",
                first_indirect["address"] == EXPECTED["first_unresolved_indirect_site"],
                str(first_indirect["address"]),
            )
            check(
                "private:first-indirect-op",
                first_indirect["op"] == EXPECTED["first_unresolved_indirect_op"],
                str(first_indirect["op"]),
            )

            table = p8_semantics.build_semantics()
            pending: dict[str, list[int]] = {}
            for instruction in private_result.cfg.instructions:
                if not table.has("mips32-bounded-v1", instruction.op):
                    pending.setdefault(instruction.op, []).append(instruction.address)
            check("private:unruled-op-types", len(pending) == EXPECTED["unruled_op_types"], str(len(pending)))
            check(
                "private:unruled-instruction-count",
                sum(len(values) for values in pending.values()) == EXPECTED["unruled_instruction_count"],
                str(sum(len(values) for values in pending.values())),
            )
            first_unruled = min((min(values), op) for op, values in pending.items())
            check("private:first-unruled-site", first_unruled[0] == EXPECTED["first_unruled_semantic_site"], f"0x{first_unruled[0]:08x}")
            check("private:first-unruled-op", first_unruled[1] == EXPECTED["first_unruled_semantic_op"], first_unruled[1])
            check(
                "private:trap-sites",
                structure.structure_summary(private_result)["exception_sites"][0]["site_hex"] == "0x80013390",
                "0x80013390",
            )

            record_document.update(
                {
                    "identity": private_image.identity(),
                    "structure_summary": {
                        key: value for key, value in private_summary.items() if key not in ("unresolved_sites", "exception_sites")
                    },
                    "unresolved_indirect_sites": unresolved,
                    "exception_sites": private_summary["exception_sites"],
                    "new_frontier": {
                        "first_unresolved_indirect_site": f"0x{first_indirect['address']:08x}",
                        "first_unresolved_indirect_op": first_indirect["op"],
                        "first_unresolved_indirect_status": first_indirect["status"],
                        "first_unruled_semantic_site": f"0x{first_unruled[0]:08x}",
                        "first_unruled_semantic_op": first_unruled[1],
                        "unruled_op_histogram": {op: len(values) for op, values in sorted(pending.items())},
                        "unruled_op_sites": {
                            op: [f"0x{address:08x}" for address in sorted(values)]
                            for op, values in sorted(pending.items())
                        },
                    },
                }
            )
        write_json(evidence / "structure_reconciliation.json", record_document)
        if private_path.is_file():
            _assert_no_payload_leak("structure-reconciliation", record_document, private_image.payload)

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
        "stage_name": "CONTROL_WITHOUT_DELAY_SLOT reconciliation",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_02_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_02={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
