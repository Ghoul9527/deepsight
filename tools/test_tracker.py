"""Quick test: run DeepSight tracker on a video file and display results."""
from __future__ import annotations

import sys
import cv2
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "host" / "src"))

from deepsight_host.tracking.registry import get_tracker


def main(video_path: str):
    model_path = str(Path(__file__).parent.parent / "models" / "freediver_s.pt")

    tracker = get_tracker(
        "fast",
        confidence_threshold=0.3,
        iou_threshold=0.45,
        model_path=model_path,
    )

    print(f"Model: {model_path}")
    print(f"Tracker: {tracker}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: cannot open {video_path}")
        sys.exit(1)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    print(f"Video: {w}x{h}, {fps:.0f}fps, {total} frames")

    cv2.namedWindow("DeepSight Tracker", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("DeepSight Tracker", min(w, 960), min(h, 540))

    frame_idx = 0
    paused = False
    t0 = time.time()

    while True:
        if not paused:
            ret, frame = cap.read()
            if not ret:
                print(f"\nEnd of video. Press 'r' to replay or 'q' to quit.")
                paused = True
                continue
            frame_idx += 1

        t_start = time.time()
        try:
            result = tracker.process_frame(frame)
        except Exception as e:
            print(f"Error at frame {frame_idx}: {e}")
            continue
        t_track = (time.time() - t_start) * 1000

        if result is not None and (result.visible or result.confidence > 0):
            bx1, by1, bx2, by2 = result.bbox
            x1 = int(bx1 * w)
            y1 = int(by1 * h)
            x2 = int(bx2 * w)
            y2 = int(by2 * h)

            if result.visible:
                color = (0, 255, 0)  # green — detected
            else:
                color = (0, 165, 255)  # orange — motion predicted

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"diver {result.confidence:.2f}"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            if result.track_id >= 0:
                cv2.putText(frame, f"ID:{result.track_id}", (x1, y2 + 16),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # Overlay info
        elapsed = time.time() - t0
        if result is None:
            state = "N/A"
        elif result.lost:
            state = "LOST"
        elif not result.visible:
            state = "PREDICT"
        else:
            state = "TRACK"

        status = f"Frame: {frame_idx}/{total} | {t_track:.0f}ms | {state}"
        cv2.putText(frame, status, (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow("DeepSight Tracker", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord(' '):
            paused = not paused
        elif key == ord('r'):
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_idx = 0
            paused = False
            t0 = time.time()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python tools/test_tracker.py <video_path>")
        sys.exit(1)
    main(sys.argv[1])
