"""Deploy a file to Pico using raw serial REPL protocol.

Handles the case where the Pico is running a control loop that floods UART TX.
"""

import serial
import sys
import time


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyAMA0"
    src_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/control_loop.py"
    dest_name = sys.argv[3] if len(sys.argv) > 3 else "control_loop.py"

    ser = serial.Serial(port, 115200, timeout=0.3)

    # Drain any pending input
    ser.reset_input_buffer()
    time.sleep(0.2)
    ser.reset_input_buffer()

    # Send Ctrl-C rapidly to trigger KeyboardInterrupt on Pico
    for _ in range(20):
        ser.write(b"\r\x03")
        time.sleep(0.03)

    # Wait and drain output - if Pico stopped, output will stop
    time.sleep(1.5)
    ser.reset_input_buffer()

    # Try to send a simple command to check REPL
    ser.write(b"\r\nprint(42)\r\n")
    time.sleep(1.0)
    data = ser.read(4096)
    print("Initial response:", repr(data[:200]))

    # If we see REPL-like output, try to enter raw REPL
    ser.write(b"\r\x01")
    time.sleep(0.3)
    data = ser.read(256)
    print("After Ctrl-A:", repr(data[:200]))

    # Try the soft reset approach via raw REPL paste mode
    # Send Ctrl-A again for raw REPL
    ser.write(b"\r\x01")
    time.sleep(0.3)
    ser.read(256)  # drain

    # Read the source file
    with open(src_path, "r") as f:
        content = f.read()

    # Raw REPL: send Ctrl-A, then paste mode command
    # Enter paste mode: Ctrl-E
    ser.write(b"\x05")  # Ctrl-E for paste mode
    time.sleep(0.3)
    resp = ser.read(256)
    print("Paste mode response:", repr(resp[:100]))

    # Write file command
    escaped = content.replace("\\", "\\\\").replace("'", "\\'")
    cmd = f"with open('{dest_name}', 'w') as f:\n    f.write('''{escaped}''')\n"

    # Send in paste mode
    ser.write(cmd.encode())
    ser.write(b"\x04")  # Ctrl-D to end paste mode
    time.sleep(2.0)
    resp = ser.read(4096)
    print("Write response:", repr(resp[:300]))

    # Soft reset
    ser.write(b"\x04")  # Ctrl-D for soft reset
    time.sleep(1.0)
    ser.reset_input_buffer()
    final = ser.read(2048)
    print("Final:", repr(final[:300]))

    ser.close()


if __name__ == "__main__":
    main()
