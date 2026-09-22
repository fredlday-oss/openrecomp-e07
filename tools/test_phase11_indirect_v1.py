#!/usr/bin/env python3
"""Deterministic P11-02 dynamic indirect-control frontier gate.

The gate resolves exactly the causal indirect-control frontier established by
P11-01 and proves that the resolution moves the frontier:

* every reachable indirect-control site is classified against the audited BIOS
  jump-table convention (vector base in the source register, function index in
  the transfer's delay slot); the causal site resolves to the documented
  ``ps1.bios.A0.2b`` memset service;
* the resolved site is emitted as an explicit host call through the shared
  generic runtime ABI and served by a typed host-side BIOS service implemented
  through the frozen checked guest memory boundary (documented semantics, no
  BIOS image, no invented return);
* public synthetic native fixtures verify the service contract (fill with a
  non-zero byte, exact length, refusal on ``dst == 0``, fail-closed on an
  out-of-range destination and on an unimplemented vector index);
* the private fixture reruns deterministically, the frontier moves to the next
  exact blocker (``ps1.bios.A0.3f`` at ``0x80026cec``) with 468147 clean
  block entries before it, and the remaining BIOS surface stays fail-closed;
* a deterministic block-entry budget closes the recorded Phase-10 bounded
  execution gap (an access-free guest loop after truncation).

On success it emits::

    OPENRECOMP_P11_02=PASS
    OPENRECOMP_PHASE11_INDIRECT_V1=PASS tests=<count>
    OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase11_indirect_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p10_fixture_identity_v1 as fixture  # noqa: E402
import p10_structure_v1 as p10_structure  # noqa: E402
import p11_bios_v1 as bios  # noqa: E402
import p11_cache_v1 as cache  # noqa: E402
import p11_emission_v1 as emission  # noqa: E402
import p11_native_v1 as native  # noqa: E402
import p11_runtime_v1 as p11_runtime  # noqa: E402
import p11_semantics_v1 as semantics  # noqa: E402
import p11_structure_v1 as structure_bridge  # noqa: E402
import p11_trace_v1 as trace  # noqa: E402
from openrecomp.indirect_control_flow import (  # noqa: E402
    IndirectControlFlowBasis,
    IndirectControlFlowEvidence,
    IndirectControlFlowKind,
    IndirectControlFlowStatus,
)
from openrecomp.program_model import ProgramSource  # noqa: E402
from tools import test_phase10_semantics_v1 as fixture_gate  # noqa: E402

STAGE = "P11-02"
FEATURE_MARKER = "OPENRECOMP_PHASE11_INDIRECT_V1"
INITIALIZATION_MARKER = "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

FROZEN_PROGRAM_FINGERPRINT = "a047a52fb460d3786e5bff03b5c26ac2978ae768b581f5e6c4a9cbc284db4a9a"

#: The documented service surface this stage resolved. Later stages extend the
#: module surface; this stage pins its own subset so its record stays exactly
#: reproducible.
SERVICE_SUBSET = {
    "A0": {0x2B: bios.DOCUMENTED_A0_SERVICES[0x2B]},
    "B0": {},
    "C0": {},
}

EXPECTED_SERVICE_SITE = {
    "site": "0x80026ccc",
    "vector": "A0",
    "index": 0x2B,
    "name": "memset",
    "op_name": "jump_bios_a0_2b",
    "service_id": "ps1.bios.A0.2b",
    "kind": "INDIRECT_JUMP",
    "slice_evidence": ["addiu@0x80026cc8"],
    "index_evidence": ["index-addiu@0x80026cd0"],
}

#: Every reachable BIOS vector site in the fixture: site -> (vector, index, name).
EXPECTED_VECTOR_SITES = {
    "0x80015b84": ("A0", 0x43, "DoExecute"),
    "0x80015b94": ("A0", 0x44, "FlushCache"),
    "0x80015ba4": ("A0", 0x70, "_bu_init"),
    "0x80015edc": ("B0", 0x12, None),
    "0x80015eec": ("B0", 0x13, None),
    "0x80015f3c": ("B0", 0x5B, None),
    "0x80015f4c": ("C0", 0x02, "SysEnqIntRP"),
    "0x80015f5c": ("C0", 0x03, "SysDeqIntRP"),
    "0x80015fa4": ("B0", 0x57, None),
    "0x800161e0": ("C0", 0x0A, None),
    "0x8001b424": ("A0", 0x49, "GPU_cw"),
    "0x80026c74": ("B0", 0x3F, "puts"),
    "0x80026ccc": ("A0", 0x2B, "memset"),
    "0x80026cdc": ("A0", 0x30, "srand"),
    "0x80026cec": ("A0", 0x3F, "printf"),
    "0x80026e24": ("B0", 0x4A, None),
    "0x80026e34": ("B0", 0x4B, None),
    "0x80026ebc": ("B0", 0x56, None),
    "0x80026f74": ("B0", 0x57, None),
}

#: The new frontier after the resolution (access budget 1500000, no bound hit).
EXPECTED_FRONTIER = {
    "failure_site": "0x80026cec",
    "failure_source": "0x000000a0",
    "failure_message": "unresolved indirect jump",
    "failure_function": "0x80026ce8",
    "failure_block": "blk_80026ce8",
    "failure_block_index": 468147,
    "failure_count": 29,
    "block_events": 966069,
    "block_digest": "0x2e874f4475dc4486",
    "distinct_blocks": 357,
    "distinct_functions": 90,
    "reads": "636971",
    "writes": "721775",
    "denied": "11",
    "host_calls": "81",
    "p10_access_count": "1500005",
    "p10_budget_denials": "5",
    "memory": "0x18131c6ef356df7d",
    "gpu_events": "65536",
    "input_events": "65536",
    "cdrom_events": "38",
    "spu_events": "5",
    "nonram_signatures": "17",
    "progress_gain_vs_p11_01": 468147 - 9424,
}

OBSERVABLE_KEYS = (
    "failed", "error", "exit_status", "registers", "memory",
    "gpu_events", "gpu", "input_events", "input", "spu_events", "spu",
    "cdrom_events", "cdrom", "reads", "writes", "denied", "host_calls",
    "p10_access_budget", "p10_access_count", "p10_budget_denials",
    "p10_service_calls", "p10_service_failures",
    "nonram_signatures", "nonram_overflow",
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def assert_no_payload_leak(label: str, document: dict, payload: bytes) -> None:
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
    for value in _string_values(document):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def structure_for_words(words: list[int]):
    """The Phase-11 BIOS-overlaid structure for one synthetic word list."""
    data = fixture_gate.builder.build_from_words(words, load_address=fixture_gate.LOAD)
    image = psx.ingest(data)
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
    base = p10_structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
    result, document = structure_bridge.analyze_structure_with_bios(
        pipeline.analysis, source=source, entry=image.header.pc0, services=SERVICE_SUBSET
    )
    sites = bios.resolved_sites(document)
    return image, contract, flat, base, result, sites, document


def synthetic_words(*, index: int, dst: int, fill: int, length: int, read_back: bool,
                    tail: tuple[tuple[str, dict], ...] = ()) -> list[int]:
    """A tiny OpenRecomp-authored program that calls an A0 vector stub.

    The BIOS call is a ``jal`` to a two-instruction stub (the audited PS1
    pattern), so the caller's continuation is reachable in the neutral CFG and
    the host call returns into it.
    """
    a = fixture_gate.Assembler()
    a.i("lui", rt=8, imm=0x8002)
    a.i("addiu", rs=8, rt=8, imm=8)
    a.i("addiu", rt=9, imm=0x55)
    a.i("sw", rs=8, rt=9, imm=0)          # sentinel word at 0x80020008
    a.i("lui", rt=4, imm=(dst >> 16) & 0xFFFF)
    a.i("ori", rs=4, rt=4, imm=dst & 0xFFFF)
    a.i("addiu", rt=5, imm=fill & 0xFFFF)
    a.i("addiu", rt=6, imm=length & 0xFFFF)
    a.jump("jal", "bios_stub")            # A0 vector call through the stub
    a.nop()
    if read_back:
        a.i("lw", rs=4, rt=8, imm=0)
        a.i("lw", rs=4, rt=9, imm=4)
        a.i("lui", rt=10, imm=0x8002)
        a.i("addiu", rs=10, rt=10, imm=8)
        a.i("lw", rs=10, rt=10, imm=0)
    for op, operands in tail:
        a.i(op, **operands)
    a.r("jr", rs=31)
    a.nop()
    a.label("bios_stub")
    a.i("addiu", rt=10, imm=0xA0)         # $t2 = A0 vector base
    a.r("jr", rs=10)                      # A0 vector call
    a.i("addiu", rt=9, imm=index)         # delay slot: $t1 = function index
    return a.finish()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-02")
    parser.add_argument("--private-fixture-root", default=str(DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()

    evidence = (ROOT / options.evidence_dir).resolve()
    fixture_root = pathlib.Path(options.private_fixture_root)
    build_root = ROOT / ".openrecomp-phase11" / "build"

    try:
        # --- 1. private BIOS vector frontier ---------------------------------
        check("fixture:directory", fixture_root.is_dir(), "private fixture directory present")
        image = psx.ingest((fixture_root / fixture.PRIMARY_EXECUTABLE).read_bytes())
        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)
        source = ProgramSource(
            "mips32-bounded-v1",
            adapter="adapters.mips32",
            address_width_bits=32,
            endianness="little",
            input_sha256=image.file_sha256,
        )
        pipeline = bridge.analyze(image, contract, flat)
        base_result = p10_structure.analyze_structure(pipeline.analysis, source=source, entry=image.header.pc0)
        result, site_document = structure_bridge.analyze_structure_with_bios(
            pipeline.analysis, source=source, entry=image.header.pc0, services=SERVICE_SUBSET
        )
        sites = bios.resolved_sites(site_document)
        classification = bios.classify_vector_sites(pipeline.analysis, services=SERVICE_SUBSET)
        check(
            "bios:histogram",
            classification["histogram"] == {"BIOS_VECTOR_SERVICE": 1, "BIOS_VECTOR_NOT_IMPLEMENTED": 18},
            json.dumps(classification["histogram"], sort_keys=True),
        )
        observed_sites = {
            item["site_hex"]: (item["vector"], item["function_index"], item["documented_name"])
            for item in classification["sites"]
        }
        check(
            "bios:site-table",
            observed_sites == EXPECTED_VECTOR_SITES,
            json.dumps(observed_sites, sort_keys=True),
        )
        check("bios:resolved-count", len(sites) == 1, str(len(sites)))
        resolved = sites[0]
        check("bios:resolved-site", f"0x{resolved.site:08x}" == EXPECTED_SERVICE_SITE["site"], hex(resolved.site))
        check("bios:resolved-vector", resolved.vector == EXPECTED_SERVICE_SITE["vector"], resolved.vector)
        check("bios:resolved-index", resolved.function_index == EXPECTED_SERVICE_SITE["index"], str(resolved.function_index))
        check("bios:resolved-op", resolved.op_name == EXPECTED_SERVICE_SITE["op_name"], str(resolved.op_name))
        check("bios:resolved-service", resolved.service_id == EXPECTED_SERVICE_SITE["service_id"], str(resolved.service_id))
        check("bios:resolved-kind", resolved.kind == EXPECTED_SERVICE_SITE["kind"], resolved.kind)
        check(
            "bios:resolved-evidence",
            list(resolved.slice_evidence) == EXPECTED_SERVICE_SITE["slice_evidence"]
            and list(resolved.index_evidence) == EXPECTED_SERVICE_SITE["index_evidence"],
            f"{resolved.slice_evidence} {resolved.index_evidence}",
        )
        check(
            "bios:documented-name",
            classification["documented_a0_services"]["0x2b"]["name"] == EXPECTED_SERVICE_SITE["name"],
            json.dumps(classification["documented_a0_services"], sort_keys=True),
        )
        check(
            "bios:not-implemented-stay-fail-closed",
            all(item["op_name"] is None and item["service_id"] is None
                for item in classification["sites"] if item["classification"] != "BIOS_VECTOR_SERVICE"),
            "no unimplemented index is renamed",
        )

        # The shared classifier carries the external-runtime evidence.
        classified_site = None
        for unit in result.classification.units:
            for item in unit.classifications:
                if item.address == resolved.site:
                    classified_site = item
        check("classifier:site-present", classified_site is not None, "site classified")
        check(
            "classifier:external-status",
            classified_site.status is IndirectControlFlowStatus.EXTERNAL_OR_RUNTIME_MEDIATED,
            classified_site.status.value,
        )
        check(
            "classifier:external-basis",
            classified_site.basis is IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE,
            classified_site.basis.value,
        )
        check(
            "classifier:external-mechanism",
            classified_site.external_mechanism == "ps1.bios.A0",
            str(classified_site.external_mechanism),
        )
        check(
            "classifier:evidence-proven",
            classified_site.evidence.value == "PROVEN",
            classified_site.evidence.value,
        )
        # Fail-closed evidence validation: a RESOLVED claim with external basis
        # and a BOUNDED claim without bounded evidence must both be rejected.
        rejected = 0
        for status, basis in (
            (IndirectControlFlowStatus.RESOLVED, IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE),
            (IndirectControlFlowStatus.BOUNDED_CANDIDATES, IndirectControlFlowBasis.EXTERNAL_RUNTIME_EVIDENCE),
        ):
            try:
                IndirectControlFlowEvidence(
                    function_id=classified_site.function_id,
                    block_id=classified_site.block_id,
                    address=classified_site.address,
                    kind=IndirectControlFlowKind.INDIRECT_JUMP,
                    status=status,
                    basis=basis,
                    external_mechanism="ps1.bios.A0",
                    source="phase11-negative",
                )
            except ValueError:
                rejected += 1
        check("classifier:invalid-claims-rejected", rejected == 2, str(rejected))

        # --- 2. semantics, services and runtime composition -------------------
        rule_document = semantics.semantics_document(sites)
        check("semantics:bios-rule-count", len(rule_document["bios_rules"]) == 1, str(len(rule_document["bios_rules"])))
        check(
            "semantics:bios-rule",
            rule_document["bios_rules"][0]["op"] == EXPECTED_SERVICE_SITE["op_name"]
            and rule_document["bios_rules"][0]["service"] == EXPECTED_SERVICE_SITE["service_id"]
            and rule_document["bios_rules"][0]["args"] == ["bios_arg0", "bios_arg1", "bios_arg2"]
            and rule_document["bios_rules"][0]["result"] == "bios_ret",
            json.dumps(rule_document["bios_rules"], sort_keys=True),
        )
        check(
            "semantics:phase10-rules-reused",
            rule_document["rules_total"]
            == len(p10_structure_rule_count()) + len(semantics_added_rules()) + 1,
            str(rule_document["rules_total"]),
        )
        check(
            "semantics:service-surface",
            rule_document["service_ids"] == sorted(list(p10_service_ids()) + ["ps1.bios.A0.2b"]),
            ",".join(rule_document["service_ids"]),
        )
        check(
            "semantics:service-arity",
            rule_document["service_arities"]["ps1.bios.A0.2b"] == 3,
            str(rule_document["service_arities"]["ps1.bios.A0.2b"]),
        )
        service_table = semantics.build_service_table(sites)
        numeric_id = service_table.numeric_id("ps1.bios.A0.2b")
        check("semantics:numeric-id", numeric_id == 8, str(numeric_id))

        composed, runtime_record = p11_runtime.compose_runtime_source(sites, trace=True)
        frozen, _ = p11_runtime.p10_runtime.compose_runtime_source()
        expected_prefix = frozen.replace(
            p11_runtime.HOST_CALL_DEFINITION_ANCHOR, p11_runtime.HOST_CALL_DECLARATION_REPLACEMENT
        ).replace(
            p11_runtime.HOST_CALL_FALLBACK_ANCHOR, p11_runtime.HOST_CALL_FALLBACK_REPLACEMENT
        ).rstrip("\n")
        check(
            "runtime:phase10-verbatim-prefix",
            composed.startswith(expected_prefix),
            "the Phase-10 composition is preserved except the two anchored substitutions",
        )
        check(
            "runtime:substitution-count",
            len(runtime_record["substitutions"]) == 2,
            str(len(runtime_record["substitutions"])),
        )
        check(
            "runtime:service-id-macro",
            f"#define OR_RT_SERVICE_PS1_BIOS_A0_2B UINT64_C({numeric_id})" in composed,
            "generated macro matches the declared numeric id",
        )
        check(
            "runtime:frozen-source-reused",
            runtime_record["base"]["frozen_source_reused_verbatim"] is True,
            "frozen Phase-9 runtime reused verbatim",
        )
        check("runtime:bios-fragment", runtime_record["bios_fragment"]["fragment_sha256"] != "", "fragment recorded")
        check("runtime:trace-fragment", runtime_record["trace_fragment"]["fragment_sha256"] != "", "trace recorded")
        # Composition negatives.
        try:
            p11_runtime.service_id_macros([])
            empty_rejected = False
        except p11_runtime.Phase11RuntimeError:
            empty_rejected = True
        check("runtime:empty-service-table-rejected", empty_rejected, "empty service surface fails closed")
        try:
            p11_runtime._inject_service_ids("no anchor here", ["ps1.bios.A0.2b"])
            anchor_rejected = False
        except p11_runtime.Phase11RuntimeError:
            anchor_rejected = True
        check("runtime:missing-anchor-rejected", anchor_rejected, "missing anchor fails closed")

        # --- 3. private native runs ------------------------------------------
        traced_build = emission.build_bios_build_set(
            result, base_result, contract, flat, image.file_sha256, sites=sites, trace=True
        )
        untraced_build = emission.build_bios_build_set(
            result, base_result, contract, flat, image.file_sha256, sites=sites, trace=False
        )
        check(
            "emission:base-identity",
            traced_build["base_program_fingerprint"] == FROZEN_PROGRAM_FINGERPRINT,
            traced_build["base_program_fingerprint"],
        )
        check(
            "emission:program-carries-bios-rule",
            "OR_RT_SERVICE_PS1_BIOS_A0_2B" in traced_build["files"][emission.PROGRAM_NAME],
            "declared service macro present",
        )
        check(
            "emission:no-guest-machine-code",
            image.payload[:64].hex() not in traced_build["files"][emission.PROGRAM_NAME].lower(),
            "no guest payload bytes in the generated program",
        )
        traced_native = native.build_native(
            traced_build, build_root / "p11-02-traced", fixture_id="p11-02-traced"
        )
        untraced_native = native.build_native(
            untraced_build, build_root / "p11-02-untraced", fixture_id="p11-02-untraced"
        )
        check("native:traced-build", all(status == "OK" for status in traced_native["build_status"]),
              str(traced_native["build_status"]))
        check("native:untraced-build", all(status == "OK" for status in untraced_native["build_status"]),
              str(untraced_native["build_status"]))
        check("native:traced-reproducible", traced_native["build_reproducible"] is True,
              traced_native["executable_sha256"])
        check("native:untraced-reproducible", untraced_native["build_reproducible"] is True,
              untraced_native["executable_sha256"])

        frontier_run = native.run_native(
            traced_native["executables"][0], access_budget=1500000, block_budget=8000000, timeout=600
        )
        frontier_second = native.run_native(
            traced_native["executables"][0], access_budget=1500000, block_budget=8000000, timeout=600
        )
        check("frontier:deterministic", frontier_run["stdout_sha256"] == frontier_second["stdout_sha256"],
              frontier_run["stdout_sha256"])
        check("frontier:exit", frontier_run["returncode"] == 0, str(frontier_run["returncode"]))
        check("frontier:stderr", frontier_run["stderr_bytes"] == 0, str(frontier_run["stderr_bytes"]))
        traced = frontier_run["parsed"]
        for key, expected in sorted(EXPECTED_FRONTIER.items()):
            if key in ("failure_site", "failure_source", "failure_message", "failure_function",
                       "failure_block", "failure_block_index", "failure_count", "block_events",
                       "block_digest", "distinct_blocks", "distinct_functions",
                       "progress_gain_vs_p11_01"):
                continue
            check(f"frontier:{key}", traced.get(key) == expected, str(traced.get(key)))

        untraced_run = native.run_native(
            untraced_native["executables"][0], access_budget=1500000, block_budget=8000000, timeout=600
        )
        plain = untraced_run["parsed"]
        mismatches = [key for key in OBSERVABLE_KEYS if plain.get(key) != traced.get(key)]
        check("frontier:semantics-equivalent", not mismatches, ",".join(mismatches[:4]) or "all observables")
        check(
            "frontier:nonram-identical",
            plain["nonram"] == traced["nonram"],
            "non-RAM access log identical",
        )
        check(
            "frontier:register-file-identical",
            plain["register_file"] == traced["register_file"],
            "register file identical",
        )

        index = trace.StructureIndex(result)
        analysis = trace.analyze_trace(traced, index, None)
        failure = analysis["failure"]
        check("frontier:site", failure["site"] == EXPECTED_FRONTIER["failure_site"], failure["site"])
        check("frontier:source", failure["source_value"] == EXPECTED_FRONTIER["failure_source"], str(failure["source_value"]))
        check("frontier:message", failure["message"] == EXPECTED_FRONTIER["failure_message"], str(failure["message"]))
        check(
            "frontier:function",
            failure["function_entry"] == EXPECTED_FRONTIER["failure_function"]
            and failure["block_id"] == EXPECTED_FRONTIER["failure_block"],
            f"{failure['function_entry']}/{failure['block_id']}",
        )
        check(
            "frontier:block-index",
            failure["block_index"] == EXPECTED_FRONTIER["failure_block_index"],
            str(failure["block_index"]),
        )
        check(
            "frontier:failure-count",
            failure["failure_count"] == EXPECTED_FRONTIER["failure_count"],
            str(failure["failure_count"]),
        )
        check(
            "frontier:totals",
            analysis["totals"]["block_events"] == EXPECTED_FRONTIER["block_events"]
            and analysis["totals"]["block_digest"] == EXPECTED_FRONTIER["block_digest"]
            and analysis["totals"]["distinct_blocks"] == EXPECTED_FRONTIER["distinct_blocks"]
            and analysis["totals"]["distinct_functions"] == EXPECTED_FRONTIER["distinct_functions"],
            json.dumps(analysis["totals"], sort_keys=True),
        )
        check(
            "frontier:moved-past-memset",
            failure["site"] != "0x80026ccc"
            and failure["block_index"] > 9424
            and EXPECTED_FRONTIER["progress_gain_vs_p11_01"] == 458723,
            f"progress {failure['block_index']} vs 9424",
        )
        check(
            "frontier:memset-served",
            traced.get("p10_service_failures") == "0"
            and int(traced.get("host_calls", "0")) > 79,
            f"host_calls={traced.get('host_calls')} failures={traced.get('p10_service_failures')}",
        )
        check(
            "frontier:new-blocker-is-printf-site",
            observed_sites["0x80026cec"][1] == 0x3F,
            str(observed_sites["0x80026cec"]),
        )

        # Bounded-execution closure: the default access budget plus the block
        # budget terminates deterministically even though the post-failure path
        # contains an access-free loop.
        bounded_run = native.run_native(
            traced_native["executables"][0], access_budget=2000000, block_budget=8000000, timeout=900
        )
        bounded = bounded_run["parsed"]
        check("bounded:terminates", bounded_run["returncode"] == 0, str(bounded_run["returncode"]))
        check(
            "bounded:block-budget-reached",
            bounded.get("bound_reached") == "1"
            and bounded.get("bound_budget") == "8000000"
            and int(bounded.get("trace_block_events", "0")) == 8000001,
            json.dumps({key: bounded.get(key) for key in ("bound_reached", "bound_budget", "trace_block_events")},
                       sort_keys=True),
        )
        check(
            "bounded:access-budget-reached",
            int(bounded.get("p10_access_count", "0")) > 2000000,
            str(bounded.get("p10_access_count")),
        )
        bounded_second = native.run_native(
            traced_native["executables"][0], access_budget=2000000, block_budget=8000000, timeout=900
        )
        check("bounded:deterministic", bounded_run["stdout_sha256"] == bounded_second["stdout_sha256"],
              bounded_run["stdout_sha256"])

        # --- 4. public synthetic service fixtures ----------------------------
        synthetic_records: list[dict] = []
        cases = (
            (
                "memset-positive",
                synthetic_words(index=0x2B, dst=0x80020000, fill=0xAB, length=8, read_back=True),
                {"failed": "0", "error": "", "r02": "0x80020000", "r08": "0xabababab",
                 "r09": "0xabababab", "r10": "0x00000055"},
            ),
            (
                "memset-refusal-zero-dst",
                synthetic_words(index=0x2B, dst=0, fill=0xAB, length=8, read_back=False,
                                tail=(("addiu", {"rs": 2, "rt": 3, "imm": 1}),)),
                {"failed": "0", "error": "", "r02": "0x00000000", "r03": "0x00000001"},
            ),
            (
                "memset-refusal-zero-length",
                synthetic_words(index=0x2B, dst=0x80020000, fill=0xAB, length=0, read_back=True),
                {"failed": "0", "error": "", "r02": "0x00000000", "r08": "0x00000000",
                 "r09": "0x00000000", "r10": "0x00000055"},
            ),
            (
                "memset-out-of-range-dst",
                synthetic_words(index=0x2B, dst=0x10000000, fill=0xAB, length=8, read_back=False),
                {"failed": "1", "error": "runtime host service ps1.bios.A0.2b failed"},
            ),
            (
                "unknown-index-fail-closed",
                synthetic_words(index=0x99, dst=0x80020000, fill=0xAB, length=8, read_back=False),
                {"failed": "1", "error": "unresolved indirect jump"},
            ),
        )
        for name, words, expectations in cases:
            synth_image, synth_contract, synth_flat, synth_base, synth_result, synth_sites, _ = structure_for_words(words)
            synth_build = emission.build_bios_build_set(
                synth_result, synth_base, synth_contract, synth_flat, synth_image.file_sha256,
                sites=synth_sites, trace=False,
            )
            synth_native = native.build_native(
                synth_build, build_root / f"p11-02-{name}", fixture_id=f"p11-02-{name}", run_count=2
            )
            check(f"synthetic:{name}:build", all(status == "OK" for status in synth_native["build_status"]),
                  str(synth_native["build_status"]))
            synth_run = native.run_native(synth_native["executables"][0], timeout=300)
            synth_second = native.run_native(synth_native["executables"][0], timeout=300)
            check(f"synthetic:{name}:deterministic",
                  synth_run["stdout_sha256"] == synth_second["stdout_sha256"], synth_run["stdout_sha256"])
            synth_parsed = synth_run["parsed"]
            for key, expected in sorted(expectations.items()):
                observed = synth_parsed.get(key) if key not in synth_parsed["register_file"] else synth_parsed["register_file"][key]
                check(f"synthetic:{name}:{key}", observed == expected, str(observed))
            synthetic_records.append(
                {
                    "name": name,
                    "executable_sha256": synth_native["executable_sha256"],
                    "stdout_sha256": synth_run["stdout_sha256"],
                    "failed": synth_parsed.get("failed"),
                    "error": synth_parsed.get("error"),
                    "service_calls": synth_parsed.get("p10_service_calls"),
                    "service_failures": synth_parsed.get("p10_service_failures"),
                    "observables": {
                        key: synth_parsed["register_file"].get(key)
                        for key in ("r02", "r03", "r08", "r09", "r10")
                    },
                    "expected": expectations,
                }
            )
        check(
            "synthetic:service-invoked",
            all(record["service_calls"] == "1" for record in synthetic_records[:3]),
            json.dumps([record["service_calls"] for record in synthetic_records[:3]]),
        )
        check(
            "synthetic:failures-attributed",
            synthetic_records[3]["service_failures"] == "1" and synthetic_records[4]["service_calls"] == "0",
            json.dumps([(record["service_failures"], record["service_calls"]) for record in synthetic_records[3:]]),
        )

        # --- 5. cache provenance ---------------------------------------------
        identity = fixture.build_identity(fixture_root)
        provenance = cache.build_provenance(identity, traced=True)
        provenance["bios_site_plan_digest"] = hashlib.sha256(
            json.dumps(bios.site_plan(classification), sort_keys=True).encode("utf-8")
        ).hexdigest()
        phase_cache = cache.Phase11Cache(ROOT / ".openrecomp-phase11" / "cache")
        document = {"stage": STAGE, "service_site": EXPECTED_SERVICE_SITE["site"]}
        key = phase_cache.store(provenance, document)
        check("cache:hit", phase_cache.lookup(provenance) == document, "stored document returned")
        stale = dict(provenance)
        stale["bios_site_plan_digest"] = "0" * 64
        check("cache:site-plan-miss", phase_cache.key(stale) != key and phase_cache.lookup(stale) is None,
              "site plan is part of the key")

        # --- 6. evidence ------------------------------------------------------
        frontier_document = {
            "schema": "openrecomp-phase11-indirect-frontier-v1",
            "stage": STAGE,
            "label": "hercules-private-fixture",
            "bios_vector_classification": classification,
            "resolved_site": resolved.to_document(),
            "classifier_status": {
                "status": classified_site.status.value,
                "basis": classified_site.basis.value,
                "external_mechanism": classified_site.external_mechanism,
                "evidence": classified_site.evidence.value,
            },
            "documented_service": classification["documented_a0_services"]["0x2b"],
            "documented_index_names": {
                f"{vector}:0x{index:02x}": name
                for (vector, index), name in sorted(bios.DOCUMENTED_INDEX_NAMES.items())
            },
            "remaining_surface": [
                item for item in classification["sites"]
                if item["classification"] != "BIOS_VECTOR_SERVICE"
            ],
            "remaining_surface_count": classification["histogram"].get("BIOS_VECTOR_NOT_IMPLEMENTED", 0),
            "runtime_composition": runtime_record,
            "emission": {
                "program_fingerprint": traced_build["program_fingerprint"],
                "base_program_fingerprint": traced_build["base_program_fingerprint"],
                "files": [
                    {"name": name, "sha256": traced_build["hashes"][name],
                     "bytes": len(traced_build["files"][name].encode("utf-8"))}
                    for name in emission.EMISSION_NAMES
                ],
                "bios_sites": traced_build["bios_sites"],
                "semantics": rule_document,
            },
            "frontier_run": {
                "access_budget": 1500000,
                "block_budget": 8000000,
                "executable_sha256": traced_native["executable_sha256"],
                "stdout_sha256": frontier_run["stdout_sha256"],
                "observables": {key: traced.get(key) for key in OBSERVABLE_KEYS},
                "trace": {
                    key: traced.get(key) for key in (
                        "trace_block_events", "trace_function_events", "trace_block_digest",
                        "trace_distinct_blocks", "trace_distinct_functions",
                        "trace_failure_count", "trace_failure_site", "trace_failure_source",
                        "trace_failure_message", "trace_failure_block_index",
                        "trace_failure_function", "trace_ring_count",
                        "bound_budget", "bound_reached", "bound_denials",
                    )
                },
                "analysis": analysis,
                "uninstrumented_equivalence": {
                    "mismatches": mismatches,
                    "nonram_identical": plain["nonram"] == traced["nonram"],
                    "register_file_identical": plain["register_file"] == traced["register_file"],
                    "executable_sha256": untraced_native["executable_sha256"],
                },
            },
            "bounded_execution": {
                "access_budget": 2000000,
                "block_budget": 8000000,
                "terminates": True,
                "bound_reached": bounded.get("bound_reached") == "1",
                "block_events": bounded.get("trace_block_events"),
                "access_count": bounded.get("p10_access_count"),
                "stdout_sha256": bounded_run["stdout_sha256"],
                "closed_phase10_gap": [
                    "the access budget bounds memory accesses only; a post-truncation",
                    "guest loop with no memory access could not be interrupted",
                ],
            },
            "synthetic_service_fixtures": synthetic_records,
            "frontier_movement": {
                "previous_first_failure_site": "0x80026ccc",
                "previous_first_failure_block_index": 9424,
                "new_first_failure_site": EXPECTED_FRONTIER["failure_site"],
                "new_first_failure_block_index": EXPECTED_FRONTIER["failure_block_index"],
                "clean_progress_gain_block_entries": EXPECTED_FRONTIER["progress_gain_vs_p11_01"],
                "statement": [
                    "serving the proven A0:0x2b memset call removes the first fail-closed",
                    "event and moves the frontier to the next exact blocker, the",
                    "documented A0:0x3f printf vector call at 0x80026cec; every other",
                    "BIOS vector site stays fail-closed",
                ],
            },
        }
        cache_document = {
            "schema": "openrecomp-phase11-cache-v1",
            "stage": STAGE,
            "cache_root": ".openrecomp-phase11/cache",
            "provenance": provenance,
            "key": key,
            "checks": {"hit": True, "site_plan_miss": True},
        }
        for name, document in (("frontier", frontier_document), ("cache", cache_document)):
            write_json(evidence / f"{name}.json", document)
            assert_no_payload_leak(f"public:{name}", document, image.payload)

        check("claim:initialization-not-promoted", True, NOT_PROVEN)
        check("claim:frame-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-permanent", True, NOT_PROVEN)
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    stage_record = {
        "stage": STAGE,
        "stage_name": "Dynamic indirect-control frontier",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p11_02_tests.json", stage_record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P11_02={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{INITIALIZATION_MARKER}={NOT_PROVEN}")
    print(f"{FRAME_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


def p10_structure_rule_count() -> list:
    import p10_mips32_semantics_v1 as p10_semantics

    return list(p10_semantics.semantics_rules())


def semantics_added_rules() -> list:
    import p11_semantics_v1 as p11_semantics

    return list(p11_semantics.added_rules())


def p10_service_ids() -> list:
    import p10_mips32_semantics_v1 as p10_semantics

    return list(p10_semantics.build_service_table().service_ids)


if __name__ == "__main__":
    raise SystemExit(main())
