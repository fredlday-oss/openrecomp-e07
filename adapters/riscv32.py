from .interface import ArchitectureInfo

REGS=("zero","ra","sp","gp","tp","t0","t1","t2","s0","s1","a0","a1","a2","a3","a4","a5","a6","a7","s2","s3","s4","s5","s6","s7","s8","s9","s10","s11","t3","t4","t5","t6")
info=ArchitectureInfo("riscv32-rv32i",32,"little",REGS,"RISC-V ILP32: a0-a7 args, a0 return, ra link, sp stack")

def sext(x,b):
    return x-(1<<b) if x&(1<<(b-1)) else x

def decode(address, w):
    op=w&0x7f; rd=(w>>7)&31; f3=(w>>12)&7; rs1=(w>>15)&31; rs2=(w>>20)&31; f7=(w>>25)&0x7f
    d={"address":address,"word":f"0x{w:08x}","rd":rd,"rs1":rs1,"rs2":rs2}
    if op==0x13:
        imm=sext(w>>20,12)
        if f3==0: d.update(op="addi",imm=imm)
        elif f3==7: d.update(op="andi",imm=imm)
        elif f3==1 and f7==0: d.update(op="slli",imm=(w>>20)&31)
        elif f3==5 and f7==0: d.update(op="srli",imm=(w>>20)&31)
        else: raise ValueError(f"unsupported OP-IMM 0x{w:08x} at 0x{address:x}")
    elif op==0x33:
        names={(0,0):"add",(4,0):"xor"}; k=(f3,f7)
        if k not in names: raise ValueError(f"unsupported OP 0x{w:08x} at 0x{address:x}")
        d["op"]=names[k]
    elif op==0x03:
        imm=sext(w>>20,12); names={2:"lw",5:"lhu"}
        if f3 not in names: raise ValueError(f"unsupported LOAD 0x{w:08x} at 0x{address:x}")
        d.update(op=names[f3],imm=imm)
    elif op==0x23:
        imm=((w>>25)<<5)|((w>>7)&31); imm=sext(imm,12)
        if f3!=2: raise ValueError(f"unsupported STORE 0x{w:08x} at 0x{address:x}")
        d.update(op="sw",imm=imm)
    elif op==0x37:
        d.update(op="lui",imm=w&0xfffff000)
    elif op==0x63:
        imm=((w>>31)&1)<<12 | ((w>>7)&1)<<11 | ((w>>25)&0x3f)<<5 | ((w>>8)&0xf)<<1
        imm=sext(imm,13); names={6:"bltu",7:"bgeu",0:"beq",1:"bne"}
        if f3 not in names: raise ValueError(f"unsupported BRANCH 0x{w:08x} at 0x{address:x}")
        d.update(op=names[f3],imm=imm,target=(address+imm)&0xffffffff)
    elif op==0x6f:
        imm=((w>>31)&1)<<20 | ((w>>12)&0xff)<<12 | ((w>>20)&1)<<11 | ((w>>21)&0x3ff)<<1
        imm=sext(imm,21); d.update(op="jal",imm=imm,target=(address+imm)&0xffffffff)
    elif op==0x67:
        imm=sext(w>>20,12)
        if f3!=0: raise ValueError(f"unsupported JALR 0x{w:08x}")
        d.update(op="jalr",imm=imm)
    else:
        raise ValueError(f"unsupported opcode 0x{op:02x}, word 0x{w:08x} at 0x{address:x}")
    return d

def branch_targets(insn):
    return [insn["target"]] if "target" in insn else []
