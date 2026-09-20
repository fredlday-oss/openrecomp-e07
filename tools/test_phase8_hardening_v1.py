#!/usr/bin/env python3
"""OpenRecomp Phase-8 fail-closed hardening gate (P8-11).

Focused negative coverage for the Phase-8 mechanisms (not a fuzzing project):

* deterministic rejection of malformed/unsupported inputs;
* no guessed recovery (indirect targets, unsupported encodings, delay-slot
  violations);
* no silent compatibility widening (closed rule table, class/endianness/type
  rejection);
* no stale-cache acceptance (immutable-hash analysis cache and the
  content-hash incremental object cache);
* no generated-code execution after a required earlier classification
  failure.

On success it emits::

    OPENRECOMP_P8_11=PASS
    OPENRECOMP_PHASE8_HARDENING_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_hardening_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))

import p3_elf_image_v1 as elf  # noqa: E402
import p3_target_mips32_v1 as target  # noqa: E402
import p8_analysis_cache_v1 as analysis_cache  # noqa: E402
import p8_incremental_build_v1 as incremental  # noqa: E402
import p8_mips32_semantics_v1 as semantics  # noqa: E402
import p8_workflow_v1 as workflow  # noqa: E402
from openrecomp import build_pipeline as bp  # noqa: E402

EVIDENCE_DIR = ROOT / ".openrecomp-phase8" / "evidence" / "P8-11"
WORKSPACE = ROOT / ".openrecomp-phase8" / "build" / "P8-11"

STAGE = "P8-11"
STAGE_MARKER = "OPENRECOMP_P8_11"
FEATURE_MARKER = "OPENRECOMP_PHASE8_HARDENING_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_ELF = ROOT / ".openrecomp-phase8" / "build" / "P8-01" / "candidate-a" / "p8_aes128_mips32_O1.elf"
FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL", "detail": detail})
        raise AssertionError(f"{label}: condition failed ({detail})")
    RESULTS.append({"check": label, "status": "PASS", "detail": detail})
    print(f"PASS: {label}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evidence_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_evidence(name: str, payload: object) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / name).write_bytes(evidence_json(payload))


def patch_word(data: bytes, address: int, word: int) -> bytes:
    mutated = bytearray(data)
    mutated[address : address + 4] = word.to_bytes(4, "little")
    return bytes(mutated)


def main() -> int:
    try:
        data = FIXTURE_ELF.read_bytes()
        check("fixture:sha256", sha256_bytes(data) == FIXTURE_SHA256, sha256_bytes(data))
        if WORKSPACE.exists():
            shutil.rmtree(WORKSPACE)
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        negative_dir = WORKSPACE / "negatives"
        negative_dir.mkdir(parents=True, exist_ok=True)

        def run_case(name: str, payload: bytes) -> dict:
            path = negative_dir / f"{name}.elf"
            path.write_bytes(payload)
            return workflow.run_workflow(path, workspace=negative_dir / name)

        def expect_fail(name: str, payload: bytes, category: str) -> dict:
            first = run_case(name, payload)
            second = run_case(name, payload)
            check(f"reject:{name}:category", first["outcome"] == "FAIL_CLOSED" and first["category"] == category, json.dumps(first, sort_keys=True)[:240])
            check(f"reject:{name}:deterministic", first == second, "identical rejection record")
            check(f"reject:{name}:no-build-execution", "build" not in first and "native" not in first and "emission" not in first, "stopped before emission/build/execution")
            check(f"reject:{name}:no-program", not (negative_dir / name / "run1" / "program.exe").exists(), "no generated executable")
            return first

        # no silent compatibility widening: class/endianness/type/policy
        expect_fail("big-endian", data[:5] + bytes([2]) + data[6:], "UNSUPPORTED_ELF_CONTAINER")
        expect_fail("elfclass64", data[:4] + bytes([2]) + data[5:], "UNSUPPORTED_ELF_CONTAINER")
        expect_fail("et-rel", data[:16] + (1).to_bytes(2, "little") + data[18:], "UNSUPPORTED_ELF_CONTAINER")
        expect_fail("entry-not-executable", data[:24] + (0x00000000).to_bytes(4, "little") + data[28:], "UNSUPPORTED_ELF_CONTAINER")

        # no guessed recovery: unsupported encodings stay unsupported
        expect_fail("reachable-divu", patch_word(data, 0x2440, 0x0085001B), "UNSUPPORTED_ISA_SEMANTIC")
        # A synthetic reachable indirect call has no evidence-backed delay-slot
        # ownership; the workflow refuses it rather than guessing (fail closed).
        expect_fail("reachable-jalr", patch_word(data, 0x2440, (25 << 21) | (0 << 16) | (31 << 11) | 0x09), "UNSUPPORTED_ISA_SEMANTIC")
        expect_fail("reachable-lh", patch_word(data, 0x2440, (25 << 26) | (1 << 21) | (2 << 16) | 0x0000), "UNSUPPORTED_ISA_SEMANTIC")
        expect_fail("indirect-jr-t9", patch_word(data, 0x247C, (25 << 21) | 0x08), "UNRESOLVED_INDIRECT_CONTROL_FLOW")

        # closed rule table: unsupported MIPS32 forms remain unrepresentable
        missing = semantics.missing_rules(("div", "divu", "mult", "multu", "mul", "movn", "jalr", "swl", "swr", "lwl", "lwr", "lh", "lhu", "sh", "beql", "bnel"))
        check("rules:closed", missing == tuple(sorted(("div", "divu", "mult", "multu", "mul", "movn", "jalr", "swl", "swr", "lwl", "lwr", "lh", "lhu", "sh", "beql", "bnel"))), json.dumps(missing))
        check("rules:supported-count", len(semantics.SUPPORTED_OPS) == 22, str(len(semantics.SUPPORTED_OPS)))

        # no stale-cache acceptance: immutable-hash analysis cache
        cache_root = WORKSPACE / "analysis-cache"
        cache = analysis_cache.AnalysisCache(cache_root, "P8-11")
        key_inputs = {
            "product": "elf-inventory",
            "input_sha256": FIXTURE_SHA256,
            "input_size_bytes": len(data),
            "analysis_config": {"entry": 0x2490, "text_words": 1325},
            "frontend_sha256": {".openrecomp-phase3/src/p3_elf_image_v1.py": "unused-for-test"},
            "semantic_model": {"program_model": "1.0.0"},
            "producer_sha256": "test-producer",
        }
        payload = {"regions": 4, "reachable": 509}
        key = cache.put(key_inputs, payload)
        check("cache:hit", cache.get(key_inputs) == payload, key)
        entry_path = cache_root / "P8-11" / "elf-inventory" / f"{key}.json"
        entry = json.loads(entry_path.read_text(encoding="utf-8"))
        entry["key_inputs"]["input_size_bytes"] = entry["key_inputs"]["input_size_bytes"] + 1
        entry_path.write_text(json.dumps(entry, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        check("cache:stale-rejected", cache.get(key_inputs) is None, "recomputed key mismatch")
        check("cache:stale-counted", cache.stats()["stale"] == 1, json.dumps(cache.stats()))
        check(
            "cache:different-input-misses",
            cache.get({**key_inputs, "input_sha256": "0" * 64}) is None,
            "different fixture identity",
        )
        check("cache:product-scoped", (cache_root / "P8-11" / "other-product").exists() is False, "no cross-product reuse")

        # no stale-cache acceptance: content-hash incremental object cache
        toolchain = bp.discover_toolchain()
        check("toolchain:available", toolchain is not None, "clang-cl + lld-link")
        builder = incremental.IncrementalBuilder(WORKSPACE / "incremental", WORKSPACE / "object-cache", toolchain)
        source = "int main(void) { return 0; }\n"
        cold = builder.build({"generated.c": source})
        warm = builder.build({"generated.c": source})
        check("object-cache:cold-compiles", cold["compiled"] == 1 and cold["reused"] == 0, json.dumps({"compiled": cold["compiled"], "reused": cold["reused"]}))
        check("object-cache:warm-reuses", warm["compiled"] == 0 and warm["reused"] == 1, json.dumps({"compiled": warm["compiled"], "reused": warm["reused"]}))
        changed = builder.build({"generated.c": source + "/* changed */\n"})
        check("object-cache:changed-source-recompiles", changed["compiled"] == 1 and changed["reused"] == 0, json.dumps({"compiled": changed["compiled"], "reused": changed["reused"]}))
        check("object-cache:different-key", changed["records"][0]["key"] != cold["records"][0]["key"], "content-addressed")
        cached_object = next((WORKSPACE / "object-cache").glob("*.obj"))
        cached_object.write_bytes(b"corrupt")
        repaired = builder.build({"generated.c": source + "/* changed */\n"})
        check("object-cache:corrupt-recompiles", repaired["compiled"] == 1 and repaired["reused"] == 0, json.dumps({"compiled": repaired["compiled"], "reused": repaired["reused"]}))

        # positive control: the frozen fixture still completes the whole path
        positive = workflow.run_workflow(FIXTURE_ELF, workspace=WORKSPACE / "fixture")
        check("fixture:still-completes", positive["outcome"] == "COMPLETED" and positive.get("equivalence", {}).get("mismatches") == {}, json.dumps(positive, sort_keys=True)[:240])

        write_evidence(
            "hardening.json",
            {
                "stage": STAGE,
                "fixture": {"sha256": FIXTURE_SHA256},
                "negative_cases": [
                    "big-endian",
                    "elfclass64",
                    "et-rel",
                    "entry-not-executable",
                    "reachable-divu",
                    "reachable-jalr",
                    "reachable-lh",
                    "indirect-jr-t9",
                ],
                "analysis_cache": cache.stats(),
                "object_cache": {
                    "cold": {"compiled": cold["compiled"], "reused": cold["reused"]},
                    "warm": {"compiled": warm["compiled"], "reused": warm["reused"]},
                    "changed": {"compiled": changed["compiled"], "reused": changed["reused"]},
                    "corrupt": {"compiled": repaired["compiled"], "reused": repaired["reused"]},
                },
                "positive_control": {
                    "outcome": positive["outcome"],
                    "emission_fingerprint": positive["emission"]["program_fingerprint"],
                    "exit_status": positive["native"]["exit_status"],
                },
                "markers": {
                    "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                    "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
                },
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Fail-closed hardening",
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
    write_evidence("p8_11_tests.json", record)

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
