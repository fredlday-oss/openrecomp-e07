; ============================================================================
; OpenRecomp Phase-7 public indirect-control-flow fixture: bank 1
; (original work, Apache-2.0, authored for Phase 7)
; ----------------------------------------------------------------------------
; Bank 1 hosts three `jmp ($E2)` dispatch sites selected by the runtime
; selector at zero page $10:
;
;   * exact path: constant pointer bytes -> exactly one feasible target;
;   * finite path: a masked table index (`and #$06`) into a four-entry
;     contiguous pointer table -> four feasible targets;
;   * unresolved path: pointer bytes copied from runtime RAM $12/$13, which
;     the static evidence model cannot resolve (fail closed).
;
; Every target records a marker and finishes at the fixed-bank run-exit thunk
; (`$C200` area). No third-party or console-derived program data.
; ============================================================================

.equ SELECTOR,     $10
.equ FINITE_INDEX, $11
.equ PTR_LO,       $12
.equ PTR_HI,       $13
.equ PTR_LOW,      $E2
.equ PTR_HIGH,     $E3
.equ MARK_KIND,    $0300
.equ MARK_TARGET,  $0301
.equ FIXED_TARGET, $C200

.org $8000

bank_entry:
        lda $10
        beq exact_path
        cmp #$01
        beq finite_path
        jmp unresolved_path

exact_path:
        lda #<exact_target
        sta $E2
        lda #>exact_target
        sta $E3
        jmp (PTR_LOW)

finite_path:
        lda $11
        and #$06
        tay
        lda finite_table,y
        sta $E2
        lda finite_table+1,y
        sta $E3
        jmp (PTR_LOW)

unresolved_path:
        lda $12
        sta $E2
        lda $13
        sta $E3
        jmp (PTR_LOW)

exact_target:
        lda #$E0
        sta MARK_KIND
        lda #$01
        sta MARK_TARGET
        jmp FIXED_TARGET

.org $8100
finite_target_a:
        lda #$F1
        sta MARK_KIND
        lda #$01
        sta MARK_TARGET
        jmp FIXED_TARGET

.org $8110
finite_target_b:
        lda #$F2
        sta MARK_KIND
        lda #$02
        sta MARK_TARGET
        jmp FIXED_TARGET

.org $8120
finite_target_c:
        lda #$F3
        sta MARK_KIND
        lda #$03
        sta MARK_TARGET
        jmp FIXED_TARGET

.org $8130
finite_target_d:
        lda #$F4
        sta MARK_KIND
        lda #$04
        sta MARK_TARGET
        jmp FIXED_TARGET

.org $8200
finite_table:
        .word finite_target_a
        .word finite_target_b
        .word finite_target_c
        .word finite_target_d
