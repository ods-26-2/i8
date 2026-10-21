"""Contract tests run offline without importing Torch or executing triage."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.contracts import ContractError, build_piece_analysis, validate_piece_analysis
from src.taxonomy import TaxonomyError, load_taxonomy


TIME = "2026-10-20T12:00:00.000Z"
SESSION = "1c3ab594-7321-4d43-9e71-8f2cd5e1d542"
SCHEMAS = Path(__file__).resolve().parents[1] / "shared/schemas/6c"


def package(tmp_path, version="defects-a1-1.0.0", name="Amassado"):
    content = {"classes": [{"defect_class": "AMASSADO", "name": name,
                            "description": "Superfície deformada", "severity": "HIGH"}]}
    path = tmp_path / f"{version}.json"
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    descriptor = dict(artifact_id="defect-taxonomy-a1", artifact_version=version,
                      kind="DEFECT_TAXONOMY", owner="A1", uri=f"registry://b5/a1/defect-taxonomy/{version}",
                      hash_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      valid_from=TIME, schema_version="1.0")
    descriptor_path = tmp_path / f"{version}-descriptor.json"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")
    return path, descriptor_path


@pytest.fixture
def taxonomy(tmp_path):
    return load_taxonomy(*package(tmp_path), expected_version="defects-a1-1.0.0")


def event(taxonomy, result="NON_CONFORMING"):
    return build_piece_analysis(taxonomy=taxonomy, source_id="cam1", session_id=SESSION,
        sequence=0, captured_at=TIME, published_at=TIME, artifact_version="piece-cls-0.9.2",
        frame_index=3, detection_id=0, bbox=[0, 0, 20, 30], result=result,
        confidence=0.9, similarity=0.7,
        defect_class="AMASSADO" if result == "NON_CONFORMING" else None)


def schema_validator(name):
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.mark.parametrize("result", ["CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN"])
def test_four_results_match_schema_and_loaded_version(taxonomy, result):
    message = event(taxonomy, result)
    schema_validator("i8-piece-analysis.schema.json").validate(message)
    assert validate_piece_analysis(json.loads(json.dumps(message)), taxonomy) == message
    assert message["payload"]["taxonomy_version"] == taxonomy.version
    assert message["artifact_version"] == "piece-cls-0.9.2"
    assert ("defect_class" in message["payload"]) == (result == "NON_CONFORMING")


@pytest.mark.parametrize("field,value", [
    ("message_type", "command"), ("message_id", "not-uuid"),
    ("message_id", "1c3ab594-7321-1d43-9e71-8f2cd5e1d542"),
    ("message_id", "{" + SESSION + "}"), ("session_id", None),
    ("schema", "ods.ver1.i8_piece_analyzed"), ("schema_version", "1.1"),
    ("producer", "A1"), ("sequence", True), ("sequence", -1), ("sequence", 1.5),
    ("source_id", " "), ("artifact_version", None),
    ("captured_at", "2026-02-30T12:00:00.000Z"),
    ("published_at", "2026-10-20T12:00:00+00:00"),
    ("published_at", "2026-10-20T12:00:00Z"), ("correlation_id", "bad"),
    ("target", "A1"), ("evidence", {}),
])
def test_invalid_envelope_rejected(taxonomy, field, value):
    message = event(taxonomy)
    message[field] = value
    with pytest.raises(ContractError):
        validate_piece_analysis(message, taxonomy)


@pytest.mark.parametrize("field,value", [
    ("frame_index", True), ("frame_index", -1), ("detection_id", 0.5),
    ("bbox", [1, 0, 1, 20]), ("bbox", [0, 2, 20, 1]),
    ("bbox", [-1, 0, 20, 30]), ("bbox", [False, 0, 20, 30]),
    ("bbox", [0, 0, 20.5, 30]), ("bbox", [0, 1]), ("bbox", "0,0,20,30"),
    ("confidence", float("nan")), ("confidence", float("inf")),
    ("confidence", True), ("confidence", -0.1), ("similarity", 1.01),
    ("similarity", 10 ** 500), ("similarity", "0.7"), ("result", "APPROVED"),
    ("defect_class", "MISSING"), ("defect_class", None),
    ("taxonomy_version", "new-version"), ("evidence", {"image_url": "x.png"}),
    ("media_uri", "s4://x"), ("classification", {"id": "AMASSADO"}),
    ("piece_id", "P1"), ("severity", "HIGH"), ("status", "REJECTED"),
    ("source_id", "cam1"),
])
def test_invalid_payload_rejected(taxonomy, field, value):
    message = event(taxonomy)
    message["payload"][field] = value
    with pytest.raises(ContractError):
        validate_piece_analysis(message, taxonomy)


def test_required_fields_and_class_coherence(taxonomy):
    original = event(taxonomy)
    for field in original:
        message = copy.deepcopy(original)
        del message[field]
        with pytest.raises(ContractError):
            validate_piece_analysis(message, taxonomy)
    for field in original["payload"]:
        message = copy.deepcopy(original)
        del message["payload"][field]
        with pytest.raises(ContractError):
            validate_piece_analysis(message, taxonomy)
    for result in ("CONFORMING", "ANOMALY", "UNCERTAIN"):
        message = event(taxonomy, result)
        message["payload"]["defect_class"] = "AMASSADO"
        with pytest.raises(ContractError):
            validate_piece_analysis(message, taxonomy)


def test_ratios_boundaries_correlation_and_immutability(taxonomy):
    message = event(taxonomy)
    message["payload"].update(confidence=0, similarity=1)
    message["correlation_id"] = SESSION
    before = copy.deepcopy(message)
    validate_piece_analysis(message, taxonomy)
    assert message == before
    schema_validator("i8-piece-analysis.schema.json").validate(message)


def test_runtime_modules_do_not_import_torch():
    completed = subprocess.run([sys.executable, "-c",
        "import sys; import src.contracts, src.taxonomy; assert 'torch' not in sys.modules"],
        cwd=SCHEMAS.parents[2], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_taxonomy_schema_hash_and_historical_resolution(tmp_path):
    paths1 = package(tmp_path)
    paths2 = package(tmp_path, "defects-a1-2.0.0", "Nome atualizado")
    old = load_taxonomy(*paths1, expected_version="defects-a1-1.0.0")
    new = load_taxonomy(*paths2, expected_version="defects-a1-2.0.0")
    for paths in (paths1, paths2):
        schema_validator("defect-taxonomy.schema.json").validate(json.loads(paths[0].read_text(encoding="utf-8")))
        schema_validator("defect-taxonomy-descriptor.schema.json").validate(json.loads(paths[1].read_text()))
    assert old.resolve("AMASSADO", version=old.version)["name"] == "Amassado"
    assert new.resolve("AMASSADO", version=new.version)["name"] == "Nome atualizado"
    with pytest.raises(TaxonomyError):
        old.resolve("AMASSADO", version=new.version)
    with pytest.raises(TaxonomyError):
        old.resolve("MISSING", version=old.version)
    with pytest.raises(TypeError):
        old.classes["AMASSADO"]["name"] = "changed"
    paths1[0].write_bytes(paths1[0].read_bytes() + b" ")
    with pytest.raises(TaxonomyError, match="SHA-256"):
        load_taxonomy(*paths1, expected_version=old.version)


@pytest.mark.parametrize("field,value", [
    ("artifact_id", " "), ("artifact_version", "unknown"), ("kind", "MODEL"),
    ("owner", "I8"), ("uri", "relative/path"), ("uri", "registry://bad path"),
    ("hash_sha256", "0" * 64), ("hash_sha256", "invalid"),
    ("valid_from", "2026-10-20"), ("schema_version", "2.0"), ("extra", True),
])
def test_invalid_descriptor(tmp_path, field, value):
    paths = package(tmp_path)
    descriptor = json.loads(paths[1].read_text())
    descriptor[field] = value
    paths[1].write_text(json.dumps(descriptor))
    with pytest.raises(TaxonomyError):
        load_taxonomy(*paths, expected_version="defects-a1-1.0.0")


@pytest.mark.parametrize("content", [
    {}, {"classes": []}, {"classes": {}},
    {"classes": [{"defect_class": "AMASSADO"}]},
    {"classes": [{"defect_class": "NORMAL", "name": "N", "description": "D", "severity": "NONE"}]},
    {"classes": [{"defect_class": "X", "name": " ", "description": "D", "severity": "HIGH"}]},
    {"classes": [{"defect_class": "X", "name": "X", "description": "D", "severity": "HIGH", "consequence": "REJECT"}]},
    {"classes": [{"defect_class": "X", "name": "X", "description": "D", "severity": "HIGH"}] * 2},
])
def test_invalid_content_with_valid_hash(tmp_path, content):
    paths = package(tmp_path)
    paths[0].write_text(json.dumps(content))
    descriptor = json.loads(paths[1].read_text())
    descriptor["hash_sha256"] = hashlib.sha256(paths[0].read_bytes()).hexdigest()
    paths[1].write_text(json.dumps(descriptor))
    with pytest.raises(TaxonomyError):
        load_taxonomy(*paths, expected_version="defects-a1-1.0.0")


def test_missing_descriptor_fields_and_invalid_json(tmp_path):
    paths = package(tmp_path)
    original = json.loads(paths[1].read_text())
    for field in original:
        descriptor = dict(original)
        del descriptor[field]
        paths[1].write_text(json.dumps(descriptor))
        with pytest.raises(TaxonomyError):
            load_taxonomy(*paths, expected_version="defects-a1-1.0.0")
    for raw in (b'{"classes":[],"classes":[]}', b'{"classes":NaN}', b'not json', b'\xff'):
        paths[0].write_bytes(raw)
        descriptor = dict(original, hash_sha256=hashlib.sha256(raw).hexdigest())
        paths[1].write_text(json.dumps(descriptor))
        with pytest.raises(TaxonomyError):
            load_taxonomy(*paths, expected_version="defects-a1-1.0.0")
    with pytest.raises(TaxonomyError):
        load_taxonomy(tmp_path / "missing", paths[1], expected_version="defects-a1-1.0.0")
