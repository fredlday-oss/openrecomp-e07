#!/usr/bin/env python3
"""OpenRecomp Phase-9 PS-X EXE ingestion gate (P9-01).

The gate proves the ingestion module
(`.openrecomp-phase9/src/p9_psx_exe_v1.py`) is deterministic, exact and
fail-closed:

* a canonical OpenRecomp-authored synthetic PS-X EXE round-trips with exact
  identity fields and hashes;
* a closed set of malformed/unsupported forms is rejected with stable codes
  and no guessed recovery;
* the identity record contains no executable payload bytes;
* the private Hercules `SLUS_005.29` fixture, when present at the documented
  local path, is ingested and reduced to non-reconstructive metadata only.

The private fixture is never a `PASS` criterion: when it is absent the gate
records `PRIVATE_FIXTURE=ABSENT` and still passes on the synthetic coverage.

On success it emits::

    OPENRECOMP_P9_01=PASS
    OPENRECOMP_PHASE9_INGESTION_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_ingestion_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import struct
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "fixture"))

import p9_psx_exe_v1 as psx  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402

STAGE = "P9-01"
STAGE_MARKER = "OPENRECOMP_P9_01"
FEATURE_MARKER = "OPENRECOMP_PHASE9_INGESTION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

#: Pinned non-reconstructive identity of the private fixture.
PRIVATE_EXPECTED = {
    "file_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
    "file_size": 129024,
    "payload_sha256": "2f48da4c642b25dd9d0b033f77b80a19e5befe34dc19da3194a51998e97c71be",
    "payload_size": 0x1F000,
    "entry_pc": "0x800132e8",
    "initial_gp": "0x00000000",
    "load_address": "0x80010000",
    "stack_pointer": "0x801ffff0",
    "reserved_sha256": "e6a138356b7e46be030334fdd789fab8cafeee2c85d44b54edafd391427b54fe",
    "reserved_nonzero_bytes": 55,
    "reserved_first_nonzero_offset": "0x4c",
    "reserved_last_nonzero_offset": "0x82",
}

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
    RESULTS.append(
        {"check": label, "status": "PASS" if condition else "FAIL", "detail": detail}
    )
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patched(base: bytes, offset: int, value: int) -> bytes:
    out = bytearray(base)
    struct.pack_into("<I", out, offset, value)
    return bytes(out)


def expect_error(label: str, data: bytes, expected: str) -> None:
    try:
        psx.ingest(data)
    except psx.PsxExeError as exc:
        check(label, exc.code == expected, f"expected {expected} got {exc.code}")
        check(f"{label}:code-closed", exc.code in psx.ERROR_CODES, exc.code)
        return
    check(label, False, f"expected {expected} but ingestion succeeded")


def assert_no_payload_leak(label: str, text: str, payload: bytes) -> None:
    """Fail if serialized metadata contains executable payload content."""
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
        default=".openrecomp-phase9/evidence/P9-01",
        help="evidence directory relative to the repository root",
    )
    parser.add_argument(
        "--private-fixture",
        default=os.environ.get("OPENRECOMP_PSX_PRIVATE_FIXTURE", str(DEFAULT_PRIVATE_FIXTURE)),
        help="optional local path to the private Hercules fixture",
    )
    options = parser.parse_args()

    try:
        # --- canonical synthetic positive path -----------------------------
        spec = builder.assemble_spec(CANONICAL_WORDS)
        canonical = builder.build(spec)
        check("synthetic:build-deterministic", builder.build(spec) == canonical, "byte-identical")
        check("synthetic:magic", canonical[:8] == b"PS-X EXE", canonical[:8].decode("ascii", "replace"))
        check("synthetic:size", len(canonical) == 0x800 + 32, str(len(canonical)))

        image = psx.ingest(canonical)
        identity = image.identity()
        check("synthetic:entry", image.entry == 0x80010000, f"0x{image.entry:08x}")
        check("synthetic:load-address", image.load_address == 0x80010000, f"0x{image.load_address:08x}")
        check("synthetic:text-end", image.text_end == 0x80010020, f"0x{image.text_end:08x}")
        check("synthetic:file-sha256", image.file_sha256 == sha256(canonical), image.file_sha256)
        check("synthetic:payload-sha256", image.payload_sha256 == sha256(spec.payload()), image.payload_sha256)
        check("synthetic:payload-size", len(image.payload) == 32, str(len(image.payload)))
        check("synthetic:identity-magic", identity["magic"] == "PS-X EXE", identity["magic"])
        check("synthetic:identity-entry", identity["entry_pc"] == "0x80010000", identity["entry_pc"])
        check("synthetic:identity-gp", identity["initial_gp"] == "0x00000000", identity["initial_gp"])
        check("synthetic:identity-stack", identity["stack_pointer"] == "0x801ffff0", identity["stack_pointer"])
        check("synthetic:identity-header-size", identity["header_size"] == 0x800, str(identity["header_size"]))
        check("synthetic:identity-data-absent", identity["data_section"]["present"] is False, "absent")
        check("synthetic:identity-bss-absent", identity["bss_section"]["present"] is False, "absent")
        check("synthetic:identity-reserved-zero", identity["reserved"]["nonzero_bytes"] == 0, "0")
        check("synthetic:identity-ram-span", identity["ram_span"]["end"] == "0x80010020", identity["ram_span"]["end"])
        for index, word in enumerate(CANONICAL_WORDS):
            address = 0x80010000 + 4 * index
            check(f"synthetic:read-u32[{index}]", image.read_u32(address) == word, f"0x{word:08x}")
        try:
            image.read_u32(0x80010020)
            check("synthetic:read-outside", False, "expected READ_OUTSIDE_PAYLOAD")
        except psx.PsxExeError as exc:
            check("synthetic:read-outside", exc.code == "READ_OUTSIDE_PAYLOAD", exc.code)

        # A payload with an ASCII pattern must not leak into the identity record.
        leak_pattern = b"OPENRECOMP-ORIGINAL-PAYLOAD-PATTERN!"
        leak_payload = (leak_pattern * 4)[:64]
        leak_words = tuple(
            struct.unpack_from("<I", leak_payload, offset)[0]
            for offset in range(0, 64, 4)
        )
        leak_image = psx.ingest(builder.build_from_words(leak_words))
        leak_text = json.dumps(leak_image.identity(), sort_keys=True)
        assert_no_payload_leak("synthetic:identity", leak_text, leak_image.payload)

        # BSS positive path.
        bss_spec = builder.assemble_spec(
            CANONICAL_WORDS, bss_address=0x80020000, bss_size=0x100
        )
        bss_image = psx.ingest(builder.build(bss_spec))
        bss_identity = bss_image.identity()
        check("synthetic:bss-present", bss_identity["bss_section"]["present"] is True, "present")
        check("synthetic:bss-address", bss_identity["bss_section"]["address"] == "0x80020000", bss_identity["bss_section"]["address"])
        check("synthetic:bss-ram-span", bss_identity["ram_span"]["end"] == "0x80020100", bss_identity["ram_span"]["end"])

        # Nonzero initial GP is recorded exactly.
        gp_image = psx.ingest(builder.build_from_words(CANONICAL_WORDS, gp=0x8001FFF0))
        check("synthetic:gp-recorded", gp_image.identity()["initial_gp"] == "0x8001fff0", gp_image.identity()["initial_gp"])

        # --- fail-closed negative paths ------------------------------------
        expect_error("negative:empty", b"", "INPUT_TOO_SMALL")
        expect_error("negative:short-header", b"\x00" * 0x7FF, "INPUT_TOO_SMALL")
        expect_error("negative:bad-magic", b"PS-Y EXE" + canonical[8:], "BAD_MAGIC")
        expect_error("negative:zero1", patched(canonical, 0x08, 1), "NONZERO_RESERVED_HEADER_FIELD")
        expect_error("negative:zero2", patched(canonical, 0x0C, 1), "NONZERO_RESERVED_HEADER_FIELD")
        expect_error("negative:empty-payload", patched(canonical, 0x1C, 0), "EMPTY_PAYLOAD")
        expect_error(
            "negative:misaligned-payload-size",
            patched(canonical[: 0x800 + 2], 0x1C, 2),
            "MISALIGNED_PAYLOAD_SIZE",
        )
        expect_error("negative:truncated-payload", canonical[: 0x800 + 16], "TRUNCATED_PAYLOAD")
        expect_error("negative:trailing-data", canonical + b"\x00\x00\x00\x00", "UNSUPPORTED_TRAILING_DATA")
        expect_error("negative:misaligned-load", patched(canonical, 0x18, 0x80010002), "MISALIGNED_LOAD_ADDRESS")
        expect_error("negative:load-outside-ram", patched(canonical, 0x18, 0x00010000), "LOAD_ADDRESS_OUTSIDE_RAM")
        expect_error(
            "negative:payload-exceeds-ram",
            builder.build_from_words([0] * 0x800, load_address=0x801FF000),
            "PAYLOAD_EXCEEDS_RAM",
        )
        expect_error("negative:misaligned-entry", patched(canonical, 0x10, 0x80010002), "MISALIGNED_ENTRY")
        expect_error("negative:entry-outside", patched(canonical, 0x10, 0x80020000), "ENTRY_OUTSIDE_PAYLOAD")
        expect_error("negative:data-section", patched(canonical, 0x24, 4), "UNSUPPORTED_DATA_SECTION")
        expect_error(
            "negative:misaligned-bss",
            patched(patched(canonical, 0x2C, 4), 0x28, 2),
            "MISALIGNED_BSS_ADDRESS",
        )
        expect_error(
            "negative:bss-outside-ram",
            patched(patched(canonical, 0x2C, 4), 0x28, 0x00010000),
            "BSS_OUTSIDE_RAM",
        )
        expect_error(
            "negative:bss-exceeds-ram",
            patched(patched(canonical, 0x2C, 0x2000), 0x28, 0x801FF000),
            "BSS_EXCEEDS_RAM",
        )
        expect_error("negative:misaligned-stack", patched(canonical, 0x30, 0x801FFFF4), "MISALIGNED_STACK")
        expect_error("negative:stack-below-ram", patched(canonical, 0x30, 0x80000000), "STACK_OUTSIDE_RAM")
        expect_error("negative:stack-above-ram", patched(canonical, 0x30, 0x80200008), "STACK_OUTSIDE_RAM")
        expect_error("negative:misaligned-gp", patched(canonical, 0x14, 2), "MISALIGNED_GP")
        check("negative:error-code-closed-set", len(psx.ERROR_CODES) == len(set(psx.ERROR_CODES)), str(len(psx.ERROR_CODES)))

        # --- private fixture (metadata only; never a PASS criterion) -------
        fixture_path = pathlib.Path(options.private_fixture)
        private_record = {
            "schema": "openrecomp-phase9-private-fixture-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "usage": "local bounded validation input only; never a public PASS criterion",
        }
        if fixture_path.is_file():
            data = fixture_path.read_bytes()
            private_image = psx.ingest(data)
            private_identity = private_image.identity()
            check("private:file-sha256", private_image.file_sha256 == PRIVATE_EXPECTED["file_sha256"], private_image.file_sha256)
            check("private:file-size", private_image.file_size == PRIVATE_EXPECTED["file_size"], str(private_image.file_size))
            check("private:payload-sha256", private_image.payload_sha256 == PRIVATE_EXPECTED["payload_sha256"], private_image.payload_sha256)
            check("private:payload-size", len(private_image.payload) == PRIVATE_EXPECTED["payload_size"], str(len(private_image.payload)))
            check("private:entry", private_identity["entry_pc"] == PRIVATE_EXPECTED["entry_pc"], private_identity["entry_pc"])
            check("private:gp", private_identity["initial_gp"] == PRIVATE_EXPECTED["initial_gp"], private_identity["initial_gp"])
            check("private:load", private_identity["load_address"] == PRIVATE_EXPECTED["load_address"], private_identity["load_address"])
            check("private:stack", private_identity["stack_pointer"] == PRIVATE_EXPECTED["stack_pointer"], private_identity["stack_pointer"])
            check(
                "private:reserved-hash",
                private_identity["reserved"]["sha256"] == PRIVATE_EXPECTED["reserved_sha256"],
                private_identity["reserved"]["sha256"],
            )
            check(
                "private:reserved-nonzero",
                private_identity["reserved"]["nonzero_bytes"] == PRIVATE_EXPECTED["reserved_nonzero_bytes"],
                str(private_identity["reserved"]["nonzero_bytes"]),
            )
            check(
                "private:reserved-first",
                private_identity["reserved"]["first_nonzero_offset"] == PRIVATE_EXPECTED["reserved_first_nonzero_offset"],
                str(private_identity["reserved"]["first_nonzero_offset"]),
            )
            check(
                "private:reserved-last",
                private_identity["reserved"]["last_nonzero_offset"] == PRIVATE_EXPECTED["reserved_last_nonzero_offset"],
                str(private_identity["reserved"]["last_nonzero_offset"]),
            )
            private_record["identity"] = private_identity
            private_record["bytes_committed"] = False
            private_text = json.dumps(private_record, sort_keys=True)
            assert_no_payload_leak("private:identity", private_text, private_image.payload)
        else:
            private_record["bytes_committed"] = False

        write_json((ROOT / options.evidence_dir).resolve() / "private_fixture.json", private_record)

        synthetic_record = {
            "schema": "openrecomp-phase9-psx-exe-synthetic-v1",
            "stage": STAGE,
            "fixture": "openrecomp-authored-canonical",
            "words": len(CANONICAL_WORDS),
            "identity": identity,
            "bss_identity": bss_identity,
            "identity_sha256": sha256(json.dumps(identity, sort_keys=True).encode("utf-8")),
        }
        write_json((ROOT / options.evidence_dir).resolve() / "synthetic_identity.json", synthetic_record)

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
        "stage_name": "PS-X EXE ingestion",
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
    write_json((ROOT / options.evidence_dir).resolve() / "p9_01_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_01={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
