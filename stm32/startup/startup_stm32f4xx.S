/* Startup for STM32F4xx.
 * Mock mode: minimal macOS/Linux startup.
 * Real mode: STM32F4 vector table + Reset_Handler.
 */
#ifdef MOCK_MODE
    .text
    .global _start
    .global _main
_start:
    bl _main
    /* exit syscall */
    mov X0, #0
    mov X16, #1
    svc #0x80
#else
    .syntax unified
    .cpu cortex-m4
    .thumb
    .global g_pfnVectors
    .global Default_Handler

    .section .isr_vector, "a"
    .type g_pfnVectors, %object
    .size g_pfnVectors, .-g_pfnVectors
g_pfnVectors:
    .word _estack
    .word Reset_Handler

    .section .text.Reset_Handler
    .weak Reset_Handler
    .type Reset_Handler, %function
Reset_Handler:
    ldr sp, =_estack
    bl main
    b .

    .section .text.Default_Handler
    .weak Default_Handler
    .type Default_Handler, %function
Default_Handler:
    b .
#endif
