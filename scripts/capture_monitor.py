#!/usr/bin/env python3
"""HDMI capture monitor — 30s frame health check, non-interactive.
Usage: python3 capture_monitor.py <device> <label> [duration_sec]
"""
import sys
import time
import json
import numpy as np
import cv2

device = sys.argv[1]
label = sys.argv[2]
duration = int(sys.argv[3]) if len(sys.argv) > 3 else 30

cap = cv2.VideoCapture(device)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
cap.set(cv2.CAP_PROP_FPS, 60)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

if not cap.isOpened():
    print(f"FATAL:Cannot open {device}")
    sys.exit(1)

actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
actual_fps = cap.get(cv2.CAP_PROP_FPS)
fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
fourcc = "".join(chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4))
print(f"DEVICE:{label} {actual_w}x{actual_h}@{actual_fps:.1f}fps codec={fourcc}")

total = 0
black = 0
dark = 0
errors = 0
prev_ts = time.time()
start_ts = prev_ts
gaps = 0
brightness_samples = []

while time.time() - start_ts < duration:
    ret, frame = cap.read()
    now = time.time()

    if not ret or frame is None:
        errors += 1
        continue

    total += 1
    interval = now - prev_ts
    prev_ts = now

    mean_b = float(np.mean(frame))
    brightness_samples.append(mean_b)
    if mean_b < 5:
        black += 1
    elif mean_b < 30:
        dark += 1

    if interval > (1.0 / max(actual_fps, 1)) * 2.5:
        gaps += 1

cap.release()
elapsed = time.time() - start_ts

samples = np.array(brightness_samples) if brightness_samples else np.array([0])
result = {
    "label": label,
    "device": device,
    "resolution": f"{actual_w}x{actual_h}",
    "target_fps": actual_fps,
    "duration_s": round(elapsed, 1),
    "total_frames": total,
    "effective_fps": round(total / max(elapsed, 0.001), 2),
    "black_pct": round(100 * black / max(total, 1), 1),
    "dark_pct": round(100 * dark / max(total, 1), 1),
    "frame_time_gaps": gaps,
    "read_errors": errors,
    "brightness_mean": round(float(np.mean(samples)), 1),
    "brightness_min": round(float(np.min(samples)), 1),
    "brightness_max": round(float(np.max(samples)), 1),
}
print("RESULT:" + json.dumps(result))
