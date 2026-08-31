#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MATCH_KEYS = [
    "return_a0",
    "tick_count",
    "graphics_calls",
    "audio_calls",
    "input_calls",
    "system_calls",
    "checksum",
    "operations",
    "framebuffer_sha256",
    "audio_payload_sha256",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print(
            "usage: check_core_api_v1.py <module.json> <core-result.json> <bridge-result.json> <golden-state.json> <native-run.txt>",
            file=sys.stderr,
        )
        return 2

    try:
        module = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        core = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        bridge = json.loads(Path(argv[3]).read_text(encoding="utf-8"))
        golden = json.loads(Path(argv[4]).read_text(encoding="utf-8"))
        native_text = Path(argv[5]).read_text(encoding="utf-8")

        if module["module_format_version"] != "1.0.0":
            fail("unexpected module format version")
        if module["ir"]["version"] != "1.0.0":
            fail("module does not reference normalized IR V1")

        for key in MATCH_KEYS:
            if core.get(key) != bridge.get(key):
                fail(f"core/bridge mismatch for {key}: core={core.get(key)} bridge={bridge.get(key)}")

        for key in ["return_a0", "tick_count", "graphics_calls", "audio_calls", "input_calls", "system_calls", "checksum"]:
            if core.get(key) != golden.get(key):
                fail(f"core/golden mismatch for {key}: core={core.get(key)} golden={golden.get(key)}")

        match = re.search(r"^CHECKSUM=(\d+)\s*$", native_text, re.MULTILINE)
        if not match:
            fail("native checksum marker missing")
        native_checksum = int(match.group(1))
        if native_checksum != core["checksum"]:
            fail(f"native/Core API checksum mismatch native={native_checksum} core={core['checksum']}")

        print(f"CORE_API_V1_MODULE_FORMAT={module['module_format_version']}")
        print(f"CORE_API_V1_OPERATIONS={core['operations']}")
        print(f"OPENRECOMP_CORE_API_V1_EQUIVALENCE=PASS checksum={core['checksum']}")
        return 0
    except (OSError, json.JSONDecodeError, KeyError, AssertionError) as exc:
        print(f"OPENRECOMP_CORE_API_V1_EQUIVALENCE=FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
