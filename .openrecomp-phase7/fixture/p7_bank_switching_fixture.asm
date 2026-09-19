; ============================================================================
; OpenRecomp Phase-7 public bank-switching structure fixture
; (original work, Apache-2.0, authored for Phase 7)
; ----------------------------------------------------------------------------
; Demonstrates bank-aware CFG / function / translation-unit structure across
; physical MMC1 PRG banks:
;
;   * the fixed last bank (bank 3, $C000-$FFFF) commits PRG bank 1 through an
;     unrolled five-write constant sequence, then calls code in the switchable
;     window (`jsr $8000`);
;   * the switchable-bank routine calls back into a fixed-bank helper
;     (`jsr $C100`), so the program exercises a cross-bank call edge in both
;     directions;
;   * banks 0 and 2 contain different routines that are never selected, so no
;     physical bank content is merged with the selected bank;
;   * the program exits through the declared `jmp ($02FF)` run-exit thunk.
;
; The fixture contains no third-party or console-derived program data.
; This is the fixed-bank part of the fixture; the banked parts are declared in
; `.openrecomp-phase7/src/p7_bank_switching_fixture_v1.py`.
; ============================================================================

.equ EXIT_VEC, $02FF
.equ MMC1_PRG, $E000
.equ MARK_A,   $0300
.equ MARK_B,   $0301
.equ MARK_C,   $0302

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
        jsr $8000
        sta MARK_B
        jmp (EXIT_VEC)

.org $C100
fixed_helper:
        lda #$42
        sta MARK_C
        rts

.org $C140
nmi_handler:
        rti
irq_handler:
        rti

.org $FFFA
        .word nmi_handler
        .word reset
        .word irq_handler
