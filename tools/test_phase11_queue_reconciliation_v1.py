#!/usr/bin/env python3
"""Deterministic P11-RC control-only queue-reconciliation gate.

This gate proves that the explicitly authorized terminal route changes only
Phase-11 control/evidence state. It does not execute or simulate P11-08 through
P11-12 and does not add runtime, BIOS, translation, emission or guest behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
P11 = ROOT / ".openrecomp-phase11"
STAGE = "P11-RC"
BASELINE = "515e3fb0e660d3c7975e3828eb3e26ac025c7cf2"
BRANCH = "phase11/ps1-playability-v1"
CLASSIFICATION = "QUEUE_RECONCILIATION_REQUIRED"
ROUTE = ["P11-RC", "P11-90", "P11-91", "P11-99"]
UNEXECUTED = ["P11-08", "P11-09", "P11-10", "P11-11", "P11-12"]
PRESERVED = [f"P11-{index:02d}" for index in range(8)]

INITIALIZATION_MARKER = (
    "OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN"
)
FRAME_MARKER = "OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN"
GENERAL_MARKER = "OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN"
GPU_MARKER = "OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN"

RESULTS: list[dict[str, str]] = []


def check(name: str, condition: bool, detail: object = "") -> None:
    RESULTS.append({
        "check": name,
        "status": "PASS" if condition else "FAIL",
        "detail": str(detail),
    })
    if not condition:
        raise AssertionError(f"{name}: {detail}")


def run_git(*args: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", *args], cwd=str(ROOT), check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=text, encoding="utf-8" if text else None,
    )
    if completed.returncode != 0 or completed.stderr:
        stderr = completed.stderr if text else completed.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"git {' '.join(args)}: {stderr.strip()}")
    return completed.stdout


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: pathlib.Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def preserved_evidence_record() -> dict[str, Any]:
    stages: dict[str, Any] = {}
    for stage in PRESERVED:
        prefix = f".openrecomp-phase11/evidence/{stage}"
        listed = str(run_git("ls-tree", "-r", "--name-only", BASELINE, "--", prefix))
        baseline_paths = tuple(line for line in listed.splitlines() if line)
        current_root = ROOT / prefix
        current_paths = tuple(sorted(
            path.relative_to(ROOT).as_posix()
            for path in current_root.rglob("*") if path.is_file()
        ))
        check(f"history:{stage}:file-set", current_paths == baseline_paths,
              f"files={len(current_paths)}")

        entries: list[tuple[str, str]] = []
        for relative in baseline_paths:
            baseline_bytes = bytes(run_git("show", f"{BASELINE}:{relative}", text=False))
            current_bytes = (ROOT / relative).read_bytes()
            check(f"history:{stage}:bytes:{relative.rsplit('/', 1)[-1]}",
                  current_bytes == baseline_bytes, relative)
            entries.append((relative, sha256_bytes(current_bytes)))
        aggregate = "".join(f"{path}\0{digest}\n" for path, digest in entries)
        stages[stage] = {
            "file_count": len(entries),
            "tree_sha256": sha256_bytes(aggregate.encode("utf-8")),
        }
    return {
        "baseline_commit": BASELINE,
        "comparison": "byte-for-byte tracked file set and content",
        "stages": stages,
    }


def source_exhaustion_document() -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase11-source-exhaustion-v1",
        "stage": STAGE,
        "classification": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
        "question": (
            "legal architecture-compatible guest representation for the "
            "B0:0x5B target and required writable target-relative object"
        ),
        "sources": [
            {
                "name": "PSX-SPX",
                "repository": "https://github.com/psx-spx/psx-spx.github.io",
                "revision": "f37fc9a7a889a55e3bdec2d09a8a34640edf3082",
                "files": [{
                    "path": "docs/kernelbios.md",
                    "git_blob": "02145e7b785f4e20ed8e0f13deb44c54758ddfe6",
                }],
                "establishes": [
                    "B0:0x57 GetB0Table contract",
                    "B0:0x5B lookup and documented target-relative patch pattern",
                ],
                "insufficient": (
                    "documentation supplies no licensed callable guest code object, "
                    "initialized table representation or fail-closed entry targets"
                ),
            },
            {
                "name": "PCSX-Redux OpenBIOS/nugget",
                "repository": "https://github.com/pcsx-redux/nugget",
                "superproject_repository": "https://github.com/grumpycoders/pcsx-redux",
                "superproject_revision": "911271b7af5008a2fbbcb9b2390e26475208423d",
                "revision": "77adff516017044f2c6d9b21f66c124b9593959a",
                "license": "MIT",
                "files": [
                    {"path": "LICENSE", "git_blob": "490e7cb3ef1aebb1c931ff365233bb7adeaaf54f"},
                    {"path": "openbios/kernel/handlers.c", "git_blob": "55f56a3cae2dacd0e52cdefcee785631885e4a11"},
                    {"path": "openbios/kernel/vectors.s", "git_blob": "70367583247abc3782759ab13266350af5b48f23"},
                    {"path": "openbios/psx-bios.ld", "git_blob": "b3450294e0a7c246a9705845f5ce1dd9863fd28c"},
                    {"path": "openbios/sio0/driver.c", "git_blob": "b846e440f98f89f55cd8eecd93fa815e424c4099"},
                    {"path": "openbios/sio0/sio0.h", "git_blob": "c23fdff10fb9f994796c61c97265d0b6a0fa2592"},
                ],
                "symbols": ["B0table", "getB0table", "setSIO0AutoAck", "unimplementedThunk"],
                "establishes": [
                    "mutable 0x60-entry B0 table",
                    "B0:0x57 returns the table",
                    "B0:0x5B calls setSIO0AutoAck and returns the old value",
                    "unsupported entries use an explicit thunk",
                ],
                "insufficient": (
                    "addresses and relative layout are linker-specific and entries "
                    "depend on the complete replacement BIOS; the required target-relative "
                    "object is not a portable API guarantee"
                ),
            },
            {
                "name": "PCSX HLE BIOS in PSX-Bundle",
                "repository": "https://cgit.grumpycoder.net/cgit/PSX-Bundle",
                "revision": "7787631c6ee37a489732c95cb0864422e3a3bdd1",
                "license": "GPL-2.0",
                "files": [
                    {"path": "COPYING", "git_blob": "5b6e7c66c276e7610d4a73c70ec1a1f7c1003259"},
                    {"path": "PcsxSrc/PsxBios.c", "git_blob": "5494a20310c74d640ce3e5b79be6a5aae1bed838"},
                ],
                "symbols": ["bios_GetB0Table", "bios_ChangeClearPad"],
                "establishes": ["host HLE returns 0x00000874 for B0:0x57"],
                "insufficient": (
                    "no callable guest B0:0x5B target, initialized guest table entries "
                    "or documented writable target-relative object"
                ),
            },
            {
                "name": "PCSX-ReARMed HLE BIOS",
                "repository": "https://github.com/notaz/pcsx_rearmed",
                "revision": "17b970035fee27a0e21f1ba9f9b1e75377329de3",
                "license": "GPL-2.0",
                "files": [
                    {"path": "COPYING", "git_blob": "abacb82956be1ca676b1f864c9df61752deba442"},
                    {"path": "libpcsxcore/psxbios.c", "git_blob": "542b9d4d3fd92b92f8f5f74421bc79f1b7f806f8"},
                ],
                "symbols": ["psxBios_GetB0Table", "psxBios_ChangeClearPad", "A_B0_5B_TRAP"],
                "establishes": [
                    "emulator-specific fake B0 table and 0x43d0 HLE trap",
                    "synthetic helper code at the documented relative call offsets",
                ],
                "insufficient": (
                    "the entry is a custom emulator HLE opcode, the patch span is not "
                    "an independently specified guest object, and reuse requires a second HLE runtime"
                ),
            },
            {
                "name": "PCSX-Reloaded mirror HLE BIOS",
                "repository": "https://github.com/mirror/pcsxr",
                "revision": "51b2ad7c2bdc83ed6a0f297679233bc4d19de027",
                "license": "GPL-3.0",
                "files": [
                    {"path": "COPYING", "git_blob": "78d6dccf703947ae1db5a967866fa80b721f8df0"},
                    {"path": "libpcsxcore/psxbios.c", "git_blob": "204e75365ca1fe0194881b7ea4bc3fca8d61d209"},
                ],
                "symbols": ["psxBios_GetB0Table", "psxBios_ChangeClearPad"],
                "establishes": ["legacy 0x00000874 host-HLE table convention"],
                "insufficient": (
                    "placeholder entries and emulator-only HLE opcodes do not provide "
                    "a normal callable guest target or a proven writable target object"
                ),
            },
            {
                "name": "EmuMaster PCSX-derived HLE BIOS",
                "repository": "https://github.com/ruedigergad/emumaster",
                "revision": "9ab6e8d2bc3966fcb80f6a085346fb0e509bd9e0",
                "license": "source header GPL-2.0-or-later; no top-level license file at pin",
                "files": [{
                    "path": "src/psx/bios.cpp",
                    "git_blob": "420ed6b69948ce630c7d66d789034cee264f09b5",
                }],
                "symbols": ["psxBios_GetB0Table", "psxBios_ChangeClearPad"],
                "establishes": ["PCSX-derived 0x00000874 host-HLE convention"],
                "insufficient": (
                    "no independent normal guest representation and incomplete repository-level "
                    "license record; it retains the same host-HLE architectural dependency"
                ),
            },
        ],
        "required_but_unavailable": [
            "deterministic guest-addressable mutable B0 table representation",
            "normal callable guest representation for B0:0x5B",
            "established initialization and meaning for target offsets 0x594..0x5BC",
            "established pointer meaning at target offsets 0x884 and 0x894",
            "callable fail-closed unsupported entries",
            "compatibility with no BIOS image, no BIOS execution and one runtime",
        ],
        "decision": (
            "no candidate establishes all required facts; importing a replacement BIOS "
            "or emulator HLE runtime is outside Phase 11"
        ),
    }


def dependency_record(evidence: pathlib.Path) -> dict[str, Any]:
    expected = {
        "P11-00": ("p11-00-regression", "p11_00_tests.json", 482),
        "P11-05": ("p11-05-regression", "p11_05_tests.json", 294),
        "P11-06": ("p11-06-regression", "p11_06_tests.json", 75),
        "P11-07": ("p11-07-regression", "p11_07_tests.json", 41),
    }
    record: dict[str, Any] = {}
    for stage, (directory, tests_name, expected_count) in expected.items():
        root = evidence / directory
        official = json.loads((root / "official_runs.json").read_text(encoding="utf-8"))
        determinism = json.loads((root / "determinism.json").read_text(encoding="utf-8"))
        tests = json.loads((root / tests_name).read_text(encoding="utf-8"))
        check(f"dependency:{stage}:stage", official["stage"] == stage, official["stage"])
        check(f"dependency:{stage}:official-pass",
              all(official[key] for key in (
                  "identical_raw", "identical_lf", "returncode_zero_both",
                  "stderr_empty_both", "markers_present_both",
              )), "official runner")
        check(f"dependency:{stage}:sidecars",
              determinism["artifacts_identical"] is True, "deterministic sidecars")
        check(f"dependency:{stage}:no-fail-lines",
              all(not run["fail_lines"] for run in official["runs"]), "no FAIL lines")
        check(f"dependency:{stage}:check-count",
              len(tests["checks"]) == expected_count, len(tests["checks"]))
        record[stage] = {
            "checks": expected_count,
            "stdout_sha256_raw": official["runs"][0]["stdout_sha256_raw"],
            "stdout_sha256_lf": official["runs"][0]["stdout_sha256_lf"],
            "deterministic": True,
            "stderr_empty": True,
            "returncode_zero": True,
        }
    return record


def reconciliation_document(preserved: dict[str, Any],
                            dependencies: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "openrecomp-phase11-queue-reconciliation-v1",
        "stage": STAGE,
        "baseline": {"branch": BRANCH, "commit": BASELINE},
        "control_decision": CLASSIFICATION,
        "authorization": "explicit-user-authorized-control-only-route",
        "forcing_dependency": {
            "completed_stage": "P11-07",
            "site": "0x80015fa4",
            "block_index": 468341,
            "service": "ps1.bios.B0.57",
            "first_required_entry": "B0:0x5B ChangeClearPAD",
            "required_accesses": {
                "table_entry_offset": "0x16c",
                "derived_pointer_offsets": ["0x884", "0x894"],
                "write_span": "eleven aligned words at 0x594..0x5bc",
            },
            "classification": "BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE",
            "cause": "architectural/evidentiary, not implementation defect",
        },
        "preserved_evidence": preserved,
        "dependency_regressions": dependencies,
        "historical_queue": {
            "unexecuted_stages": UNEXECUTED,
            "stage_verdict_assigned": False,
            "rows_preserved_verbatim": True,
        },
        "authorized_terminal_route": ROUTE,
        "implementation_delta": {
            "runtime": False,
            "bios": False,
            "semantics": False,
            "translation": False,
            "emission": False,
            "guest_memory": False,
            "guest_registers": False,
            "device_behavior": False,
        },
        "milestones": {
            "A": "INHERITED_PROVEN",
            "B": "NOT_PROVEN",
            "C": "PROVEN_PRIVATE_FIXTURE_BOUNDED",
            "D": "NOT_PROVEN",
            "E": "NOT_PROVEN",
            "F": "NOT_PROVEN",
            "G": "NOT_PROVEN",
            "general_ps1_compatibility": "NOT_PROVEN_PERMANENT",
        },
        "future_phase_option": {
            "kind": "licensed replacement-BIOS integration",
            "inside_phase11": False,
            "requirements": [
                "new control plane",
                "new branch",
                "architecture review",
                "license and redistribution review",
                "explicit user authorization",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-RC")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    branch = str(run_git("branch", "--show-current")).strip()
    head = str(run_git("rev-parse", "HEAD")).strip()
    check("authority:branch", branch == BRANCH, branch)
    check("authority:baseline-head", head == BASELINE, head)

    preserved = preserved_evidence_record()

    source_integrity = subprocess.run(
        [sys.executable, str(P11 / "src" / "p11_source_manifest_v1.py")],
        cwd=str(ROOT), check=False, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8",
    )
    check("source-integrity:pass",
          source_integrity.returncode == 0
          and source_integrity.stderr == ""
          and source_integrity.stdout.startswith(
              "OPENRECOMP_PHASE11_SOURCE_INTEGRITY=PASS entries="
          ), source_integrity.stdout.strip() or source_integrity.stderr.strip())
    dependencies = dependency_record(evidence)

    control = (P11 / "CONTROL_POLICY.md").read_text(encoding="utf-8")
    scope = (P11 / "SCOPE.md").read_text(encoding="utf-8")
    queue = (P11 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
    state = (P11 / "STATE.md").read_text(encoding="utf-8")
    handoff = (P11 / "HANDOFF.md").read_text(encoding="utf-8")

    historical_rows = [
        "| P11-08 | CD-ROM / overlay / resource-loading frontier | `OPENRECOMP_P11_08=PASS` |",
        "| P11-09 | Controller / event / SPU frontier (deterministic replay format) | `OPENRECOMP_P11_09=PASS` |",
        "| P11-10 | Title/menu progression (milestones E and F) | `OPENRECOMP_P11_10=PASS` |",
        "| P11-11 | Milestone G: controllable gameplay (scripted input -> reproducible guest state change) | `OPENRECOMP_P11_11=PASS` |",
        "| P11-12 | Playability hardening + reproducibility | `OPENRECOMP_P11_12=PASS` |",
    ]
    for index, row in enumerate(historical_rows, 8):
        check(f"queue:historical-row:P11-{index:02d}", queue.count(row) == 1, row)
    check("queue:authorized-stage", "| P11-RC |" in queue, "P11-RC")
    check("queue:terminal-route", "`P11-RC -> P11-90 -> P11-91 -> P11-99`" in queue, "route")
    check("queue:no-verdict", "No stage verdict is" in queue, "unexecuted stages")
    check("control:decision", CLASSIFICATION in control, CLASSIFICATION)
    check("control:baseline", BASELINE in control, BASELINE)
    check("control:no-runtime-authorization", "does not authorize a BIOS replacement" in control,
          "control-only")
    check("scope:single-route", "Authorized P11-RC completion route" in scope, "scope")
    check("scope:no-verdict", "receive no stage verdict" in scope, "scope")
    check("state:reconciliation-record", "### P11-RC" in state, "state")
    check("handoff:reconciliation-record", "`P11-RC` is authorized" in handoff or "`P11-RC` `PASS`" in handoff,
          "handoff")

    for marker in (GPU_MARKER, INITIALIZATION_MARKER, FRAME_MARKER,
                   PLAYABILITY_MARKER, GENERAL_MARKER):
        check(f"claims:{marker}", marker in state, marker)

    changed = str(run_git(
        "status", "--porcelain=v1", "--untracked-files=all", "--",
        ".openrecomp-phase11", "tools/test_phase11_*.py",
    )).splitlines()
    allowed_exact = {
        ".openrecomp-phase11/CONTROL_POLICY.md",
        ".openrecomp-phase11/HANDOFF.md",
        ".openrecomp-phase11/SCOPE.md",
        ".openrecomp-phase11/SOURCE_SHA256SUMS.txt",
        ".openrecomp-phase11/STAGE_QUEUE.md",
        ".openrecomp-phase11/STATE.md",
        "tools/test_phase11_queue_reconciliation_v1.py",
    }
    unexpected: list[str] = []
    for line in changed:
        path = line[3:].replace("\\", "/")
        if path in allowed_exact or path.startswith(".openrecomp-phase11/evidence/P11-RC/"):
            continue
        unexpected.append(path)
    check("delta:authorized-paths-only", not unexpected, unexpected)

    implementation_diff = str(run_git(
        "diff", "--name-only", BASELINE, "--",
        ".openrecomp-phase11/runtime", ".openrecomp-phase11/src",
        "tools/test_phase11_boundary_v1.py",
        "tools/test_phase11_b0_table_v1.py",
        "tools/test_phase11_gpu_closure_v1.py",
        "tools/test_phase11_gpu_v1.py",
    )).splitlines()
    check("delta:no-runtime-or-completed-gate-change", not implementation_diff,
          implementation_diff)

    source_exhaustion = source_exhaustion_document()
    reconciliation = reconciliation_document(preserved, dependencies)
    write_json(evidence / "source_exhaustion.json", source_exhaustion)
    write_json(evidence / "reconciliation.json", reconciliation)

    public_text = json.dumps(
        {"source_exhaustion": source_exhaustion, "reconciliation": reconciliation},
        sort_keys=True,
    )
    check("public-safety:no-absolute-host-path",
          re.search(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])", public_text)
          is None, "no host paths")
    check("public-safety:no-private-payload",
          all(term not in public_text.lower() for term in (
              "payload bytes", "raw instruction words", "bios bytes",
              "reconstructive disassembly",
          )), "non-reconstructive metadata only")

    tests = {
        "schema": "openrecomp-phase11-tests-v1",
        "stage": STAGE,
        "classification": CLASSIFICATION,
        "checks": RESULTS,
        "summary": {
            "passed": sum(item["status"] == "PASS" for item in RESULTS),
            "failed": sum(item["status"] == "FAIL" for item in RESULTS),
        },
    }
    write_json(evidence / "p11_rc_tests.json", tests)

    for result in RESULTS:
        detail = f" {result['detail']}" if result["detail"] else ""
        print(f"{result['status']}: {result['check']}{detail}")
    print("OPENRECOMP_P11_RC=PASS")
    print(f"OPENRECOMP_PHASE11_QUEUE_RECONCILIATION={CLASSIFICATION}")
    print("OPENRECOMP_PHASE11_HIGHEST_MILESTONE=C_PRIVATE_FIXTURE_BOUNDED")
    print(INITIALIZATION_MARKER)
    print(FRAME_MARKER)
    print(PLAYABILITY_MARKER)
    print(GENERAL_MARKER)
    print(f"P11_RC_CHECKS={len(RESULTS)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: p11-rc:{type(exc).__name__}:{exc}")
        raise SystemExit(1)
