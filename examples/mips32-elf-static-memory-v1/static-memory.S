.set noreorder
.set noat

.section .text,"ax",@progbits
.globl static_memory_main
.ent static_memory_main
.type static_memory_main, @function
static_memory_main:
    addiu $8,  $0, 0x2000
    lw    $9,  0($8)
    addiu $10, $0, 0x3000
    lw    $11, 0($10)
    addu  $12, $9, $11
    sw    $12, 0($10)
    addiu $13, $0, 0x3010
    lw    $14, 0($13)
    addu  $2,  $12, $14
    sw    $2,  0($13)
    jr    $31
    nop
.size static_memory_main, .-static_memory_main
.end static_memory_main

.section .openrecomp_rodata,"a",@progbits
.align 2
ro_word:
    .word 0x11223344

.section .openrecomp_data,"aw",@progbits
.align 2
data_word:
    .word 0x01020304

.section .openrecomp_bss,"aw",@nobits
.align 2
bss_word:
    .space 4
