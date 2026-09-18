/*
 * OpenRecomp Phase 4 fixture linker script (P4-07).
 * Original work; Apache License 2.0 (repository LICENSE).
 *
 * Single contiguous load image based at 0x00001000; .bss is zero-filled by
 * the runtime loader.  The layout mirrors the Phase-3 fixture convention so
 * the same bounded ingestion/translation layers apply.
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
