#!/usr/bin/env python3
"""OpenRecomp Phase-9 translation-frontier closure gate (P9-04).

The gate proves the reachable translation frontier of the bounded fixtures is
completely and explicitly classified against the frozen Phase-8 semantics and
emitter paths:

* every reachable neutral instruction of the original public fixture is
  covered exactly once by the frozen Phase-8 rule table with matching flow,
  and the public structure emits deterministically through the frozen host
  emitter with no original machine code embedded;
* an injected unsupported form (`lwl`) fails closed as an uncovered
  reachable instruction instead of being guessed;
* the private Hercules reachable recognized-unsupported words are classified
  into explicit categories (unaligned partial-word memory, indirect control
  flow, trap/system, overflow-trapping arithmetic) with an exact total, and no
  COP0/GTE instruction is reachable; the fixture is never a `PASS` criterion
  and only non-reconstructive metadata is recorded.

No new instruction semantics are added at this stage.

On success it emits::

    OPENRECOMP_P9_04=PASS
    OPENRECOMP_PHASE9_TRANSLATION_CLOSURE_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_translation_v1.py
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
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "fixture"))

import p8_mips32_semantics_v1 as p8_semantics  # noqa: E402
import p9_image_bridge_v1 as bridge  # noqa: E402
import p9_memory_map_v1 as memory_map  # noqa: E402
import p9_psx_exe_v1 as psx  # noqa: E402
import p9_public_fixture_v1 as fixture  # noqa: E402
import p9_semantics_v1 as semantics  # noqa: E402
import psx_fixture_builder_v1 as builder  # noqa: E402
from openrecomp.host_emitter import emit_host_translation  # noqa: E402

STAGE = "P9-04"
FEATURE_MARKER = "OPENRECOMP_PHASE9_TRANSLATION_CLOSURE_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

DEFAULT_PRIVATE_FIXTURE = (
    ROOT.parents[1] / "fixtures" / "psx" / "hercules" / "SLUS_005.29"
)
PRIVATE_FIXTURE_LABEL = "hercules-slus-005.29"

FROZEN_MODULE_HASHES = {
    ".openrecomp-phase8/src/p8_mips32_semantics_v1.py":
        "aa5b4b2a65d944ba721636d9a8a9dc08c1af0229255400963bc902a3291b6daf",
    ".openrecomp-phase8/src/p8_structure_v1.py":
        "24109660cfa1876b9ffabe141374d1a1b26c74d6fc0f68260bfb440617077a1b",
}

PUBLIC_EXPECTED_COVERED = {
    "addiu": 14,
    "andi": 1,
    "beq": 1,
    "bne": 1,
    "jal": 2,
    "jr": 3,
    "lui": 6,
    "lw": 3,
    "sb": 3,
    "sw": 5,
}

PRIVATE_EXPECTED_CATEGORY_TOTALS = {
    "INDIRECT_CONTROL_FLOW": 22,
    "OVERFLOW_TRAPPING_ARITHMETIC": 3,
    "TRAP_OR_SYSTEM": 3,
    "UNALIGNED_PARTIAL_WORD_LOAD": 34,
    "UNALIGNED_PARTIAL_WORD_STORE": 34,
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def analyze_bytes(data: bytes) -> bridge.PipelineResult:
    image = psx.ingest(data)
    contract = memory_map.build_contract(image)
    flat = memory_map.flat_image(image)
    return bridge.analyze(image, contract, flat)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase9/evidence/P9-04",
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
        for rel, expected in sorted(FROZEN_MODULE_HASHES.items()):
            check(f"reuse:module:{rel}", sha256((ROOT / rel).read_bytes()) == expected, expected)

        # --- public fixture: complete closure and deterministic emission ----
        public = analyze_bytes(fixture.build_fixture())
        check("public:structure-built", public.structure is not None, str(public.structure_error))
        closure = semantics.coverage(public.structure)
        check("public:closure", closure["closed"] is True, json.dumps(closure, sort_keys=True))
        check("public:covered-total", closure["covered"] == 39, str(closure["covered"]))
        check(
            "public:covered-histogram",
            closure["covered_histogram"] == PUBLIC_EXPECTED_COVERED,
            json.dumps(closure["covered_histogram"], sort_keys=True),
        )
        check("public:no-uncovered", closure["uncovered"] == [], json.dumps(closure["uncovered"]))
        check("public:no-flow-mismatch", closure["flow_mismatch"] == [], json.dumps(closure["flow_mismatch"]))

        emission = emit_host_translation(
            public.structure.units,
            public.structure.classification,
            config=semantics.build_emitter_config(public.structure.discovery.entry_function_id),
        )
        emission_again = emit_host_translation(
            public.structure.units,
            public.structure.classification,
            config=semantics.build_emitter_config(public.structure.discovery.entry_function_id),
        )
        check("public:emission-deterministic", emission.source_text == emission_again.source_text, "stable source")
        check("public:emission-fingerprint", emission.fingerprint() == emission_again.fingerprint(), emission.fingerprint())
        check("public:emission-functions", len(emission.translations) == 3, str(len(emission.translations)))
        public_payload = psx.ingest(fixture.build_fixture()).payload
        emission_text = emission.source_text
        check("public:emission-no-machine-code", public_payload.hex() not in emission_text.lower(), "no payload hex")
        for offset in range(0, min(len(public_payload), 512)):
            run = public_payload[offset : offset + 8]
            if len(run) == 8 and all(32 <= byte < 127 for byte in run):
                check("public:emission-no-ascii-payload", run.decode("ascii") not in emission_text, "no ascii payload run")
                break

        public_record = {
            "schema": "openrecomp-phase9-translation-closure-v1",
            "stage": STAGE,
            "fixture": fixture.PUBLIC_FIXTURE.label,
            "closure": closure,
            "emission_fingerprint": emission.fingerprint(),
            "emission_functions": [translation.function_name for translation in emission.translations],
            "emission_bytes": len(emission_text.encode("utf-8")),
        }
        write_json(evidence / "public_closure.json", public_record)

        # --- injected unsupported form fails closed -------------------------
        injected_words = list(fixture.build_words())
        bad_index = len(injected_words)
        injected_words += [
            builder.i_type("lwl", rs=8, rt=9, imm=1),
            builder.r_type("jr", rs=31),
            builder.nop(),
        ]
        injected_words[38] = builder.j_type("jal", fixture.PROGRAM_LOAD_ADDRESS + 4 * bad_index)
        injected = analyze_bytes(builder.build_from_words(injected_words))
        check("injected:decodable-no-frontier-gap", injected.first_blocker is None, str(injected.first_blocker))
        check("injected:structure-built", injected.structure is not None, str(injected.structure_error))
        injected_closure = semantics.coverage(injected.structure) if injected.structure else None
        check("injected:closure-open", bool(injected_closure) and injected_closure["closed"] is False, json.dumps(injected_closure, sort_keys=True))
        if injected_closure:
            check("injected:uncovered-op", [item["op"] for item in injected_closure["uncovered"]] == ["lwl"], json.dumps(injected_closure["uncovered"], sort_keys=True))
        try:
            emit_host_translation(
                injected.structure.units,
                injected.structure.classification,
                config=semantics.build_emitter_config(injected.structure.discovery.entry_function_id),
            )
            check("injected:emitter-fails-closed", False, "emitter accepted an uncovered op")
        except Exception as exc:
            check("injected:emitter-fails-closed", type(exc).__name__ in ("HostEmitterError",), f"{type(exc).__name__}")

        # --- private fixture: explicit unsupported classification -----------
        fixture_path = pathlib.Path(options.private_fixture)
        private_record = {
            "schema": "openrecomp-phase9-private-closure-v1",
            "stage": STAGE,
            "label": PRIVATE_FIXTURE_LABEL,
            "present": fixture_path.is_file(),
            "is_pass_criterion": False,
        }
        if fixture_path.is_file():
            private_bytes = fixture_path.read_bytes()
            private = analyze_bytes(private_bytes)
            histogram = {
                op: count
                for op, count in private.summary["reachable_op_histogram"].items()
                if private.summary["supported_reachable_histogram"].get(op, 0) != count
                or op in ("lwl", "lwr", "swl", "swr", "jalr", "break", "syscall", "addi", "add", "sub")
            }
            unsupported = semantics.classify_reachable_unsupported(
                {
                    op: private.summary["unsupported_reachable_histogram"][op]
                    for op in private.summary["unsupported_reachable_histogram"]
                }
            )
            check(
                "private:category-totals",
                unsupported["category_totals"] == PRIVATE_EXPECTED_CATEGORY_TOTALS,
                json.dumps(unsupported["category_totals"], sort_keys=True),
            )
            check("private:category-total-sum", unsupported["total"] == 96, str(unsupported["total"]))
            check("private:no-unknown-category", unsupported["unknown_ops"] == {}, json.dumps(unsupported["unknown_ops"], sort_keys=True))
            coprocessor = semantics.coprocessor_reachable(private.summary["reachable_op_histogram"])
            check("private:no-cop0-gte-reachable", coprocessor == {}, json.dumps(coprocessor, sort_keys=True))
            private_record["unsupported_classification"] = unsupported
            private_record["coprocessor_reachable"] = coprocessor
            private_record["closure_state"] = "OPEN_FIRST_BLOCKER_0x80013390"
            private_text = json.dumps(private_record, sort_keys=True)
            assert_no_payload_leak("private:closure", private_text, psx.ingest(private_bytes).payload)
        write_json(evidence / "private_closure.json", private_record)
        check("private:marker", True, "PRESENT" if fixture_path.is_file() else "ABSENT")

        # The frozen table itself is unchanged.
        check("table:op-count", len(p8_semantics.SUPPORTED_OPS) == 22, str(len(p8_semantics.SUPPORTED_OPS)))
        check("table:missing-rules-none", p8_semantics.missing_rules(PUBLIC_EXPECTED_COVERED) == (), "all public ops have rules")
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    record = {
        "stage": STAGE,
        "stage_name": "Reachable translation-frontier closure",
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
    write_json(evidence / "p9_04_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P9_04={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
