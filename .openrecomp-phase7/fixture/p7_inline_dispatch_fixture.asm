; ============================================================================
; OpenRecomp Phase-7 public inline-dispatch classification fixture
; (original work, Apache-2.0, authored for Phase 7)
; ----------------------------------------------------------------------------
; Demonstrates the P7-02 classification mechanism on public, original code:
;
;   * `jsr dispatch` at `call_site` is immediately followed by an inline
;     table of little-endian code pointers;
;   * the table's first byte is the undocumented opcode value 0x7C, so a
;     documented-only decoder stops exactly at the table base (as it does at
;     0xC570 in the private compatibility image);
;   * `dispatch` consumes the pushed return address (the address of the last
;     byte of the jsr, i.e. one before the table) through pla/pla, reads the
;     selected 16-bit pointer through `lda (ptr),y` and tail-jumps through
;     `jmp (target)`;
;   * documented code resumes after the table and is never executed by the
;     fixture's own dynamic path;
;   * the running program selects entry 1, the dispatched target writes its
;     marker byte, then control exits through the declared `jmp ($02FF)`
;     run-exit thunk.
;
; The fixture contains no third-party or console-derived program data.
; ============================================================================

.equ PPUCTRL,    $2000
.equ PPUMASK,    $2001
.equ MARKER,     $0300
.equ SELECTOR,   $0301
.equ RESUME_OUT, $0302
.equ PLAIN_OUT,  $0303
.equ EXIT_VEC,   $02FF
.equ SELECT_ONE, $01

.org $C000

reset:
        sei
        cld
        ldx #$FF
        txs
        inx
        lda #$00
        sta PPUCTRL
        sta PPUMASK
        lda #SELECT_ONE
        sta SELECTOR
        jsr plain_sub
        lda #SELECT_ONE
        jsr dispatch
inline_table:
        .word target0
        .word target1
        .word target2
resume_code:
        lda #$00
        sta RESUME_OUT
        rts

.org $C07C
target0:
        lda #$10
        sta MARKER
        jmp exit_thunk

.org $C090
target1:
        lda #$11
        sta MARKER
        jmp exit_thunk

.org $C0A0
target2:
        lda #$12
        sta MARKER
        jmp exit_thunk

.org $C0B0
plain_sub:
        lda #$22
        sta PLAIN_OUT
        rts

.org $C100
dispatch:
        asl a
        tay
        iny
        pla
        sta $00
        pla
        sta $01
        lda ($00),y
        sta $02
        iny
        lda ($00),y
        sta $03
        jmp ($0002)

.org $C130
exit_thunk:
        jmp (EXIT_VEC)

.org $C140
nmi_handler:
        rti
irq_handler:
        rti

.org $FFFA
        .word nmi_handler
        .word reset
        .word irq_handler
