/*
 * OpenRecomp Phase 4 fixture - freestanding MIPS32 entry stub (P4-07).
 * Original work; Apache License 2.0 (repository LICENSE).
 *
 * Initialises the global pointer and the stack pointer (the stack lives at
 * the top of the p4_stack region in .bss), calls main(), and halts.  The
 * program itself performs the exit through the runtime exit window.
 */
    .text
    .globl  _start
    .ent    _start
    .set    noreorder
    .set    noat
_start:
    lui     $gp, %hi(_gp)
    addiu   $gp, $gp, %lo(_gp)
    lui     $sp, %hi(p4_stack + 8192)
    addiu   $sp, $sp, %lo(p4_stack + 8192)
    jal     main
    nop
p4_idle:
    j       p4_idle
    nop
    .end    _start
