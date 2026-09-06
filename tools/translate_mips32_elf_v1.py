#!/usr/bin/env python3
import json
import sys
import struct
from pathlib import Path

from mips32_elf_loader import load_mips32_elf
from mips32_frontend_v1 import convert

def main(argv):
    if len(argv) != 5:
        print("usage: translate_mips32_elf_v1.py <fixture.elf> <host-contract.json> <out-ir.json> <out-sidecar.json>", file=sys.stderr)
        return 2

    elf_path = argv[1]
    contract_path = argv[2]
    ir_path = argv[3]
    sidecar_path = argv[4]

    contract = json.loads(Path(contract_path).read_text(encoding="utf-8"))
    
    # Ingest ELF
    elf_meta = load_mips32_elf(elf_path)
    
    # Parse words from executable regions
    words = {}
    for region in elf_meta["regions"]:
        region_bytes = bytes.fromhex(region["_bytes"])
        vaddr = region["virtual_address"]
        for i in range(0, len(region_bytes), 4):
            if i + 4 <= len(region_bytes):
                word = struct.unpack_from('<I', region_bytes, i)[0]
                words[vaddr + i] = word

    # Construct frontend metadata
    meta = {
        "fixture_version": "1.0.0",
        "architecture": "mips32-le",
        "memory_size_bytes": contract["memory"]["size_bytes"],
        "entry_address": elf_meta["entry_point"],
        "initial_state": {},
        "observe_state_slot": "gpr:r2",
        "max_operations": 200000,
        "functions": [{"id": "fixture_main", "address": elf_meta["entry_point"]}]
    }

    # Convert to V1 IR
    ir, sidecar, report = convert(meta, words, elf_meta["source_sha256"], contract)

    Path(ir_path).write_text(json.dumps(ir, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path(sidecar_path).write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    
    # Also save the report for TRANSLATION_TRACE
    report_path = str(Path(sidecar_path).parent / "TRANSLATION_TRACE.md")
    trace = ["# TRANSLATION TRACE\n"]
    for func in ir["functions"]:
        trace.append(f"## Function {func['id']}")
        for block in func["blocks"]:
            trace.append(f"\n### Block {block['id']}")
            for insn in block["instructions"]:
                trace.append(f"0x{insn.get('source_address', 0):08x}: {insn['op']}")
            term = block["terminator"]
            trace.append(f"0x{term.get('source_address', 0):08x}: {term['op']} (terminator)")
            
    Path(report_path).write_text("\n".join(trace) + "\n", encoding="utf-8")

    print("MIPS32_ELF_TRANSLATE=PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
