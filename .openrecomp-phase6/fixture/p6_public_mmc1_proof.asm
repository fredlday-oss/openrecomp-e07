; ============================================================================
; OpenRecomp Phase-6 public MMC1 proof fixture (original work, Apache-2.0)
; ----------------------------------------------------------------------------
; The full behavioural MMC1/mapper-1 proof fixture for the Phase-6 bounded
; static-recompilation claim. It is a new revision over the P6-01 established
; fixture (which remains frozen as its own audited identity).
;
; The program runs entirely in the fixed last bank (PRG mode 3) and exercises
; the supported MMC1 contract:
;   * serial writes to all four MMC1 register windows ($8000/$A000/$C000/$E000);
;   * PRG bank switching across the four 16 KiB banks and reads from the
;     switched $8000-$BFFF window;
;   * CHR 4 KiB banking (mode 1) across eight 4 KiB banks observed through
;     PPUDATA reads from the CHR window;
;   * all four mirroring settings observed through aliased nametable reads;
;   * standard controller reads through $4016 into a per-frame transcript;
;   * palette/nametable/sprite graphics setup and NMI-driven per-frame update;
;   * the declared page-wrap run-exit service thunk at $02FF.
;
; The program contains no third-party or console-derived program data.
; ============================================================================

.equ PPUCTRL,    $2000
.equ PPUMASK,    $2001
.equ PPUSTATUS,  $2002
.equ OAMADDR,    $2003
.equ OAMDATA,    $2004
.equ PPUSCROLL,  $2005
.equ PPUADDR,    $2006
.equ PPUDATA,    $2007
.equ OAMDMA,     $4014
.equ JOY1,       $4016
.equ MMC1_CTRL,  $8000
.equ MMC1_CHR0,  $A000
.equ MMC1_CHR1,  $C000
.equ MMC1_PRG,   $E000
.equ PTR_LO,     $00
.equ PTR_HI,     $01
.equ frames,     $0300
.equ input0,     $0301
.equ prg_sum,    $0302
.equ chr_sum,    $0303
.equ mirror_sum, $0304
.equ nmi_count,  $0305
.equ irq_count,  $0306
.equ checksum,   $0307
.equ TARGET_FRAMES, 6
.equ EXIT_VEC,   $02FF

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
clear_ram:
        sta $0000,x
        sta $0100,x
        sta $0200,x
        sta $0300,x
        sta $0400,x
        sta $0500,x
        sta $0600,x
        sta $0700,x
        inx
        bne clear_ram
        lda #$0F
        jsr mmc1_write_ctrl
        lda #$00
        jsr mmc1_write_prg
        lda #$00
        jsr mmc1_write_chr0
        lda #$00
        jsr mmc1_write_chr1
        jsr wait_vblank
        jsr load_palette
        jsr load_nametable
        jsr setup_sprites
        lda #$1F
        jsr mmc1_write_ctrl
        lda #$80
        sta PPUCTRL
        lda #$1E
        sta PPUMASK

main_loop:
        lda frames
        cmp #TARGET_FRAMES
        bcs script_done
        jsr exercise_prg_banks
        jsr exercise_chr_banks
        jsr exercise_mirroring
        jmp main_loop

script_done:
        lda #$00
        sta checksum
        ldx #$00
sum_loop:
        lda $0400,x
        clc
        adc checksum
        sta checksum
        inx
        cpx #TARGET_FRAMES
        bne sum_loop
        lda checksum
        eor #$5A
        sta checksum
        jmp (EXIT_VEC)

; ============================================================================
; MMC1 serial writes (five writes, LSB first, per register window)
; ============================================================================
mmc1_write_ctrl:
        ldx #5
mmc1_control_loop:
        pha
        and #$01
        sta MMC1_CTRL
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
        sta MMC1_CHR0
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
        sta MMC1_CHR1
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
        sta MMC1_PRG
        pla
        lsr a
        dex
        bne mmc1_prg_loop
        rts

; ============================================================================
; PRG bank switching: select banks 0..3, read the switchable window
; ============================================================================
exercise_prg_banks:
        ldy #$00
prg_loop:
        tya
        jsr mmc1_write_prg
        lda $8000
        clc
        adc prg_sum
        sta prg_sum
        lda $8100
        clc
        adc prg_sum
        sta prg_sum
        iny
        cpy #$04
        bne prg_loop
        rts

; ============================================================================
; CHR 4 KiB banking: select banks 0..7, read CHR through PPUDATA
; ============================================================================
exercise_chr_banks:
        ldy #$00
chr_loop:
        tya
        jsr mmc1_write_chr0
        tya
        jsr mmc1_write_chr1
        lda #$00
        sta PPUADDR
        sta PPUADDR
        lda PPUDATA
        lda PPUDATA
        clc
        adc chr_sum
        sta chr_sum
        lda #$10
        sta PPUADDR
        lda #$00
        sta PPUADDR
        lda PPUDATA
        lda PPUDATA
        clc
        adc chr_sum
        sta chr_sum
        iny
        cpy #$08
        bne chr_loop
        rts

; ============================================================================
; Mirroring: select modes 0..3, observe aliased nametable reads
; ============================================================================
exercise_mirroring:
        ldy #$00
mirror_loop:
        tya
        ora #$1C
        jsr mmc1_write_ctrl
        lda #$20
        sta PPUADDR
        lda #$00
        sta PPUADDR
        lda #$11
        sta PPUDATA
        lda #$28
        sta PPUADDR
        lda #$00
        sta PPUADDR
        lda #$22
        sta PPUDATA
        lda #$24
        sta PPUADDR
        lda #$00
        sta PPUADDR
        lda PPUDATA
        lda PPUDATA
        clc
        adc mirror_sum
        sta mirror_sum
        lda #$2C
        sta PPUADDR
        lda #$00
        sta PPUADDR
        lda PPUDATA
        lda PPUDATA
        clc
        adc mirror_sum
        sta mirror_sum
        iny
        cpy #$04
        bne mirror_loop
        rts

; ============================================================================
; Graphics setup
; ============================================================================
wait_vblank:
        bit PPUSTATUS
wait_one:
        bit PPUSTATUS
        bpl wait_one
wait_two:
        bit PPUSTATUS
        bpl wait_two
        rts

load_palette:
        lda #$3F
        sta PPUADDR
        lda #$00
        sta PPUADDR
        ldx #$00
pal_loop:
        lda palette,x
        sta PPUDATA
        inx
        cpx #$20
        bne pal_loop
        rts

load_nametable:
        lda #$20
        sta PPUADDR
        lda #$00
        sta PPUADDR
        ldx #$00
nt_loop:
        lda nametable,x
        sta PPUDATA
        inx
        cpx #$20
        bne nt_loop
        rts

setup_sprites:
        lda #$00
        sta OAMADDR
        lda #$20
        sta OAMDATA
        lda #$01
        sta OAMDATA
        lda #$00
        sta OAMDATA
        lda #$20
        sta OAMDATA
        lda #$10
        sta OAMDATA
        lda #$23
        sta OAMDATA
        lda #$00
        sta OAMDATA
        lda #$30
        sta OAMDATA
        rts

read_controller:
        lda #$00
        sta input0
        ldx #$08
rc_loop:
        lda JOY1
        lsr a
        rol input0
        dex
        bne rc_loop
        rts

; ============================================================================
; NMI / IRQ
; ============================================================================
nmi_handler:
        pha
        txa
        pha
        tya
        pha
        lda #$01
        sta JOY1
        lda #$00
        sta JOY1
        jsr read_controller
        ldx frames
        cpx #TARGET_FRAMES
        bcs no_record
        lda input0
        sta $0400,x
no_record:
        lda #$02
        sta OAMDMA
        lda #$00
        sta PPUSCROLL
        sta PPUSCROLL
        lda #$80
        sta PPUCTRL
        inc nmi_count
        inc frames
        pla
        tay
        pla
        tax
        pla
        rti

irq_handler:
        pha
        inc irq_count
        pla
        rti

; ============================================================================
; Data
; ============================================================================
palette:
        .byte $0F, $01, $11, $21, $0F, $06, $16, $26
        .byte $0F, $09, $19, $29, $0F, $0A, $1A, $2A
        .byte $0F, $0B, $1B, $2B, $0F, $0C, $1C, $2C
        .byte $0F, $02, $12, $22, $0F, $07, $17, $27

nametable:
        .byte $00, $01, $02, $03, $00, $01, $02, $03
        .byte $00, $01, $02, $03, $00, $01, $02, $03
        .byte $00, $01, $02, $03, $00, $01, $02, $03
        .byte $00, $01, $02, $03, $00, $01, $02, $03

; ============================================================================
; Vectors
; ============================================================================
        .org $FFFA
        .word nmi_handler
        .word reset
        .word irq_handler
