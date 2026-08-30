ENTRY(_start)
SECTIONS
{
  . = 0x00010000;
  .text : { *(.text*) }
  . = ALIGN(16);
  .rodata : { *(.rodata*) }
  . = ALIGN(16);
  .data : { *(.data*) }
  . = ALIGN(16);
  .bss : { *(.bss*) *(COMMON) }
}
