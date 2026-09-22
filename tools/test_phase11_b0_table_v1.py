#!/usr/bin/env python3
"""Deterministic P11-07 B0-table contract and bounded-blocker gate.

This stage pins the public B0:57 GetB0Table contract, proves the exact
post-return use made by the private caller using neutral IR only, and stops
before inventing a guest table entry or BIOS code object.  No BIOS service,
table, renderer, device behavior, or indirect target is implemented here.
"""

from __future__ import annotations

import argparse
import base64
import json
import pathlib
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase3/src", ".openrecomp-phase8/src",
              ".openrecomp-phase9/src", ".openrecomp-phase9/fixture",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p11_bios_v1 as bios  # noqa: E402
from tools import test_phase11_gpu_closure_v1 as p11_06  # noqa: E402


STAGE = "P11-07"
BLOCKER = "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE"
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN"

PSX_SPX_REVISION = "f37fc9a7a889a55e3bdec2d09a8a34640edf3082"
PCSX_REDUX_REVISION = "911271b7af5008a2fbbcb9b2390e26475208423d"
OPENBIOS_REVISION = "77adff516017044f2c6d9b21f66c124b9593959a"
PSX_BUNDLE_REVISION = "7787631c6ee37a489732c95cb0864422e3a3bdd1"

CALL_SITE = 0x80015FA4
CALLER_FUNCTION = "fn_80015f90"
CALLER_BLOCK = "blk_80015fa0"
CURRENT_BLOCK_INDEX = 468_341

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL",
                    "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def strings(document: Any):
    if isinstance(document, dict):
        for value in document.values():
            yield from strings(value)
    elif isinstance(document, list):
        for value in document:
            yield from strings(value)
    elif isinstance(document, str):
        yield document


def assert_public_safe(label: str, document: dict[str, Any], payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    sample = payload[:64]
    check(f"{label}:no-private-path", ":\\" not in text and "fixtures/" not in text,
          "absolute private paths absent")
    check(f"{label}:no-payload-hex", sample.hex() not in text.lower(),
          "payload sample absent")
    check(f"{label}:no-payload-base64",
          base64.b64encode(sample).decode("ascii") not in text,
          "payload sample absent")
    check(f"{label}:no-raw-words",
          all(term not in text for term in ("raw_instruction", "instruction_word",
                                            "payload_bytes", "bios_bytes")),
          "reconstructive fields absent")
    check(f"{label}:bounded-strings", all(len(value) <= 240 for value in strings(document)),
          "all strings bounded")


def operands(instruction: Any) -> dict[str, int]:
    return instruction.metadata.get("operands", {})


def public_contract_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase11-b0-57-public-contract-v1",
        "stage": STAGE,
        "service_id": "ps1.bios.B0.57",
        "established_contract": {
            "vector": "B0",
            "function_index": "0x57",
            "name": "GetB0Table",
            "arguments": [],
            "result": {"kind": "guest_pointer", "register": "$v0"},
            "object": "mutable B0 BIOS jump table",
            "entry_model": "32-bit guest function pointers indexed by B0 function number",
            "excluded_behavior": [
                "GPU", "renderer", "DMA", "VRAM", "interrupt", "timing", "frame"
            ],
        },
        "public_sources": [
            {
                "name": "PSX-SPX",
                "revision": PSX_SPX_REVISION,
                "path": "docs/kernelbios.md",
                "locations": ["B(57h) GetB0Table", "public pad-error patch descriptions"],
                "url": (
                    "https://github.com/psx-spx/psx-spx.github.io/blob/"
                    f"{PSX_SPX_REVISION}/docs/kernelbios.md"
                ),
                "establishes": [
                    "B0:57 returns the B0 jump-list address for entry patching",
                    "B0 entry 0x5B is read at byte offset 0x16C in the published patch pattern",
                    "the published pattern derives offsets 0x884 and 0x894 and mutates eleven words from 0x594",
                ],
            },
            {
                "name": "PCSX-Redux OpenBIOS",
                "superproject_revision": PCSX_REDUX_REVISION,
                "submodule_revision": OPENBIOS_REVISION,
                "license": "MIT",
                "license_path": "LICENSE",
                "license_url": (
                    "https://github.com/pcsx-redux/nugget/blob/"
                    f"{OPENBIOS_REVISION}/LICENSE"
                ),
                "paths": [
                    "openbios/kernel/handlers.c",
                    "openbios/kernel/vectors.s",
                    "openbios/psx-bios.ld",
                    "LICENSE",
                ],
                "url": (
                    "https://github.com/pcsx-redux/nugget/tree/"
                    f"{OPENBIOS_REVISION}/openbios"
                ),
                "establishes": [
                    "B0table is a mutable 0x60-entry pointer array",
                    "entry 0x57 returns B0table",
                    "unsupported entries use an explicit unimplemented thunk",
                    "B0table address is assigned by that implementation's linker, not fixed by the API",
                ],
            },
            {
                "name": "PCSX HLE BIOS in PSX-Bundle",
                "revision": PSX_BUNDLE_REVISION,
                "license": "GPL-2.0",
                "license_path": "COPYING",
                "license_url": (
                    "https://cgit.grumpycoder.net/cgit/PSX-Bundle/tree/"
                    f"COPYING?h=origin&id={PSX_BUNDLE_REVISION}"
                ),
                "path": "PcsxSrc/PsxBios.c",
                "url": (
                    "https://cgit.grumpycoder.net/cgit/PSX-Bundle/tree/PcsxSrc/"
                    f"PsxBios.c?h=origin&id={PSX_BUNDLE_REVISION}"
                ),
                "establishes": [
                    "an independently structured HLE returns 0x00000874 in v0",
                    "the HLE dispatch maps B0:57 to GetB0Table",
                    "the HLE does not establish guest B0 entry contents for this caller",
                ],
            },
        ],
        "address_and_initialization_boundary": {
            "contract_table_address": "implementation-defined",
            "legacy_hle_address": "0x00000874",
            "openbios_address": "linker-assigned B0table object",
            "phase11_selected_address": None,
            "phase11_selected_entry_5b_target": None,
            "reason": "no public source defines a portable guest code object satisfying the caller's B0:5B-relative accesses",
        },
    }


def caller_use_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase11-b0-57-caller-use-v1",
        "stage": STAGE,
        "evidence_class": "PRIVATE_FIXTURE_BOUNDED",
        "call": {
            "site": "0x80015fa4",
            "function_id": CALLER_FUNCTION,
            "block_id": CALLER_BLOCK,
            "block_index": CURRENT_BLOCK_INDEX,
            "vector": "B0",
            "function_index": "0x57",
            "argument_count": 0,
            "result_register": "$v0",
        },
        "post_return_use": [
            {
                "pc": "0x80015fac",
                "kind": "table_entry_read",
                "base": "$v0",
                "byte_offset": "0x16c",
                "entry_index": "0x5b",
                "width_bits": 32,
                "result": "$v0",
            },
            {
                "pc": "0x80015fb4",
                "kind": "derive_function_relative_pointer",
                "base": "B0[0x5b]",
                "byte_offset": "0x884",
                "stored_at": "0x8002ed84",
                "width_bits": 32,
            },
            {
                "pc": "0x80015fc0",
                "kind": "derive_function_relative_pointer",
                "base": "B0[0x5b]",
                "byte_offset": "0x894",
                "stored_at": "0x8002ed88",
                "width_bits": 32,
            },
            {
                "pc": "0x80015fd0",
                "kind": "function_relative_clear_loop",
                "base": "B0[0x5b]",
                "first_byte_offset": "0x594",
                "last_byte_offset": "0x5bc",
                "width_bits": 32,
                "write_count": 11,
                "value": "0x00000000",
            },
        ],
        "classification": {
            "first_required_entry": "B0:0x5b ChangeClearPAD",
            "table_access": "read-only 32-bit entry lookup",
            "subsequent_access": "mutating 32-bit writes to entry-target-relative guest memory",
            "expects_function_pointer": True,
            "patches_table_entry": False,
            "only_stores_table_pointer": False,
            "public_pattern_corroboration": "PSX-SPX pad-error patch description",
        },
        "next_frontier": {
            "status": BLOCKER,
            "dynamic_site": None,
            "reason": "a valid post-return state cannot be constructed without an evidenced B0:5B guest target object",
        },
    }


def blocker_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase11-b0-57-blocker-v1",
        "stage": STAGE,
        "classification": BLOCKER,
        "current_frontier": {
            "site": "0x80015fa4",
            "block_index": CURRENT_BLOCK_INDEX,
            "service": "ps1.bios.B0.57",
            "disposition": "FAIL_CLOSED",
        },
        "established": [
            "GetB0Table has no arguments and returns a mutable B0 jump-table guest pointer in v0",
            "entries are 32-bit function pointers indexed by B0 function number",
            "this caller first requires B0:0x5B and performs the publicly described relative patch pattern",
        ],
        "missing_evidence": [
            "a portable public guest address and callable representation for the B0:0x5B entry target",
            "a public guest code/data object that makes the required target-relative writes valid without BIOS execution",
            "a non-fabricated fail-closed target mapping for all other readable table entries",
        ],
        "causal_ab": {
            "A": "existing fail-closed B0:57 boundary at block 468341",
            "B": "NOT_CONSTRUCTED",
            "decision": "a B variant would require an arbitrary pointer, placeholder table, or BIOS code layout",
            "prefix_requirement": "preserved by retaining A unchanged",
        },
        "implementation_delta": {
            "bios_service_added": False,
            "runtime_dispatch_added": False,
            "guest_table_added": False,
            "indirect_target_added": False,
            "device_behavior_added": False,
        },
        "milestones": {
            "C": "PROVEN_IN_P11_05",
            "D": "NOT_PROVEN",
            "E": "NOT_PROVEN",
            "F": "NOT_PROVEN",
            "G": "NOT_PROVEN",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-07")
    parser.add_argument("--private-fixture-root",
                        default=str(p11_06.p11_05.DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    private = p11_06.build_extended_private(pathlib.Path(options.private_fixture_root))
    image = private["image"]

    site_records = [item for item in private["site_document_b"]["sites"]
                    if item["site"] == CALL_SITE]
    check("classification:one-site", len(site_records) == 1, str(len(site_records)))
    site = site_records[0]
    check("classification:vector-index",
          site["vector"] == "B0" and site["function_index"] == 0x57,
          f"{site['vector']}:{site['function_index']:02x}")
    check("classification:public-name", site["documented_name"] == "GetB0Table",
          str(site["documented_name"]))
    check("classification:still-unimplemented",
          site["classification"] == "BIOS_VECTOR_NOT_IMPLEMENTED"
          and site["disposition"] == "FAIL_CLOSED"
          and site["service_id"] is None,
          f"{site['classification']}/{site['disposition']}")
    check("classification:no-b0-runtime-service", bios.DOCUMENTED_B0_SERVICES == {},
          str(len(bios.DOCUMENTED_B0_SERVICES)))

    units = [unit for unit in private["result_b"].units.units
             if unit.function_id == CALLER_FUNCTION]
    check("caller:one-function", len(units) == 1, str(len(units)))
    unit = units[0]
    instructions = {instruction.address: instruction
                    for block in unit.blocks for instruction in block.instructions}

    required_pcs = {
        0x80015FA0, 0x80015FA4, 0x80015FAC, 0x80015FB4, 0x80015FB8,
        0x80015FC0, 0x80015FC8, 0x80015FCC, 0x80015FD0, 0x80015FD4,
        0x80015FDC,
    }
    check("caller:required-pcs", required_pcs.issubset(instructions),
          str(len(required_pcs & instructions.keys())))

    call_setup = instructions[0x80015FA0]
    call = instructions[0x80015FA4]
    delay = call.metadata["delay_slot"]
    check("caller:b0-vector-setup",
          call_setup.op == "addiu"
          and operands(call_setup) == {"rs": 0, "rt": 10, "imm": 0xB0},
          "t2 receives B0")
    check("caller:indirect-call",
          call.op == "jalr" and operands(call) == {"rs": 10, "rd": 31},
          "jalr through t2")
    check("caller:index-delay-slot",
          delay["op"] == "addiu"
          and delay["operands"] == {"rs": 0, "rt": 9, "imm": 0x57},
          "t1 receives 0x57")

    entry_read = instructions[0x80015FAC]
    check("caller:first-use-entry-5b",
          entry_read.op == "lw"
          and operands(entry_read) == {"rs": 2, "rt": 2, "imm": 0x16C},
          "32-bit read at v0+0x16c")

    first_derive = instructions[0x80015FB4]
    first_store = instructions[0x80015FB8]
    second_derive = instructions[0x80015FC0]
    second_store = instructions[0x80015FC8]
    check("caller:first-derived-pointer",
          first_derive.op == "addi"
          and operands(first_derive) == {"rs": 2, "rt": 3, "imm": 0x884}
          and first_store.op == "sw"
          and operands(first_store) == {"rs": 1, "rt": 3, "imm": -4732},
          "B0[0x5b]+0x884 -> 0x8002ed84")
    check("caller:second-derived-pointer",
          second_derive.op == "addi"
          and operands(second_derive) == {"rs": 2, "rt": 3, "imm": 0x894}
          and second_store.op == "sw"
          and operands(second_store) == {"rs": 1, "rt": 3, "imm": -4728},
          "B0[0x5b]+0x894 -> 0x8002ed88")

    decrement = instructions[0x80015FCC]
    clear = instructions[0x80015FD0]
    loop = instructions[0x80015FD4]
    loop_delay = loop.metadata["delay_slot"]
    check("caller:eleven-word-clear",
          decrement.op == "addiu"
          and operands(decrement) == {"rs": 9, "rt": 9, "imm": -1}
          and clear.op == "sw"
          and operands(clear) == {"rs": 2, "rt": 0, "imm": 0x594}
          and loop.op == "bne"
          and operands(loop) == {"rs": 9, "rt": 0, "target": 0x80015FCC}
          and loop_delay["op"] == "addiu"
          and loop_delay["operands"] == {"rs": 2, "rt": 2, "imm": 4},
          "11 aligned 32-bit writes at offsets 0x594..0x5bc")
    check("caller:post-patch-direct-call",
          instructions[0x80015FDC].op == "jal"
          and instructions[0x80015FDC].direct_target == 0x80015B90,
          "direct call follows patch loop")

    p11_06_frontier = json.loads(
        (ROOT / ".openrecomp-phase11/evidence/P11-06/frontier.json").read_text(
            encoding="utf-8")
    )
    frontier = p11_06_frontier["new_frontier"]
    check("frontier:exact-a",
          frontier["site"] == "0x80015fa4"
          and frontier["block_index"] == CURRENT_BLOCK_INDEX
          and frontier["bios_vector"] == "B0"
          and frontier["function_index"] == "0x57",
          f"{frontier['site']}/{frontier['block_index']}")

    runtime_source = (
        ROOT / ".openrecomp-phase11/runtime/p11_bios_extension_v1.c"
    ).read_text(encoding="utf-8")
    check("runtime:no-b0-57-dispatch",
          "OR_RT_SERVICE_PS1_BIOS_B0_57" not in runtime_source
          and "GetB0Table" not in runtime_source,
          "runtime remains fail closed")

    contract = public_contract_document()
    caller_use = caller_use_document()
    blocker = blocker_document()

    check("public:revisions-pinned",
          all(len(revision) == 40 for revision in (
              PSX_SPX_REVISION, PCSX_REDUX_REVISION,
              OPENBIOS_REVISION, PSX_BUNDLE_REVISION,
          )), "four full Git revisions")
    check("public:openbios-license",
          contract["public_sources"][1]["license"] == "MIT", "MIT")
    check("public:corroborating-license",
          contract["public_sources"][2]["license"] == "GPL-2.0", "GPL-2.0")
    check("public:contract-no-arguments",
          contract["established_contract"]["arguments"] == [], "argc=0")
    check("public:contract-v0-result",
          contract["established_contract"]["result"] == {
              "kind": "guest_pointer", "register": "$v0"
          }, "guest pointer in v0")
    check("public:mutable-b0-object",
          contract["established_contract"]["object"]
          == "mutable B0 BIOS jump table", "mutable table")
    check("public:no-fixed-contract-address",
          contract["address_and_initialization_boundary"]["contract_table_address"]
          == "implementation-defined"
          and contract["address_and_initialization_boundary"]["phase11_selected_address"]
          is None, "no invented pointer")
    check("blocker:no-b-variant",
          blocker["causal_ab"]["B"] == "NOT_CONSTRUCTED"
          and not any(blocker["implementation_delta"].values()),
          "zero implementation delta")
    check("blocker:frame-not-proven",
          blocker["milestones"]["D"] == "NOT_PROVEN", "milestone D unchanged")

    write_json(evidence / "public_contract.json", contract)
    write_json(evidence / "caller_use.json", caller_use)
    write_json(evidence / "blocker.json", blocker)
    for name, document in (("contract", contract), ("caller", caller_use),
                           ("blocker", blocker)):
        assert_public_safe(f"public:{name}", document, image.payload)

    tests = {
        "schema": "openrecomp-phase11-tests-v1",
        "stage": STAGE,
        "classification": BLOCKER,
        "checks": RESULTS,
        "summary": {
            "passed": sum(item["status"] == "PASS" for item in RESULTS),
            "failed": sum(item["status"] == "FAIL" for item in RESULTS),
        },
    }
    write_json(evidence / "p11_07_tests.json", tests)

    for result in RESULTS:
        detail = f" {result['detail']}" if result["detail"] else ""
        print(f"{result['status']}: {result['check']}{detail}")
    print(f"OPENRECOMP_P11_07=PASS")
    print(f"OPENRECOMP_PHASE11_P11_07_CLASSIFICATION={BLOCKER}")
    print(FRAME_MARKER)
    print(PLAYABILITY_MARKER)
    print(GENERAL_MARKER)
    print(f"P11_07_CHECKS={len(RESULTS)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: p11-07:{type(exc).__name__}:{exc}")
        raise SystemExit(1)
