/* Linker script stub for STM32F4xx.
 * In real builds, use the STM32CubeF4-generated linker script.
 */

#ifdef MOCK_MODE
SECTIONS
{
    . = 0x10000;
    .text : { *(.text) }
    .data : { *(.data) }
    .bss  : { *(.bss) }
}
#else
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 1024K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector :
    {
        KEEP(*(.isr_vector))
    } >FLASH

    .text :
    {
        *(.text*)
        *(.rodata*)
    } >FLASH

    .data :
    {
        _sdata = .;
        *(.data*)
        _edata = .;
    } >RAM AT>FLASH

    .bss :
    {
        _sbss = .;
        *(.bss*)
        _ebss = .;
    } >RAM
}
#endif
