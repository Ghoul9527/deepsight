#!/usr/bin/env python3
"""Split annotated dataset into train/val/test and generate YOLO dataset.yaml.

Usage:
  python tools/split_dataset.py --input data/raw/ --output data/freediver/
"""

from __future__ import annotations

import argparse
import os
import random
import shutil
from pathlib import Path


def split_dataset(input_dir: str, output_dir: str,
                  train_ratio: float = 0.8, val_ratio: float = 0.1,
                  seed: int = 42):
    src_img = Path(input_dir) / "images"
    src_lbl = Path(input_dir) / "labels"

    if not src_img.exists():
        raise FileNotFoundError(f"Images directory not found: {src_img}")

    out = Path(output_dir)
    splits = {
        "train": train_ratio,
        "val": val_ratio,
        "test": 1.0 - train_ratio - val_ratio,
    }

    # Find all images that have corresponding labels
    pairs = []
    for img_path in sorted(src_img.iterdir()):
        if img_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
            continue
        lbl_path = src_lbl / f"{img_path.stem}.txt"
        pairs.append((img_path, lbl_path))

    if not pairs:
        print("No images found. Run the annotator first.")
        return

    random.seed(seed)
    random.shuffle(pairs)

    n = len(pairs)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    assignment = (
        ["train"] * n_train +
        ["val"] * n_val +
        ["test"] * (n - n_train - n_val)
    )
    random.shuffle(assignment)

    counts: dict[str, int] = {}
    for (img_path, lbl_path), split in zip(pairs, assignment, strict=True):
        dst_img = out / "images" / split
        dst_lbl = out / "labels" / split
        dst_img.mkdir(parents=True, exist_ok=True)
        dst_lbl.mkdir(parents=True, exist_ok=True)

        shutil.copy2(img_path, dst_img / img_path.name)
        if lbl_path.exists():
            shutil.copy2(lbl_path, dst_lbl / lbl_path.name)

        counts[split] = counts.get(split, 0) + 1

    # Write dataset.yaml
    yaml_path = out / "dataset.yaml"
    abs_out = out.resolve()
    yaml_path.write_text(f"""# Freediver detection dataset
path: {abs_out}
train: images/train
val: images/val
test: images/test

nc: 1
names:
  0: freediver
""")

    print(f"Split {n} samples:")
    for s in ["train", "val", "test"]:
        print(f"  {s}: {counts.get(s, 0)}")
    print(f"Wrote {yaml_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Split dataset into train/val/test for YOLO training")
    parser.add_argument("--input", "-i", required=True,
                        help="Input directory (contains images/ and labels/)")
    parser.add_argument("--output", "-o", required=True,
                        help="Output directory for split dataset")
    parser.add_argument("--train", type=float, default=0.8,
                        help="Train ratio (default: 0.8)")
    parser.add_argument("--val", type=float, default=0.1,
                        help="Validation ratio (default: 0.1)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    args = parser.parse_args()

    split_dataset(args.input, args.output, args.train, args.val, args.seed)


if __name__ == "__main__":
    main()
