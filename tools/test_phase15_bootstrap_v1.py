#!/usr/bin/env python3
"""Deterministic P15-00 Phase-15 bootstrap / frozen-baseline gate.

Verifies the frozen Phase-14 ancestry (commit + tree), the canonical frozen
Phase-14 source integrity, the Phase-15 control-plane presence, and records the
non-reconstructive baseline identities (fixture metadata, reconnaissance
digests, branch/HEAD). No private payload bytes are recorded.
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for extra in ("", ".openrecomp-phase15/src"):
    sys.path.insert(0, str(ROOT / extra) if extra else str(ROOT))

from p15_gate_v1 import run_stage, write_json  # noqa: E402

STAGE = "P15-00"

PHASE14_BASE_COMMIT = "830be0f7be998061e8d442134cfae511d5dd8c62"
PHASE14_BASE_TREE = "3b5b998dacc60eff88258509bdb5cc548b8b1401"

FIXTURE_ROOT = ROOT.parents[1] / "fixtures" / "psx" / "hercules"
PRIMARY_EXECUTABLE = "SLUS_005.29"

RECON_ROOT = ROOT.parents[1] / "reconnaissance"
RECON_DIRS = (
    "phase15-istat-imask-live-contract-v1",
    "phase15-rootcounter-gpustat-live-v1",
    "phase15-init-proof-boundary-v1",
)
RECON_FILES = ("PHASE15_PREPRODUCTION_MMIO_RECON_CAMPAIGN_V1_SUMMARY.md",)

CONTROL_FILES = (
    "CONTROL_POLICY.md",
    "SCOPE.md",
    "STAGE_QUEUE.md",
    "EVIDENCE_SCHEMA.md",
    "FIXTURE_POLICY.md",
    "STATE.md",
    "HANDOFF.md",
)

REQUIRED_DIRS = ("src", "runtime", "evidence", "build", "scratch")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True).stdout.strip()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_digest(paths: tuple[pathlib.Path, ...]) -> str:
    """A deterministic digest over sorted (relative path, content digest) pairs."""
    digest = hashlib.sha256()
    entries: list[tuple[str, str]] = []
    for base in paths:
        if base.is_file():
            entries.append((base.name, sha256_file(base)))
            continue
        for item in sorted(base.rglob("*")):
            if item.is_file():
                entries.append((f"{base.name}/{item.relative_to(base).as_posix()}",
                                sha256_file(item)))
    for relative, content in sorted(entries):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def root_manifest_audit() -> dict[str, object]:
    """Audit the frozen repository-root manifest without mutating its known gap."""
    manifest = ROOT / "SOURCE_SHA256SUMS.txt"
    missing: list[str] = []
    mismatched: list[str] = []
    checked = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        recorded, relative = line.split(" *", 1)
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        checked += 1
        if sha256_file(path) != recorded:
            mismatched.append(relative)
    return {
        "manifest_sha256": sha256_file(manifest),
        "checked_entries": checked,
        "missing_entries": sorted(missing),
        "mismatched_entries": sorted(mismatched),
        "authority": ".openrecomp-phase14/SOURCE_SHA256SUMS.txt",
        "classification": "INHERITED_FROZEN_ROOT_MANIFEST_GAP",
    }


def body(gate, evidence: pathlib.Path, root: pathlib.Path) -> None:
    # --- frozen Phase-14 ancestry ---------------------------------------------
    gate.check("ancestry:phase14-base",
               subprocess.run(["git", "merge-base", "--is-ancestor",
                               PHASE14_BASE_COMMIT, "HEAD"], cwd=str(root),
                              capture_output=True).returncode == 0,
               "830be0f7 is an ancestor of HEAD")
    gate.check("ancestry:phase14-tree",
               git("rev-parse", f"{PHASE14_BASE_COMMIT}^{{tree}}") == PHASE14_BASE_TREE,
               git("rev-parse", f"{PHASE14_BASE_COMMIT}^{{tree}}"))
    changed = git("diff", "--name-only", f"{PHASE14_BASE_COMMIT}..HEAD", "--",
                  ".openrecomp-phase14")
    gate.check("ancestry:phase14-unmodified", changed == "", changed)

    # The repository-root manifest has one frozen historical entry for a file
    # already absent at the Phase-14 base. Preserve and disclose that inherited
    # gap; the canonical Phase-14 manifest below remains the source authority.
    root_manifest = root_manifest_audit()
    expected_missing = ["tools/test_build_package_reproducibility_v1.py"]
    gate.check("integrity:root-manifest-frozen",
               git("rev-parse", f"{PHASE14_BASE_COMMIT}:SOURCE_SHA256SUMS.txt")
               == git("rev-parse", "HEAD:SOURCE_SHA256SUMS.txt"),
               "frozen blob unchanged")
    gate.check("integrity:root-manifest-existing-entries",
               root_manifest["mismatched_entries"] == [],
               "all present entries match")
    gate.check("integrity:root-manifest-known-gap",
               root_manifest["missing_entries"] == expected_missing,
               ",".join(root_manifest["missing_entries"]))
    absent_at_base = subprocess.run(
        ["git", "cat-file", "-e",
         f"{PHASE14_BASE_COMMIT}:{expected_missing[0]}"],
        cwd=str(root), capture_output=True,
    ).returncode != 0
    gate.check("integrity:root-manifest-gap-inherited", absent_at_base,
               "entry absent at frozen base")

    # --- canonical frozen Phase-14 source integrity ---------------------------
    integrity = subprocess.run(
        [sys.executable, str(root / ".openrecomp-phase15" / "src" / "p15_frozen_phase14_integrity_v1.py")],
        cwd=str(root), capture_output=True, text=True)
    gate.check("integrity:phase14-sources", integrity.returncode == 0,
               integrity.stdout.strip() or integrity.stderr.strip())
    boundary = subprocess.run(
        [sys.executable, str(root / ".openrecomp-phase15" / "src" / "p15_frozen_phase14_boundary_v1.py")],
        cwd=str(root), capture_output=True, text=True)
    gate.check("integrity:phase14-boundary", boundary.returncode == 0,
               boundary.stdout.strip() or boundary.stderr.strip())

    # --- control plane presence ------------------------------------------------
    for name in CONTROL_FILES:
        gate.check(f"control:{name}", (root / ".openrecomp-phase15" / name).is_file(),
                   "present")
    for name in REQUIRED_DIRS:
        gate.check(f"dir:{name}", (root / ".openrecomp-phase15" / name).is_dir(),
                   "present")

    # --- fixture identity (non-reconstructive metadata only) -------------------
    primary = FIXTURE_ROOT / PRIMARY_EXECUTABLE
    gate.check("fixture:primary-present", primary.is_file(), "present")
    fixture_primary_sha256 = sha256_file(primary) if primary.is_file() else ""
    fixture_bin = FIXTURE_ROOT / "Disney's Hercules Action Game (USA).bin"
    fixture_cue = FIXTURE_ROOT / "Disney's Hercules Action Game (USA).cue"
    fixture = {
        "primary_executable": PRIMARY_EXECUTABLE,
        "primary_sha256": fixture_primary_sha256,
        "primary_size": primary.stat().st_size if primary.is_file() else 0,
        "disc_bin_size": fixture_bin.stat().st_size if fixture_bin.is_file() else 0,
        "cue_present": fixture_cue.is_file(),
    }

    # --- reconnaissance identity (read-only) -----------------------------------
    recon_paths = tuple(RECON_ROOT / name for name in RECON_DIRS) + \
        tuple(RECON_ROOT / name for name in RECON_FILES)
    gate.check("recon:present", all(path.exists() for path in recon_paths),
               "recon present")
    recon_digest = directory_digest(tuple(path for path in recon_paths if path.exists()))

    baseline = {
        "schema": "openrecomp-phase15-baseline-v1",
        "stage": STAGE,
        "branch": git("branch", "--show-current"),
        "head": git("rev-parse", "HEAD"),
        "phase14_base_commit": PHASE14_BASE_COMMIT,
        "phase14_base_tree": PHASE14_BASE_TREE,
        "phase14_worktree_clean": git("status", "--porcelain", "--",
                                      ".openrecomp-phase14") == "",
        "fixture": fixture,
        "recon_digest": recon_digest,
        "frozen_phase14_sources": integrity.stdout.strip().splitlines(),
        "frozen_phase14_boundary": boundary.stdout.strip().splitlines(),
        "repository_root_source_manifest": root_manifest,
        "third_party_code_imported": "NO",
        "private_fixture_bytes_recorded": "NO",
    }
    write_json(evidence / "baseline.json", baseline)
    write_json(evidence / "RESULT.json", {
        "schema": "openrecomp-phase15-result-v1", "stage": STAGE, "status": "PASS",
        "markers": {"OPENRECOMP_P15_00": "PASS"},
        "next_stage": "P15-01",
    })
    gate.mark("OPENRECOMP_P15_00")


if __name__ == "__main__":
    raise SystemExit(run_stage(STAGE, body, ".openrecomp-phase15/evidence/P15-00"))
