#!/usr/bin/env python3
"""OpenRecomp Phase-10 BREAK semantic classification gate (P10-01).

The gate establishes the exact classification of the inherited Phase-9 first
blocker, the ``break`` at ``0x80013390``:

* independent bit-level encoding verification against the frozen Phase-3
  decoder (two independent extraction implementations must agree);
* public, OpenRecomp-authored synthetic PS-X EXE fixtures that isolate the
  trap behaviour: the frozen frontier records the trap as an ``external-trap``
  site and stops flow, the frozen Phase-8 structure bridge fails closed with
  ``CONTROL_WITHOUT_DELAY_SLOT`` (the exact Phase-9 blocker class), and a trap
  in a branch delay slot is rejected rather than folded;
* the architectural BREAK/SYSCALL semantics: synchronous Breakpoint (``Bp``,
  ExcCode 9) / Syscall (``Sys``, ExcCode 8) exceptions, no delay slot, ``EPC``
  at the faulting instruction, ``Cause.BD`` = 0, PS1 general-exception vectors
  ``0x80000080`` (BEV=0) and ``0xBFC00180`` (BEV=1);
* the exact private-site context: predecessor, region, inbound targets,
  exception-vector expectation, continuation policy and the bounded handling
  strategy;
* a structural proof that no generic exception machinery was added: the shared
  OpenRecomp layers and the frozen Phase-1..9 sources are unchanged.

No exception delivery, no BIOS handler, no continuation and no delay slot is
invented. The private fixture contributes non-reconstructive metadata only.

On success it emits::

    OPENRECOMP_P10_01=PASS
    OPENRECOMP_PHASE10_BREAK_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_break_v1.py
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P3 = ROOT / ".openrecomp-phase3"
P8 = ROOT / ".openrecomp-phase8"
P9 = ROOT / ".openrecomp-phase9"
P10 = ROOT / ".openrecomp-phase10"
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p3_code_frontier_v1 as frontier  # noqa: E402
import p8_structure_v1 as structure_bridge  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402
import p10_exception_v1 as exception  # noqa: E402
from openrecomp.program_model import ProgramSource  # noqa: E402

STAGE = "P10-01"
FEATURE_MARKER = "OPENRECOMP_PHASE10_BREAK_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

BASELINE_COMMIT = "08c639d9032a364163f2985432744be420d402eb"

SHARED_LAYERS = ("openrecomp", "adapters", "src", "include", "contracts", "schema")

DEFAULT_PRIVATE_FIXTURE = ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"

PRIVATE_EXPECTED = {
    "file_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
    "entry": 0x800132E8,
    "break_site": 0x80013390,
    "break_code": 1,
    "predicted_region_start": 0x800132E8,
    "predicted_predecessor": 0x80013388,
    "predicted_predecessor_kind": "direct-call-continuation",
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


def synthetic_analysis(words: list[int], *, load: int = 0x80010000):
    data = builder.build_from_words(words, load_address=load)
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    return image, contract, flat


def run_frontier(image, contract, flat):
    return frontier.analyze(
        lambda address: memory_map.read_u32(contract, flat, address),
        image.header.t_addr,
        image.header.t_addr + image.header.t_size,
        image.header.pc0,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase10/evidence/P10-01")
    parser.add_argument("--private-fixture", default=str(DEFAULT_PRIVATE_FIXTURE))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    private_path = pathlib.Path(options.private_fixture)

    image_records: dict[str, list[int]] = {}
    try:
        facts = exception.architectural_facts()
        check("facts:version", facts["exception_version"] == exception.EXCEPTION_VERSION, facts["exception_version"])
        check("facts:funct-syscall", facts["special_functs"]["0x0c"] == "syscall", "0x0c")
        check("facts:funct-break", facts["special_functs"]["0x0d"] == "break", "0x0d")
        check("facts:exc-bp", facts["exception_codes"]["9"] == "Bp", "9")
        check("facts:exc-sys", facts["exception_codes"]["8"] == "Sys", "8")
        check(
            "facts:vectors",
            facts["vectors"]["BEV0"] == "0x80000080" and facts["vectors"]["BEV1"] == "0xbfc00180",
            json.dumps(facts["vectors"], sort_keys=True),
        )
        check(
            "facts:continuation-policy",
            facts["continuation_policy"] == "NOT_MODELLED_FAIL_CLOSED",
            facts["continuation_policy"],
        )

        # --- Independent encoding verification against the frozen decoder ---
        encoding = {}
        for name, word in (("break1", builder.break_(1)), ("break0", builder.break_(0)),
                           ("syscall0", builder.syscall(0)), ("syscall7", builder.syscall(7))):
            decoded = exception.decode_trap_word(word)
            frozen = frontier.decode_v1.classify(0x80010000, word)
            encoding[name] = {
                "word": f"0x{word:08x}",
                "independent": decoded,
                "frozen": {
                    "decode_class": frozen["decode_class"],
                    "op": frozen["op"],
                    "control_flow": frozen["control_flow"],
                    "terminator": frozen["terminator"],
                    "delay_slot": frozen["delay_slot"],
                    "exception_transfer": frozen["exception_transfer"],
                    "target": frozen["target"],
                },
            }
            expected_op = "break" if name.startswith("break") else "syscall"
            check(f"encoding:{name}:opcode", decoded["opcode"] == 0, str(decoded["opcode"]))
            check(f"encoding:{name}:agreement", frozen["op"] == expected_op, str(frozen["op"]))
            check(
                f"encoding:{name}:code20",
                decoded["code20"] == frozen["operands"]["code"],
                f"{decoded['code20']} != {frozen['operands']['code']}",
            )
            check(f"encoding:{name}:control", frozen["control_flow"] is True, "control_flow")
            check(
                f"encoding:{name}:terminator",
                frozen["terminator"] == frontier.decode_v1.TERM_EXTERNAL_TRAP,
                str(frozen["terminator"]),
            )
            check(f"encoding:{name}:no-delay-slot", frozen["delay_slot"] is False, "delay_slot")
            check(f"encoding:{name}:exception-transfer", frozen["exception_transfer"] is True, "exception_transfer")
            check(f"encoding:{name}:no-target", frozen["target"] is None, "target")
        check("encoding:break1-code", encoding["break1"]["independent"]["code20"] == 1, "1")
        check("encoding:break1-funct", encoding["break1"]["independent"]["funct"] == 0x0D, "0x0d")

        # --- Behavioural classification on a public synthetic fixture ---
        words = [
            builder.i_type("beq", 0, 0, 4),
            builder.nop(),
            builder.j_type("jal", 0x80010018),
            builder.i_type("addiu", 4, 4, 1),
            builder.break_(1),
            builder.syscall(0),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        image_records["trap-fixture"] = words
        image, contract, flat = synthetic_analysis(words)
        analysis = run_frontier(image, contract, flat)
        summary = analysis["summary"]
        check("synthetic:reachable-words", summary["reachable_words"] == 8, str(summary["reachable_words"]))
        reachable_ops = dict(summary["supported_reachable_histogram"])
        for op, count in summary["unsupported_reachable_histogram"].items():
            reachable_ops[op] = reachable_ops.get(op, 0) + count
        check(
            "synthetic:reachable-traps",
            reachable_ops.get("break") == 1 and reachable_ops.get("syscall") == 1,
            json.dumps(dict(sorted(reachable_ops.items())), sort_keys=True),
        )
        check("synthetic:exception-sites", summary["exception_site_count"] == 2, str(summary["exception_site_count"]))
        check(
            "synthetic:unresolved-traps",
            summary["unresolved_site_counts"] == {"external-trap": 2},
            json.dumps(summary["unresolved_site_counts"], sort_keys=True),
        )
        records = {record["address"]: record for record in analysis["records"]}
        for site in (0x80010010, 0x80010014):
            check(f"synthetic:flow-stopped:0x{site:08x}", records[site]["reachability"] == frontier.REACHABLE, "reachable")
        check(
            "synthetic:call-target-still-reachable",
            records[0x80010018]["reachability"] == frontier.REACHABLE
            and records[0x8001001C]["reachability"] == frontier.REACHABLE,
            "direct call target and its delay slot remain reachable",
        )
        check(
            "synthetic:no-traps-after-trap",
            all(
                item["site"] not in (0x80010018, 0x8001001C)
                for item in analysis["exception_sites"]
            ),
            "no fabricated trap sites",
        )

        # A trap terminator must not fabricate a fall-through successor.
        terminator_words = [builder.break_(1), builder.nop(), builder.nop(), builder.nop()]
        image_records["trap-terminator-fixture"] = terminator_words
        image_t, contract_t, flat_t = synthetic_analysis(terminator_words)
        analysis_t = run_frontier(image_t, contract_t, flat_t)
        check(
            "terminator:reachable-words",
            analysis_t["summary"]["reachable_words"] == 1,
            str(analysis_t["summary"]["reachable_words"]),
        )
        for address in (0x80010004, 0x80010008, 0x8001000C):
            record = next(item for item in analysis_t["records"] if item["address"] == address)
            check(
                f"terminator:no-fabricated-fallthrough:0x{address:08x}",
                record["reachability"] == frontier.UNREACHABLE,
                record["reachability"],
            )
        trap_classification = exception.classify_trap_sites(
            [record for record in analysis["records"] if record["address"] in {0x80010010, 0x80010014}]
        )
        check("synthetic:classified-sites", trap_classification["site_count"] == 2, str(trap_classification["site_count"]))
        check(
            "synthetic:classified-histogram",
            trap_classification["histogram"] == {"break": 1, "syscall": 1},
            json.dumps(trap_classification["histogram"], sort_keys=True),
        )
        for site in trap_classification["sites"]:
            check(f"synthetic:no-successor:0x{site['site']:08x}", site["successors"] == [], "no successors")
            check(f"synthetic:epc:0x{site['site']:08x}", site["epc"] == site["site"], "EPC = site")
            check(f"synthetic:bd:0x{site['site']:08x}", site["bd"] == 0, "BD = 0")
            check(
                f"synthetic:continuation:0x{site['site']:08x}",
                site["continuation"] == "NOT_MODELLED_FAIL_CLOSED",
                site["continuation"],
            )
        syscall_site = next(item for item in trap_classification["sites"] if item["op"] == "syscall")
        check("synthetic:syscall-exc-code", syscall_site["exception_code"] == 8, str(syscall_site["exception_code"]))
        break_site = next(item for item in trap_classification["sites"] if item["op"] == "break")
        check("synthetic:break-exc-code", break_site["exception_code"] == 9, str(break_site["exception_code"]))

        # --- The frozen Phase-8 bridge fails closed on the trap record ---
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image.file_sha256,
        )
        failure = None
        try:
            structure_bridge.analyze_structure(analysis, source=source, entry=image.header.pc0)
        except structure_bridge.P8StructureError as exc:
            failure = {"code": exc.code, "detail": exc.detail}
        check("bridge:fail-closed", failure is not None, "must fail closed")
        check(
            "bridge:fail-closed-reason",
            (failure or {}).get("code") == "CONTROL_WITHOUT_DELAY_SLOT",
            json.dumps(failure, sort_keys=True),
        )
        check(
            "bridge:fail-closed-site",
            (failure or {}).get("detail") == "0x80010010",
            str((failure or {}).get("detail")),
        )

        # A trap-free variant structures successfully: the failure is specific
        # to the trap record, not to the fixture or the pipeline.
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
        image_records["trap-free-fixture"] = trap_free
        image2, contract2, flat2 = synthetic_analysis(trap_free)
        analysis2 = run_frontier(image2, contract2, flat2)
        source2 = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image2.file_sha256,
        )
        structured = structure_bridge.analyze_structure(analysis2, source=source2, entry=image2.header.pc0)
        structured_summary = structure_bridge.structure_summary(structured)
        check("bridge:trap-free-structures", structured_summary["neutral_instructions"] == 5, str(structured_summary["neutral_instructions"]))
        check(
            "bridge:trap-free-no-unresolved",
            structured_summary["unresolved_sites"] == [],
            json.dumps(structured_summary["unresolved_sites"], sort_keys=True),
        )

        # --- Negative: a trap inside a branch delay slot is rejected ---
        delay_words = [
            builder.j_type("jal", 0x80010010),
            builder.break_(1),
            builder.nop(),
            builder.nop(),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        image_records["delay-slot-trap-fixture"] = delay_words
        image3, contract3, flat3 = synthetic_analysis(delay_words)
        analysis3 = run_frontier(image3, contract3, flat3)
        kinds = analysis3["summary"]["unresolved_site_counts"]
        check(
            "delay-slot-trap:rejected",
            kinds.get("control-transfer-in-delay-slot") == 1,
            json.dumps(kinds, sort_keys=True),
        )
        check(
            "delay-slot-trap:not-reachable",
            0x80010004 not in set(analysis3["reachable_addresses"]),
            "delay slot not reachable",
        )
        check(
            "delay-slot-trap:no-trap-site",
            all(item["site"] != 0x80010004 for item in analysis3["exception_sites"]),
            "no folded trap site",
        )
        check(
            "delay-slot-trap:no-call-successor",
            analysis3["control_flow"]["direct-calls"] == [],
            "no successor invented for the unresolved transfer",
        )

        # --- Fail-closed classification negatives ---
        negatives = [
            ("NOT_A_TRAP_RECORD", {"op": "nop", "terminator": None, "control_flow": False,
                                   "exception_transfer": False, "delay_slot": False, "target": None,
                                   "address": 0x80010000, "word": 0}),
            ("TRAP_FLAG_MISMATCH", {"op": "break", "terminator": "external-trap", "control_flow": False,
                                    "exception_transfer": True, "delay_slot": False, "target": None,
                                    "address": 0x80010000, "word": 0x0000004D}),
            ("TRAP_HAS_DELAY_SLOT", {"op": "break", "terminator": "external-trap", "control_flow": True,
                                     "exception_transfer": True, "delay_slot": True, "target": None,
                                     "address": 0x80010000, "word": 0x0000004D}),
            ("TRAP_HAS_TARGET", {"op": "break", "terminator": "external-trap", "control_flow": True,
                                 "exception_transfer": True, "delay_slot": False, "target": 0x80010000,
                                 "address": 0x80010000, "word": 0x0000004D}),
        ]
        for expected_code, record in negatives:
            observed = None
            try:
                exception.classify_trap_site(record)
            except exception.TrapClassificationError as exc:
                observed = exc.code
            check(f"negative:{expected_code}", observed == expected_code, str(observed))

        code_mismatch = {
            "op": "break", "terminator": "external-trap", "control_flow": True,
            "exception_transfer": True, "delay_slot": False, "target": None,
            "address": 0x80010000, "word": 0x0000004D, "operands": {"code": 2},
        }
        observed = None
        try:
            exception.classify_trap_site(code_mismatch)
        except exception.TrapClassificationError as exc:
            observed = exc.code
        check("negative:TRAP_CODE_OUT_OF_RANGE", observed == "TRAP_CODE_OUT_OF_RANGE", str(observed))

        # --- Private site classification (non-reconstructive) ---
        check("private:present", private_path.is_file(), "private fixture present")
        private_record: dict = {
            "schema": "openrecomp-phase10-break-classification-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "is_pass_criterion": False,
            "architectural_facts": facts,
            "public_encoding_evidence": encoding,
            "bounded_handling_strategy": {
                "static": "explicit terminal exception site (InstructionFlow.TRAP, no successor, no delay slot)",
                "dynamic": "fail closed with GUEST_BREAK / GUEST_SYSCALL; no exception delivery, no BIOS handler, no continuation",
                "never": [
                    "manufactured delay slot",
                    "fabricated fall-through past a trap",
                    "invented exception-vector dispatch",
                    "invented BIOS handler semantics",
                ],
            },
            "generated_exception_machinery": "none",
            "public_fixtures": {
                name: [f"0x{word:08x}" for word in words]
                for name, words in sorted(image_records.items())
            },
        }
        if private_path.is_file():
            private_image = psx.ingest(private_path.read_bytes())
            private_identity = private_image.identity()
            check("private:file-sha256", private_identity["file_sha256"] == PRIVATE_EXPECTED["file_sha256"], private_identity["file_sha256"])
            check("private:entry", private_image.header.pc0 == PRIVATE_EXPECTED["entry"], f"0x{private_image.header.pc0:08x}")

            private_contract = memory_map.build_contract(private_image)
            private_flat = memory_map.flat_image(private_image)
            private_pipeline = bridge.analyze(private_image, private_contract, private_flat)
            private_analysis = private_pipeline.analysis
            private_reachable = set(private_analysis["reachable_addresses"])
            check("private:break-reachable", PRIVATE_EXPECTED["break_site"] in private_reachable, "reachable")

            trap_records = [
                record for record in private_analysis["records"]
                if record["terminator"] == "external-trap" and record["address"] in private_reachable
            ]
            private_traps = exception.classify_trap_sites(trap_records)
            check("private:trap-site-count", private_traps["site_count"] == 3, str(private_traps["site_count"]))
            check(
                "private:trap-histogram",
                private_traps["histogram"] == {"break": 1, "syscall": 2},
                json.dumps(private_traps["histogram"], sort_keys=True),
            )
            break_record = next(item for item in private_traps["sites"] if item["op"] == "break")
            check("private:break-site", break_record["site"] == PRIVATE_EXPECTED["break_site"], break_record["site_hex"])
            check("private:break-code", break_record["code"] == PRIVATE_EXPECTED["break_code"], str(break_record["code"]))
            check("private:break-exception", break_record["exception_name"] == "Bp", break_record["exception_name"])
            check("private:break-successors", break_record["successors"] == [], "none")
            check("private:break-continuation", break_record["continuation"] == "NOT_MODELLED_FAIL_CLOSED", break_record["continuation"])
            check(
                "private:break-vector-expectation",
                break_record["vector_bev0"] == "0x80000080" and break_record["vector_bev1"] == "0xbfc00180",
                f"{break_record['vector_bev0']}/{break_record['vector_bev1']}",
            )

            context = exception.trap_site_context(private_analysis, PRIVATE_EXPECTED["break_site"])
            check("private:context-region-start", context["region_start"] == PRIVATE_EXPECTED["predicted_region_start"], context["region_start_hex"])
            check("private:context-region-is-entry", context["region_start_is_entry"] is True, str(context["region_start_is_entry"]))
            check(
                "private:context-predecessor",
                context["predecessor_site"] == PRIVATE_EXPECTED["predicted_predecessor"],
                context["predecessor_site_hex"],
            )
            check(
                "private:context-predecessor-kind",
                context["predecessor_kind"] == PRIVATE_EXPECTED["predicted_predecessor_kind"],
                context["predecessor_kind"],
            )
            check("private:context-inbound-targets", context["inbound_target_count"] == 0, str(context["inbound_target_count"]))
            check("private:context-fallthrough-only", context["reached_by_fallthrough_only"] is True, "true")
            check(
                "private:context-no-return-before",
                context["reachable_return_count_before_site"] == 0,
                str(context["reachable_return_count_before_site"]),
            )
            check(
                "private:context-chain",
                context["predecessor_chain"] == [
                    {"address": PRIVATE_EXPECTED["predicted_predecessor"], "role": "direct-call-continuation"},
                    {"address": PRIVATE_EXPECTED["predicted_predecessor"] + 4, "role": "straight-line-predecessor"},
                ],
                json.dumps(context["predecessor_chain"], sort_keys=True),
            )

            region_records = [
                record for record in private_analysis["records"]
                if context["region_start"] <= record["address"] < PRIVATE_EXPECTED["break_site"]
                and record["address"] in private_reachable
            ]
            region_zero_stores = sum(
                1 for record in region_records if record["op"] == "sw" and record["operands"].get("rt") == 0
            )
            region_increments = sum(
                1 for record in region_records
                if record["op"] == "addiu" and record["operands"].get("rs") == record["operands"].get("rt")
            )
            next_record = next(
                record for record in private_analysis["records"]
                if record["address"] == PRIVATE_EXPECTED["break_site"] + 4
            )
            call_targets_in_region = sorted(
                record["target"] for record in region_records
                if record["control_flow"] and record["terminator"] == "direct-call"
                and isinstance(record["target"], int)
            )
            check("private:region-zero-stores", region_zero_stores >= 1, str(region_zero_stores))
            check("private:region-increments", region_increments >= 1, str(region_increments))
            check(
                "private:region-call-targets",
                call_targets_in_region == sorted([0x80011AF0, 0x800119C8]),
                ",".join(f"0x{value:08x}" for value in call_targets_in_region),
            )

            private_record.update(
                {
                    "identity": private_identity,
                    "trap_classification": private_traps,
                    "break_site_context": context,
                    "region_observations": {
                        "region_start": context["region_start_hex"],
                        "region_start_is_entry_point": True,
                        "region_reachable_words": len(region_records),
                        "region_zero_stores": region_zero_stores,
                        "region_self_incrementing_addiu": region_increments,
                        "region_direct_call_targets": [f"0x{value:08x}" for value in call_targets_in_region],
                        "next_word_decode_class": next_record["decode_class"],
                    },
                    "role_classification": {
                        "role": "entry-function-terminator-after-application-entry-call",
                        "basis": [
                            "the site lies in a region beginning at the PS-X EXE entry point",
                            "no reachable function return exists between the region start and the site",
                            "the site is reached only by the fall-through continuation of a direct call",
                            "the region contains consecutive zero stores and self-incrementing address arithmetic",
                            "the following word is not reachable code",
                        ],
                        "not_claimed": [
                            "assertion/debugger semantics",
                            "BIOS handler behaviour",
                            "continuation after the exception",
                        ],
                    },
                    "dynamic_reachability": {
                        "status": "NOT_YET_DETERMINED",
                        "resolved_by": "P10-05 bounded native execution",
                        "static": "REQUIRED_BY_FALLTHROUGH",
                    },
                }
            )
        write_json(evidence / "break_classification.json", private_record)
        if private_path.is_file():
            _assert_no_payload_leak("break-classification", private_record, private_image.payload)

        # --- No generic exception machinery and no shared-layer change ---
        diff = git("diff", "--name-only", BASELINE_COMMIT, "--", *SHARED_LAYERS)
        check("integrity:shared-layers-unchanged", diff == "", diff or "none")
        for attr in ("install_handler", "vector_dispatch", "deliver_exception", "exception_handler"):
            check(
                f"integrity:no-{attr}",
                not hasattr(exception, attr),
                "absent",
            )
        check(
            "integrity:trap-handling-is-terminator",
            break_record["handling"] == "explicit-trap-terminator",
            break_record["handling"],
        )

        # --- Claim guards ---
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
    record = {
        "stage": STAGE,
        "stage_name": "BREAK semantic classification",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p10_01_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_01={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
