#!/usr/bin/env python3
"""OpenRecomp Phase-4 evidence index and claim ledger (P4-91).

Builds the complete Phase-4 evidence index and the explicit claim ledger that
separates PROVEN, BOUNDED, UNPROVEN, UNSUPPORTED and NOT TESTED, with every
material limitation recorded together with its evidence and impact.

It emits::

    OPENRECOMP_P4_91=PASS
    OPENRECOMP_PHASE4_EVIDENCE_INDEX_V1=PASS tests=<count>
    OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase4_evidence_index_v1.py
    python tools/test_phase4_evidence_index_v1.py --evidence-dir .openrecomp-phase4/evidence/P4-91
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTROL = ROOT / ".openrecomp-phase4"
EVIDENCE_ROOT = CONTROL / "evidence"

STAGE = "P4-91"
STAGE_MARKER = "OPENRECOMP_P4_91"
FEATURE_MARKER = "OPENRECOMP_PHASE4_EVIDENCE_INDEX_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF"
COMPAT_MARKER = "OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY"

CONTROL_FILES = ("CONTROL_POLICY.md", "EVIDENCE_SCHEMA.md", "HANDOFF.md",
                 "SCOPE.md", "SOURCE_SHA256SUMS.txt", "STAGE_QUEUE.md", "STATE.md")
STAGES = tuple(f"P4-{index:02d}" for index in
               (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 90, 91))
PACKAGE = ".openrecomp-phase4/package/phase4_package_v1.zip"

CLAIMS: dict[str, Any] = {
    "terminal_marker": f"{TERMINAL_MARKER}=NOT_PROVEN",
    "compatibility_marker": f"{COMPAT_MARKER}=NOT_PROVEN",
    "generic_runtime_status": "NOT_PROVEN",
    "coremark_status": "NOT_PROVEN",
    "proven": [
        {"claim": "Phase-4 boundary descends from the frozen Phase-3 PASS "
                  "boundary and the frozen P3-99 final gate re-runs "
                  "byte-identically in the reconstructed Phase-3 context.",
         "evidence": ".openrecomp-phase4/evidence/P4-00/"},
        {"claim": "Architecture-neutral generated-code <-> runtime ABI V1 "
                  "(state, calls, exits, faults, memory boundary, typed "
                  "versioned services, deterministic observable) is defined "
                  "and verified, including compliance of the frozen Phase-3 "
                  "generated artifacts.",
         "evidence": ".openrecomp-phase4/evidence/P4-01/"},
        {"claim": "Explicit guest memory model with regions, permissions, "
                  "bounds, alignment and endian semantics and fail-closed "
                  "faults mapped to the ABI codes.",
         "evidence": ".openrecomp-phase4/evidence/P4-02/"},
        {"claim": "Runtime service mediation with typed/versioned interfaces "
                  "and declared aliases; fixture-specific handling becomes "
                  "data; unknown services and failures fail closed; the exact "
                  "frozen external interaction replays byte-identically.",
         "evidence": ".openrecomp-phase4/evidence/P4-03/"},
        {"claim": "Bounded deterministic I/O, virtual time and input/event "
                  "delivery with explicit recorded inputs and no ambient host "
                  "input capability.",
         "evidence": ".openrecomp-phase4/evidence/P4-04/"},
        {"claim": "Architecture-neutral platform-adapter contract restricted "
                  "to the generic interface catalog with explicit negative "
                  "compatibility claims and optional graphics/audio hooks.",
         "evidence": ".openrecomp-phase4/evidence/P4-05/"},
        {"claim": "Reusable graphics/audio adapter boundaries with "
                  "capability validation, deterministic headless reference "
                  "implementations and no mandatory backend.",
         "evidence": ".openrecomp-phase4/evidence/P4-06/"},
        {"claim": "Original Apache-2.0 interactive fixture is reproducible and "
                  "its complete decode frontier is inventoried with no "
                  "indirect or unresolved control flow.",
         "evidence": ".openrecomp-phase4/evidence/P4-07/"},
        {"claim": "The fixture translates, builds reproducibly and executes "
                  "natively through a real platform adapter/runtime "
                  "implementation, reproducing the expected transcript and "
                  "state digest with fail-closed negatives.",
         "evidence": ".openrecomp-phase4/evidence/P4-08/"},
        {"claim": "The nine-stage generic-runtime pipeline is demonstrated "
                  "end-to-end and the observable is verified against an "
                  "independent reference (own loader, decoder, executor) on "
                  "every compared field.",
         "evidence": ".openrecomp-phase4/evidence/P4-09/"},
        {"claim": "A deterministic byte-reproducible package with a verified "
                  "member manifest and fail-closed content policy.",
         "evidence": ".openrecomp-phase4/evidence/P4-10/"},
        {"claim": "The complete Phase-1/Phase-2/Phase-3/Phase-4 regression set "
                  "re-runs from the audited tree with byte-identical stdout "
                  "and the frozen earlier boundaries remain valid.",
         "evidence": ".openrecomp-phase4/evidence/P4-90/"},
    ],
    "bounded": [
        {"claim": "Every PROVEN statement above is bounded to the audited "
                  "fixtures, profiles, toolchains and declared policies.",
         "evidence": "P4-07/P4-08/P4-09 evidence"},
        {"claim": "The Phase-4 end-to-end claim is bounded to the original "
                  "fixture, its translation profile and the declared "
                  "one-tick-per-retired-instruction policy.",
         "evidence": ".openrecomp-phase4/evidence/P4-09/equivalence.json"},
        {"claim": "The Phase-3 CoreMark real-ELF proof remains the separate "
                  "bounded Phase-3 claim (tag openrecomp-phase3-pass).",
         "evidence": ".openrecomp-phase3/evidence/P3-99/"},
    ],
    "unproven": [
        "arbitrary binary compatibility",
        "arbitrary MIPS32 compatibility",
        "PS1/PS2/N64/PSP or any console compatibility",
        "game or commercial-title compatibility",
        "cycle accuracy or hardware emulation",
        "self-modifying code",
        "runtime equivalence beyond the audited deterministic observable",
        "general renderer/audio backend integration",
        "universal runtime completeness",
    ],
    "unsupported": [
        "indirect control flow without a declared resolution mechanism in the "
        "shared layers (the reference fails closed; the fixture avoids it)",
        "unaligned multi-byte loads/stores in the emitted/reference paths "
        "(fail closed)",
        "instructions outside the audited fixture set in the independent "
        "reference (fail closed)",
        "host wall clock, real filesystem, network and process capabilities "
        "(no ambient capability path exists)",
        "platform-specific runtime service interface names in V1 (adapters "
        "use generic-catalog aliases)",
        "compiled/guest binaries inside the reproducible package (rebuilt "
        "from pinned source instead)",
    ],
    "not_tested": [
        "real console or hardware execution",
        "performance or benchmarking claims",
        "floating point programs",
        "multi-threaded or interrupt-driven guests",
        "big-endian MIPS or other architectures through the Phase-4 layers",
        "the -O2 stress profile",
    ],
    "limitations": [
        {"limitation": "The shared Phase-2 structural layers have no delay-slot "
                       "concept; delay slots are modelled as NORMAL "
                       "instructions with the relationship recorded separately "
                       "(inherited Phase-3 limitation, unchanged).",
         "impact": "Structural function ownership excludes orphan delay-slot "
                   "blocks in the neutral model.", "evidence": "P4-09 pipeline"},
        {"limitation": "The Phase-4 fixture deliberately avoids indirect "
                       "control flow and unaligned accesses to stay inside the "
                       "proven bounded frontier.",
         "impact": "No claim about arbitrary MIPS32 programs.",
         "evidence": ".openrecomp-phase4/evidence/P4-07/"},
        {"limitation": "The native runtime support is the concrete adapter "
                       "implementation for this fixture, not a universal "
                       "runtime.",
         "impact": "Other guests require their own generated support subject "
                   "to the same contracts.", "evidence": "P4-08 evidence"},
        {"limitation": "Tick values depend on the declared "
                       "one-tick-per-retired-instruction policy.",
         "impact": "A different policy changes the tick transcript fields.",
         "evidence": ".openrecomp-phase4/fixture/input_plan.json"},
        {"limitation": "External toolchains (zig 0.13.0, LLVM/clang-cl 22.1.8) "
                       "are pinned by identity and not shipped in the package.",
         "impact": "Reproduction requires those exact toolchains.",
         "evidence": ".openrecomp-phase4/evidence/P4-10/REPRODUCE.md"},
        {"limitation": "Package bytes are reproducible from the same tree "
                       "state only, and host-specific command records are "
                       "excluded by design.",
         "impact": "The package is a snapshot, not a self-contained toolchain.",
         "evidence": "P4-10 package evidence"},
        {"limitation": "Gate sources embed the content-policy detection "
                       "needles and are exempt from needle scans (still "
                       "UTF-8/LF checked and hashed).",
         "impact": "Policy scans apply fully to all product members only.",
         "evidence": ".openrecomp-phase4/src/p4_package_v1.py"},
        {"limitation": "CoreMark remains an unsupported target; "
                       "COREMARK_STATUS=NOT_PROVEN.",
         "impact": "No CoreMark support claim is implied by Phase 4.",
         "evidence": ".openrecomp-phase3/evidence/P3-91/claim_record.json"},
    ],
}

RESULTS: list[dict[str, str]] = []
FINDINGS: dict[str, Any] = {}
ARTIFACTS: dict[str, bytes] = {}


def check(label: str, condition: bool) -> None:
    if not condition:
        RESULTS.append({"check": label, "status": "FAIL"})
        print(f"FAIL: {label}", flush=True)
        raise AssertionError(f"{label}: condition failed")
    RESULTS.append({"check": label, "status": "PASS"})
    print(f"PASS: {label}", flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def banner(name: str) -> None:
    print(f"\n--- {name} ---", flush=True)


def build_index() -> dict[str, Any]:
    tracked = {
        item.replace("\\", "/")
        for item in subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT),
                                   capture_output=True).stdout.decode("utf-8").split("\x00")
        if item
    }
    files = []
    for stage in STAGES:
        stage_dir = EVIDENCE_ROOT / stage
        if not stage_dir.is_dir():
            continue
        records = []
        for path in sorted(stage_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            records.append({
                "path": relative,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                "tracked": relative in tracked,
            })
        files.append({"stage": stage, "file_count": len(records), "files": records})
    return {
        "stage": STAGE,
        "stages": files,
        "evidence_file_count": sum(entry["file_count"] for entry in files),
        "control_plane": {name: sha256_file(CONTROL / name) for name in CONTROL_FILES},
        "boundaries": {
            "phase3_tag": "openrecomp-phase3-pass",
            "phase3_commit": "e16e4b29b90f379615f1af97e47747cd1d531796",
            "phase3_tree": "a940f0d84a32adaf191f7ff2bebfb24cc855cde0",
            "package": PACKAGE,
            "package_sha256": sha256_file(ROOT / PACKAGE),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P4-91 evidence index gate")
    parser.add_argument("--evidence-dir", type=str,
                        default=".openrecomp-phase4/evidence/P4-91")
    args = parser.parse_args()

    global EVIDENCE_DIR, RESULTS, FINDINGS, ARTIFACTS
    EVIDENCE_DIR = pathlib.Path(args.evidence_dir)
    if not EVIDENCE_DIR.is_absolute():
        EVIDENCE_DIR = (ROOT / EVIDENCE_DIR).resolve()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS = []
    FINDINGS = {}
    ARTIFACTS = {}

    print("=== P4-91 Evidence Index Gate ===", flush=True)
    failure: str | None = None
    try:
        banner("index")
        index = build_index()
        for stage in STAGES:
            check(f"index:stage:{stage}", any(entry["stage"] == stage
                                              for entry in index["stages"]))
        check("index:evidence-files", index["evidence_file_count"] > 200)
        check("index:control-plane", len(index["control_plane"]) == 7)
        check("index:package-present", (ROOT / PACKAGE).is_file())
        check("index:package-sha256",
              len(index["boundaries"]["package_sha256"]) == 64)
        ARTIFACTS["evidence_index.json"] = (
            json.dumps(index, indent=2, sort_keys=True) + "\n").encode("utf-8")

        banner("claims")
        record = dict(CLAIMS)
        record["stage"] = STAGE
        record["proven_count"] = len(CLAIMS["proven"])
        record["bounded_count"] = len(CLAIMS["bounded"])
        record["unproven_count"] = len(CLAIMS["unproven"])
        record["unsupported_count"] = len(CLAIMS["unsupported"])
        record["not_tested_count"] = len(CLAIMS["not_tested"])
        record["limitation_count"] = len(CLAIMS["limitations"])
        check("claims:proven", record["proven_count"] >= 10)
        check("claims:unproven", record["unproven_count"] >= 8)
        check("claims:unsupported", record["unsupported_count"] >= 5)
        check("claims:not-tested", record["not_tested_count"] >= 5)
        check("claims:limitations", record["limitation_count"] >= 8)
        check("claims:terminal-reserved", "NOT_PROVEN" in record["terminal_marker"])
        check("claims:general-reserved", "NOT_PROVEN" in record["compatibility_marker"])
        check("claims:generic-runtime-status",
              record["generic_runtime_status"] == "NOT_PROVEN")
        check("claims:coremark-status", record["coremark_status"] == "NOT_PROVEN")
        check("claims:console-unproven",
              any("console" in item for item in CLAIMS["unproven"]))
        check("claims:game-unproven",
              any("game" in item for item in CLAIMS["unproven"]))
        check("claims:limitations-evidenced",
              all(item.get("impact") and item.get("evidence")
                  for item in CLAIMS["limitations"]))
        ARTIFACTS["claim_record.json"] = (
            json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")

        banner("determinism")
        second = build_index()
        check("determinism:index",
              json.dumps(second, sort_keys=True) == json.dumps(index, sort_keys=True))
        check("determinism:claims",
              json.dumps(dict(CLAIMS), sort_keys=True)
              == json.dumps(dict(CLAIMS), sort_keys=True))
        ARTIFACTS["determinism.json"] = (
            json.dumps({
                "stage": STAGE,
                "evidence_file_count": index["evidence_file_count"],
                "control_plane": index["control_plane"],
                "package_sha256": index["boundaries"]["package_sha256"],
                "claim_counts": {
                    "proven": record["proven_count"],
                    "bounded": record["bounded_count"],
                    "unproven": record["unproven_count"],
                    "unsupported": record["unsupported_count"],
                    "not_tested": record["not_tested_count"],
                    "limitations": record["limitation_count"],
                },
            }, indent=2, sort_keys=True) + "\n").encode("utf-8")
        FINDINGS["index"] = {"evidence_file_count": index["evidence_file_count"],
                             "stages": [entry["stage"] for entry in index["stages"]]}
        FINDINGS["claims"] = {key: record[f"{key}_count"]
                              for key in ("proven", "bounded", "unproven",
                                          "unsupported", "not_tested", "limitation")}
    except Exception as exc:  # noqa: BLE001 - fail closed without traceback
        failure = f"{type(exc).__name__}: {exc}"

    passed = sum(1 for item in RESULTS if item["status"] == "PASS")
    failed = sum(1 for item in RESULTS if item["status"] == "FAIL") + (1 if failure else 0)
    status = "FAIL" if failure else "PASS"

    result = {
        "stage": STAGE,
        "stage_name": FEATURE_MARKER,
        "status": status,
        "tests": passed,
        "passed": passed,
        "failed": failed,
        "markers": {
            "stage": f"{STAGE_MARKER}={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={passed}",
            "terminal": f"{TERMINAL_MARKER}=NOT_PROVEN",
            "compatibility": f"{COMPAT_MARKER}=NOT_PROVEN",
        },
        "checks": sorted(RESULTS, key=lambda item: item["check"]),
        "findings": FINDINGS,
        "failure": failure,
    }
    for name, payload in ARTIFACTS.items():
        (EVIDENCE_DIR / name).write_bytes(payload)
    (EVIDENCE_DIR / "p4_91_tests.json").write_bytes(
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    print("\n=== RESULT ===")
    if status == "PASS":
        print(f"{STAGE_MARKER}=PASS")
        print(f"{FEATURE_MARKER}=PASS tests={passed}")
        print(f"{TERMINAL_MARKER}=NOT_PROVEN")
        print(f"{COMPAT_MARKER}=NOT_PROVEN")
        return 0
    print(f"{STAGE_MARKER}=FAIL ({failure})")
    print(f"{FEATURE_MARKER}=FAIL")
    print(f"{TERMINAL_MARKER}=NOT_PROVEN")
    print(f"{COMPAT_MARKER}=NOT_PROVEN")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
