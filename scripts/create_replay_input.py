"""Create a small reproducible replay input from a manifest split."""

import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=4)
    args = parser.parse_args()
    rows = list(csv.DictReader(args.manifest.open(encoding="utf-8", newline="")))
    rows = [row for row in rows if row["split"] == args.split][:args.limit]
    with args.output.open("w", encoding="utf-8") as stream:
        for index, row in enumerate(rows):
            event = {
                "source_id": "camera-demo",
                "session_id": "1c3ab594-7321-4d43-9e71-8f2cd5e1d542",
                "frame_index": index,
                "detection_id": 0,
                "captured_at": "2026-11-05T12:00:00.000Z",
                "bbox": [0, 0, 100, 100],
                "frame_path": str((args.manifest.parent / row["image"]).resolve()),
            }
            stream.write(json.dumps(event) + "\n")
    print(json.dumps({"samples": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
