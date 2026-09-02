#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mips32_elf_frontend_v1 import MIPS32ELFError, load_mips32_elf, runtime_meta_for_elf
from tools.run_mips32_expansion_reference import ReferenceError, ReferenceMachine


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: run_mips32_elf_reference_v1.py <input.elf> <runtime.json> <out-result.json>", file=sys.stderr)
        return 2
    try:
        loaded = load_mips32_elf(argv[1])
        runtime = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        meta = runtime_meta_for_elf(runtime, loaded)
        machine = ReferenceMachine(loaded["words"], meta)
        machine.run()
        result = machine.result(loaded["input_sha256"])
        result["input_format"] = "ELF32"
        result["elf_machine"] = loaded["machine"]
        result["elf_entry_point"] = loaded["entry_point"]
        result["elf_text_sha256"] = loaded["text"]["sha256"]
        Path(argv[3]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, json.JSONDecodeError, KeyError, MIPS32ELFError, ReferenceError) as exc:
        print(f"OPENRECOMP_MIPS32_ELF_REFERENCE=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"MIPS32_ELF_REFERENCE_CHECKSUM={result['checksum']}")
    print("OPENRECOMP_MIPS32_ELF_REFERENCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
