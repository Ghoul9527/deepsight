#!/usr/bin/env python3
"""Lightweight YOLO-format bounding box annotator for single-class labeling.

Usage:
  # Annotate images from a directory
  python tools/annotator.py --input data/raw/images/ --output data/raw/

  # Extract frames from video (dedup on)
  python tools/annotator.py extract --input videos/ --output data/raw/ --interval 0.5

Controls:
  Mouse drag   Draw bounding box
  N / →        Next frame
  P / ←        Previous frame
  S            Save all boxes for current frame
  D            Delete last box on current frame
  C            Clear all boxes on current frame
  Q / Esc      Quit
  Space        Toggle play/pause (video only)
  + / -        Zoom in/out
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

CLASS_ID = 0
CLASS_NAME = "freediver"
DEFAULT_WIN = "Annotator"
BOX_COLORS = [(0, 255, 0), (0, 255, 255), (255, 0, 255), (255, 255, 0)]


class Annotator:
    def __init__(self, input_dir: str, output_dir: str):
        self._input = Path(input_dir)
        self._output = Path(output_dir)
        self._img_dir = self._output / "images"
        self._lbl_dir = self._output / "labels"
        self._img_dir.mkdir(parents=True, exist_ok=True)
        self._lbl_dir.mkdir(parents=True, exist_ok=True)

        self._files: list[Path] = []
        self._idx = 0
        self._frame: np.ndarray | None = None
        self._display: np.ndarray | None = None
        self._boxes: list[tuple[float, float, float, float]] = []
        self._drawing = False
        self._start_pt: tuple[int, int] | None = None
        self._zoom = 1.0
        self._cap: cv2.VideoCapture | None = None
        self._is_video = False
        self._playing = False

        self._scan_files()

    def _scan_files(self):
        exts = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
        video_exts = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}

        if self._input.is_file() and self._input.suffix.lower() in video_exts:
            self._is_video = True
            self._cap = cv2.VideoCapture(str(self._input))
            self._files = [self._input]
        elif self._input.is_dir():
            self._files = sorted(
                [p for p in self._input.iterdir()
                 if p.suffix.lower() in exts],
                key=lambda p: p.name,
            )
        else:
            raise FileNotFoundError(f"Not found: {self._input}")

        print(f"Found {len(self._files)} {'video' if self._is_video else 'images'}")

    def run(self):
        cv2.namedWindow(DEFAULT_WIN, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(DEFAULT_WIN, self._on_mouse)

        self._load_current()
        self._refresh_display()

        while True:
            cv2.imshow(DEFAULT_WIN, self._display)
            key = cv2.waitKey(30 if self._playing else 0) & 0xFF

            if key == 0:
                continue

            if key == ord('q') or key == 27:  # Q or Esc
                break
            elif key == ord('n') or key == 83:  # N or Right arrow
                self._next()
            elif key == ord('p') or key == 81:  # P or Left arrow
                self._prev()
            elif key == ord('s'):
                self._save()
            elif key == ord('d'):
                if self._boxes:
                    self._boxes.pop()
                    self._refresh_display()
            elif key == ord('c'):
                self._boxes.clear()
                self._refresh_display()
            elif key == ord(' ') and self._is_video:
                self._playing = not self._playing
            elif key == ord('+') or key == ord('='):
                self._zoom = min(4.0, self._zoom + 0.25)
                self._refresh_display()
            elif key == ord('-') or key == ord('_'):
                self._zoom = max(0.25, self._zoom - 0.25)
                self._refresh_display()

        cv2.destroyAllWindows()
        if self._cap:
            self._cap.release()

    def _next(self):
        self._save()
        if self._is_video:
            self._idx = min(self._idx + 1, int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT)) - 1)
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, self._idx)
        else:
            self._idx = min(self._idx + 1, len(self._files) - 1)
        self._load_current()
        self._refresh_display()

    def _prev(self):
        self._save()
        if self._is_video:
            self._idx = max(self._idx - 1, 0)
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, self._idx)
        else:
            self._idx = max(self._idx - 1, 0)
        self._load_current()
        self._refresh_display()

    def _load_current(self):
        if self._is_video:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, self._idx)
            ok, frame = self._cap.read()
            if not ok:
                return
            self._frame = frame
        else:
            if not self._files:
                return
            path = self._files[self._idx]
            self._frame = cv2.imread(str(path))

        self._boxes = self._load_labels()

    def _label_path(self) -> Path | None:
        if self._is_video:
            return self._lbl_dir / f"{self._input.stem}_{self._idx:06d}.txt"
        if self._files:
            return self._lbl_dir / f"{self._files[self._idx].stem}.txt"
        return None

    def _load_labels(self) -> list[tuple[float, float, float, float]]:
        lp = self._label_path()
        boxes = []
        if lp and lp.exists():
            with open(lp) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        boxes.append(tuple(float(x) for x in parts[1:5]))
        return boxes

    def _save(self):
        if self._frame is None:
            return
        lp = self._label_path()
        if lp is None or not self._boxes:
            return
        h, w = self._frame.shape[:2]
        with open(lp, "w") as f:
            for bx, by, bw_abs, bh_abs in self._boxes:
                cx = bx + bw_abs / 2.0
                cy = by + bh_abs / 2.0
                f.write(
                    f"{CLASS_ID} {cx / w:.6f} {cy / h:.6f} "
                    f"{bw_abs / w:.6f} {bh_abs / h:.6f}\n"
                )
        print(f"  Saved {len(self._boxes)} box(es) → {lp.name}")

    def _on_mouse(self, event, x, y, flags, param):
        if self._display is None:
            return
        dh, dw = self._display.shape[:2]
        fh, fw = self._frame.shape[:2] if self._frame is not None else (dh, dw)

        scale = self._zoom
        offset_x = int((dw - fw * scale) / 2)
        offset_y = int((dh - fh * scale) / 2)

        fx = (x - offset_x) / scale
        fy = (y - offset_y) / scale

        if event == cv2.EVENT_LBUTTONDOWN and 0 <= fx < fw and 0 <= fy < fh:
            self._drawing = True
            self._start_pt = (int(fx), int(fy))
        elif event == cv2.EVENT_MOUSEMOVE and self._drawing:
            if self._start_pt:
                self._refresh_display()
                sx, sy = self._start_pt
                cv2.rectangle(self._display,
                              self._to_display(sx, sy),
                              self._to_display(int(fx), int(fy)),
                              BOX_COLORS[0], 2)
        elif event == cv2.EVENT_LBUTTONUP and self._drawing:
            self._drawing = False
            if self._start_pt:
                sx, sy = self._start_pt
                ex, ey = int(fx), int(fy)
                x1, x2 = min(sx, ex), max(sx, ex)
                y1, y2 = min(sy, ey), max(sy, ey)
                if x2 - x1 > 4 and y2 - y1 > 4:
                    self._boxes.append((float(x1), float(y1),
                                        float(x2 - x1), float(y2 - y1)))
                self._refresh_display()

    def _to_display(self, fx: int, fy: int) -> tuple[int, int]:
        dh, dw = self._display.shape[:2]
        fh, fw = self._frame.shape[:2] if self._frame is not None else (dh, dw)
        scale = self._zoom
        ox = int((dw - fw * scale) / 2)
        oy = int((dh - fh * scale) / 2)
        return (int(fx * scale) + ox, int(fy * scale) + oy)

    def _refresh_display(self):
        if self._frame is None:
            return
        fh, fw = self._frame.shape[:2]

        new_w = int(fw * self._zoom)
        new_h = int(fh * self._zoom)
        scaled = cv2.resize(self._frame, (new_w, new_h))

        canvas_h = max(new_h, 480)
        canvas_w = max(new_w, 640)
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        canvas[:] = (30, 30, 30)

        ox = (canvas_w - new_w) // 2
        oy = (canvas_h - new_h) // 2
        canvas[oy:oy + new_h, ox:ox + new_w] = scaled

        for i, (bx, by, bw_abs, bh_abs) in enumerate(self._boxes):
            color = BOX_COLORS[i % len(BOX_COLORS)]
            x1 = int(bx * self._zoom) + ox
            y1 = int(by * self._zoom) + oy
            x2 = int((bx + bw_abs) * self._zoom) + ox
            y2 = int((by + bh_abs) * self._zoom) + oy
            cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
            cv2.putText(canvas, CLASS_NAME, (x1, max(y1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        info = self._status_text()
        for i, line in enumerate(info.split("\n")):
            cv2.putText(canvas, line, (6, 18 + i * 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

        self._display = canvas

    def _status_text(self) -> str:
        idx_str = f"{self._idx + 1}/{len(self._files)}"
        if self._is_video:
            idx_str += " (video)"
        name = self._files[self._idx].name if self._files else "-"
        if len(name) > 50:
            name = name[:47] + "..."
        return (
            f"File: {name}  [{idx_str}]\n"
            f"Boxes: {len(self._boxes)}  |  Zoom: {self._zoom:.0%}\n"
            f"N/→:next P/←:prev S:save D:del C:clear Q:quit"
        )


def extract_frames(input_dir: str, output_dir: str, interval: float = 0.5,
                   similarity_threshold: float = 0.95):
    """Extract frames from video files with dedup and save to output/images/."""
    input_path = Path(input_dir)
    out_img = Path(output_dir) / "images"
    out_img.mkdir(parents=True, exist_ok=True)

    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".MP4", ".MOV"}
    if input_path.is_file():
        videos = [input_path]
    else:
        videos = sorted([p for p in input_path.iterdir()
                         if p.suffix in video_exts])

    total_frames = 0
    for vpath in videos:
        cap = cv2.VideoCapture(str(vpath))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_interval = max(1, int(fps * interval))
        count = 0
        saved = 0
        prev_gray = None

        prefix = vpath.stem
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            count += 1
            if count % frame_interval != 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (128, 72))

            if prev_gray is not None and similarity_threshold > 0:
                sim = cv2.matchTemplate(gray, prev_gray, cv2.TM_CCOEFF_NORMED)[0, 0]
                if sim > similarity_threshold:
                    prev_gray = gray
                    continue

            prev_gray = gray
            out_name = f"{prefix}_{count:06d}.jpg"
            cv2.imwrite(str(out_img / out_name), frame)
            saved += 1

        cap.release()
        print(f"  {vpath.name}: {saved} frames extracted (every {frame_interval} frames)")
        total_frames += saved

    print(f"Done: {total_frames} total frames → {out_img}")


def main():
    parser = argparse.ArgumentParser(description="YOLO bounding box annotator")
    sub = parser.add_subparsers(dest="cmd")

    # Annotate
    p_ann = sub.add_parser("annotate", help="Annotate images")
    p_ann.add_argument("--input", "-i", required=True, help="Image directory or video file")
    p_ann.add_argument("--output", "-o", required=True,
                       help="Output dir (creates images/ and labels/)")

    # Extract
    p_ext = sub.add_parser("extract", help="Extract frames from video")
    p_ext.add_argument("--input", "-i", required=True,
                       help="Video file or directory of videos")
    p_ext.add_argument("--output", "-o", required=True, help="Output directory")
    p_ext.add_argument("--interval", "-t", type=float, default=0.5,
                       help="Extraction interval in seconds (default: 0.5)")
    p_ext.add_argument("--similarity", "-s", type=float, default=0.95,
                       help="Similarity threshold for dedup (default: 0.95)")

    args = parser.parse_args()

    if args.cmd == "extract":
        extract_frames(args.input, args.output, args.interval, args.similarity)
    elif args.cmd == "annotate":
        app = Annotator(args.input, args.output)
        app.run()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
