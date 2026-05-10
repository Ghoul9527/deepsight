"""Pico test fixtures — add pico dir to path for MicroPython-style imports."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
