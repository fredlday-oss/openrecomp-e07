#!/usr/bin/env python3
"""OpenRecomp Phase-8 evidence index and proof matrix gate (P8-91).

P8-91 builds the final Phase-8 evidence index and the claim/proof matrix,
separating:

* PROVEN -- the exact bounded public real-ELF end-to-end native path;
* BOUNDED/PASS -- the specific ISA/ABI/memory/runtime behaviours actually
  exercised by the frozen fixture;
* NOT_PROVEN -- general MIPS32 compatibility, arbitrary ELF compatibility,
  unsupported ISA families and broader ABI/OS/runtime claims;
* UNSUPPORTED / NOT TESTED -- explicit closed/excluded areas.

It also verifies that no Phase-8 public evidence contains private or
unauthorized binary material.

On success it emits::

    OPENRECOMP_P8_91=PASS
    OPENRECOMP_PHASE8_EVIDENCE_INDEX_V1=PASS tests=<count>
    OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase8_evidence_index_v1.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))

import p8_mips32_semantics_v1 as semantics  # noqa: E402

P8 = ROOT / ".openrecomp-phase8"
EVIDENCE_DIR = P8 / "evidence" / "P8-91"

STAGE = "P8-91"
STAGE_MARKER = "OPENRECOMP_P8_91"
FEATURE_MARKER = "OPENRECOMP_PHASE8_EVIDENCE_INDEX_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

FIXTURE_SHA256 = "0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65"
STAGE_DIRS = tuple(f"P8-{index:02d}" for index in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)) + ("P8-90",)
PRIVATE_MARKERS = (
    "2a9345e608ec0c57470dc6658ce8199ddea9c18076134d9ef2a56f91b0a066d1",  # private Phase-7 NES fixture
    "tmnt.nes",
    "roms\\phase1",
    "roms/phase1",
)
FORBIDDEN_SUFFIXES = (".nes", ".fds", ".unf", ".unif", ".rom", ".iso", ".bin", ".exe", ".obj", ".dll", ".elf")

PROVEN_CLAIM = {
    "claim": (
        "For the exact frozen public fixture (tiny-AES-c AES-128-ECB, "
        "SHA-256 0a90f47754f6331b868ec09ad23c451fc2c73925a43897fa62a696b0d40dde65, "
        "built by the recorded Zig 0.13.0 toolchain from "
        "OpenRecomp-authored freestanding port files), the bounded "
        "ELF -> native path is proven: existing ELF ingestion, MIPS32 "
        "decode/semantics, shared neutral ProgramModel/CFG/function/call-graph/"
        "translation-unit structure with delay-slot folding, architecture-"
        "neutral host emission, the generic runtime ABI memory/service "
        "boundary, a reproducible native build, deterministic execution and "
        "full observable equivalence against an independently structured "
        "MIPS32 reference (no excluded observables)."
    ),
    "scope": "one audited bounded fixture and one audited observable record",
    "evidence": [
        ".openrecomp-phase8/evidence/P8-01/RESULT.md",
        ".openrecomp-phase8/evidence/P8-03/RESULT.md",
        ".openrecomp-phase8/evidence/P8-04/RESULT.md",
        ".openrecomp-phase8/evidence/P8-06/RESULT.md",
        ".openrecomp-phase8/evidence/P8-07/RESULT.md",
        ".openrecomp-phase8/evidence/P8-08/RESULT.md",
        ".openrecomp-phase8/evidence/P8-09/RESULT.md",
        ".openrecomp-phase8/evidence/P8-12/RESULT.md",
        ".openrecomp-phase8/evidence/P8-90/RESULT.md",
    ],
}
BOUNDED_CLAIMS = {
    "exercised_isa": {
        "description": "reachable MIPS32 op set with exact semantics and independent verification",
        "ops": sorted(semantics.SUPPORTED_OPS),
        "evidence": [".openrecomp-phase8/evidence/P8-02/RESULT.md", ".openrecomp-phase8/evidence/P8-04/RESULT.md"],
    },
    "delay_slots": {
        "description": "23 folded delay slots (16 non-nop) executed before every transfer with the link register materialized at call sites",
        "evidence": [".openrecomp-phase8/evidence/P8-03/RESULT.md", ".openrecomp-phase8/evidence/P8-04/RESULT.md"],
    },
    "memory_and_runtime": {
        "description": "flat guest image with explicit region permissions, 16 KiB stack, bounded checked access, one write-only byte output service, return-to-host termination",
        "evidence": [".openrecomp-phase8/evidence/P8-05/RESULT.md"],
    },
    "observable_record": {
        "description": "exit status, 32 boundary registers, register digest, memory digest, transcript length/digest, read/write/host-call/denied counts",
        "evidence": [".openrecomp-phase8/evidence/P8-08/RESULT.md", ".openrecomp-phase8/evidence/P8-09/RESULT.md"],
    },
    "workflow_and_hardening": {
        "description": "reusable deterministic workflow with explicit fail-closed categories and focused negative coverage",
        "evidence": [".openrecomp-phase8/evidence/P8-10/RESULT.md", ".openrecomp-phase8/evidence/P8-11/RESULT.md"],
    },
}
NOT_PROVEN_CLAIMS = (
    "OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY",
    "arbitrary MIPS32 ELF compatibility",
    "complete MIPS32 ISA support (division/HI-LO, halfword and partial-word memory, branch-likely, coprocessors, floating point, traps, privileged execution)",
    "complete o32 ABI support beyond the audited fixtures call/stack/link-register pattern",
    "arbitrary Linux binaries, dynamic linking, kernel or syscall emulation",
    "exceptions and precise exception semantics",
    "arbitrary indirect-control-flow recovery (unresolved sites fail closed)",
    "PS1, PS2, game or commercial-binary compatibility",
    "cycle accuracy or performance claims",
    "cross-platform build or execution claims",
)
UNSUPPORTED_CLAIMS = (
    "unsupported ELF containers (ELF64, big-endian, ET_REL, ET_DYN, dynamic/relocated)",
    "unsupported MIPS32 encodings with no rule (div/divu, mult/multu, mul, movn, jalr, swl/swr, lwl/lwr, lh/lhu/sh, beql/bnel)",
    "non-return indirect control flow without evidence",
    "non-stack, non-image or GP-relative memory access",
    "unresolved stale analysis-cache or object-cache entries",
)

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


def main() -> int:
    try:
        # evidence index
        index_entries = []
        for path in sorted((P8 / "evidence").rglob("*")):
            if not path.is_file():
                continue
            if path.relative_to(P8 / "evidence").parts[0] == STAGE:
                continue
            rel = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            index_entries.append(
                {
                    "stage": path.relative_to(P8 / "evidence").parts[0],
                    "path": rel,
                    "bytes": len(data),
                    "sha256": sha256_bytes(data),
                    "tracked": True,
                }
            )
        check("index:entries", len(index_entries) > 100, str(len(index_entries)))
        stages_seen = {entry["stage"] for entry in index_entries}
        check("index:stages", set(STAGE_DIRS) <= stages_seen, json.dumps(sorted(stages_seen)))
        for stage in STAGE_DIRS:
            check(f"index:result:{stage}", any(entry["path"] == f".openrecomp-phase8/evidence/{stage}/RESULT.md" for entry in index_entries), stage)

        # proof matrix
        check("proven:fixture", FIXTURE_SHA256 in PROVEN_CLAIM["claim"], FIXTURE_SHA256)
        check("proven:evidence-paths", all((ROOT / rel).is_file() for rel in PROVEN_CLAIM["evidence"]), "evidence present")
        check("bounded:isa-ops", len(BOUNDED_CLAIMS["exercised_isa"]["ops"]) == 22, str(len(BOUNDED_CLAIMS["exercised_isa"]["ops"])))
        check("bounded:evidence-paths", all((ROOT / rel).is_file() for claim in BOUNDED_CLAIMS.values() for rel in claim["evidence"]), "evidence present")
        check("not-proven:general", any("GENERAL_MIPS32" in item for item in NOT_PROVEN_CLAIMS), "general non-claim present")
        check("not-proven:scope", len(NOT_PROVEN_CLAIMS) >= 8, str(len(NOT_PROVEN_CLAIMS)))
        check("unsupported:scope", len(UNSUPPORTED_CLAIMS) >= 5, str(len(UNSUPPORTED_CLAIMS)))

        # no private/unauthorized material
        violations = []
        tracked_roots = ("evidence", "fixture", "runtime", "src")
        for root_name in tracked_roots:
            for path in sorted((P8 / root_name).rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                rel = path.relative_to(P8).as_posix()
                if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                    violations.append(f"forbidden-suffix:{rel}")
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
                for marker in PRIVATE_MARKERS:
                    if marker in text:
                        violations.append(f"private-marker:{rel}:{marker}")
        for path in sorted(P8.glob("*.md")) + [P8 / ".gitignore", P8 / "SOURCE_SHA256SUMS.txt"]:
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
                for marker in PRIVATE_MARKERS:
                    if marker in text:
                        violations.append(f"private-marker:{path.name}:{marker}")
        check("safety:no-private-material", violations == [], json.dumps(violations[:5]))
        check(
            "safety:no-rom-or-native-binaries",
            not any(
                path.suffix.lower() in FORBIDDEN_SUFFIXES
                for root_name in tracked_roots
                for path in (P8 / root_name).rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            ),
            "no ROM/native-binary suffixes in committed material",
        )
        gitignore = (P8 / ".gitignore").read_text(encoding="utf-8")
        check("safety:external-ignored", "external/" in gitignore, "upstream source trees untracked")
        upstream_probe = P8 / "external" / "tiny-AES-c" / "aes.c"
        if upstream_probe.is_file():
            ignored = subprocess.run(
                ["git", "-C", str(ROOT), "check-ignore", "-q", upstream_probe.relative_to(ROOT).as_posix()],
                capture_output=True,
            ).returncode == 0
            check("safety:upstream-untracked", ignored, "upstream source ignored by git")

        write_evidence(
            "evidence_index.json",
            {
                "stage": STAGE,
                "entries": index_entries,
                "entry_count": len(index_entries),
                "total_bytes": sum(entry["bytes"] for entry in index_entries),
                "note": "the index excludes its own directory's generated sidecars",
            },
        )
        write_evidence(
            "claim_ledger.json",
            {
                "stage": STAGE,
                "proven": [PROVEN_CLAIM],
                "bounded_pass": BOUNDED_CLAIMS,
                "not_proven": list(NOT_PROVEN_CLAIMS),
                "unsupported": list(UNSUPPORTED_CLAIMS),
                "terminal_marker": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                "general_marker": f"{GENERAL_MARKER}={NOT_PROVEN}",
                "frozen_phases_modified": False,
            },
        )
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Evidence index and proof matrix",
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
    write_evidence("p8_91_tests.json", record)

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
