# STM32 Winch Controller Makefile

TARGET = stm32_winch
MCU = stm32f407vg

# Toolchain
PREFIX = arm-none-eabi-
CC = $(PREFIX)gcc
CXX = $(PREFIX)g++
LD = $(PREFIX)ld
OBJCOPY = $(PREFIX)objcopy
SIZE = $(PREFIX)size

# Directories
SRC_DIR = Src
INC_DIR = Inc
STARTUP_DIR = startup
LINKER_DIR = linker
BUILD_DIR = build

# Sources
C_SOURCES = $(wildcard $(SRC_DIR)/*.c)
ASM_SOURCES = $(STARTUP_DIR)/startup_stm32f4xx.S
OBJECTS = $(C_SOURCES:$(SRC_DIR)/%.c=$(BUILD_DIR)/%.o)
OBJECTS += $(ASM_SOURCES:$(STARTUP_DIR)/%.s=$(BUILD_DIR)/%.o)

# Flags
ifeq ($(MOCK_MODE),1)
DEFINES = -DMOCK_MODE
CFLAGS = -Wall -Wextra -g -O0 $(DEFINES) -I$(INC_DIR)
LDFLAGS =
else
DEFINES = -DSTM32F407xx -DUSE_HAL_DRIVER
CFLAGS = -mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 \
         -Wall -Wextra -Os -g $(DEFINES) -I$(INC_DIR)
LDFLAGS = -T$(LINKER_DIR)/STM32F4xx_FLASH.ld -nostartfiles
endif

# Build
.PHONY: all clean flash

all: $(BUILD_DIR)/$(TARGET).elf

$(BUILD_DIR)/$(TARGET).elf: $(OBJECTS)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: $(STARTUP_DIR)/%.s
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

flash: $(BUILD_DIR)/$(TARGET).elf
	openocd -f interface/stlink-v2.cfg -f target/stm32f4x.cfg \
		-c "program $< verify reset exit"

clean:
	rm -rf $(BUILD_DIR)
