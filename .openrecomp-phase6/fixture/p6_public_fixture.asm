; OpenRecomp Phase-6 public MMC1 fixture - fixed last bank (bank 3 of 4)
; Original Apache-2.0 work authored for OpenRecomp Phase 6.
;
; This is the P6-01 established fixture revision: a valid MMC1/mapper-1 image
; whose fixed last bank explicitly initializes the MMC1 control, CHR and PRG
; registers at reset and then runs a bounded deterministic main loop.
; P6-06 extends the behavioural coverage (bank switching, CHR switching,
; mirroring, graphics) over this established source.

.equ MMC1_CTRL_WINDOW, $8000
.equ MMC1_CHR0_WINDOW, $A000
.equ MMC1_CHR1_WINDOW, $C000
.equ MMC1_PRG_WINDOW,  $E000

; control 0x0F = horizontal mirroring (3), PRG mode 3 (fix last at $C000),
; CHR mode 0 (8 KiB)
.equ CONTROL_HORIZONTAL_MODE3_CHR8K, $0F

.org $C000

reset:
    sei
    cld
    ldx #$FF
    txs
    lda #CONTROL_HORIZONTAL_MODE3_CHR8K
    jsr mmc1_write_control
    lda #$00
    jsr mmc1_write_chr0
    lda #$00
    jsr mmc1_write_chr1
    lda #$00
    jsr mmc1_write_prg

main_loop:
    inc $00
    lda $00
    sta $0200
    lda $4016
    sta $0300
    jmp main_loop

nmi_handler:
    inc $01
    rti

irq_handler:
    rti

mmc1_write_control:
    ldx #5
mmc1_control_loop:
    pha
    and #$01
    sta MMC1_CTRL_WINDOW
    pla
    lsr a
    dex
    bne mmc1_control_loop
    rts

mmc1_write_chr0:
    ldx #5
mmc1_chr0_loop:
    pha
    and #$01
    sta MMC1_CHR0_WINDOW
    pla
    lsr a
    dex
    bne mmc1_chr0_loop
    rts

mmc1_write_chr1:
    ldx #5
mmc1_chr1_loop:
    pha
    and #$01
    sta MMC1_CHR1_WINDOW
    pla
    lsr a
    dex
    bne mmc1_chr1_loop
    rts

mmc1_write_prg:
    ldx #5
mmc1_prg_loop:
    pha
    and #$01
    sta MMC1_PRG_WINDOW
    pla
    lsr a
    dex
    bne mmc1_prg_loop
    rts

.org $FFFA
.word nmi_handler, reset, irq_handler
