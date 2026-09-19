; ============================================================================
; OpenRecomp Phase-7 public indirect-control-flow fixture: fixed bank
; (original work, Apache-2.0, authored for Phase 7)
; ----------------------------------------------------------------------------
; The fixed last bank commits PRG bank 1 through an unrolled five-write
; constant sequence, sets up the runtime selector/index/pointer state and
; calls the bank-1 dispatch entry. The bank-1 code (see
; `p7_indirect_flow_bank.asm`) exercises exact, finite-set and unresolved
; indirect dispatch through the `$E2/$E3` pointer pair; all target routines
; finish here at the fixed `run_exit` thunk.
;
; No third-party or console-derived program data.
; ============================================================================

.equ EXIT_VEC,     $02FF
.equ MMC1_PRG,     $E000
.equ SELECTOR,     $10
.equ FINITE_INDEX, $11
.equ PTR_LO,       $12
.equ PTR_HI,       $13
.equ MARK_KIND,    $0300
.equ MARK_TARGET,  $0301
.equ MARK_FIXED,   $0302
.equ SELECT_EXACT, $00

.org $C000

reset:
        sei
        cld
        ldx #$FF
        txs
        lda #$01
        sta MMC1_PRG
        lda #$00
        sta MMC1_PRG
        lda #$00
        sta MMC1_PRG
        lda #$00
        sta MMC1_PRG
        lda #$00
        sta MMC1_PRG
        lda #SELECT_EXACT
        sta $10
        lda #$02
        sta $11
        lda #$00
        sta $12
        lda #$C2
        sta $13
        jsr $8000
        jmp run_exit

.org $C200
fixed_target:
        lda #$F0
        sta MARK_FIXED
run_exit:
        jmp (EXIT_VEC)

.org $C240
nmi_handler:
        rti
irq_handler:
        rti

.org $FFFA
        .word nmi_handler
        .word reset
        .word irq_handler
