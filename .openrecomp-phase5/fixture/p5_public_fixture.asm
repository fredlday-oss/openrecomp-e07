; ============================================================================
; OpenRecomp Phase-5 public NES fixture (original work, Apache-2.0)
; ----------------------------------------------------------------------------
; An original deterministic NROM-128 (mapper 0) program authored for the
; OpenRecomp Phase-5 NES static-recompilation proof. It contains no
; third-party or console-derived program data.
;
; The program exercises the bounded Phase-5 feature set:
;   * documented 6502 instructions and addressing modes (zero page, absolute,
;     indexed, indirect, relative branches, stack, RMW, flags);
;   * reset/NMI/IRQ vectors, one software BRK through the IRQ vector;
;   * PPU register window use: PPUCTRL/PPUMASK/PPUSTATUS/PPUSCROLL/PPUADDR/
;     PPUDATA/OAMADDR/OAMDATA and OAM DMA ($4014);
;   * standard controller serial reads through $4016 into a per-frame
;     transcript at $0400..$0407;
;   * a declared indirect service thunk at $02FF (the NMOS page-wrap vector
;     layout) used only for the bounded run-exit service;
;   * SED/ADC binary-only behaviour of the NES 2A03 (decimal mode ignored).
;
; The run observes eight NMI frames against a recorded controller transcript.
; ============================================================================

; --- PPU / APU / controller registers --------------------------------------
.equ PPUCTRL,    $2000
.equ PPUMASK,    $2001
.equ PPUSTATUS,  $2002
.equ OAMADDR,    $2003
.equ OAMDATA,    $2004
.equ PPUSCROLL,  $2005
.equ PPUADDR,    $2006
.equ PPUDATA,    $2007
.equ OAMDMA,     $4014
.equ APUSTATUS,  $4015
.equ JOY1,       $4016
.equ JOY2,       $4017

; --- zero page layout --------------------------------------------------------
.equ PTR_LO,     $00
.equ PTR_HI,     $01
.equ IDX_BASE,   $10

; --- RAM variables -----------------------------------------------------------
.equ frames,     $0300
.equ input0,     $0301
.equ state_a,    $0302
.equ state_x,    $0303
.equ nmi_count,  $0304
.equ irq_count,  $0305
.equ checksum,   $0306
.equ scratch,    $0307
.equ TARGET_FRAMES, 8
.equ SPRITE_X,   $0203
.equ EXIT_VEC,   $02FF

; ============================================================================
; Reset entry
; ============================================================================
.org $C000
reset:
        sei
        cld
        ldx #$FF
        txs
        inx
        stx PPUCTRL
        stx PPUMASK
        lda #$00
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
        jsr wait_vblank
        jsr load_palette
        jsr load_nametable
        jsr setup_sprites
        lda #$00
        sta frames
        sta input0
        sta state_a
        sta state_x
        sta nmi_count
        sta irq_count
        sta checksum
        sta scratch
        ; indirect-indexed read across a page boundary: (zp),Y with Y=9
        lda #<data_page
        sta PTR_LO
        lda #>data_page
        sta PTR_HI
        ldy #$09
        lda (PTR_LO),y
        sta scratch
        ; indexed-indirect read: (zp,X)
        lda #<edge_table
        sta IDX_BASE
        lda #>edge_table
        sta IDX_BASE+1
        ldx #$00
        lda (IDX_BASE,x)
        clc
        adc scratch
        sta scratch
        ; absolute,X read across a page boundary
        ldx #$08
        lda data_page,x
        sta state_x
        ; absolute,Y read
        ldy #$01
        lda data_page,y
        ora state_x
        sta state_x
        ; SBC / CMP / carry chain
        sec
        lda #$20
        sbc #$01
        cmp #$1F
        bne sub_bad
        jsr mark_ok
sub_bad:
        ; CLV and BVC
        clv
        bvc clv_ok
        lda #$00
        sta checksum
clv_ok:
        ; 2A03 decimal mode is ignored: SED followed by binary ADC
        sed
        clc
        lda #$0A
        adc #$01
        sta checksum
        cld
        ; one software BRK through the IRQ vector
        brk
        nop
        ; zero-page indexed forms
        ldx #$03
        stx $18,y
        ldy #$02
        sty $20,x
        ldx #$02
        lda $10,x
        ldy #$01
        ldx $10,y
        ldy $10,x
        cpy #$00
        ; enable NMI and rendering
        lda #$80
        sta PPUCTRL
        lda #$1E
        sta PPUMASK
main_loop:
        lda frames
        cmp #TARGET_FRAMES
        bcs script_done
        jsr mix
        jmp main_loop

; ============================================================================
; Deterministic script completion: transcript checksum and run-exit service
; ============================================================================
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
        php
        plp
        ldy #$03
delay:
        dey
        bne delay
        iny
        lda #$00
        sta (IDX_BASE,x)
        jmp (EXIT_VEC)

; ============================================================================
; Subroutines
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
        lda #$00
        sta APUSTATUS
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

mix:
        pha
        clc
        lda checksum
        adc #$07
        asl a
        sta checksum
        pla
        rts

mark_ok:
        lda #$01
        sta scratch
        rts

; ============================================================================
; NMI handler: one controller read and state update per frame
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
        lda input0
        and #$01
        beq no_a
        lda state_a
        clc
        adc #$03
        sta state_a
no_a:
        lda input0
        and #$80
        beq no_right
        inc SPRITE_X
no_right:
        lda input0
        and #$40
        beq no_left
        dec SPRITE_X
no_left:
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

; ============================================================================
; IRQ/BRK handler
; ============================================================================
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

        .org $C3F8
data_page:
        .byte $11, $22, $33, $44, $55, $66, $77, $88
        .byte $99, $AA, $BB, $CC, $DD, $EE, $F0, $0F
edge_table:
        .byte $03, $00

; ============================================================================
; Vectors
; ============================================================================
        .org $FFFA
        .word nmi_handler
        .word reset
        .word irq_handler
