#!/usr/bin/env python3
"""Verify or prepare the frozen Phase-2 untracked verification context.

The 28 paths are taken from the frozen Phase-3 and Phase-4 boundary gates.
Bytes come only from the pinned Phase-2 Git tree, never from the ambient
Phase-11 worktree. Preparation creates absent, untracked files with exclusive
creation in the exact isolated Phase-10 checkout; verification is read-only.

It also restores the audited working-tree bytes of clean tracked text files
whose line endings a Windows checkout normalized (``* text=auto`` without an
``eol=lf`` rule): each such file is re-materialized from its own Git blob,
which keeps every frozen manifest and the working tree Git-clean. A genuinely
modified tracked file is never touched.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKOUT = ROOT.parent / "p11-90-phase10-regression"
SOURCE_COMMIT = "b935699991bdcbea518e5f6fbbd69ecb45bc12cf"
SOURCE_TREE = "e84ed211a5abac3dfa738cdca48aadddf15ba6ee"
TARGET_BRANCH = "phase10/ps1-commercial-game-native-v1"
TARGET_COMMIT = "8961682aa36e14db979e8e8dbe88e04fa2b4c87a"
TARGET_TREE = "4a58d9238d76a490560c588bb470fd9e6a58cafe"
SCRIPT_PATH = "tools/test_build_package_reproducibility_v1.py"
SCRIPT_BLOB = "08e21e6b497ada6944a1c8f9fa1017857a40c7eb"
SCRIPT_SHA256 = "2b9b09386c6f530f41b4cfe3b8d9dec868ae858603e5b0bc54ae8f5c37691085"
AGGREGATE_SHA256 = "40e4f23a35f40c5d25da630467d46f5e8ad8409a40efff8412892217447a8349"

# Frozen external toolchain dependency of the Phase-8/Phase-10 boundary.
ZIG_REL = ".openrecomp-phase3/tools/zig"
ZIG_VERSION = "0.13.0"
ZIG_EXE_SHA256 = "2e44af5bbf7a72ef8cbdae370284687c95d65a19affa469d2ad0364d905b8e84"
ZIG_ARCHIVE_SHA256 = "d859994725ef9402381e557c60bb57497215682e355204d754ee3df75ee3c158"


def git(*args: str, cwd: pathlib.Path = ROOT, data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", *args], cwd=cwd, input=data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0 or result.stderr:
        raise ValueError(f"Git verification failed: {' '.join(args[:3])}")
    return result.stdout


def git_text(*args: str, cwd: pathlib.Path = ROOT) -> str:
    return git(*args, cwd=cwd).decode("utf-8").strip()


def frozen_paths(gate: str) -> tuple[str, ...]:
    tree = ast.parse((ROOT / gate).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "FROZEN_UNTRACKED_FILES"
            for target in node.targets
        ):
            paths = ast.literal_eval(node.value)
            if not isinstance(paths, tuple) or not all(
                isinstance(path, str) for path in paths
            ):
                raise ValueError(f"invalid frozen path tuple in {gate}")
            return paths
    raise ValueError(f"frozen path tuple missing in {gate}")


def source_blobs(paths: tuple[str, ...]) -> dict[str, str]:
    raw = git("ls-tree", "-r", "-z", SOURCE_COMMIT, "--", *paths)
    entries: dict[str, str] = {}
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, blob = metadata.decode("ascii").split()
        path = raw_path.decode("utf-8")
        if mode != "100644" or kind != "blob" or path in entries:
            raise ValueError(f"invalid Phase-2 tree entry: {path}")
        entries[path] = blob
    if set(entries) != set(paths):
        raise ValueError("historical Phase-2 tree does not contain all 28 exact paths")
    return entries


def verify_authorities(paths: tuple[str, ...]) -> None:
    if len(paths) != 28 or len(set(paths)) != len(paths):
        raise ValueError("frozen verification context is not exactly 28 unique files")
    if paths != frozen_paths("tools/test_phase4_boundary_v1.py"):
        raise ValueError("frozen Phase-3 and Phase-4 path tuples differ")
    for path in paths:
        candidate = pathlib.PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts or "\\" in path:
            raise ValueError(f"unsafe frozen path: {path}")
    if git_text("rev-parse", f"{SOURCE_COMMIT}^{{tree}}") != SOURCE_TREE:
        raise ValueError("historical Phase-2 tree identity differs")
    if git_text("branch", "--show-current", cwd=CHECKOUT) != TARGET_BRANCH:
        raise ValueError("isolated checkout branch differs")
    if git_text("rev-parse", "HEAD", cwd=CHECKOUT) != TARGET_COMMIT:
        raise ValueError("isolated checkout commit differs")
    if git_text("rev-parse", "HEAD^{tree}", cwd=CHECKOUT) != TARGET_TREE:
        raise ValueError("isolated checkout tree differs")
    if git_text("status", "--porcelain", "--untracked-files=no", cwd=CHECKOUT):
        raise ValueError("isolated checkout has tracked modifications")
    if git("ls-files", "-z", "--", *paths, cwd=CHECKOUT):
        raise ValueError("a frozen verification-context path is tracked")
    manifest = (ROOT / "SOURCE_SHA256SUMS.txt").read_text(encoding="utf-8")
    if f"{SCRIPT_SHA256} *{SCRIPT_PATH}" not in manifest.splitlines():
        raise ValueError("root manifest does not pin the expected script SHA-256")


def inspect_blobs(paths: tuple[str, ...], blobs: dict[str, str]) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    records: list[dict[str, object]] = []
    data_by_path: dict[str, bytes] = {}
    lines: list[str] = []
    for path in sorted(paths):
        blob = blobs[path]
        data = git("cat-file", "blob", blob)
        if git("hash-object", "--stdin", data=data).decode("ascii").strip() != blob:
            raise ValueError(f"blob integrity mismatch: {path}")
        sha256 = hashlib.sha256(data).hexdigest()
        if path == SCRIPT_PATH and (blob != SCRIPT_BLOB or sha256 != SCRIPT_SHA256):
            raise ValueError("reproducibility script blob or root-manifest hash differs")
        records.append({"path": path, "git_blob": blob, "sha256": sha256, "bytes": len(data)})
        data_by_path[path] = data
        lines.append(f"{sha256}  {path}")
    aggregate = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
    if aggregate != AGGREGATE_SHA256:
        raise ValueError("frozen aggregate residue digest differs")
    return records, data_by_path


def tracked_clean_text() -> list[tuple[str, str, str]]:
    """Return clean tracked LF text files as (path, worktree_eol, blob).

    Only tracked files whose index EOL is LF and whose normalized diff is empty
    are considered; a genuinely modified file is excluded and never touched.
    All Git queries are scoped to the isolated checkout, never to the ambient
    Phase-11 worktree. Two Git calls total, so this stays fast.
    """
    dirty = set(filter(
        None, git_text("diff", "--name-only", "HEAD", cwd=CHECKOUT).splitlines()
    ))
    blobs: dict[str, str] = {}
    for line in git_text("ls-files", "-s", cwd=CHECKOUT).splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        tokens = meta.split()
        if len(tokens) >= 2:
            blobs[path] = tokens[1]
    found: list[tuple[str, str, str]] = []
    for line in git_text("ls-files", "--eol", cwd=CHECKOUT).splitlines():
        if "\t" not in line:
            continue
        head, path = line.rsplit("\t", 1)
        tokens = head.split()
        if len(tokens) < 2 or not tokens[0].startswith("i/") or not tokens[1].startswith("w/"):
            continue
        index_eol = tokens[0].split("/", 1)[1]
        work_eol = tokens[1].split("/", 1)[1]
        if index_eol == "lf" and path not in dirty and path in blobs:
            found.append((path, work_eol, blobs[path]))
    return found


def refresh_index_stat(paths: list[str]) -> None:
    """Refresh the index stat cache for restored paths without staging content.

    ``git add`` re-records the stat cache; because the working bytes already
    equal the Git blob, it stages no content change, which is asserted. Running
    under ``core.autocrlf=false`` avoids the harmless LF/CRLF conversion
    warnings.
    """
    if not paths:
        return
    result = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "add", "--", *paths],
        cwd=CHECKOUT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise ValueError("unable to refresh the isolated index stat cache")
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", *paths],
        cwd=CHECKOUT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8",
    )
    if staged.returncode != 0 or staged.stdout.strip():
        raise ValueError("tracked restoration would stage content; refusing")


def restore_tracked_audited() -> dict[str, object]:
    """Materialize checkout-normalized tracked LF text files from their blobs.

    Windows checkouts normalize ``* text=auto`` files to CRLF; the frozen
    manifests pin the LF audited bytes. Writing the blob bytes restores the
    audited content while remaining Git-clean. Idempotent and non-destructive
    to modified files.
    """
    recovered: list[str] = []
    for path, work_eol, blob in tracked_clean_text():
        if work_eol not in ("crlf", "mixed"):
            continue
        data = git("cat-file", "blob", blob, cwd=CHECKOUT)
        target = CHECKOUT / path
        if not target.is_file():
            raise ValueError(f"tracked path missing from checkout: {path}")
        if target.read_bytes() != data:
            target.write_bytes(data)
            recovered.append(path)
    refresh_index_stat(recovered)
    return {"recovered": recovered, "count": len(recovered)}


def verify_tracked_audited() -> dict[str, object]:
    """Verify no clean tracked LF text file was left line-ending-normalized.

    The evidence digest is computed from the index blob ids, so it is stable
    across runs regardless of whether a given run had to restore anything.
    """
    entries = tracked_clean_text()
    remaining = [path for path, work_eol, _blob in entries
                 if work_eol in ("crlf", "mixed")]
    if remaining:
        raise ValueError(f"tracked file still line-ending-normalized: {remaining[0]}")
    digest = hashlib.sha256(
        ("\n".join(f"{blob}  {path}" for path, _work_eol, blob in sorted(entries)) + "\n").encode("utf-8")
    ).hexdigest()
    return {
        "clean_tracked_lf_text_files": len(entries),
        "normalized_remaining": 0,
        "audited_blob_digest": digest,
    }


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _zig_version(exe: pathlib.Path) -> str:
    result = subprocess.run(
        [str(exe), "version"], cwd=str(exe.parent), check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    return (result.stdout or result.stderr).strip()


def _check_zig(exe: pathlib.Path) -> None:
    if not exe.is_file():
        raise ValueError("audited Zig toolchain executable is missing")
    if sha256_file(exe) != ZIG_EXE_SHA256:
        raise ValueError("Zig executable SHA-256 differs from the frozen identity")
    if _zig_version(exe) != ZIG_VERSION:
        raise ValueError("Zig version differs from the frozen 0.13.0 identity")


def ensure_zig_toolchain(materialize: bool) -> dict[str, object]:
    """Verify, and if needed materialize, the exact frozen Zig 0.13.0 toolchain.

    The only admissible source is a local copy whose executable matches the
    frozen SHA-256 and version; no download, install or upgrade is performed,
    and no existing path is overwritten.
    """
    target_root = CHECKOUT / ZIG_REL
    exe = target_root / "zig.exe"
    if not exe.is_file():
        if not materialize:
            raise ValueError("audited Zig toolchain missing from the isolated checkout")
        source_root = ROOT / ZIG_REL
        _check_zig(source_root / "zig.exe")
        if target_root.exists():
            raise ValueError("refusing to overwrite an existing toolchain path")
        shutil.copytree(source_root, target_root)
    _check_zig(exe)
    files = 0
    total = 0
    for item in target_root.rglob("*"):
        if item.is_file():
            files += 1
            total += item.stat().st_size
    return {
        "path": f"{ZIG_REL}/zig.exe",
        "version": ZIG_VERSION,
        "executable_sha256": ZIG_EXE_SHA256,
        "archive_sha256": ZIG_ARCHIVE_SHA256,
        "files": files,
        "bytes": total,
    }


def prepare(paths: tuple[str, ...], data_by_path: dict[str, bytes]) -> None:
    # Idempotent recovery: absent untracked files are created with exclusive
    # creation, existing files are verified byte-for-byte and never
    # overwritten. This keeps repeated official runs byte-identical while
    # failing closed on any pre-existing file whose bytes differ.
    for path in paths:
        target = CHECKOUT / path
        if not target.parent.resolve().is_relative_to(CHECKOUT.resolve()):
            raise ValueError(f"verification-context path escapes checkout: {path}")
        if target.is_symlink():
            raise ValueError(f"refusing to follow verification-context link: {path}")
        if target.exists():
            if target.read_bytes() != data_by_path[path]:
                raise ValueError(f"refusing to overwrite verification-context file: {path}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(data_by_path[path])
    restore_tracked_audited()


def verify_materialized(paths: tuple[str, ...], data_by_path: dict[str, bytes]) -> None:
    for path in paths:
        target = CHECKOUT / path
        if target.is_symlink() or not target.is_file():
            raise ValueError(f"missing or linked verification-context file: {path}")
        if target.read_bytes() != data_by_path[path]:
            raise ValueError(f"materialized bytes differ from historical blob: {path}")
    if git_text("status", "--porcelain", "--untracked-files=no", cwd=CHECKOUT):
        raise ValueError("isolated checkout tracked state changed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("prepare", "verify"), required=True)
    parser.add_argument("--evidence-dir", default=".openrecomp-phase11/evidence/P11-90")
    args = parser.parse_args()
    try:
        paths = frozen_paths("tools/test_phase3_boundary_v1.py")
        verify_authorities(paths)
        blobs = source_blobs(paths)
        records, data_by_path = inspect_blobs(paths, blobs)
        if args.mode == "prepare":
            prepare(paths, data_by_path)
        verify_materialized(paths, data_by_path)
        tracked_audited = verify_tracked_audited()
        zig_toolchain = ensure_zig_toolchain(materialize=(args.mode == "prepare"))
        document = {
            "schema": "openrecomp-phase11-verification-context-v1",
            "historical_source": {"commit": SOURCE_COMMIT, "tree": SOURCE_TREE},
            "isolated_checkout": {
                "branch": TARGET_BRANCH, "commit": TARGET_COMMIT, "tree": TARGET_TREE,
                "tracked_files_modified": False,
            },
            "method": "exclusive untracked creation from the pinned Phase-2 Git tree; every materialized file compared byte-for-byte with its Git blob",
            "frozen_gate_path_tuples_equal": True,
            "file_count": len(records),
            "unique_git_blobs": len(set(blobs.values())),
            "aggregate_residue_sha256": AGGREGATE_SHA256,
            "root_manifest_script_sha256": SCRIPT_SHA256,
            "root_manifest_script_blob": SCRIPT_BLOB,
            "tracked_audited": {
                "method": "checkout-normalized tracked LF text files materialized from their own Git blobs; modified files never touched; Git-clean",
                "clean_tracked_lf_text_files": tracked_audited["clean_tracked_lf_text_files"],
                "normalized_remaining": tracked_audited["normalized_remaining"],
                "audited_blob_digest": tracked_audited["audited_blob_digest"],
            },
            "zig_toolchain": zig_toolchain,
            "files": records,
        }
        evidence = (ROOT / args.evidence_dir).resolve()
        if not evidence.is_relative_to((ROOT / ".openrecomp-phase11/evidence").resolve()):
            raise ValueError("evidence directory outside Phase-11 evidence root")
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "verification_context.json").write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(f"OPENRECOMP_PHASE11_VERIFICATION_CONTEXT=PASS files={len(records)} aggregate={AGGREGATE_SHA256}")
        print(f"OPENRECOMP_PHASE11_VERIFICATION_CONTEXT_TOOLCHAIN=PASS zig={ZIG_VERSION} sha256={ZIG_EXE_SHA256}")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"FAIL: verification context: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
