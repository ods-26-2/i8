"""Dados sintéticos temporários testam validações; nunca são evidência industrial."""
import copy
import csv
import json
import sys
from pathlib import Path

from PIL import Image
import pytest

from scripts.prepare_dataset import validate_manifest, validate_predictions
from scripts.calibrate_policy import select_thresholds
from scripts.package_demo import build_demo
from scripts import evaluate


def write_manifest(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["product_id", "image", "label", "piece_id", "session_id", "split", "source_image"])
        writer.writeheader()
        writer.writerows(rows)


@pytest.fixture
def dataset(tmp_path):
    labels = [("train", "CONFORMING"), ("train", "AMASSADO"),
              ("calibration", "CONFORMING"), ("calibration", "AMASSADO"),
              ("test", "CONFORMING"), ("test", "AMASSADO"),
              ("test", "ANOMALY"), ("test", "FURADO")]
    rows = []
    for index, (split, label) in enumerate(labels):
        image = f"sintetica-{index}.png"
        Image.new("RGB", (7, 5), (index * 25, 20, 30)).save(tmp_path / image)
        rows.append(dict(product_id="produto-teste", image=image, label=label,
                         piece_id=f"p{index}", session_id=f"s{index}", split=split, source_image=""))
    manifest = tmp_path / "manifest.csv"
    write_manifest(manifest, rows)
    return manifest, rows


def predictions(inventory, split="test"):
    result = []
    for row in inventory["images"]:
        if row["split"] != split:
            continue
        label = row["label"]
        expected = label if label in {"CONFORMING", "ANOMALY"} else "NON_CONFORMING"
        predicted = "UNCERTAIN" if label == "FURADO" else expected
        result.append({**row, "image_sha256": row["sha256"],
            "manifest_sha256": inventory["manifest_sha256"],
            "artifacts_sha256": {k: "a" * 64 for k in ("normal", "classifier", "taxonomy", "policy")},
            "artifact_versions": {"product_id": "produto-teste", "normal_model_version": "teste",
                                  "classifier_version": "teste", "taxonomy_version": "teste", "policy_version": "teste"},
            "predicted_result": predicted,
            "predicted_defect_class": label if predicted == "NON_CONFORMING" else None,
            "expected_result": expected,
            "expected_defect_class": label if expected == "NON_CONFORMING" else None,
            "confidence": 0.9, "similarity": 0.9 if label == "CONFORMING" else 0.1})
    return result


def test_inventory_has_image_hashes_and_exact_count(dataset):
    report = validate_manifest(dataset[0], expected_count=8)
    assert report["samples"] == 8 and report["labels"]["ANOMALY"] == 1
    assert all(len(row["sha256"]) == 64 for row in report["images"])
    with pytest.raises(ValueError, match="quantidade"):
        validate_manifest(dataset[0], expected_count=369)


@pytest.mark.parametrize("field", ["piece_id", "session_id"])
def test_identity_cannot_cross_splits(dataset, field):
    manifest, rows = dataset
    rows[-1][field] = rows[0][field]
    write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="splits"):
        validate_manifest(manifest)


def test_duplicate_hash_cannot_cross_splits(dataset):
    manifest, rows = dataset
    (manifest.parent / rows[-1]["image"]).write_bytes((manifest.parent / rows[0]["image"]).read_bytes())
    with pytest.raises(ValueError, match="hash"):
        validate_manifest(manifest)


@pytest.mark.parametrize("reverse", [False, True])
def test_augmentation_origin_cannot_leak_regardless_of_row_order(dataset, reverse):
    manifest, rows = dataset
    rows[-1]["source_image"] = rows[0]["image"]
    write_manifest(manifest, list(reversed(rows)) if reverse else rows)
    with pytest.raises(ValueError, match="origem divididos"):
        validate_manifest(manifest)


def test_non_image_bytes_are_rejected(dataset):
    manifest, rows = dataset
    (manifest.parent / rows[0]["image"]).write_text("não é imagem")
    with pytest.raises(ValueError, match="ilegível"):
        validate_manifest(manifest)


@pytest.mark.parametrize("path", ["../fora.png", "C:/dados/fora.png"])
def test_manifest_paths_must_stay_under_manifest_directory(dataset, path):
    manifest, rows = dataset
    rows[0]["image"] = path
    write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="manifesto|diretório"):
        validate_manifest(manifest)


def test_unknown_anomaly_cannot_train_known_classifier(dataset):
    manifest, rows = dataset
    rows[0]["label"] = "ANOMALY"
    write_manifest(manifest, rows)
    with pytest.raises(ValueError, match="treinar"):
        validate_manifest(manifest)


@pytest.mark.parametrize("mutation", ["hash", "split", "missing", "duplicate", "artifacts"])
def test_predictions_must_match_complete_manifest_split(dataset, mutation):
    inventory = validate_manifest(dataset[0])
    rows = predictions(inventory)
    if mutation == "hash": rows[0]["image_sha256"] = "b" * 64
    elif mutation == "split": rows[0]["split"] = "calibration"
    elif mutation == "missing": rows.pop()
    elif mutation == "duplicate": rows.append(copy.deepcopy(rows[0]))
    else: rows[0]["artifacts_sha256"] = {}
    with pytest.raises(ValueError):
        validate_predictions(rows, inventory, "test")


def test_calibration_without_unknown_anomaly_is_explicitly_provisional(dataset):
    inventory = validate_manifest(dataset[0])
    report = select_thresholds(predictions(inventory, "calibration"))
    assert report["parameters"]["conforming_similarity"] == 0.9
    assert report["status"] == "PROVISORIA_NAO_HOMOLOGADA"
    assert report["bloqueios"] and "não calibrado" in report["justificativa"]["known_confidence"]


@pytest.mark.parametrize("mutation", ["test_split", "nan", "empty"])
def test_calibration_rejects_invalid_inputs(dataset, mutation):
    rows = predictions(validate_manifest(dataset[0]), "calibration")
    if mutation == "test_split": rows[0]["split"] = "test"
    elif mutation == "nan": rows[0]["similarity"] = float("nan")
    else: rows = []
    with pytest.raises(ValueError):
        select_thresholds(rows)


def provenance(inventory):
    return {"natureza": "sintetica_teste", "origem": "PIL temporário nos testes",
            "responsavel_rotulos": "fixture de teste", "licenca": "fixture local",
            "manifest_sha256": inventory["manifest_sha256"]}


def test_four_synthetic_examples_are_never_called_real(dataset):
    inventory = validate_manifest(dataset[0])
    report = build_demo(predictions(inventory), inventory, provenance(inventory))
    assert report["status"] == "SOMENTE_TESTE_SINTETICO"
    assert len(report["exemplos"]) == 4


def test_demo_requires_true_unknown_anomaly_not_false_positive(dataset):
    inventory = validate_manifest(dataset[0])
    rows = predictions(inventory)
    for row in rows:
        if row["label"] == "ANOMALY": row["predicted_result"] = "UNCERTAIN"
        if row["label"] == "FURADO": row["predicted_result"] = "ANOMALY"
    report = build_demo(rows, inventory, provenance(inventory))
    assert report["status"] == "BLOQUEADA"
    assert report["resultados_ausentes"] == ["ANOMALY"]


def test_evaluation_uses_test_truth_and_hashes(dataset, tmp_path, monkeypatch):
    inventory = validate_manifest(dataset[0])
    path, output = tmp_path / "test.jsonl", tmp_path / "evaluation.json"
    rows = predictions(inventory)
    path.write_text("\n".join(json.dumps(row) for row in rows))
    monkeypatch.setattr(sys, "argv", ["evaluate", str(path), "--manifest", str(dataset[0]), "--output", str(output)])
    evaluate.main()
    report = json.loads(output.read_text())
    assert report["samples"] == 4 and report["anomaly"]["support"] == 1
    assert report["defect_class_metrics"]["FURADO"]["recall"] == 0
    assert report["proveniencia"]["estado"] == "RASTREAVEL_AO_MANIFESTO"
    rows[0]["expected_result"] = "ANOMALY"
    path.write_text("\n".join(json.dumps(row) for row in rows))
    with pytest.raises(SystemExit, match="verdade"):
        evaluate.main()
