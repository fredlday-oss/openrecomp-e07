import subprocess
from pathlib import Path

# Generates TRANSLATION_FIXTURE.elf
def build():
    Path("artifacts/mips32_translation_v1").mkdir(parents=True, exist_ok=True)
    asm = """
    .globl _start
    .set noat
    .set noreorder
_start:
    addiu $2, $0, 42
    addiu $3, $0, 8
    addiu $2, $2, 3
    jr $31
    nop
    """
    Path("scratch/fixture.s").write_text(asm)
    subprocess.run(["clang", "-target", "mips-unknown-elf", "-mabi=32", "-mips32", "-O0", "-nostdlib", "-Wl,-e_start", "-o", "artifacts/mips32_translation_v1/TRANSLATION_FIXTURE.elf", "scratch/fixture.s"], check=True)

if __name__ == "__main__":
    build()
