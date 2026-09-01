#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "tools/public_safety_scan.py"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="openrecomp-public-safety-") as temp_dir:
        repo = Path(temp_dir)
        tools = repo / "tools"
        tools.mkdir(parents=True)
        scanner_copy = tools / "public_safety_scan.py"
        shutil.copy2(SCANNER, scanner_copy)

        tracked = repo / "evidence.txt"
        tracked.write_text("public-safe evidence\n", encoding="utf-8")

        require(run(["git", "init", "-q"], repo).returncode == 0, "git init failed")
        require(
            run(["git", "add", "tools/public_safety_scan.py", "evidence.txt"], repo).returncode == 0,
            "git add failed",
        )

        tracked.unlink()
        result = run([sys.executable, str(scanner_copy)], repo)

        require(result.returncode == 1, f"expected exit 1, got {result.returncode}")
        require(
            "FAIL: tracked file missing from working tree: evidence.txt" in result.stdout,
            f"clean missing-file diagnostic absent: {result.stdout!r}",
        )
        require(
            "OPENRECOMP_PUBLIC_SAFETY=FAIL" in result.stdout,
            "public safety FAIL marker absent",
        )
        require("Traceback" not in result.stdout, "traceback leaked to stdout")
        require("Traceback" not in result.stderr, f"traceback leaked to stderr: {result.stderr!r}")

    print("OPENRECOMP_PUBLIC_SAFETY_MISSING_FILE_TEST=PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"OPENRECOMP_PUBLIC_SAFETY_MISSING_FILE_TEST=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(2)
