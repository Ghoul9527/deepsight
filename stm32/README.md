# STM32 Winch Controller

Target: STM32F4xx (STM32F407VG or similar)
Toolchain: arm-none-eabi-gcc
HAL: STM32F4xx HAL

## Build

```bash
# Requires arm-none-eabi-gcc in PATH
make
```

## Mock Mode

Define `MOCK_MODE=1` to build without hardware dependencies.
In mock mode, all peripherals are simulated.

```bash
make MOCK_MODE=1
```
