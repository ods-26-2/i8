"""Organize a labeled image collection into the I8 split layout.

The source collection is never modified. Images are copied into split folders
and a manifest with paths relative to its own directory is generated.
"""

import argparse
import csv
import hashlib
import shutil
from pathlib import Path


LABEL_DIRECTORIES = {
    "AMASSADO": "amassado",
    "FURADO": "furo",
    "FURADO_AMASSADO": "furo_e_amassado",
}
REQUIRED_COLUMNS = {
    "product_id",
    "image",
    "label",
    "piece_id",
    "session_id",
    "split",
}
VALID_SPLITS = {"train", "calibration", "test"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_source(source_root: Path, row: dict[str, str]) -> Path:
    image = Path(row["image"]).name
    label = row["label"]
    if label == "CONFORMING":
        directories = (
            source_root / "train" / "normal",
            source_root / "test" / "normal",
        )
    else:
        directories = (source_root / "test" / LABEL_DIRECTORIES[label],)

    candidates = [directory / image for directory in directories if (directory / image).is_file()]
    if not candidates:
        raise ValueError(f"imagem não encontrada para {image!r} ({label})")
    if len({digest(candidate) for candidate in candidates}) != 1:
        raise ValueError(f"fontes diferentes para o mesmo arquivo: {image!r}")
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--exclude-image", action="append", default=[])
    args = parser.parse_args()

    with args.csv.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or not REQUIRED_COLUMNS.issubset(rows[0]):
        raise SystemExit(f"CSV deve conter: {sorted(REQUIRED_COLUMNS)}")

    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_root / "manifest.csv"
    fieldnames = ["product_id", "image", "label", "piece_id", "session_id", "split"]
    organized = []
    for row in rows:
        if Path(row["image"]).name in set(args.exclude_image):
            continue
        if row["split"] not in VALID_SPLITS:
            raise SystemExit(f"split inválido: {row['split']}")
        if row["label"] not in {"CONFORMING", *LABEL_DIRECTORIES}:
            raise SystemExit(f"label inválido: {row['label']}")
        source = find_source(args.source_root, row)
        subdirectory = "normal" if row["split"] == "train" and row["label"] == "CONFORMING" else ""
        destination = args.output_root / row["split"] / subdirectory / Path(row["image"]).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and digest(destination) != digest(source):
            raise SystemExit(f"destino já existe com conteúdo diferente: {destination}")
        if not destination.exists():
            shutil.copy2(source, destination)
        organized.append({**row, "image": destination.relative_to(args.output_root).as_posix()})

    with manifest_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(organized)
    print(f"organizadas={len(organized)}")
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()
