#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.2.0"
EXPECTED_CHANGELOG = "## [0.2.0] - 2026-09-01"
REQUIRED_FILES = [
    "VERSION",
    "CHANGELOG.md",
    "README.md",
    "DEVELOPMENT_PROCESS.md",
    "docs/FUNDING_SCOPE.md",
    "docs/PROOF_STATUS.md",
    "docs/REPRODUCIBILITY.md",
    "docs/RELEASE_V0_2_0.md",
    "docs/RELEASE_CHECKLIST_V0_2_0.md",
    "include/openrecomp/native_aot_abi_v1.h",
]
REQUIRED_RELEASE_TEXT = [
    "122010428",
    "1950232098",
    "PASS — local runtime evidence",
    "FROZEN-FOR-PORTABILITY-TESTING",
    "openrecomp_native_aot_query",
    "OPENRECOMP_V0_2_RELEASE_METADATA=PASS",
]
FORBIDDEN_PLACEHOLDERS = ["<commit-sha>", "<tag-sha>", "TBD", "TODO"]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    print("OPENRECOMP_V0_2_RELEASE_METADATA=FAIL")
    raise SystemExit(1)


version_path = ROOT / "VERSION"
if not version_path.is_file():
    fail("VERSION is missing")
if version_path.read_text(encoding="utf-8").strip() != EXPECTED_VERSION:
    fail(f"VERSION must be exactly {EXPECTED_VERSION}")

for rel in REQUIRED_FILES:
    if not (ROOT / rel).is_file():
        fail(f"required release file missing: {rel}")

changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
if EXPECTED_CHANGELOG not in changelog:
    fail(f"CHANGELOG missing release heading: {EXPECTED_CHANGELOG}")
if "## Unreleased" not in changelog:
    fail("CHANGELOG must retain an Unreleased section")

release_notes = (ROOT / "docs/RELEASE_V0_2_0.md").read_text(encoding="utf-8")
for expected in REQUIRED_RELEASE_TEXT:
    if expected not in release_notes:
        fail(f"release notes missing required evidence text: {expected}")
for placeholder in FORBIDDEN_PLACEHOLDERS:
    if placeholder in release_notes:
        fail(f"release notes contain unresolved placeholder: {placeholder}")

try:
    tracked = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files"], text=True, stderr=subprocess.STDOUT
    ).splitlines()
except (OSError, subprocess.CalledProcessError) as exc:
    fail(f"cannot enumerate tracked files: {exc}")

for rel in tracked:
    path = ROOT / rel
    if not path.exists():
        fail(f"tracked path missing from working tree: {rel}")

print(f"OPENRECOMP_RELEASE_VERSION={EXPECTED_VERSION}")
print("OPENRECOMP_V0_2_RELEASE_METADATA=PASS")
