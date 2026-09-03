ENTRY(static_memory_main)
SECTIONS
{
  . = 0x00001000;
  .text : ALIGN(4) { *(.text*) }

  . = 0x00002000;
  .rodata : ALIGN(4) { *(.openrecomp_rodata) }

  . = 0x00003000;
  .data : ALIGN(4) { *(.openrecomp_data) }
  .bss (NOLOAD) : ALIGN(4) { *(.openrecomp_bss) }

  /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.gnu.attributes) *(.pdr) }
}
