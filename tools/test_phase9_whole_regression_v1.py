#!/usr/bin/env python3
"""OpenRecomp Phase-9 whole-project regression gate (P9-90).

This is the expensive terminal gate. On one audited tree it verifies:

* the exact frozen Phase-8 terminal boundary identity and the pinned Phase-8
  terminal evidence;
* the frozen P8-90/P8-91/P8-99 record identities (re-verified after the live
  re-runs, so any frozen-evidence modification fails closed);
* the frozen Phase-3 module hashes and the Phase-8/Phase-9 source manifests;
* a live re-run of all thirteen completed Phase-9 official gates, each with
  byte-identical stdout to its committed official capture, redirected to
  scratch evidence so no committed Phase-9 evidence is modified;
* a live re-run of the frozen P8-90, P8-91 and P8-99 terminal gates, each with
  byte-identical stdout to its committed official capture (P8-90 itself
  re-runs the Phase-1 host gates, the reconstructed Phase-7 chain and all
  thirteen Phase-8 gates);
* an evidence snapshot proving no committed Phase-9 evidence file changed.

On success it emits::

    OPENRECOMP_P9_90=PASS
    OPENRECOMP_PHASE9_WHOLE_REGRESSION_V1=PASS tests=<count>
    OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN
    OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN
    OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN

Usage:

    python tools/test_phase9_whole_regression_v1.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
P8 = ROOT / ".openrecomp-phase8"
P9 = ROOT / ".openrecomp-phase9"

STAGE = "P9-90"
FEATURE_MARKER = "OPENRECOMP_PHASE9_WHOLE_REGRESSION_V1"
TERMINAL_MARKER = "OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF"
GENERAL_MARKER = "OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY"
PLAYABILITY_MARKER = "OPENRECOMP_PHASE9_HERCULES_PLAYABILITY"
NOT_PROVEN = "NOT_PROVEN"

BASELINE_COMMIT = "61136fc37cf0810e64241addd8f57a91872bc0af"
BASELINE_TREE = "f9262497b82fe0027c3b23432ba7bd8cbccdf433"
BRANCH = "phase8/mips32-end-to-end-native-v1"

FROZEN_P8_TERMINAL = {
    ".openrecomp-phase8/evidence/P8-99/RESULT.md": "b07c3ec76c591df7999599e0fa5f1f43f0a1854462b45da96bc8523b2cb04204",
    ".openrecomp-phase8/evidence/P8-99/terminal_verdict.json": "ffe1b89d1284435cbb9dd53318025ee052ad0fa58b1f8a304736a381712dc693",
    ".openrecomp-phase8/evidence/P8-99/verdict_record.json": "fa9d62c79ab6399981e1acedbedbd07a149daec2c6ea4bde1dc7aee3a7d52738",
    ".openrecomp-phase8/evidence/P8-99/p8_99_tests.json": "ff8ed0a79569b95810527b1a395ece4aec3b6eedba9054f704cd0dfd1bbd7f77",
    ".openrecomp-phase8/evidence/P8-99/official_runs.json": "459c5f397681e49cfb6830d8f1687e5923120bb061864f8319a0c8eb15dc333d",
    ".openrecomp-phase8/STATE.md": "ef56426db4f17deef78635a35ea8074ef6c7a5f17926cd18f4687f6bea63bcd4",
    ".openrecomp-phase8/STAGE_QUEUE.md": "5f1dc76669db00f766afcb55fa5d943b5b3498333cfc9cc8b6e63971ceeb1fbf",
    ".openrecomp-phase8/HANDOFF.md": "01abbc46c810b9da697932d34e3be7b18acab88b54a630ed777ab96f4da60c70",
    ".openrecomp-phase8/SOURCE_SHA256SUMS.txt": "5ac27eb1f23ae412a14e94c62a80f811b7a1670e53b404356b49595d1f9f4221",
    ".openrecomp-phase8/CONTROL_POLICY.md": "50bd69203c78f8ff45439f133a0b4dd01f54e1dcf4175a1886a49d0effff20b7",
    ".openrecomp-phase8/SCOPE.md": "82bc03b864b85509c7eb23a5e1aea124edc431f94d412064fa4d076c6b349ca1",
    ".openrecomp-phase8/ACCELERATION_POLICY.md": "02a10bc6aaa9c2d4accd8d9e5eab30c6e608c09d7090148e180dc4babc36bf95",
    ".openrecomp-phase8/EVIDENCE_SCHEMA.md": "4c7b4473972bed35bbdc0e6df54d642886b6697112361f2a8f04a6a659b86acf",
    ".openrecomp-phase8/FIXTURE_POLICY.md": "723e5794c836371ece147af53039a4134b788c1ea9ee9fc5d52a91edc330f879",
    ".openrecomp-phase8/evidence/README.md": "7167bc52738c562ff84e48c58f4381dc858a972cb7044f1cb850d4c5302ccd27",
}

FROZEN_P8_RECORDS = {
    ".openrecomp-phase8/evidence/P8-90/RESULT.md": "dfca91b11cf89cc3247e274ab45390975c305cb28f9f18f46e7b2ac220a79454",
    ".openrecomp-phase8/evidence/P8-90/p8_90_tests.json": "782597be2f9bd4b4a834d55094a3304616675857b88e4b84abc509bbdd658912",
    ".openrecomp-phase8/evidence/P8-90/whole_regression.json": "b97e35c69f649d446c01d1c833e7e7da2a8886a37d58bf9249b66189f4b5f5e7",
    ".openrecomp-phase8/evidence/P8-90/official_runs.json": "bc14415c4c3bfa3562507357bb9ab4e32c9ae496b46d3e4e707d520560fb1ba6",
    ".openrecomp-phase8/evidence/P8-91/RESULT.md": "b49c7328ddeb2005dbc766a2835dce3242140044b44bf45b7ec06f2934db67c1",
    ".openrecomp-phase8/evidence/P8-91/evidence_index.json": "9133c838980091d5b72775fed0678e5895cf90c858eb18549de5ced10c7772f7",
    ".openrecomp-phase8/evidence/P8-91/claim_ledger.json": "a8eee1edcde541659a24269dfae4f29bfecce63966cd030ce6f024a4173ff2e3",
    ".openrecomp-phase8/evidence/P8-91/p8_91_tests.json": "364c9ff5062400cc68d3f1680c7b54b0db7b430b31f840c55fe9fd3d44ceea87",
    ".openrecomp-phase8/evidence/P8-91/official_runs.json": "86859d8c6dff9b950104bd83917708e7ff943e92069b259082966bcdf2f4c44e",
    ".openrecomp-phase8/evidence/P8-99/RESULT.md": "b07c3ec76c591df7999599e0fa5f1f43f0a1854462b45da96bc8523b2cb04204",
    ".openrecomp-phase8/evidence/P8-99/official_runs.json": "459c5f397681e49cfb6830d8f1687e5923120bb061864f8319a0c8eb15dc333d",
}

FROZEN_P3_MODULES = {
    ".openrecomp-phase3/src/p3_code_frontier_v1.py": "f02c4e7507087e052f1a899ef67d87f8ed82ecc4954e8214ccea922a2e361d71",
    ".openrecomp-phase3/src/p3_decode_mips32_v1.py": "c808a23afad5771a42f3f7eee9450b84fc6131d0416961a3ed8e78a9f5126b0b",
    ".openrecomp-phase8/src/p8_structure_v1.py": "24109660cfa1876b9ffabe141374d1a1b26c74d6fc0f68260bfb440617077a1b",
}

PHASE9_GATES = (
    ("P9-00", "tools/test_phase9_boundary_v1.py", ["--verify-only"], "OPENRECOMP_P9_00=PASS"),
    ("P9-01", "tools/test_phase9_ingestion_v1.py", [], "OPENRECOMP_P9_01=PASS"),
    ("P9-02", "tools/test_phase9_memory_map_v1.py", [], "OPENRECOMP_P9_02=PASS"),
    ("P9-03", "tools/test_phase9_pipeline_v1.py", [], "OPENRECOMP_P9_03=PASS"),
    ("P9-04", "tools/test_phase9_translation_v1.py", [], "OPENRECOMP_P9_04=PASS"),
    ("P9-05", "tools/test_phase9_bios_v1.py", [], "OPENRECOMP_P9_05=PASS"),
    ("P9-06", "tools/test_phase9_gpu_v1.py", [], "OPENRECOMP_P9_06=PASS"),
    ("P9-07", "tools/test_phase9_input_timer_v1.py", [], "OPENRECOMP_P9_07=PASS"),
    ("P9-08", "tools/test_phase9_spu_v1.py", [], "OPENRECOMP_P9_08=PASS"),
    ("P9-09", "tools/test_phase9_cdrom_v1.py", [], "OPENRECOMP_P9_09=PASS"),
    ("P9-10", "tools/test_phase9_native_v1.py", [], "OPENRECOMP_P9_10=PASS"),
    ("P9-11", "tools/test_phase9_hercules_v1.py", [], "OPENRECOMP_P9_11=PASS"),
    ("P9-12", "tools/test_phase9_hardening_v1.py", [], "OPENRECOMP_P9_12=PASS"),
)

P8_AUDIT_GATES = (
    ("P8-90", "tools/test_phase8_whole_regression_v1.py", "OPENRECOMP_P8_90=PASS"),
    ("P8-91", "tools/test_phase8_evidence_index_v1.py", "OPENRECOMP_P8_91=PASS"),
    ("P8-99", "tools/test_phase8_final_verdict_v1.py", "OPENRECOMP_P8_99=PASS"),
)

DOCUMENTED_PRIOR_TRACKED_DIFF = {
    ".openrecomp-phase3/evidence/P3-00/p3_00_tests.json",
    ".openrecomp-phase3/evidence/P3-00/residue_manifest.txt",
}

SCRATCH = P9 / "build" / "P9-90" / "scratch"
EVIDENCE_DIR = P9 / "evidence" / "P9-90"

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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def snapshot_evidence() -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted((P9 / "evidence").rglob("*")):
        if path.is_file():
            snapshot[path.relative_to(ROOT).as_posix()] = sha256_file(path)
    return snapshot


def run_gate(script: str, extra: list[str]) -> tuple[int, bytes, bytes]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / script), *extra],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode, completed.stdout, completed.stderr


def tests_from_stdout(stdout: bytes) -> int:
    for line in stdout.decode("utf-8", "replace").splitlines():
        if "=PASS tests=" in line:
            return int(line.rsplit("tests=", 1)[1])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", default=".openrecomp-phase9/evidence/P9-90")
    options = parser.parse_args()
    evidence = (ROOT / options.evidence_dir).resolve()

    try:
        # --- frozen baseline identity ---------------------------------------
        check("baseline:commit-tree", git("rev-parse", f"{BASELINE_COMMIT}^{{tree}}") == BASELINE_TREE, BASELINE_TREE)
        check("branch:name", git("branch", "--show-current") == BRANCH, BRANCH)
        ancestor = subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).returncode == 0
        check("branch:descends-from-baseline", ancestor, BASELINE_COMMIT)

        # --- frozen terminal evidence and records ---------------------------
        for rel, digest in sorted(FROZEN_P8_TERMINAL.items()):
            check(f"frozen:p8-terminal:{rel}", sha256_file(ROOT / rel) == digest, digest)
        for rel, digest in sorted(FROZEN_P8_RECORDS.items()):
            if digest is None:
                continue
            check(f"frozen:p8-record:{rel}", sha256_file(ROOT / rel) == digest, digest)
        for rel, digest in sorted(FROZEN_P3_MODULES.items()):
            check(f"frozen:module:{rel}", sha256_file(ROOT / rel) == digest, digest)

        changed = git("diff", "--name-only", BASELINE_COMMIT, "--", *[f".openrecomp-phase{i}" for i in range(1, 9)])
        changed_set = set(filter(None, changed.splitlines()))
        check("frozen:no-undocumented-prior-diff", changed_set <= DOCUMENTED_PRIOR_TRACKED_DIFF, ",".join(sorted(changed_set)) or "none")

        manifest9 = subprocess.run([sys.executable, str(P9 / "src" / "p9_source_manifest_v1.py")], capture_output=True, text=True, encoding="utf-8")
        check("manifest:p9", manifest9.returncode == 0 and "=PASS entries=" in manifest9.stdout, manifest9.stdout.strip())
        manifest8 = subprocess.run([sys.executable, str(P8 / "src" / "p8_source_manifest_v1.py")], capture_output=True, text=True, encoding="utf-8")
        check("manifest:p8", manifest8.returncode == 0 and "=PASS entries=" in manifest8.stdout, manifest8.stdout.strip())

        # --- committed Phase-9 stage records ---------------------------------
        for stage, script, extra, marker in PHASE9_GATES:
            runs_path = P9 / "evidence" / stage / "official_runs.json"
            check(f"record:{stage}:official-runs", runs_path.is_file(), stage)
            runs = json.loads(runs_path.read_text(encoding="utf-8"))
            check(f"record:{stage}:two-runs-identical", runs["identical_raw"] and runs["identical_lf"], "identical")
            check(f"record:{stage}:stderr-empty", runs["stderr_empty_both"], "empty")
            check(f"record:{stage}:exit-zero", runs["returncode_zero_both"], "zero")
            check(f"record:{stage}:markers", runs["markers_present_both"], "markers")
            tests_path = P9 / "evidence" / stage / f"p9_{stage.split('-')[1]}_tests.json"
            check(f"record:{stage}:tests-json", tests_path.is_file(), stage)
            tests = json.loads(tests_path.read_text(encoding="utf-8"))
            check(f"record:{stage}:status", tests["status"] == "PASS" and tests["failed"] == 0, tests["status"])

        # --- live Phase-9 gate re-runs ---------------------------------------
        if SCRATCH.exists():
            shutil.rmtree(SCRATCH)
        SCRATCH.mkdir(parents=True, exist_ok=True)
        evidence_before = snapshot_evidence()
        phase9_counts: list[dict] = []
        for stage, script, extra, marker in PHASE9_GATES:
            runs = json.loads((P9 / "evidence" / stage / "official_runs.json").read_text(encoding="utf-8"))
            expected_stdout = runs["runs"][0]["stdout_sha256_raw"]
            target = SCRATCH / stage
            target.mkdir(parents=True, exist_ok=True)
            args = list(extra) + ["--evidence-dir", str(target.relative_to(ROOT).as_posix())]
            rc, stdout, stderr = run_gate(script, args)
            check(f"p9:{stage}:exit", rc == 0, str(rc))
            check(f"p9:{stage}:stderr", stderr == b"", stderr[:120].decode("ascii", "replace"))
            check(f"p9:{stage}:marker", marker.encode("utf-8") in stdout, marker)
            observed = hashlib.sha256(stdout).hexdigest()
            check(f"p9:{stage}:stdout-identity", observed == expected_stdout, observed)
            phase9_counts.append({"stage": stage, "tests": tests_from_stdout(stdout), "stdout_sha256_raw": observed})

        # --- frozen Phase-8 terminal audit re-runs ---------------------------
        # The frozen P8-91 gate rewrites its committed index from the current
        # evidence; its committed index predates the P8-99 post-verdict
        # stabilization and therefore records stale P8-99 hashes. Frozen
        # evidence is snapshotted and restored so the re-run cannot modify it.
        frozen_snapshot: dict[pathlib.Path, bytes] = {}
        for directory in (P8 / "evidence" / "P8-90", P8 / "evidence" / "P8-91", P8 / "evidence" / "P8-99"):
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    frozen_snapshot[path] = path.read_bytes()

        phase8_audit: list[dict] = []
        for stage, script, marker in P8_AUDIT_GATES:
            runs = json.loads((P8 / "evidence" / stage / "official_runs.json").read_text(encoding="utf-8"))
            expected_stdout = runs["runs"][0]["stdout_sha256_raw"]
            rc, stdout, stderr = run_gate(script, [])
            check(f"p8:{stage}:exit", rc == 0, str(rc))
            check(f"p8:{stage}:stderr", stderr == b"", stderr[:120].decode("ascii", "replace"))
            check(f"p8:{stage}:marker", marker.encode("utf-8") in stdout, marker)
            observed = hashlib.sha256(stdout).hexdigest()
            check(f"p8:{stage}:stdout-identity", observed == expected_stdout, observed)
            phase8_audit.append({"stage": stage, "tests": tests_from_stdout(stdout), "stdout_sha256_raw": observed})

        restored: list[str] = []
        for path, data in sorted(frozen_snapshot.items(), key=lambda item: str(item[0])):
            if path.read_bytes() != data:
                path.write_bytes(data)
                restored.append(path.relative_to(ROOT).as_posix())
        check("post-run:frozen-evidence-restored", all(sha256_file(ROOT / rel) == digest for rel, digest in FROZEN_P8_RECORDS.items() if digest is not None), ",".join(restored) or "none")

        # --- frozen evidence unchanged after the live re-runs ----------------
        for rel, digest in sorted(FROZEN_P8_RECORDS.items()):
            if digest is None:
                continue
            check(f"post-run:p8-record:{rel}", sha256_file(ROOT / rel) == digest, digest)
        for rel, digest in sorted(FROZEN_P8_TERMINAL.items()):
            check(f"post-run:p8-terminal:{rel}", sha256_file(ROOT / rel) == digest, digest)
        evidence_after = snapshot_evidence()
        changed_evidence = sorted(
            set(evidence_before) ^ set(evidence_after)
            | {path for path in evidence_before if evidence_before[path] != evidence_after.get(path)}
        )
        check("post-run:p9-evidence-unchanged", not changed_evidence, ",".join(changed_evidence) or "none")

        # --- counts ----------------------------------------------------------
        whole = json.loads((P8 / "evidence" / "P8-90" / "whole_regression.json").read_text(encoding="utf-8"))
        p8_90_record = json.loads((P8 / "evidence" / "P8-90" / "p8_90_tests.json").read_text(encoding="utf-8"))
        total = (
            sum(item["tests"] for item in phase9_counts)
            + sum(item["tests"] for item in phase8_audit)
            + int(p8_90_record["tests"])
            + int(whole["total_reverified_tests"])
        )
        check("counts:phase9-tests", all(item["tests"] > 0 for item in phase9_counts), str(sum(item["tests"] for item in phase9_counts)))
        check("counts:p8-90-tests", p8_90_record["tests"] == 215, str(p8_90_record["tests"]))
        check("counts:p8-90-reverified", whole["total_reverified_tests"] == 1463, str(whole["total_reverified_tests"]))

        write_payload = {
            "stage": STAGE,
            "decision": "PASS",
            "phase9_stage_gates": phase9_counts,
            "phase8_terminal_audits": phase8_audit,
            "phase8_90": {
                "tests": p8_90_record["tests"],
                "total_reverified_tests": whole["total_reverified_tests"],
                "phase7_gates": len(whole["phase7_stage_gates"]),
                "phase8_gates": len(whole["phase8_stage_gates"]),
                "stdout_sha256_raw": hashlib.sha256((P8 / "evidence" / "P8-90" / "run1.txt").read_bytes()).hexdigest(),
            },
            "total_reverified_tests": total,
            "frozen_evidence_restored": restored,
            "markers": {
                "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
                "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
                "playability": f"{PLAYABILITY_MARKER}={NOT_PROVEN}",
            },
        }
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        (EVIDENCE_DIR / "whole_regression.json").write_bytes(
            (json.dumps(write_payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        )
    except AssertionError as exc:
        RESULTS.append({"check": "gate:assertion", "status": "FAIL", "detail": str(exc)})
    except Exception as exc:  # stable fail-closed boundary
        RESULTS.append({"check": "gate:exception", "status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"})

    status = "PASS" if all(item["status"] == "PASS" for item in RESULTS) else "FAIL"
    record = {
        "stage": STAGE,
        "stage_name": "Phase-9 whole-project regression",
        "status": status,
        "tests": len(RESULTS),
        "passed": sum(1 for item in RESULTS if item["status"] == "PASS"),
        "failed": sum(1 for item in RESULTS if item["status"] != "PASS"),
        "checks": RESULTS,
        "failure": None if status == "PASS" else [item for item in RESULTS if item["status"] != "PASS"],
        "markers": {
            "stage": f"OPENRECOMP_P9_90={status}",
            "gate": f"{FEATURE_MARKER}={status} tests={len(RESULTS)}",
            "terminal": f"{TERMINAL_MARKER}={NOT_PROVEN}",
            "general": f"{GENERAL_MARKER}={NOT_PROVEN}",
            "playability": f"{PLAYABILITY_MARKER}={NOT_PROVEN}",
        },
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (EVIDENCE_DIR / "p9_90_tests.json").write_bytes(
        (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )

    for item in RESULTS:
        if item["status"] != "PASS":
            print(f"FAIL: {item['check']} :: {item.get('detail', '')}")
    print(f"OPENRECOMP_P9_90={status}")
    print(f"{FEATURE_MARKER}={status} tests={len(RESULTS)}")
    print(f"{TERMINAL_MARKER}={NOT_PROVEN}")
    print(f"{GENERAL_MARKER}={NOT_PROVEN}")
    print(f"{PLAYABILITY_MARKER}={NOT_PROVEN}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
