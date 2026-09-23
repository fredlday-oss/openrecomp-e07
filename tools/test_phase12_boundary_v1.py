#!/usr/bin/env python3
"""Deterministic P12-00 boundary, freeze and proof-contract gate.

Establishes the Phase-12 baseline efficiently from the frozen Phase-11
terminal commit, verifies the frozen Phase-11/Phase-10 trees are untouched,
re-verifies the private-fixture identity, writes the machine-readable proof
contracts, and records the reserved markers. It does not rerun historical
Phase-1..11 gates: ancestry, frozen tree comparison and hashes establish the
baseline.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase7/src", ".openrecomp-phase9/src",
              ".openrecomp-phase10/src", ".openrecomp-phase11/src",
              ".openrecomp-phase12/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

import p10_fixture_identity_v1 as fixture_identity  # noqa: E402
import p12_contracts_v1 as contracts  # noqa: E402


STAGE = "P12-00"
BASE_COMMIT = "665d11dc9f760d0c4ea2486e186c1fe5c762647c"
ANCESTORS = ("1aef50f6", "615e769c")
PHASE11_BRANCH = "phase11/ps1-playability-v1"

EXPECTED_EXECUTABLE_SHA256 = "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f"
EXPECTED_EXECUTABLE_SIZE = 129024

FROZEN_PREFIXES = (
    ".openrecomp-phase1", ".openrecomp-phase2", ".openrecomp-phase3",
    ".openrecomp-phase4", ".openrecomp-phase5", ".openrecomp-phase6",
    ".openrecomp-phase7", ".openrecomp-phase8", ".openrecomp-phase9",
    ".openrecomp-phase10", ".openrecomp-phase11", "tools",
)

DEFAULT_PRIVATE_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

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


def git(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=str(ROOT),
                          capture_output=True, text=True)


def assert_public_safe(label: str, document: dict[str, Any]) -> None:
    text = json.dumps(document, sort_keys=True)
    check(f"{label}:no-private-path",
          ":\\" not in text and "fixtures/" not in text,
          "absolute private paths absent")
    check(f"{label}:no-raw-words",
          all(term not in text for term in ("raw_instruction", "instruction_word",
                                            "payload_bytes", "bios_bytes")),
          "reconstructive fields absent")
    check(f"{label}:bounded",
          all(len(value) <= 240 for value in _strings(document)),
          "all strings bounded")


def _strings(document: Any):
    if isinstance(document, dict):
        for value in document.values():
            yield from _strings(value)
    elif isinstance(document, list):
        for value in document:
            yield from _strings(value)
    elif isinstance(document, str):
        yield document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase12/evidence/P12-00")
    parser.add_argument("--private-fixture-root",
                        default=str(DEFAULT_PRIVATE_FIXTURE_ROOT))
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)

    try:
        head = git("rev-parse", "HEAD").stdout.strip()
        branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        check("boundary:branch", branch == "phase12/ps1-hercules-init-frame-v1", branch)

        base_type = git("cat-file", "-t", BASE_COMMIT).stdout.strip()
        check("boundary:base-commit", base_type == "commit", base_type)
        base_tree = git("rev-parse", f"{BASE_COMMIT}^{{tree}}").stdout.strip()

        ancestor_head = git("merge-base", "--is-ancestor", BASE_COMMIT, head).returncode
        check("boundary:base-is-ancestor", ancestor_head == 0, str(ancestor_head))
        for ancestor in ANCESTORS:
            code = git("merge-base", "--is-ancestor", ancestor, head).returncode
            check(f"boundary:ancestor-{ancestor}", code == 0, str(code))
        phase11_tip = git("rev-parse", PHASE11_BRANCH).stdout.strip()
        check("boundary:phase11-tip-frozen", phase11_tip == BASE_COMMIT, phase11_tip)

        # Frozen Phase-1..Phase-11 trees and the historical gates must be
        # byte-identical between the base commit and the current HEAD.
        diff = git("diff", "--name-only", BASE_COMMIT, head, "--",
                   *FROZEN_PREFIXES)
        check("freeze:tracked-tree-unchanged", diff.stdout.strip() == "",
              diff.stdout.strip()[:200])

        # The frozen Phase-11 boundary must be an unmodified worktree.
        dirty = git("status", "--porcelain", "--", *FROZEN_PREFIXES)
        tracked_dirty = [
            line for line in dirty.stdout.splitlines()
            if not line.startswith("??")
        ]
        check("freeze:worktree-clean", not tracked_dirty,
              "\n".join(tracked_dirty)[:200])

        # Private fixture identity, re-derived read-only.
        identity = fixture_identity.build_identity(
            pathlib.Path(options.private_fixture_root)
        )
        executable = identity["executable"]
        check("fixture:executable-entry",
              executable["directory_entry"] == "SLUS_005.29",
              executable["directory_entry"])
        check("fixture:executable-size",
              executable["size"] == EXPECTED_EXECUTABLE_SIZE, str(executable["size"]))
        check("fixture:executable-sha256",
              executable["sha256"] == EXPECTED_EXECUTABLE_SHA256,
              executable["sha256"])
        check("fixture:boot-extent-matches",
              identity["system_cnf"]["matches_primary_executable"] is True,
              "boot extent == primary executable")
        check("fixture:track-layout",
              identity["disc"]["cue"]["track_count"] == 1,
              str(identity["disc"]["cue"]["track_count"]))

        contract_document = contracts.contracts_document()
        check("contract:initialization-predicates",
              tuple(item["id"] for item in
                    contract_document["initialization"]["predicates"])
              == contracts.INITIALIZATION_PREDICATES,
              str(len(contract_document["initialization"]["predicates"])))
        check("contract:frame-predicates",
              tuple(item["id"] for item in contract_document["frame"]["predicates"])
              == contracts.FRAME_PREDICATES,
              str(len(contract_document["frame"]["predicates"])))
        check("contract:reserved-markers",
              contract_document["reserved_markers"] == {
                  contracts.PLAYABILITY_MARKER: "NOT_PROVEN",
                  contracts.GENERAL_MARKER: "NOT_PROVEN",
              },
              json.dumps(contract_document["reserved_markers"], sort_keys=True))
        check("contract:no-third-party",
              contract_document["third_party_code_imported"] == "NO",
              contract_document["third_party_code_imported"])

        boundary_document = {
            "schema": "openrecomp-phase12-boundary-v1",
            "stage": STAGE,
            "phase11_base_commit": BASE_COMMIT,
            "phase11_base_tree": base_tree,
            "phase11_branch": PHASE11_BRANCH,
            "phase12_branch": branch,
            "phase12_head_at_boundary": head,
            "ancestors": list(ANCESTORS),
            "frozen_prefixes": list(FROZEN_PREFIXES),
            "frozen_tree_unchanged": True,
            "worktree_clean": True,
            "fixture_executable_sha256": executable["sha256"],
            "fixture_executable_size": executable["size"],
            "fixture_boot_extent_matches": True,
            "third_party_code_imported": "NO",
        }
        write_json(evidence / "proof_contracts.json", contract_document)
        write_json(evidence / "boundary.json", boundary_document)
        write_json(evidence / "fixture_identity.json", {
            "schema": "openrecomp-phase12-fixture-identity-v1",
            "stage": STAGE,
            "executable": executable,
            "cue": identity["disc"]["cue"],
            "bins": identity["disc"]["bins"],
            "system_cnf": identity["system_cnf"],
        })
        assert_public_safe("contracts", contract_document)
        assert_public_safe("boundary", boundary_document)

        tests = {
            "schema": "openrecomp-phase12-tests-v1",
            "stage": STAGE,
            "checks": RESULTS,
            "summary": {
                "passed": sum(item["status"] == "PASS" for item in RESULTS),
                "failed": sum(item["status"] == "FAIL" for item in RESULTS),
            },
        }
        write_json(evidence / "p12_00_tests.json", tests)

        result = {
            "schema": "openrecomp-phase12-result-v1",
            "stage": STAGE,
            "status": "PASS",
            "markers": {
                "OPENRECOMP_P12_00": "PASS",
                contracts.INITIALIZATION_MARKER: "NOT_PROVEN",
                contracts.FRAME_MARKER: "NOT_PROVEN",
                contracts.PLAYABILITY_MARKER: "NOT_PROVEN",
                contracts.GENERAL_MARKER: "NOT_PROVEN",
            },
            "next_stage": "P12-01",
        }
        write_json(evidence / "RESULT.json", result)

        for item in RESULTS:
            detail = f" {item['detail']}" if item["detail"] else ""
            print(f"{item['status']}: {item['check']}{detail}")
        print("OPENRECOMP_P12_00=PASS")
        print(f"{contracts.INITIALIZATION_MARKER}=NOT_PROVEN")
        print(f"{contracts.FRAME_MARKER}=NOT_PROVEN")
        print(f"{contracts.PLAYABILITY_MARKER}=NOT_PROVEN")
        print(f"{contracts.GENERAL_MARKER}=NOT_PROVEN")
        print(f"P12_00_CHECKS={len(RESULTS)}")
        return 0
    except AssertionError as exc:
        print(f"FAIL: p12-00:{exc}")
        return 1
    except Exception as exc:  # fail closed without a traceback
        print(f"FAIL: p12-00:{type(exc).__name__}:{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
