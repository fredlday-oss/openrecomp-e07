#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")

raw = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"])
tracked = [ROOT / item.decode("utf-8") for item in raw.split(b"\0") if item]
markdown = [path for path in tracked if path.suffix.lower() == ".md"]
errors: list[str] = []

for doc in markdown:
    text = doc.read_text(encoding="utf-8")
    for match in LINK_RE.finditer(text):
        target = match.group(1).strip().strip("<>")

        if (
            not target
            or target.startswith("#")
            or target.startswith("http://")
            or target.startswith("https://")
            or target.startswith("mailto:")
        ):
            continue

        if " " in target:
            target = target.split(" ", 1)[0]

        target = unquote(target.split("#", 1)[0])
        resolved = (doc.parent / target).resolve()

        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"{doc.relative_to(ROOT)} -> escapes repository: {target}")
            continue

        if not resolved.exists():
            errors.append(f"{doc.relative_to(ROOT)} -> missing: {target}")

if errors:
    for error in errors:
        print("FAIL:", error)
    raise SystemExit(1)

print("OPENRECOMP_DOC_LINKS=PASS")
