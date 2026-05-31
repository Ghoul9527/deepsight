"""Minimal UART loopback test for Pi ? Pico connectivity.

Flash this to Pico, then on Pi run: screen /dev/ttyAMA0 115200
You should see a heartbeat JSON line every second.
If you type in screen, Pico will echo it back.

Wiring: Pico GP16 (UART0 TX) -> Pi GPIO15 (UART0 RX)
             Pico GP17 (UART0 RX) -> Pi GPIO14 (UART0 TX)
"""

import time
import sys
from machine import UART, Pin

uart = UART(0, baudrate=115200, tx=Pin(16), rx=Pin(17), bits=8, parity=None, stop=1)

print("Pico UART test started (UART0, GP16=TX->Pi, GP17=RX?Pi, 115200)")

while True:
    # Send heartbeat every second
    uart.write('{"type":"sys.heartbeat","node_id":"pico","test":true}\n')

    # Read and echo any incoming data
    while uart.any():
        b = uart.read(1)
        if b:
            uart.write(b)  # echo back

    time.sleep(1)
