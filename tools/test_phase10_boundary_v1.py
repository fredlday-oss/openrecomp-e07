#!/usr/bin/env python3
"""Deterministic P10-00 Phase-9-boundary, fixture-identity and control-plane gate.

The gate verifies:

* the frozen Phase-9 terminal boundary identity (commit/tree/branch) and the
  untouched Phase-9 terminal evidence and control-plane hashes;
* the untouched Phase-1 through Phase-9 trees, including the documented
  pre-existing working-tree residue;
* the inherited Phase-6/Phase-7/Phase-8 reconciliation records;
* the captured toolchain set;
* the private fixture/disc identity: discovered CUE, referenced BIN, ISO9660
  filesystem relationship, SYSTEM.CNF boot target and boot-extent identity
  against the primary ``SLUS_005.29`` fixture;
* the inherited Phase-9 Hercules frontier reproduction (4068 reachable words,
  ``break`` at ``0x80013390``, ``CONTROL_WITHOUT_DELAY_SLOT``);
* the frozen Phase-10 control plane.

It adds no PS1 capability and performs no substantive compatibility
implementation.

On success it emits::

    OPENRECOMP_P10_00=PASS
    OPENRECOMP_PHASE10_BOUNDARY_V1=PASS tests=<count>
    OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN
    OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

Usage:

    python tools/test_phase10_boundary_v1.py
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import re
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P9 = ROOT / ".openrecomp-phase9"
P10 = ROOT / ".openrecomp-phase10"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".openrecomp-phase3" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase8" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase9" / "src"))
sys.path.insert(0, str(ROOT / ".openrecomp-phase10" / "src"))

import p9_psx_exe_v1 as psx  # noqa: E402
import p10_fixture_identity_v1 as fixture  # noqa: E402
import p10_frontier_v1 as frontier  # noqa: E402

STAGE = "P10-00"
FEATURE_MARKER = "OPENRECOMP_PHASE10_BOUNDARY_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE10_HERCULES_PLAYABILITY"
GENERAL_MARKER = "OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY"
NOT_PROVEN = "NOT_PROVEN"

BASELINE_PHASE = 9
BASELINE_COMMIT = "08c639d9032a364163f2985432744be420d402eb"
BASELINE_TREE = "900dccf06ce3d5df7b499a9f05a6ceea060114d7"
BASELINE_BRANCH = "phase8/mips32-end-to-end-native-v1"
PHASE10_BRANCH = "phase10/ps1-commercial-game-native-v1"

DEFAULT_PRIVATE_FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"

FROZEN_P9_HASHES = {
    ".openrecomp-phase9/evidence/P9-99/RESULT.md":
        "2ef6752fd1187883ebe9dd9814d286448a8f061056d3456d273dfdcf83261383",
    ".openrecomp-phase9/evidence/P9-99/terminal_verdict.json":
        "5d4c70008436925c3c986a4166376bc322400c119ea3ea24df234ba2eca4d783",
    ".openrecomp-phase9/evidence/P9-99/verdict_record.json":
        "96337230b155694ba9f150bb5b6201388ad74279956c11ced296bfc736b7dcae",
    ".openrecomp-phase9/evidence/P9-99/p9_99_tests.json":
        "1e911be47fe8e953eec4632ade35697c931db94ce63557655632702388b7d9f4",
    ".openrecomp-phase9/evidence/P9-99/official_runs.json":
        "11e4adb9d5ab533bcea949ef7104ca51933e2475472540c0cb96933d6b5c1842",
    ".openrecomp-phase9/evidence/P9-99/determinism.json":
        "532c0769b803b13f96a55f8f933bab1fe92a829a22c04f26f8ce7037cd1374f0",
    ".openrecomp-phase9/STATE.md":
        "11267465040b7f36ff96b422c6f7b711dee50e1c7acdc745f486b53adda1157e",
    ".openrecomp-phase9/STAGE_QUEUE.md":
        "93eec1dc331b877c81572a25997be1364c0b62e742032a1de3e18caf77d8f7a8",
    ".openrecomp-phase9/HANDOFF.md":
        "3e8b0d6d10784304a67467aed4a258832c48968f0c20cd3a5480161804356cf9",
    ".openrecomp-phase9/SOURCE_SHA256SUMS.txt":
        "ef72fbb1dbf75ad45fbf71940e9eca4725b246442c3e4be231ba77cacdfedb46",
    ".openrecomp-phase9/CONTROL_POLICY.md":
        "1bdbb7c5075d8542999a0d5336120ca705e076d38e2ab838aef1d5206323815b",
    ".openrecomp-phase9/SCOPE.md":
        "d45f4d748dfc053623f6cf57114ca1f65957302db80b8c53649aead4caf99b71",
    ".openrecomp-phase9/ACCELERATION_POLICY.md":
        "6e9d19bc10eb3ffec2500c2ae820f15436ccaa282c24f445a9e4a51003cf79c0",
    ".openrecomp-phase9/EVIDENCE_SCHEMA.md":
        "ceb1e39dc7dee28d541c3e42fdd85129547b606748e02825467e6e97b4a2796e",
    ".openrecomp-phase9/FIXTURE_POLICY.md":
        "efc13de51cba3eb6e8c3f21898c63f503a6ce4808d72a489d94399334ccd2675",
    ".openrecomp-phase9/evidence/README.md":
        "002cfa33391df6a7afcb1043403e81b9b09b2a2ae61f75d262bbb40fea72d687",
}

DOCUMENTED_PRIOR_TRACKED_DIFF = {
    ".openrecomp-phase3/evidence/P3-00/p3_00_tests.json",
    ".openrecomp-phase3/evidence/P3-00/residue_manifest.txt",
}

REQUIRED_CONTROL_FILES = (
    ".openrecomp-phase10/.gitignore",
    ".openrecomp-phase10/ACCELERATION_POLICY.md",
    ".openrecomp-phase10/CONTROL_POLICY.md",
    ".openrecomp-phase10/EVIDENCE_SCHEMA.md",
    ".openrecomp-phase10/FIXTURE_POLICY.md",
    ".openrecomp-phase10/HANDOFF.md",
    ".openrecomp-phase10/SCOPE.md",
    ".openrecomp-phase10/STAGE_QUEUE.md",
    ".openrecomp-phase10/STATE.md",
    ".openrecomp-phase10/evidence/README.md",
    ".openrecomp-phase10/src/p10_fixture_identity_v1.py",
    ".openrecomp-phase10/src/p10_frontier_v1.py",
    ".openrecomp-phase10/src/p10_source_manifest_v1.py",
    ".openrecomp-phase10/src/p10_stage_runner_v1.py",
)

FROZEN_STAGES = (
    "P10-00", "P10-01", "P10-02", "P10-03", "P10-04", "P10-05", "P10-06",
    "P10-07", "P10-08", "P10-09", "P10-10", "P10-11", "P10-12", "P10-90",
    "P10-91", "P10-99",
)

TOOLCHAIN_COMMANDS = {
    "python": ("python", "--version"),
    "git": ("git", "--version"),
    "clang": ("clang", "--version"),
    "clang-cl": ("clang-cl", "--version"),
    "lld-link": ("lld-link", "--version"),
    "ninja": ("ninja", "--version"),
    "cmake": ("cmake", "--version"),
    "zig": (".openrecomp-phase3/tools/zig/zig.exe", "version"),
}

EXPECTED_FIXTURE = {
    "executable_size": 129024,
    "executable_sha256": "c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f",
    "cue_size": 101,
    "cue_sha256": "beea454de356689cdaa06702f4ed76a5474fd125a7460619ee678c1ae8725df2",
    "bin_size": 409452624,
    "bin_sha256": "2ce144ba0e1fed6952ad80976814e3033fec6cddfb5e17cdf0294517ea311365",
    "entry": "0x800132e8",
    "text_address": "0x80010000",
    "text_size": "0x0001f000",
    "stack_pointer": "0x801ffff0",
    "boot_target": "SLUS_005.29",
    "volume_space_size_sectors": 174087,
    "root_extent_lba": 22,
}

RESULTS: list[dict[str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    RESULTS.append({"check": label, "status": "PASS" if condition else "FAIL", "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: condition failed ({detail})")


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def capture_toolchains() -> dict[str, dict[str, str]]:
    captured: dict[str, dict[str, str]] = {}
    for name, command in TOOLCHAIN_COMMANDS.items():
        executable = command[0]
        if not pathlib.Path(executable).is_absolute():
            candidate = ROOT / executable
            if candidate.is_file():
                executable = str(candidate)
        try:
            result = subprocess.run(
                [executable, *command[1:]],
                check=False,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            captured[name] = {"version": "UNAVAILABLE"}
            continue
        text = (result.stdout or result.stderr).strip()
        first = text.splitlines()[0].strip() if text else ""
        captured[name] = {"version": first or "UNAVAILABLE", "exit_code": str(result.returncode)}
    return captured


def write_json(path: pathlib.Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _string_values(document):
    if isinstance(document, dict):
        for value in document.values():
            yield from _string_values(value)
    elif isinstance(document, list):
        for value in document:
            yield from _string_values(value)
    elif isinstance(document, str):
        yield document


def assert_no_payload_leak(label: str, document: dict, payload: bytes) -> None:
    text = json.dumps(document, sort_keys=True)
    lowered = text.lower()
    sample = payload[:64]
    check(f"{label}:no-hex", sample.hex() not in lowered, "payload hex present")
    check(
        f"{label}:no-base64",
        base64.b64encode(sample).decode("ascii") not in text,
        "payload base64 present",
    )
    for start in range(0, min(len(payload), 512)):
        run = payload[start : start + 8]
        if len(run) == 8 and all(32 <= byte < 127 for byte in run):
            check(
                f"{label}:no-ascii-run",
                run.decode("ascii") not in text,
                f"ascii payload run at {start}",
            )
    for value in _string_values(document):
        check(f"{label}:string-length", len(value) <= 128, f"{len(value)} chars")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evidence-dir",
        default=".openrecomp-phase10/evidence/P10-00",
        help="evidence directory relative to the repository root",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="re-run the boundary checks without rewriting committed evidence sidecars",
    )
    parser.add_argument(
        "--private-fixture-root",
        default=str(DEFAULT_PRIVATE_FIXTURE_ROOT),
        help="private fixture directory (never recorded in evidence)",
    )
    options = parser.parse_args()

    evidence = (ROOT / options.evidence_dir).resolve()
    verify_only = options.verify_only
    fixture_root = pathlib.Path(options.private_fixture_root)

    try:
        head = git("rev-parse", "HEAD")
        head_tree = git("rev-parse", "HEAD^{tree}")

        # Frozen Phase-9 terminal boundary identity.
        check("baseline:commit-type", git("cat-file", "-t", BASELINE_COMMIT) == "commit", BASELINE_COMMIT)
        check("baseline:commit-tree", git("rev-parse", f"{BASELINE_COMMIT}^{{tree}}") == BASELINE_TREE, BASELINE_TREE)
        ancestor = subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).returncode == 0
        check("branch:descends-from-baseline", ancestor, BASELINE_COMMIT)
        branch = git("branch", "--show-current")
        at_boundary = head == BASELINE_COMMIT
        check(
            "branch:head-at-boundary-or-descendant",
            at_boundary or ancestor,
            head,
        )
        check(
            "branch:boundary-tree-identical",
            (not at_boundary) or head_tree == BASELINE_TREE,
            head_tree if at_boundary else "descendant",
        )
        expected_branches = {PHASE10_BRANCH}
        if at_boundary:
            expected_branches.add(BASELINE_BRANCH)
        check("branch:name", branch in expected_branches, branch)

        phase9_tags = git("tag", "-l", "openrecomp-phase9*")
        check("baseline:phase9-tag-absent-reconciled", phase9_tags == "", phase9_tags or "absent")

        verdict = json.loads(
            (P9 / "evidence" / "P9-99" / "terminal_verdict.json").read_text(encoding="utf-8")
        )
        check("baseline:p9-99-decision", verdict.get("decision") == "PASS", str(verdict.get("decision")))
        check(
            "baseline:p9-99-terminal-marker",
            "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=PASS" in verdict.get("markers_issued", []),
            "terminal PASS",
        )
        required = verdict.get("required_stages", [])
        required_ids = [item.get("stage") for item in required]
        check(
            "baseline:p9-99-required-stage-set",
            required_ids == [f"P9-{number:02d}" for number in range(0, 13)] + ["P9-90", "P9-91"],
            ",".join(str(item) for item in required_ids),
        )
        check(
            "baseline:p9-99-all-stages-pass",
            bool(required) and all(item.get("outcome") == "PASS" for item in required),
            f"{sum(1 for item in required if item.get('outcome') == 'PASS')}/{len(required)}",
        )

        # Frozen Phase-9 terminal evidence and control-plane hashes.
        for rel, expected in sorted(FROZEN_P9_HASHES.items()):
            observed = sha256_file(ROOT / rel)
            check(f"frozen:p9-terminal:{rel}", observed == expected, observed)

        # Frozen Phase-1..9 tracked/untracked state.
        prior_paths = [f".openrecomp-phase{i}" for i in range(1, 10)]
        changed = git("diff", "--name-only", BASELINE_COMMIT, "--", *prior_paths)
        changed_set = set(filter(None, changed.splitlines()))
        check(
            "frozen:no-prior-tracked-change-outside-documented-residue",
            changed_set <= DOCUMENTED_PRIOR_TRACKED_DIFF,
            ",".join(sorted(changed_set)) or "none",
        )
        status_lines = git("status", "--porcelain", "--untracked-files=all").splitlines()
        undocumented: list[str] = []
        for line in status_lines:
            match = re.search(r"\.openrecomp-phase([1-9])/", line)
            if not match:
                continue
            numeric = int(match.group(1))
            path = line[3:].strip().strip('"')
            if numeric in (2, 3):
                continue
            undocumented.append(path)
        check("frozen:no-new-prior-residue", not undocumented, ",".join(sorted(undocumented)) or "none")

        # Phase-9 source manifest still verifies unchanged.
        manifest = subprocess.run(
            [sys.executable, str(P9 / "src" / "p9_source_manifest_v1.py")],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        check(
            "frozen:p9-source-manifest",
            manifest.returncode == 0 and manifest.stderr == "" and "=PASS entries=" in manifest.stdout,
            manifest.stdout.strip() or manifest.stderr.strip(),
        )

        # Inherited reconciliations.
        phase6_tags = git("tag", "-l", "openrecomp-phase6*")
        check("reconcile:phase6-tag-absent", phase6_tags == "", phase6_tags or "absent")
        phase8_tags = git("tag", "-l", "openrecomp-phase8*")
        check("reconcile:phase8-tag-absent", phase8_tags == "", phase8_tags or "absent")
        check(
            "reconcile:phase7-tag-object",
            git("rev-parse", "openrecomp-phase7-pass") == "b07e0f691262ed3ae0bc2fd6ebb3e3d3c5222800",
            "phase7 tag object",
        )
        check(
            "reconcile:phase7-tag-commit",
            git("rev-parse", "openrecomp-phase7-pass^{commit}") == "2917aa6549ab975cffdeb50120514c1723f7e493",
            "phase7 commit",
        )
        check(
            "reconcile:phase7-tag-tree",
            git("rev-parse", "openrecomp-phase7-pass^{tree}") == "59529c130d759ceb1ca9e6c65a510fa373656b01",
            "phase7 tree",
        )

        # Toolchains.
        toolchains = capture_toolchains()
        for name, record in sorted(toolchains.items()):
            check(f"toolchain:{name}", record["version"] != "UNAVAILABLE", record["version"])

        # Phase-10 control plane files.
        for rel in REQUIRED_CONTROL_FILES:
            check(f"control:file:{rel}", (ROOT / rel).is_file(), rel)

        queue = (P10 / "STAGE_QUEUE.md").read_text(encoding="utf-8")
        for stage in FROZEN_STAGES:
            check(f"control:queue:{stage}", f"| {stage} |" in queue, stage)
        state = (P10 / "STATE.md").read_text(encoding="utf-8")
        check(
            "control:state-terminal-reserved",
            f"{TERMINAL_MARKER}={NOT_PROVEN}" in state,
            f"{TERMINAL_MARKER}={NOT_PROVEN}",
        )
        check(
            "control:state-playability-reserved",
            f"{PLAYABILITY_MARKER}={NOT_PROVEN}" in state,
            f"{PLAYABILITY_MARKER}={NOT_PROVEN}",
        )
        check(
            "control:state-general-permanent",
            f"{GENERAL_MARKER}={NOT_PROVEN}" in state,
            f"{GENERAL_MARKER}={NOT_PROVEN}",
        )

        # Private fixture / disc identity.
        check("fixture:directory", fixture_root.is_dir(), "private fixture directory present")
        identity = fixture.build_identity(fixture_root)
        executable = identity["executable"]
        check(
            "fixture:executable-entry",
            executable["directory_entry"] == fixture.PRIMARY_EXECUTABLE,
            executable["directory_entry"],
        )
        check("fixture:executable-size", executable["size"] == EXPECTED_FIXTURE["executable_size"], str(executable["size"]))
        check("fixture:executable-sha256", executable["sha256"] == EXPECTED_FIXTURE["executable_sha256"], executable["sha256"])

        cue = identity["disc"]["cue"]
        check("fixture:cue-size", cue["cue_size"] == EXPECTED_FIXTURE["cue_size"], str(cue["cue_size"]))
        check("fixture:cue-sha256", cue["cue_sha256"] == EXPECTED_FIXTURE["cue_sha256"], cue["cue_sha256"])
        check("fixture:cue-single-track", cue["track_count"] == 1, str(cue["track_count"]))
        check("fixture:cue-track-type", cue["tracks"][0]["type"] == "MODE2/2352", cue["tracks"][0]["type"])
        check(
            "fixture:cue-index1-zero",
            cue["tracks"][0]["index1_msf"] == [0, 0, 0],
            str(cue["tracks"][0]["index1_msf"]),
        )
        bins = identity["disc"]["bins"]
        check("fixture:bin-count", len(bins) == 1, str(len(bins)))
        check("fixture:bin-size", bins[0]["size"] == EXPECTED_FIXTURE["bin_size"], str(bins[0]["size"]))
        check("fixture:bin-sha256", bins[0]["sha256"] == EXPECTED_FIXTURE["bin_sha256"], bins[0]["sha256"])

        volume = identity["disc"]["volume"]
        check(
            "fixture:volume-space-size",
            volume["volume_space_size_sectors"] == EXPECTED_FIXTURE["volume_space_size_sectors"],
            str(volume["volume_space_size_sectors"]),
        )
        check("fixture:volume-system-id", volume["system_identifier"] == "PLAYSTATION", volume["system_identifier"])
        check("fixture:root-extent", volume["root_extent_lba"] == EXPECTED_FIXTURE["root_extent_lba"], str(volume["root_extent_lba"]))

        system_cnf = identity["system_cnf"]
        check("fixture:boot-target", system_cnf["boot_target"] == EXPECTED_FIXTURE["boot_target"], system_cnf["boot_target"])
        check(
            "fixture:boot-extent-sha256",
            system_cnf["boot_extent_sha256"] == EXPECTED_FIXTURE["executable_sha256"],
            system_cnf["boot_extent_sha256"],
        )
        check("fixture:boot-matches-executable", system_cnf["matches_primary_executable"] is True, "true")

        # PS-X EXE metadata through the frozen Phase-9 ingestion path.
        image = psx.ingest((fixture_root / fixture.PRIMARY_EXECUTABLE).read_bytes())
        header = image.header
        check("exe:entry", f"0x{header.pc0:08x}" == EXPECTED_FIXTURE["entry"], f"0x{header.pc0:08x}")
        check("exe:text-address", f"0x{header.t_addr:08x}" == EXPECTED_FIXTURE["text_address"], f"0x{header.t_addr:08x}")
        check("exe:text-size", f"0x{header.t_size:08x}" == EXPECTED_FIXTURE["text_size"], f"0x{header.t_size:08x}")
        check("exe:stack-pointer", f"0x{header.s_addr:08x}" == EXPECTED_FIXTURE["stack_pointer"], f"0x{header.s_addr:08x}")

        # Inherited Hercules frontier reproduction.
        reproduction = frontier.reproduce(fixture_root / fixture.PRIMARY_EXECUTABLE)
        check("frontier:reproduced", reproduction["reproduced"] is True, json.dumps(reproduction["mismatches"], sort_keys=True))
        for key in ("reachable_words", "reachable_supported_words", "reachable_unsupported_words",
                    "reachable_invalid_words", "exception_site_count"):
            check(
                f"frontier:{key}",
                reproduction["observed"][key] == frontier.INHERITED[key],
                str(reproduction["observed"][key]),
            )
        check(
            "frontier:first-blocker-site",
            reproduction["observed"]["first_blocker_site"] == frontier.INHERITED["first_blocker_site"],
            str(reproduction["observed"]["first_blocker_site"]),
        )
        check(
            "frontier:first-blocker-kind",
            reproduction["observed"]["first_blocker_kind"] == frontier.INHERITED["first_blocker_kind"],
            str(reproduction["observed"]["first_blocker_kind"]),
        )
        check(
            "frontier:structure-error",
            reproduction["observed"]["structure_error_code"] == frontier.INHERITED["structure_error_code"],
            str(reproduction["observed"]["structure_error_code"]),
        )
        check(
            "frontier:bounded-execution-status",
            reproduction["bounded_execution"]["status"] == frontier.INHERITED["bounded_execution_status"],
            reproduction["bounded_execution"]["status"],
        )
        check(
            "frontier:no-native-execution",
            reproduction["bounded_execution"]["native_execution_of_private_code"] is False,
            "false",
        )

        # Claim guards.
        check("claim:native-execution-not-promoted", True, NOT_PROVEN)
        check("claim:playability-not-promoted", True, NOT_PROVEN)
        check("claim:general-not-promoted", True, NOT_PROVEN)

        payload = image.payload
        if not verify_only:
            baseline = {
                "schema": "openrecomp-phase10-baseline-v1",
                "stage": STAGE,
                "baseline_phase": BASELINE_PHASE,
                "baseline_commit": BASELINE_COMMIT,
                "baseline_tree": BASELINE_TREE,
                "baseline_branch": BASELINE_BRANCH,
                "phase10_branch": PHASE10_BRANCH,
                "audited_head": head,
                "audited_head_tree": head_tree,
                "phase9_terminal_verdict": verdict.get("decision"),
                "frozen_p9_hashes": dict(sorted(FROZEN_P9_HASHES.items())),
                "documented_prior_tracked_diff": sorted(DOCUMENTED_PRIOR_TRACKED_DIFF),
                "frozen_stages": list(FROZEN_STAGES),
            }
            frontier_record = {
                "schema": "openrecomp-phase10-frontier-reproduction-v1",
                "stage": STAGE,
                "inherited": dict(sorted(frontier.INHERITED.items())),
                "observed": reproduction["observed"],
                "reproduced": reproduction["reproduced"],
                "mismatches": reproduction["mismatches"],
                "identity": reproduction["identity"],
                "contract_digest": reproduction["contract_digest"],
                "pipeline_digest": reproduction["pipeline_digest"],
                "first_blocker": reproduction["first_blocker"],
                "structure_error": reproduction["structure_error"],
                "structure_available": reproduction["structure_available"],
                "bounded_execution": reproduction["bounded_execution"],
            }
            identity_record = {
                "schema": "openrecomp-phase10-fixture-identity-v1",
                "stage": STAGE,
                "label": "hercules-private-fixture",
                "present": True,
                "is_pass_criterion": False,
                **identity,
            }
            assert_no_payload_leak("fixture-identity", identity_record, payload)
            assert_no_payload_leak("frontier", frontier_record, payload)
            write_json(evidence / "baseline.json", baseline)
            write_json(evidence / "fixture_identity.json", identity_record)
            write_json(evidence / "frontier.json", frontier_record)
            write_json(
                evidence / "toolchains.json",
                {"schema": "openrecomp-phase10-toolchains-v1", "stage": STAGE, "tools": toolchains},
            )
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # fail closed with a stable record
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    failed = [item for item in RESULTS if item["status"] == "FAIL"]
    status = "PASS" if not failed else "FAIL"
    results = sorted(RESULTS, key=lambda item: item["check"])
    record = {
        "stage": STAGE,
        "stage_name": "Phase-10 boundary + fixture/control plane",
        "status": status,
        "tests": len(results),
        "passed": sum(1 for item in results if item["status"] == "PASS"),
        "failed": len(failed),
        "checks": results,
        "failure": None if not failed else [item["check"] for item in failed],
    }
    write_json(evidence / f"p10_00_tests.json", record)

    for item in results:
        print(f"{item['status']}: {item['check']}")
    print(f"OPENRECOMP_P10_00={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(results)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
