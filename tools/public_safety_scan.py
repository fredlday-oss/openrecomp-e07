#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

BANNED_DIR_PARTS = {"Binaries", "Intermediate", "Saved", "DerivedDataCache"}
TEXT_SUFFIXES = {
    ".c", ".cc", ".cpp", ".h", ".hpp", ".py", ".js", ".ts",
    ".md", ".txt", ".json", ".yml", ".yaml", ".sh", ".ps1", ".toml", ".ini",
}

MARKERS = [
    re.compile(r"AUTH_PASSWORD[ \t]*=", re.I),
    re.compile(r"AUTH_LOGIN[ \t]*=", re.I),
    re.compile(r"AUTH_TYPE[ \t]*=[ \t]*exchangecode", re.I),
    re.compile(r"epicusername[ \t]*=", re.I),
    re.compile(r"epicuserid[ \t]*=", re.I),
    re.compile(r"loginid[ \t]*=", re.I),
    re.compile(r"access_token[ \t]*[:=]", re.I),
    re.compile(r"refresh_token[ \t]*[:=]", re.I),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    print("OPENRECOMP_PUBLIC_SAFETY=FAIL")
    raise SystemExit(1)


def tracked_files() -> list[Path]:
    try:
        raw = subprocess.check_output(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            stderr=subprocess.STDOUT,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        fail(f"unable to enumerate tracked files with git ls-files: {exc}")
    return [ROOT / item.decode("utf-8") for item in raw.split(bytes([0])) if item]


def main() -> int:
    for path in tracked_files():
        rel = path.relative_to(ROOT)

        if any(part in BANNED_DIR_PARTS for part in rel.parts):
            fail(f"generated Unreal directory tracked: {rel}")

        if path.suffix.lower() == ".log":
            fail(f"raw log tracked: {rel}")

        if path.resolve() == SELF:
            continue

        if not path.exists():
            fail(f"tracked file missing from working tree: {rel}")

        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            fail(f"expected UTF-8 text file is not UTF-8: {rel}")
        except OSError as exc:
            fail(f"unable to read tracked text file {rel}: {exc}")

        for marker in MARKERS:
            if marker.search(text):
                fail(f"sensitive marker matched in {rel}: {marker.pattern}")

    print("OPENRECOMP_PUBLIC_SAFETY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
