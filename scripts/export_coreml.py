"""Export the trained detector for the optional macOS Core ML backend."""
import argparse
from ultralytics import YOLO

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="models/freediver_s.pt")
    args = parser.parse_args()
    YOLO(args.model).export(format="coreml", imgsz=640, batch=1, dynamic=False,
                            nms=False, half=True, device="cpu")
