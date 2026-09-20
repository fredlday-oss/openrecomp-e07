/*
 * OpenRecomp Phase 8 - freestanding MIPS32 entry stub (OpenRecomp-authored).
 *
 * Sets up the global pointer and stack pointer, calls the fixture main and
 * returns to the host with the status value in $v0.  The host-side runtime
 * observes the register file at that return boundary.  The host enters with
 * all registers zero, so the return address in $ra is 0 and the guest return
 * lands on address 0, which is outside the mapped image.
 */

    .text
    .globl  _start
    .ent    _start
    .set    noreorder
    .set    noat
_start:
    lui     $gp, %hi(_gp)
    addiu   $gp, $gp, %lo(_gp)
    lui     $sp, %hi(p8_stack + 16384)
    addiu   $sp, $sp, %lo(p8_stack + 16384)
    jal     p8_main
    nop
    move    $ra, $zero
    jr      $ra
    nop
    .end    _start
