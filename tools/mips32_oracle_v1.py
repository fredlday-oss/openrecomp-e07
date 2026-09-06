#!/usr/bin/env python3
import sys
import json
from pathlib import Path
import struct

# Must import from the same directory
_DIR = Path(__file__).resolve().parent
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

from mips32_elf_loader import load_mips32_elf

def simulate(elf_path):
    meta = load_mips32_elf(elf_path)
    
    memory = bytearray(4096)
    for r in meta['regions']:
        vaddr = r['virtual_address']
        filesz = r['file_size']
        data = bytes.fromhex(r['_bytes'])
        memory[vaddr:vaddr+filesz] = data[:filesz]
        
    pc = meta['entry_point']
    regs = [0] * 32
    
    delay_slot_pc = None
    next_pc = pc
    operations = 0
    max_operations = 200000
    
    while True:
        if operations > max_operations:
            raise ValueError("max operations exceeded")
            
        current_pc = delay_slot_pc if delay_slot_pc is not None else next_pc
        
        # end of execution hook: returning via jr $ra to 0
        if current_pc == 0:
            break
            
        word = struct.unpack_from('<I', memory, current_pc)[0]
        
        operations += 1
        
        opcode = (word >> 26) & 0x3F
        rs = (word >> 21) & 0x1F
        rt = (word >> 16) & 0x1F
        rd = (word >> 11) & 0x1F
        shamt = (word >> 6) & 0x1F
        funct = word & 0x3F
        imm_u = word & 0xFFFF
        imm_s = imm_u
        if imm_s & 0x8000:
            imm_s -= 0x10000
            
        branch_target = None
            
        if word == 0:
            pass # nop
        elif opcode == 0 and funct == 0x21: # addu
            val = (regs[rs] + regs[rt]) & 0xFFFFFFFF
            if rd != 0: regs[rd] = val
        elif opcode == 9: # addiu
            val = (regs[rs] + imm_s) & 0xFFFFFFFF
            if rt != 0: regs[rt] = val
        elif opcode == 4: # beq
            if regs[rs] == regs[rt]:
                branch_target = (current_pc + 4 + (imm_s << 2)) & 0xFFFFFFFF
        elif opcode == 0 and funct == 8: # jr
            branch_target = regs[rs]
        else:
            raise ValueError(f"Unsupported instruction at {current_pc:08x}: {word:08x}")
            
        if delay_slot_pc is not None:
            delay_slot_pc = None
            next_pc = pending_branch_target
        else:
            if branch_target is not None:
                delay_slot_pc = current_pc + 4
                pending_branch_target = branch_target
            else:
                next_pc = current_pc + 4

    return {
        "r2": regs[2],
        "r3": regs[3],
        "operations": operations
    }

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: mips32_oracle_v1.py <fixture.elf>")
        sys.exit(2)
    try:
        state = simulate(sys.argv[1])
        print(f"r2={state['r2']}")
        print(f"r3={state['r3']}")
        print(f"operations={state['operations']}")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
