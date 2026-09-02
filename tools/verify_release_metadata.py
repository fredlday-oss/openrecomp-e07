#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "release" / "metadata.json"
SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
HEADING_RE = re.compile(r"^## \[([0-9]+\.[0-9]+\.[0-9]+)\] - ([0-9]{4}-[0-9]{2}-[0-9]{2})$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_KEYS = {
    "schema_version",
    "state",
    "version",
    "tag",
    "release_commit",
    "changelog_heading",
    "release_notes",
    "release_checklist",
    "required_files",
    "required_release_text",
    "forbidden_placeholders",
}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    print("OPENRECOMP_RELEASE_METADATA=FAIL")
    raise SystemExit(1)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except OSError as exc:
        fail(f"cannot execute git: {exc}")
    if check and result.returncode != 0:
        fail(f"git {' '.join(args)} failed: {result.stdout.strip()}")
    return result


def require_string(obj: dict, key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        fail(f"manifest field {key!r} must be a non-empty string")
    return value


def require_string_list(obj: dict, key: str) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        fail(f"manifest field {key!r} must be a non-empty list of non-empty strings")
    if len(value) != len(set(value)):
        fail(f"manifest field {key!r} contains duplicate entries")
    return value


def repo_path(value: str, field: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("./") or "\\" in value:
        fail(f"manifest field {field!r} is not a normalized repository-relative path: {value}")
    return value


if not MANIFEST_PATH.is_file():
    fail("release/metadata.json is missing")

try:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    fail(f"cannot parse release/metadata.json: {exc}")

if not isinstance(manifest, dict):
    fail("release metadata root must be an object")
if set(manifest) != ALLOWED_KEYS:
    missing = sorted(ALLOWED_KEYS - set(manifest))
    extra = sorted(set(manifest) - ALLOWED_KEYS)
    fail(f"release metadata keys mismatch; missing={missing} extra={extra}")

if require_string(manifest, "schema_version") != "1.0.0":
    fail("unsupported release metadata schema version")
state = require_string(manifest, "state")
if state not in {"candidate", "published"}:
    fail("release metadata state must be candidate or published")
version = require_string(manifest, "version")
if not SEMVER_RE.fullmatch(version):
    fail("VERSION must use stable numeric SemVer X.Y.Z")
tag = require_string(manifest, "tag")
if tag != f"v{version}":
    fail(f"tag must be exactly v{version}")

version_path = ROOT / "VERSION"
if not version_path.is_file():
    fail("VERSION is missing")
if version_path.read_text(encoding="utf-8").strip() != version:
    fail("VERSION and release/metadata.json disagree")

underscored = version.replace(".", "_")
release_notes = repo_path(require_string(manifest, "release_notes"), "release_notes")
release_checklist = repo_path(require_string(manifest, "release_checklist"), "release_checklist")
if release_notes != f"docs/RELEASE_V{underscored}.md":
    fail("release_notes path must be derived from VERSION")
if release_checklist != f"docs/RELEASE_CHECKLIST_V{underscored}.md":
    fail("release_checklist path must be derived from VERSION")

heading = require_string(manifest, "changelog_heading")
match = HEADING_RE.fullmatch(heading)
if match is None or match.group(1) != version:
    fail("changelog_heading must be '## [VERSION] - YYYY-MM-DD'")

required_files = [repo_path(item, "required_files") for item in require_string_list(manifest, "required_files")]
required_release_text = require_string_list(manifest, "required_release_text")
forbidden_placeholders = require_string_list(manifest, "forbidden_placeholders")

tracked = set(git("ls-files").stdout.splitlines())
required_paths = {
    "VERSION",
    "CHANGELOG.md",
    "release/metadata.json",
    release_notes,
    release_checklist,
    *required_files,
}
for rel in sorted(required_paths):
    path = ROOT / rel
    if not path.is_file():
        fail(f"required release file missing: {rel}")
    if rel not in tracked:
        fail(f"required release file is not tracked: {rel}")

for rel in sorted(tracked):
    if not (ROOT / rel).exists():
        fail(f"tracked path missing from working tree: {rel}")

changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
if "## Unreleased" not in changelog:
    fail("CHANGELOG must retain an Unreleased section")
if heading not in changelog:
    fail(f"CHANGELOG missing release heading: {heading}")
if changelog.index("## Unreleased") > changelog.index(heading):
    fail("CHANGELOG Unreleased section must precede the current release heading")

notes = (ROOT / release_notes).read_text(encoding="utf-8")
checklist = (ROOT / release_checklist).read_text(encoding="utf-8")
for expected in required_release_text:
    if expected not in notes:
        fail(f"release notes missing required evidence text: {expected}")
for placeholder in forbidden_placeholders:
    if placeholder in notes or placeholder in checklist:
        fail(f"release material contains unresolved placeholder: {placeholder}")

release_commit = manifest.get("release_commit")
if state == "published":
    if not isinstance(release_commit, str) or SHA_RE.fullmatch(release_commit) is None:
        fail("published release_commit must be a lowercase 40-character commit SHA")
    tag_result = git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    peeled = tag_result.stdout.strip()
    if peeled != release_commit:
        fail(f"published tag {tag} resolves to {peeled}, expected {release_commit}")
    ancestor = git("merge-base", "--is-ancestor", release_commit, "HEAD", check=False)
    if ancestor.returncode != 0:
        fail("published release commit is not an ancestor of the reviewed source")
else:
    if release_commit is not None:
        fail("candidate release_commit must be null until the release is published")
    existing = git("show-ref", "--verify", "--quiet", f"refs/tags/{tag}", check=False)
    if existing.returncode == 0:
        fail(f"candidate tag already exists: {tag}")

print(f"OPENRECOMP_RELEASE_VERSION={version}")
print(f"OPENRECOMP_RELEASE_STATE={state}")
print(f"OPENRECOMP_RELEASE_TAG={tag}")
print("OPENRECOMP_RELEASE_METADATA=PASS")
