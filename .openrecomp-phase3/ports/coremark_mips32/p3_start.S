/*
 * OpenRecomp Phase 3 - freestanding MIPS32 entry stub (OpenRecomp-authored).
 *
 * Sets up the global pointer and stack pointer, calls the CoreMark main(),
 * forwards the return value to the P3 exit hook and halts.  The toolchain
 * used for this fixture emits SVR4 abicalls code, so $gp is initialised from
 * the linker-provided _gp symbol.  The image is otherwise non-PIC.
 */

    .text
    .globl  _start
    .ent    _start
    .set    noreorder
    .set    noat
_start:
    lui     $gp, %hi(_gp)
    addiu   $gp, $gp, %lo(_gp)
    lui     $sp, %hi(p3_stack + 16384)
    addiu   $sp, $sp, %lo(p3_stack + 16384)
    jal     main
    nop
    move    $4, $2
    jal     p3_exit
    nop
p3_halt:
    b       p3_halt
    nop
    .end    _start
