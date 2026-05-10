"""DeepSight CLI — unified development tooling."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

logger = logging.getLogger("tools.cli")


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging")
def main(debug: bool):
    """DeepSight — Distributed Underwater ROV Filming System CLI."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


@main.command()
@click.option("--mock/--no-mock", default=True, help="Use mock hardware (default: true)")
@click.option("--profile", default="dev", help="Config profile to use")
def start(mock: bool, profile: str):
    """Start all DeepSight nodes."""
    from deepsight_tools.orchestrator import Orchestrator

    orch = Orchestrator()
    if mock:
        click.echo("Starting in MOCK mode (no hardware required)...")
        orch.start_all_mock()
    else:
        click.echo("Real hardware mode — not yet implemented for Phase 1")


@main.command()
def stop():
    """Stop all running DeepSight nodes."""
    click.echo("Stopping all nodes...")
    # Future: send shutdown signals


@main.command()
@click.argument("target", type=click.Choice(["pico", "stm32"]))
def flash(target: str):
    """Flash firmware to a device."""
    click.echo(f"Flashing {target}...")
    if target == "pico":
        click.echo("Pico flashing: copy .uf2 file to RPI-RP2 drive")
        click.echo("Run: cp pico/build/firmware.uf2 /Volumes/RPI-RP2/")
    elif target == "stm32":
        click.echo("STM32 flashing: use ST-Link or OpenOCD")
        click.echo("Run: cd stm32 && make flash")


@main.command()
@click.argument("target", type=click.Choice(["pi"]))
def deploy(target: str):
    """Deploy code to a remote device."""
    if target == "pi":
        click.echo("Deploying to Raspberry Pi...")
        click.echo("Run: rsync -avz pi/ pi@raspberrypi.local:~/deepsight/pi/")


@main.command()
@click.argument("port", default="/dev/tty.usbmodem*")
def monitor(port: str):
    """Open serial monitor for a device."""
    click.echo(f"Serial monitor on {port} (Ctrl+] to quit)")
    try:
        import serial
        ser = serial.Serial(port, 115200, timeout=1)
        while True:
            line = ser.readline()
            if line:
                sys.stdout.write(line.decode("utf-8", errors="replace"))
                sys.stdout.flush()
    except ImportError:
        click.echo("pyserial not installed: pip install pyserial")
    except KeyboardInterrupt:
        click.echo("\nMonitor stopped.")


@main.command()
@click.argument("output", default="logs/telemetry/")
def record(output: str):
    """Record telemetry streams to file."""
    from deepsight_host.logging.telemetry_recorder import TelemetryRecorder
    recorder = TelemetryRecorder(output)
    recorder.start()
    click.echo(f"Recording telemetry to {output} (Ctrl+C to stop)")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        recorder.stop()
        click.echo("Recording stopped.")


@main.command()
@click.argument("file_path", type=click.Path(exists=True))
def replay(file_path: str):
    """Replay a recorded telemetry session."""
    from deepsight_host.logging.replay import ReplayEngine
    engine = ReplayEngine(file_path)
    engine.load()
    click.echo(f"Replaying {file_path} ({len(engine._entries)} entries)")
    # Future: feed into replay UI


@main.command()
def test():
    """Run the test suite."""
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"])


@main.command()
@click.option("--port", default=5100, help="UDP listen port (default: 5100)")
@click.option("--video-port", default=8554, help="Video server port (default: 8554)")
def emu_console(port: int, video_port: int):
    """Launch the Signal Emulation Console (EmuConsole)."""
    from deepsight_tools.emu_console.app import main as emu_main

    click.echo(f"EmuConsole starting on UDP :{port}, video :{video_port}")
    emu_main()


@main.command()
def info():
    """Show project information."""
    click.echo("DeepSight — Distributed Underwater ROV Filming System")
    click.echo("=" * 50)
    click.echo("Nodes: host | pi | pico | stm32")
    click.echo("Protocol: JSON over UDP/WS/UART")
    click.echo("Mock mode: ready (no hardware required)")
    click.echo("Quickstart: deepsight-cli start --mock")


if __name__ == "__main__":
    main()
