#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openrecomp import ModuleError, ModuleImage


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "usage: validate_module_v1.py <module-v1.json> <ir-v1.json> <host-contract.json>",
            file=sys.stderr,
        )
        return 2
    try:
        ModuleImage.from_files(argv[1], argv[2], argv[3])
    except (OSError, ValueError, ModuleError) as exc:
        print(f"OPENRECOMP_MODULE_V1_VALID=FAIL: {exc}", file=sys.stderr)
        return 2
    print("OPENRECOMP_MODULE_V1_VALID=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
