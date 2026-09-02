#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
VERIFIER = SOURCE_ROOT / "tools" / "verify_release_metadata.py"
VERSION = "9.9.9"
TAG = f"v{VERSION}"
HEADING = f"## [{VERSION}] - 2099-01-01"


def run(root: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"command {args!r} returned {result.returncode}, expected {expect}\n{result.stdout}"
        )
    return result


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def manifest(state: str, release_commit: str | None) -> dict:
    suffix = VERSION.replace(".", "_")
    return {
        "schema_version": "1.0.0",
        "state": state,
        "version": VERSION,
        "tag": TAG,
        "release_commit": release_commit,
        "changelog_heading": HEADING,
        "release_notes": f"docs/RELEASE_V{suffix}.md",
        "release_checklist": f"docs/RELEASE_CHECKLIST_V{suffix}.md",
        "required_files": ["README.md"],
        "required_release_text": ["SYNTHETIC_RELEASE_EVIDENCE=PASS"],
        "forbidden_placeholders": ["TBD", "TODO"],
    }


def write_manifest(root: Path, data: dict) -> None:
    write(root / "release" / "metadata.json", json.dumps(data, indent=2) + "\n")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="openrecomp-release-metadata-") as temp:
        root = Path(temp)
        shutil.copy2(VERIFIER, root / "tools" / "verify_release_metadata.py") if (root / "tools").exists() else None
        (root / "tools").mkdir(parents=True, exist_ok=True)
        shutil.copy2(VERIFIER, root / "tools" / "verify_release_metadata.py")

        suffix = VERSION.replace(".", "_")
        write(root / "VERSION", VERSION + "\n")
        write(root / "README.md", "# synthetic release metadata fixture\n")
        write(root / "CHANGELOG.md", f"# Changelog\n\n## Unreleased\n\n{HEADING}\n")
        write(
            root / "docs" / f"RELEASE_V{suffix}.md",
            f"# Synthetic {VERSION}\n\nSYNTHETIC_RELEASE_EVIDENCE=PASS\n",
        )
        write(
            root / "docs" / f"RELEASE_CHECKLIST_V{suffix}.md",
            "# Synthetic release checklist\n\n- complete\n",
        )
        write_manifest(root, manifest("candidate", None))

        run(root, "git", "init", "-q")
        run(root, "git", "config", "user.name", "OpenRecomp CI")
        run(root, "git", "config", "user.email", "ci@openrecomp.invalid")
        run(root, "git", "add", ".")
        run(root, "git", "commit", "-qm", "candidate")

        candidate = run(root, sys.executable, "tools/verify_release_metadata.py")
        if "OPENRECOMP_RELEASE_STATE=candidate" not in candidate.stdout or "OPENRECOMP_RELEASE_METADATA=PASS" not in candidate.stdout:
            raise AssertionError("candidate metadata did not emit expected PASS markers")
        print("OPENRECOMP_RELEASE_AUTOMATION_V1_CANDIDATE=PASS")

        release_commit = run(root, "git", "rev-parse", "HEAD").stdout.strip()
        run(root, "git", "tag", "-a", TAG, "-m", f"Synthetic {VERSION}")
        candidate_with_tag = run(root, sys.executable, "tools/verify_release_metadata.py", expect=1)
        if "candidate tag already exists" not in candidate_with_tag.stdout:
            raise AssertionError("candidate state did not reject an already-created release tag")
        print("OPENRECOMP_RELEASE_AUTOMATION_V1_CANDIDATE_TAG_REJECTION=PASS")

        write_manifest(root, manifest("published", release_commit))
        run(root, "git", "add", "release/metadata.json")
        run(root, "git", "commit", "-qm", "publish metadata")
        published = run(root, sys.executable, "tools/verify_release_metadata.py")
        if "OPENRECOMP_RELEASE_STATE=published" not in published.stdout or "OPENRECOMP_RELEASE_METADATA=PASS" not in published.stdout:
            raise AssertionError("published metadata did not emit expected PASS markers")
        print("OPENRECOMP_RELEASE_AUTOMATION_V1_PUBLISHED=PASS")

        bad = manifest("published", "0" * 40)
        write_manifest(root, bad)
        mismatch = run(root, sys.executable, "tools/verify_release_metadata.py", expect=1)
        if "published tag" not in mismatch.stdout or "expected" not in mismatch.stdout:
            raise AssertionError("published state did not reject a tag/commit mismatch")
        print("OPENRECOMP_RELEASE_AUTOMATION_V1_TAG_COMMIT_REJECTION=PASS")

    print("OPENRECOMP_RELEASE_AUTOMATION_V1_TESTS=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, AssertionError) as exc:
        print(f"OPENRECOMP_RELEASE_AUTOMATION_V1_TESTS=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
