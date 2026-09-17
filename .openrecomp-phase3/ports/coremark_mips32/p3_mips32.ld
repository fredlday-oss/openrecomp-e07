/*
 * OpenRecomp Phase 3 - linker script for the freestanding MIPS32 CoreMark
 * fixture (OpenRecomp-authored).  The image is based at 0x00001000 and keeps
 * a single contiguous load image; .bss is zero-initialised by the runtime
 * loader (the guest entry stub does not rely on any pre-zeroed register).
 */
ENTRY(_start)

SECTIONS
{
    . = 0x00001000;

    .text : ALIGN(16) {
        *(.text .text.*)
    }

    .rodata : ALIGN(16) {
        *(.rodata .rodata.*)
        *(.sdata2 .sdata2.*)
    }

    .data : ALIGN(16) {
        *(.data .data.*)
        *(.sdata .sdata.*)
        *(.got .got.*)
    }

    .bss : ALIGN(16) {
        *(.bss .bss.*)
        *(COMMON)
    }

    /DISCARD/ : {
        *(.pdr)
    }
}
