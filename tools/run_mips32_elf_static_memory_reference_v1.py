#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mips32_elf_frontend_v1 import MIPS32ELFError, runtime_meta_for_elf
from tools.mips32_elf_static_memory_frontend_v1 import (
    MIPS32ELFStaticMemoryError,
    load_mips32_elf_static_memory,
)
from tools.run_mips32_expansion_reference import ReferenceError, ReferenceMachine


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: run_mips32_elf_static_memory_reference_v1.py <input.elf> <runtime.json> <out-result.json>", file=sys.stderr)
        return 2
    try:
        runtime = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        loaded = load_mips32_elf_static_memory(argv[1], runtime["memory_size_bytes"])
        meta = runtime_meta_for_elf(runtime, loaded)
        machine = ReferenceMachine(loaded["words"], meta)
        for segment in loaded["memory_segments"]:
            start = segment["guest_address"]
            data = bytes.fromhex(segment["data_hex"])
            machine.memory[start:start + len(data)] = data
        machine.run()
        result = machine.result(loaded["input_sha256"])
        result["input_format"] = "ELF32"
        result["elf_machine"] = loaded["machine"]
        result["elf_entry_point"] = loaded["entry_point"]
        result["elf_text_sha256"] = loaded["text"]["sha256"]
        result["initial_memory_segments"] = [
            {
                "name": item["name"],
                "guest_address": item["guest_address"],
                "size_bytes": item["size_bytes"],
                "data_sha256": item["data_sha256"],
                "zero_fill": item["zero_fill"],
            }
            for item in loaded["memory_segments"]
        ]
        Path(argv[3]).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (
        OSError, json.JSONDecodeError, KeyError, MIPS32ELFError, MIPS32ELFStaticMemoryError, ReferenceError
    ) as exc:
        print(f"OPENRECOMP_MIPS32_ELF_STATIC_MEMORY_REFERENCE=FAIL: {exc}", file=sys.stderr)
        return 2
    print(f"MIPS32_ELF_STATIC_MEMORY_REFERENCE_CHECKSUM={result['checksum']}")
    print("OPENRECOMP_MIPS32_ELF_STATIC_MEMORY_REFERENCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
