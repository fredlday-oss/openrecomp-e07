import os
import sys
import json
import subprocess
from pathlib import Path

OUT_DIR = Path("artifacts/mips32_translation_v1/microtests")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def rtype(op, rs, rt, rd, shamt, funct):
    return (op << 26) | (rs << 21) | (rt << 16) | (rd << 11) | (shamt << 6) | funct

def itype(op, rs, rt, imm):
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xffff)

def jtype(op, target):
    return (op << 26) | ((target >> 2) & 0x03ffffff)

jr_ra = [rtype(0, 31, 0, 0, 0, 8), 0]

cases = {
    "addiu_pos": [itype(9, 0, 2, 7)] + jr_ra,
    "addiu_neg": [itype(9, 0, 2, -5)] + jr_ra,
    "addiu_wrap": [itype(9, 2, 2, 1)] + jr_ra,
    "addu_norm": [rtype(0, 2, 3, 4, 0, 0x21)] + jr_ra,
    "addu_zero": [rtype(0, 0, 0, 2, 0, 0x21)] + jr_ra,
    "beq_taken": [itype(4, 2, 2, 2), 0, 0, 0] + jr_ra, # branches to the jr_ra
    "beq_not_taken": [itype(4, 0, 2, 2), 0, 0, 0] + jr_ra,
    "jr_ra": jr_ra,
    "zero_write": [itype(9, 2, 0, 5)] + jr_ra,
    "unsupported_fail": [0xFFFFFFFF] + jr_ra,
}

contract = {
    "contract_version": "0.1.1",
    "memory": {"size_bytes": 4096, "oob_policy": "deterministic fault"},
    "system": {"wall_clock": False, "randomness": False}
}
(OUT_DIR / "contract.json").write_text(json.dumps(contract))

meta = {
    "fixture_version": "1.0.0",
    "architecture": "mips32-le",
    "memory_size_bytes": 4096,
    "entry_address": 0x1000,
    "initial_state": {},
    "observe_state_slot": "gpr:r2",
    "max_operations": 200000,
    "functions": [{"id": "fixture_main", "address": 0x1000}]
}
(OUT_DIR / "meta.json").write_text(json.dumps(meta))

passes = 0
fails = 0

for name, insts in cases.items():
    hex_path = OUT_DIR / f"{name}.hex"
    ir_path = OUT_DIR / f"{name}_ir.json"
    sidecar_path = OUT_DIR / f"{name}_sidecar.json"
    report_path = OUT_DIR / f"{name}_report.json"
    
    with open(hex_path, "w") as f:
        addr = 0x1000
        for i in insts:
            f.write(f"{addr:08x} {i:08x}\n")
            addr += 4
            
    cmd = [
        sys.executable, "tools/mips32_frontend_v1.py",
        str(hex_path), str(OUT_DIR / "meta.json"), str(OUT_DIR / "contract.json"),
        str(ir_path), str(sidecar_path), str(report_path)
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    if "unsupported" in name or "fail" in name:
        if res.returncode != 0:
            passes += 1
            print(f"PASS (rejected correctly): {name}")
        else:
            fails += 1
            print(f"FAIL (should have rejected): {name}")
    else:
        if res.returncode == 0:
            passes += 1
            print(f"PASS (accepted correctly): {name}")
        else:
            fails += 1
            print(f"FAIL (should have accepted): {name}\n{res.stderr}")

print(f"Microtests: {passes} passed, {fails} failed")
if fails > 0:
    sys.exit(1)
