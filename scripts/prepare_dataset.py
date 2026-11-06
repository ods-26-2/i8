"""Valida imagens, hashes e separação por peça, sessão e origem dos aumentos."""
import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

ALLOWED_SPLITS = {"train", "calibration", "test"}
KNOWN_LABELS = {"AMASSADO", "FURADO", "FURADO_AMASSADO"}
ALLOWED_LABELS = {"CONFORMING", "ANOMALY", *KNOWN_LABELS}
REQUIRED = {"product_id", "image", "label", "piece_id", "session_id", "split"}


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_dataset_path(base, value, description):
    relative = Path(value)
    if relative.is_absolute():
        raise ValueError(f"{description} deve usar caminho relativo ao manifesto")
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"{description} deve permanecer dentro do diretório do manifesto")
    return resolved


def validate_manifest(manifest, *, expected_count=None):
    from PIL import Image
    manifest = Path(manifest).resolve()
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or not REQUIRED.issubset(rows[0]):
        raise ValueError(f"manifesto requer amostras e campos {sorted(REQUIRED)}")
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(f"quantidade divergente: esperadas {expected_count}, encontradas {len(rows)}")
    identities, paths, hashes, sources = {}, {}, {}, {}
    inventory = []

    def bind(index, key, split, description):
        if key in index and index[key] != split:
            raise ValueError(f"{description} dividida entre splits: {key}")
        index[key] = split

    for row in rows:
        if any(not isinstance(row.get(k), str) or not row[k].strip() for k in REQUIRED):
            raise ValueError("campos obrigatórios não podem ser vazios")
        split, label, product = row["split"], row["label"], row["product_id"]
        if split not in ALLOWED_SPLITS or label not in ALLOWED_LABELS:
            raise ValueError("split/rótulo inválido")
        if split == "train" and label == "ANOMALY":
            raise ValueError("anomalia desconhecida não pode treinar o classificador conhecido")
        path = resolve_dataset_path(manifest.parent, row["image"], "imagem")
        if not path.is_file():
            raise ValueError(f"imagem ausente: {path}")
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, ValueError) as exc:
            raise ValueError(f"imagem ilegível: {path}") from exc
        digest = file_hash(path)
        for kind, identity in (("peça", row["piece_id"]), ("sessão", row["session_id"])):
            bind(identities, (kind, product, identity), split, kind)
        if str(path) in paths:
            raise ValueError("mesma imagem repetida no manifesto")
        bind(paths, str(path), split, "imagem")
        bind(hashes, digest, split, "imagem duplicada por hash")
        inventory.append({**row, "sha256": digest, "size_bytes": path.stat().st_size})
    # Segunda passagem também detecta origem declarada depois de seu aumento.
    for row in rows:
        if row.get("source_image"):
            source = resolve_dataset_path(manifest.parent, row["source_image"], "origem do aumento")
            if not source.is_file():
                raise ValueError(f"origem do aumento ausente: {source}")
            split = row["split"]
            bind(sources, str(source), split, "origem do aumento")
            if str(source) in paths and paths[str(source)] != split:
                raise ValueError("aumento e imagem de origem divididos entre splits")
            digest = file_hash(source)
            if digest in hashes and hashes[digest] != split:
                raise ValueError("aumento e hash da origem divididos entre splits")
    return {"status": "MANIFESTO_VALIDADO", "manifest_sha256": file_hash(manifest),
            "samples": len(rows), "splits": dict(Counter(r["split"] for r in rows)),
            "labels": dict(Counter(r["label"] for r in rows)), "images": inventory,
            "limite": "Validação estrutural; origem real e rótulos exigem aceite humano."}


def validate_predictions(rows, inventory, split):
    if not rows:
        raise ValueError("arquivo de previsões vazio")
    products = {r.get("product_id") for r in rows}
    if len(products) != 1 or None in products:
        raise ValueError("previsões devem identificar um único produto")
    expected = {r["image"]: r for r in inventory["images"]
                if r["split"] == split and r["product_id"] in products}
    seen = set()
    for row in rows:
        image = row.get("image")
        original = expected.get(image)
        if image in seen or original is None:
            raise ValueError("imagem repetida ou fora do split/produto esperado")
        seen.add(image)
        if any(row.get(k) != original[k] for k in REQUIRED):
            raise ValueError("identidade/rótulo da previsão diverge do manifesto")
        if row.get("manifest_sha256") != inventory["manifest_sha256"] or row.get("image_sha256") != original["sha256"]:
            raise ValueError("hash da previsão diverge do manifesto/imagem")
        artifacts = row.get("artifacts_sha256", {})
        if not all(isinstance(artifacts.get(k), str) and len(artifacts[k]) == 64
                   and all(c in "0123456789abcdef" for c in artifacts[k])
                   for k in ("normal", "classifier", "taxonomy")):
            raise ValueError("previsão deve identificar hashes dos artefatos usados")
        if artifacts != rows[0].get("artifacts_sha256") or row.get("artifact_versions") != rows[0].get("artifact_versions"):
            raise ValueError("previsões misturam versões/artefatos")
        if not isinstance(row.get("artifact_versions"), dict):
            raise ValueError("previsão deve identificar versões dos artefatos")
        versions = row["artifact_versions"]
        if any(not isinstance(versions.get(k), str) or not versions[k].strip()
               for k in ("product_id", "normal_model_version", "classifier_version", "taxonomy_version", "policy_version")):
            raise ValueError("versões incompletas nas previsões")
        if versions["product_id"] != row["product_id"]:
            raise ValueError("produto dos artefatos diverge da previsão")
        for field in ("confidence", "similarity"):
            value = row.get(field)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("score inválido na previsão")
        result, defect = row.get("predicted_result"), row.get("predicted_defect_class")
        if result not in {"CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN"}:
            raise ValueError("resultado previsto inválido")
        if (result == "NON_CONFORMING" and defect not in KNOWN_LABELS) or (result != "NON_CONFORMING" and defect is not None):
            raise ValueError("classe prevista incompatível com o resultado")
    if seen != set(expected):
        raise ValueError("previsões incompletas para o split/produto")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()
    try:
        report = validate_manifest(args.manifest, expected_count=args.expected_count)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"BLOQUEADO: {exc}") from exc
    if args.inventory:
        args.inventory.parent.mkdir(parents=True, exist_ok=True)
        args.inventory.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"manifesto válido: {report['samples']} amostras; splits={sorted(report['splits'])}")


if __name__ == "__main__":
    main()
