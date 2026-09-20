#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS1 memory-map contract gate (P9-02).

The gate proves the address-space contract
(`.openrecomp-phase9/src/p9_memory_map_v1.py`) is explicit, deterministic and
fail-closed:

* the bounded 2 MiB main-RAM window with its KSEG0/KSEG1 mirrors and named
  loaded regions (text, optional BSS, bounded stack, free RAM) with explicit
  permissions;
* every other segment (KUSEG mirror, scratchpad, I/O ports, BIOS, KSEG2) is
  classified explicitly and fails closed or routes to the platform-service
  boundary;
* the flat RAM image maps the payload at its load address with deterministic
  hashes and chunk counts;
* stack/image overlap and chunk-limit violations fail closed.

The private Hercules fixture contributes a non-reconstructive contract summary
only and is never a `PASS` criterion.

On success it emits::

    OPENRECOMP_P9_02=PASS
    OPENRECOMP_PHASE9_MEMORY_MAP_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_memory_map_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "fixture"))

import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402

STAGE = "P9-02"
FEATURE_MARKER = "OPENRECOMP_PHASE9_MEMORY_MAP_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

CANONICAL_WORDS = (
    builder.nop(),
    builder.i_type("addiu", rt=2, rs=0, imm=0x1234),
    builder.r_type("addu", rs=2, rt=2, rd=3),
    builder.i_type("lui", rt=4, imm=0x8001),
    builder.i_type("sw", rs=0, rt=3, imm=0x10),
    builder.i_type("lw", rs=0, rt=5, imm=0x10),
    builder.j_type("j", 0x80010000),
    builder.nop(),
)

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expect_map_error(label: str, contract: dict, address: int, expected: str) -> None:
    try:
        memory_map.translate(contract, address)
    except memory_map.MemoryMapError as exc:
        check(label, exc.code == expected, f"expected {expected} got {exc.code}")
        return
    check(label, False, f"expected {expected} but translation succeeded")


def assert_no_payload_leak(label: str, text: str, payload: bytes) -> None:
    lowered = text.lower()
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in lowered, "payload hex present")
    encoded = base64.b64encode(sample).decode("ascii")
    check(f"{label}:no-base64", encoded not in text, "payload base64 present")
    leaks = []
    for start in range(0, min(len(payload), 512)):
        run = payload[start : start + 8]
        if len(run) == 8 and all(32 <= byte < 127 for byte in run):
            if run.decode("ascii") in text:
                leaks.append(start)
                break
    check(f"{label}:no-ascii-run", not leaks, f"ascii payload run at {leaks[:1]}")
    for value in _string_values(json.loads(text)):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase9/evidence/P9-02",
        help="evidence directory relative to the repository root",
    )
    parser.add_argument(
        "--private-fixture",
        default=os.environ.get("OPENRECOMP_PSX_PRIVATE_FIXTURE", str(DEFAULT_PRIVATE_FIXTURE)),
        help="optional local path to the private Hercules fixture",
    )
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        spec = builder.assemble_spec(CANONICAL_WORDS, bss_address=0x80020000, bss_size=0x100)
        image = psx.ingest(builder.build(spec))
        contract = memory_map.build_contract(image)
        flat = memory_map.flat_image(image)

        check("contract:ram-base", contract["ram"]["base"] == "0x80000000", contract["ram"]["base"])
        check("contract:ram-size", contract["ram"]["size"] == 0x200000, str(contract["ram"]["size"]))
        check("contract:ram-end", contract["ram"]["end"] == "0x80200000", contract["ram"]["end"])
        check("contract:ram-permissions", contract["ram"]["permissions"] == "rwx", contract["ram"]["permissions"])
        check("contract:image-size", contract["ram"]["image_size"] == 0x200000, str(contract["ram"]["image_size"]))
        check("contract:image-sha256", contract["ram"]["image_sha256"] == sha256(flat), contract["ram"]["image_sha256"])
        check("contract:entry", contract["entry"] == "0x80010000", contract["entry"])
        check("contract:load-address", contract["load_address"] == "0x80010000", contract["load_address"])
        check("contract:text-end", contract["text_end"] == "0x80010020", contract["text_end"])
        check("contract:flat-payload", flat[0x10000:0x10020] == image.payload, "payload at load offset")
        check("contract:flat-bss-zero", not any(flat[0x20000:0x20100]), "bss zero-filled")
        check("contract:flat-gap-zero", not any(flat[0x10020:0x20000]), "gap zero-filled")
        check("contract:determinism", memory_map.contract_digest(contract) == memory_map.contract_digest(memory_map.build_contract(image)), "stable digest")

        regions = {region["name"]: region for region in contract["regions"]}
        check("regions:text", regions["load_text"]["base"] == "0x80010000" and regions["load_text"]["size"] == 0x20, "text")
        check("regions:text-perms", regions["load_text"]["permissions"] == "rwx", regions["load_text"]["permissions"])
        check("regions:bss", regions["bss"]["base"] == "0x80020000" and regions["bss"]["size"] == 0x100, "bss")
        check("regions:bss-perms", regions["bss"]["permissions"] == "rw", regions["bss"]["permissions"])
        check("regions:stack", regions["stack"]["base"] == "0x801fbff0" and regions["stack"]["size"] == 0x4000, "stack")
        check("regions:stack-perms", regions["stack"]["permissions"] == "rw", regions["stack"]["permissions"])
        check("regions:ram-free", regions["ram_free"]["base"] == "0x80020100" and regions["ram_free"]["size"] == 0x1DBEF0, "ram-free")
        check("regions:sorted", [region["base"] for region in contract["regions"]] == sorted(region["base"] for region in contract["regions"]), "sorted by base")
        check("contract:stack-model", contract["stack"]["model"] == "explicit-bounded", contract["stack"]["model"])
        check("contract:stack-pointer", contract["stack"]["pointer"] == "0x801ffff0", contract["stack"]["pointer"])
        check("contract:bss-present", contract["bss"]["present"] is True, "present")

        segments = {segment["name"]: segment for segment in contract["segments"]}
        check("segments:count", len(contract["segments"]) == 7, str(len(contract["segments"])))
        check("segments:kseg0", segments["kseg0"]["classification"] == "ram-cached" and segments["kseg0"]["enabled"] is True, "kseg0")
        check("segments:kseg1", segments["kseg1"]["base"] == "0xa0000000" and segments["kseg1"]["classification"] == "ram-uncached" and segments["kseg1"]["enabled"] is True, "kseg1")
        check("segments:kuseg", segments["kuseg"]["classification"] == "ram-user-mirror" and segments["kuseg"]["enabled"] is False, "kuseg")
        check("segments:scratchpad", segments["scratchpad"]["classification"] == "unsupported-not-modelled" and segments["scratchpad"]["enabled"] is False, "scratchpad")
        check("segments:io", segments["io"]["classification"] == "platform-service" and segments["io"]["translation"] == "service", "io")
        check("segments:bios", segments["bios"]["classification"] == "absent-no-bios-image" and segments["bios"]["enabled"] is False, "bios")
        check("segments:kseg2", segments["kseg2"]["classification"] == "unsupported-privileged" and segments["kseg2"]["enabled"] is False, "kseg2")
        for segment in contract["segments"]:
            if not segment["enabled"]:
                check(f"segments:reason:{segment['name']}", bool(segment.get("reason")), "reason present")

        translation = memory_map.translate(contract, 0x80010004)
        check("translate:kseg0", translation == memory_map.Translation("kseg0", "ram", 0x10004, 0x80010004), str(translation))
        translation = memory_map.translate(contract, 0xA0010004)
        check("translate:kseg1", translation == memory_map.Translation("kseg1", "ram", 0x10004, 0xA0010004), str(translation))
        check("translate:read-u32", memory_map.read_u32(contract, flat, 0x80010004) == CANONICAL_WORDS[1], "word read")
        check("translate:read-u32-kseg1", memory_map.read_u32(contract, flat, 0xA0010004) == CANONICAL_WORDS[1], "kseg1 word read")

        expect_map_error("negative:kuseg", contract, 0x00010000, "UNSUPPORTED_SEGMENT_KUSEG")
        expect_map_error("negative:scratchpad", contract, 0x1F800000, "UNSUPPORTED_SEGMENT_SCRATCHPAD")
        expect_map_error("negative:io-unclaimed", contract, 0x1F801810, "PLATFORM_SERVICE_UNCLAIMED")
        expect_map_error("negative:bios", contract, 0xBFC00000, "UNSUPPORTED_SEGMENT_BIOS")
        expect_map_error("negative:kseg2", contract, 0xC0000000, "UNSUPPORTED_SEGMENT_KSEG2")
        expect_map_error("negative:unmapped", contract, 0x40000000, "UNMAPPED_ADDRESS")
        expect_map_error("negative:kseg0-end", contract, 0x80200000, "UNMAPPED_ADDRESS")

        overlap_words = tuple(0 for _ in range(0x400))
        overlap_spec = builder.assemble_spec(
            overlap_words,
            load_address=0x801FF000,
            stack_pointer=0x80200000,
        )
        overlap_image = psx.ingest(builder.build(overlap_spec))
        try:
            memory_map.build_contract(overlap_image)
            check("negative:stack-overlap", False, "expected STACK_OVERLAPS_IMAGE")
        except memory_map.MemoryMapError as exc:
            check("negative:stack-overlap", exc.code == "STACK_OVERLAPS_IMAGE", exc.code)

        chunk_words = tuple(
            0xFFFFFFFF if index % 5 == 0 else 0 for index in range(0x6000)
        )
        chunk_image = psx.ingest(builder.build_from_words(chunk_words))
        try:
            memory_map.build_contract(chunk_image)
            check("negative:chunk-limit", False, "expected IMAGE_CHUNK_LIMIT")
        except memory_map.MemoryMapError as exc:
            check("negative:chunk-limit", exc.code == "IMAGE_CHUNK_LIMIT", exc.code)

        # Named-region coverage: every named region is contiguous and in RAM.
        for region in contract["regions"]:
            base = int(region["base"], 16)
            check(
                f"regions:in-ram:{region['name']}",
                memory_map.RAM_KSEG0_BASE <= base and base + region["size"] <= memory_map.RAM_KSEG0_END,
                region["base"],
            )

        synthetic_record = {
            "schema": "openrecomp-phase9-memory-contract-v1",
            "stage": STAGE,
            "fixture": "openrecomp-authored-canonical",
            "contract": contract,
            "contract_digest": memory_map.contract_digest(contract),
        }
        write_json(evidence / "memory_contract.json", synthetic_record)

        # --- private fixture contract summary (metadata only) --------------
        fixture_path = pathlib.Path(options.private_fixture)
        private_record = {
            "schema": "openrecomp-phase9-private-memory-contract-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "is_pass_criterion": False,
        }
        if fixture_path.is_file():
            private_image = psx.ingest(fixture_path.read_bytes())
            private_contract = memory_map.build_contract(private_image)
            private_record["contract"] = private_contract
            private_record["contract_digest"] = memory_map.contract_digest(private_contract)
            text_region = private_contract["regions"][0]
            check("private:text-region", text_region["name"] == "load_text" and text_region["base"] == "0x80010000" and text_region["size"] == 0x1F000, text_region["name"])
            check("private:stack-base", private_contract["stack"]["base"] == "0x801fbff0", private_contract["stack"]["base"])
            check("private:entry-translates", memory_map.translate(private_contract, 0x800132E8).kind == "ram", "entry in RAM")
            private_text = json.dumps(private_record, sort_keys=True)
            assert_no_payload_leak("private:contract", private_text, private_image.payload)
        write_json(evidence / "private_contract.json", private_record)
        check("private:marker", True, "PRESENT" if fixture_path.is_file() else "ABSENT")
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    record = {
        "stage": STAGE,
        "stage_name": "PS1 executable image and memory-map contract",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "private_fixture": {
            "label": PRIVATE_FIXTURE_LABEL,
            "present": pathlib.Path(options.private_fixture).is_file(),
            "is_pass_criterion": False,
        },
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / "p9_02_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_02={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
