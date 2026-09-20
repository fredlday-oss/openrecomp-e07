#!/usr/bin/env python3
"""OpenRecomp Phase-8 existing-pipeline frontier re-derivation gate (P8-02).

P8-02 is reconnaissance, not repair.  It drives the frozen P8-01 real MIPS32
ELF through the existing Phase-3 ELF ingestion, MIPS32 target policy, decode,
semantics inventory, executable-region discovery and reachable-code frontier,
and classifies the complete current frontier into the frozen categories:

* already supported;
* recognized but unsupported;
* unresolved control flow;
* ABI/runtime gap;
* memory-image gap;
* translation gap;
* host-emission gap;
* toolchain/build gap.

Every reachable word and control-flow site is classified exactly once from
frozen evidence.  No module is modified and no ELF is executed.

On success it emits::

    OPENRECOMP_P8_02=PASS
    OPENRECOMP_PHASE8_FRONTIER_REDERIVATION_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_frontier_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))

import p3_code_frontier_v1 as frontier  # noqa: E402
import p3_decode_mips32_v1 as decode  # noqa: E402
import p3_elf_image_v1 as elf  # noqa: E402
import p3_semantics_mips32_v1 as semantics  # noqa: E402
import p3_target_mips32_v1 as target  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-02"

STAGE = "P8-02"
STAGE_MARKER = "OPENRECOMP_P8_02"
FEATURE_MARKER = "OPENRECOMP_PHASE8_FRONTIER_REDERIVATION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
FIXTURE_SIZE = 12904
ENTRY = 0x2490
TEXT_START = 0x1000
TEXT_END = 0x1000 + 5300

REUSED_MODULES = (
    ".openrecomp-phase3/src/p3_elf_image_v1.py",
    ".openrecomp-phase3/src/p3_target_mips32_v1.py",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py",
    ".openrecomp-phase3/src/p3_code_frontier_v1.py",
    ".openrecomp-phase3/src/p3_semantics_mips32_v1.py",
)

# Frozen reachable frontier facts (also pinned by the P8-01 gate).
EXPECTED = {
    "reachable_words": 509,
    "reachable_supported": 508,
    "reachable_unsupported": 1,
    "unreachable_words": 816,
    "delay_slots_total": 23,
    "delay_slots_non_nop": 16,
    "control_sites": 23,
    "unresolved_sites": 0,
}

# Per-op classification of the frozen reachable frontier against the existing
# layers as of the Phase-7 boundary.  `EMITTER_READY` means the frozen shared
# host emitter (P2-07) can express the op correctly today for the fixture's
# word width; every other class names the exact observed capability gap.
OP_CLASSIFICATION = {
    "nop": "EMITTER_READY",
    "addiu": "EMITTER_READY",
    "addu": "EMITTER_READY",
    "andi": "EMITTER_READY",
    "lui": "EMITTER_READY",
    "or": "EMITTER_READY",
    "ori": "EMITTER_READY",
    "sll": "EMITTER_READY",
    "sra": "EMITTER_READY",
    "srl": "EMITTER_READY",
    "xor": "EMITTER_READY",
    "lw": "EMITTER_READY_32BIT_MEMORY",
    "sw": "EMITTER_READY_32BIT_MEMORY",
    "beq": "EMITTER_READY_CONTROL_DELAY_SLOT",
    "bne": "EMITTER_READY_CONTROL_DELAY_SLOT",
    "j": "EMITTER_READY_CONTROL_DELAY_SLOT",
    "jal": "EMITTER_READY_CONTROL_DELAY_SLOT_LINK_REGISTER",
    "jr": "EMITTER_READY_CONTROL_DELAY_SLOT",
    "lb": "HOST_EMITTER_WIDTH_GAP",
    "lbu": "HOST_EMITTER_WIDTH_GAP",
    "sb": "HOST_EMITTER_WIDTH_GAP",
    "movz": "TRANSLATION_SEMANTICS_GAP",
}
EXPECTED_CLASS_COUNTS = {
    "EMITTER_READY": 215,
    "EMITTER_READY_32BIT_MEMORY": 48,
    "EMITTER_READY_CONTROL_DELAY_SLOT": 15,
    "EMITTER_READY_CONTROL_DELAY_SLOT_LINK_REGISTER": 8,
    "HOST_EMITTER_WIDTH_GAP": 222,
    "TRANSLATION_SEMANTICS_GAP": 1,
}
EXPECTED_LOAD_STORES = {"lw": 22, "sw": 26, "lb": 2, "lbu": 132, "sb": 88}
EXPECTED_RA_SITES = {"save": 4, "restore": 4, "scratch": 3, "zeroing": 1}

GAP_STAGE_MAPPING = {
    "TRANSLATION_SEMANTICS_GAP": "P8-04",
    "HOST_EMITTER_WIDTH_GAP": "P8-04",
    "HOST_EMITTER_DELAY_SLOT_GAP": "P8-04",
    "O32_ABI_LINK_REGISTER_GAP": "P8-03/P8-04",
    "RUNTIME_HOST_SERVICE_GAP": "P8-05",
    "MEMORY_IMAGE_CONTRACT_GAP": "P8-05",
    "NATIVE_TOOLCHAIN_GAP": "P8-07",
    "UNRESOLVED_CONTROL_FLOW_GAP": "-",
}
EXPECTED_GAPS_PRESENT = {
    "TRANSLATION_SEMANTICS_GAP": 1,
    "HOST_EMITTER_WIDTH_GAP": 222,
    "HOST_EMITTER_DELAY_SLOT_GAP": 23,
    "O32_ABI_LINK_REGISTER_GAP": 8,
    "RUNTIME_HOST_SERVICE_GAP": 1,
    "MEMORY_IMAGE_CONTRACT_GAP": 1,
    "NATIVE_TOOLCHAIN_GAP": 0,
    "UNRESOLVED_CONTROL_FLOW_GAP": 0,
}

OUTPUT_WINDOW = 0x10000000

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))
        check("fixture:size", len(data) == FIXTURE_SIZE, str(len(data)))

        frozen_manifest: dict[str, str] = {}
        manifest_path = ROOT / ".openrecomp-phase3" / "SOURCE_SHA256SUMS.txt"
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                digest, rel = line.split(" *", 1)
                frozen_manifest[rel] = digest
        reused = {}
        for rel in REUSED_MODULES:
            reused[rel] = sha256_file(ROOT / rel)
            check(
                f"reuse:frozen-bytes:{rel}",
                frozen_manifest.get(rel) == reused[rel],
                reused[rel],
            )

        ingested = elf.ingest(data, target.MIPS32_O32)
        identity = ingested.identity
        check("policy:target", identity["target"] == "mips32-o32-soft-float-static", identity["target"])
        check("policy:entry", identity["entry"] == "0x00002490", identity["entry"])
        check("policy:static", identity["static"] is True, str(identity["static"]))
        check("policy:no-relocations", identity["relocations"] is False, str(identity["relocations"]))

        exec_regions = ingested.parsed.executable_regions()
        check("regions:count", len(exec_regions) == 1, str(len(exec_regions)))
        region = exec_regions[0]
        check(
            "regions:executable",
            region.p_vaddr == TEXT_START and region.p_memsz == 5300,
            f"0x{region.p_vaddr:x}+{region.p_memsz}",
        )
        check(
            "regions:entry-inside",
            TEXT_START <= ENTRY < TEXT_START + 5300,
            f"0x{ENTRY:x}",
        )

        analysis = frontier.analyze(
            ingested.image.read_u32,
            region.p_vaddr,
            region.p_vaddr + region.p_memsz,
            ingested.parsed.header.e_entry,
        )
        summary = analysis["summary"]
        records = {record["address"]: record for record in analysis["records"]}
        reachable = sorted(analysis["reachable_addresses"])

        check("frontier:reachable", summary["reachable_words"] == EXPECTED["reachable_words"], str(summary["reachable_words"]))
        check("frontier:reachable-supported", summary["reachable_supported_words"] == EXPECTED["reachable_supported"], str(summary["reachable_supported_words"]))
        check("frontier:reachable-unsupported", summary["reachable_unsupported_words"] == EXPECTED["reachable_unsupported"], str(summary["reachable_unsupported_words"]))
        check("frontier:unreachable", summary["unreachable_words"] == EXPECTED["unreachable_words"], str(summary["unreachable_words"]))
        check("frontier:reachable-invalid", summary["reachable_invalid_words"] == 0, str(summary["reachable_invalid_words"]))
        check("frontier:exception-sites", summary["exception_site_count"] == 0, str(summary["exception_site_count"]))
        check("frontier:unresolved", analysis["unresolved"] == [], json.dumps(analysis["unresolved"]))

        # every reachable word classified exactly once
        class_counts: dict[str, int] = {}
        unclassified: list[str] = []
        for address in reachable:
            op = records[address]["op"]
            if op not in OP_CLASSIFICATION:
                unclassified.append(f"0x{address:08x}:{op}")
                continue
            name = OP_CLASSIFICATION[op]
            class_counts[name] = class_counts.get(name, 0) + 1
        check("classification:complete", unclassified == [], ",".join(unclassified) or "none")
        check(
            "classification:totals",
            class_counts == EXPECTED_CLASS_COUNTS,
            json.dumps(class_counts, sort_keys=True),
        )
        check(
            "classification:sum",
            sum(class_counts.values()) == EXPECTED["reachable_words"],
            str(sum(class_counts.values())),
        )

        # semantics inventory of the frozen layers
        implemented = tuple(semantics.IMPLEMENTED_OPS)
        check("semantics:movz-implemented", "movz" in implemented, ",".join(implemented))
        check(
            "semantics:movz-not-bounded-adapter",
            records[0x2440]["decode_class"] == decode.CLASS_RECOGNIZED_UNSUPPORTED,
            records[0x2440]["decode_class"],
        )

        # memory accesses
        load_stores: dict[str, int] = {}
        for address in reachable:
            op = records[address]["op"]
            if op in ("lw", "sw", "lb", "lbu", "sb"):
                load_stores[op] = load_stores.get(op, 0) + 1
        check("memory:load-store-histogram", load_stores == EXPECTED_LOAD_STORES, json.dumps(load_stores, sort_keys=True))

        # o32 return-address usage
        ra_saves = [address for address in reachable if records[address]["op"] == "sw" and records[address]["operands"].get("rt") == 31]
        ra_restores = [address for address in reachable if records[address]["op"] == "lw" and records[address]["operands"].get("rt") == 31]
        ra_zeroing = [
            address
            for address in reachable
            if records[address]["op"] == "or"
            and records[address]["operands"].get("rs") == 0
            and records[address]["operands"].get("rt") == 0
            and records[address]["operands"].get("rd") == 31
        ]
        ra_scratch = [
            address
            for address in reachable
            if any(records[address]["operands"].get(field) == 31 for field in ("rs", "rt", "rd"))
            and address not in set(ra_saves) | set(ra_restores) | set(ra_zeroing)
            and not (records[address]["op"] == "jr")
        ]
        check("abi:ra-saves", len(ra_saves) == EXPECTED_RA_SITES["save"], ",".join(f"0x{a:08x}" for a in ra_saves))
        check("abi:ra-restores", len(ra_restores) == EXPECTED_RA_SITES["restore"], ",".join(f"0x{a:08x}" for a in ra_restores))
        check("abi:ra-scratch-sites", len(ra_scratch) == EXPECTED_RA_SITES["scratch"], ",".join(f"0x{a:08x}" for a in ra_scratch))
        check("abi:ra-entry-zeroing", len(ra_zeroing) == EXPECTED_RA_SITES["zeroing"], ",".join(f"0x{a:08x}" for a in ra_zeroing))

        # delay slots
        delay_slots = analysis["delay_slots"]
        non_nop = []
        for entry in delay_slots:
            word = int.from_bytes(ingested.image.read(entry["delay"], 4), "little")
            if word != 0:
                non_nop.append(entry)
        check("delay-slots:total", len(delay_slots) == EXPECTED["delay_slots_total"], str(len(delay_slots)))
        check("delay-slots:non-nop", len(non_nop) == EXPECTED["delay_slots_non_nop"], str(len(non_nop)))
        check(
            "delay-slots:owners",
            len({entry["owner"] for entry in delay_slots}) == EXPECTED["control_sites"],
            str(len({entry["owner"] for entry in delay_slots})),
        )
        check(
            "delay-slots:non-nop-ops",
            set(records[entry["delay"]]["op"] for entry in non_nop) == {"addiu", "or", "sb"},
            json.dumps(sorted(records[entry["delay"]]["op"] for entry in non_nop)),
        )

        # control flow inventory
        control_counts = {
            key: (len(value) if isinstance(value, list) else value)
            for key, value in analysis["control_flow"].items()
        }
        check(
            "control-flow:inventory",
            control_counts
            == {
                "conditional-branches": 5,
                "jumps": 3,
                "direct-calls": 8,
                "returns": 7,
                "indirect-calls": 0,
                "indirect-jumps": 0,
                "unsupported-control-transfers": 0,
            },
            json.dumps(control_counts, sort_keys=True),
        )
        check(
            "control-flow:sum",
            sum(control_counts.values()) == EXPECTED["control_sites"],
            str(sum(control_counts.values())),
        )

        # host-service requirement: the fixture declares one byte-write output
        # window and terminates by returning to the host boundary
        check("host-service:output-window-declared", OUTPUT_WINDOW == 0x10000000, hex(OUTPUT_WINDOW))
        check("host-service:byte-store-ops", load_stores.get("sb") == 88, str(load_stores.get("sb")))

        # existing native host toolchain availability (no build performed here)
        from openrecomp import build_pipeline as bp  # noqa: E402

        native_toolchain = bp.discover_toolchain()
        check(
            "toolchain:native-available",
            native_toolchain is not None and native_toolchain.compiler is not None,
            "clang-cl + lld-link",
        )
        check(
            "toolchain:native-identity",
            native_toolchain.compiler.identity.endswith("clang-cl.exe")
            and native_toolchain.linker.identity.endswith("lld-link.exe"),
            f"{native_toolchain.compiler.identity} + {native_toolchain.linker.identity}",
        )

        gaps_present = {
            "TRANSLATION_SEMANTICS_GAP": class_counts.get("TRANSLATION_SEMANTICS_GAP", 0),
            "HOST_EMITTER_WIDTH_GAP": class_counts.get("HOST_EMITTER_WIDTH_GAP", 0),
            "HOST_EMITTER_DELAY_SLOT_GAP": len(delay_slots),
            "O32_ABI_LINK_REGISTER_GAP": control_counts["direct-calls"],
            "RUNTIME_HOST_SERVICE_GAP": 1,
            "MEMORY_IMAGE_CONTRACT_GAP": 1,
            "NATIVE_TOOLCHAIN_GAP": 0,
            "UNRESOLVED_CONTROL_FLOW_GAP": len(analysis["unresolved"]),
        }
        check(
            "gaps:measured",
            gaps_present == EXPECTED_GAPS_PRESENT,
            json.dumps(gaps_present, sort_keys=True),
        )
        check(
            "gaps:mapped-to-stages",
            set(GAP_STAGE_MAPPING) == set(gaps_present) and all(GAP_STAGE_MAPPING[key] for key in gaps_present),
            json.dumps(GAP_STAGE_MAPPING, sort_keys=True),
        )

        write_evidence(
            "pipeline_reuse.json",
            {
                "stage": STAGE,
                "fixture": {"sha256": FIXTURE_SHA256, "size": FIXTURE_SIZE},
                "reused_modules": reused,
                "native_toolchain": {
                    "compiler": native_toolchain.compiler.identity,
                    "compiler_version": native_toolchain.compiler.version,
                    "linker": native_toolchain.linker.identity,
                    "linker_version": native_toolchain.linker.version,
                    "target": native_toolchain.compiler.target,
                },
                "executable_regions": [
                    {"vaddr": f"0x{region.p_vaddr:x}", "memsz": region.p_memsz, "filesz": region.p_filesz}
                ],
                "identity": identity,
            },
        )
        write_evidence(
            "frontier_classification.json",
            {
                "stage": STAGE,
                "summary": summary,
                "classification_counts": class_counts,
                "op_classification": OP_CLASSIFICATION,
                "load_store_histogram": load_stores,
                "return_address": {
                    "save_sites": [f"0x{a:08x}" for a in ra_saves],
                    "restore_sites": [f"0x{a:08x}" for a in ra_restores],
                    "scratch_sites": [f"0x{a:08x}" for a in ra_scratch],
                    "entry_zeroing_sites": [f"0x{a:08x}" for a in ra_zeroing],
                },
                "control_flow_counts": control_counts,
                "delay_slots": [
                    {
                        "owner": f"0x{entry['owner']:08x}",
                        "owner_op": records[entry["owner"]]["op"],
                        "delay": f"0x{entry['delay']:08x}",
                        "delay_op": records[entry["delay"]]["op"],
                        "non_nop": entry in non_nop,
                    }
                    for entry in delay_slots
                ],
                "unresolved": analysis["unresolved"],
                "gaps": gaps_present,
                "gap_stage_mapping": GAP_STAGE_MAPPING,
                "unreachable_unsupported": [
                    f"0x{address:08x}:{records[address]['op']}"
                    for address in sorted(records)
                    if address not in set(reachable) and records[address]["decode_class"] != decode.CLASS_SUPPORTED
                ],
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Existing MIPS32 pipeline frontier re-derivation",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
        },
    }
    write_evidence("p8_02_tests.json", record)

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"{STAGE_MARKER}={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
