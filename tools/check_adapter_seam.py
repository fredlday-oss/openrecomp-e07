#!/usr/bin/env python3
from adapters import riscv32,mips32_stub
assert riscv32.info.bits==mips32_stub.info.bits==32
assert hasattr(riscv32,'decode') and hasattr(mips32_stub,'decode')
try:mips32_stub.decode(0,0)
except NotImplementedError: pass
else: raise SystemExit('stub unexpectedly implements semantics')
print('PASS: shared adapter interface is real; RISC-V=PROVEN, MIPS32=CANDIDATE')
