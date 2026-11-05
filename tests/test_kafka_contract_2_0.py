"""Industrial 2.0 and explicit legacy 1.0, offline without ML or transport."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from src.contracts import (ContractError, INDUSTRIAL_SCHEMA, LEGACY_SCHEMA,
                           SCHEMAS_BY_VERSION, build_piece_analysis, validate_piece_analysis)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "shared/mocks/kafka-2.0"

class Taxonomy:
    version = "defects-a1-1.0.0"
    def resolve(self, value, *, version):
        if value != "AMASSADO" or version != self.version:
            raise ValueError("unknown class/version")

@pytest.fixture
def sample():
    return json.loads((EXAMPLES / "i8-piece-non-conforming.json").read_text(encoding="utf-8"))

@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("i8-piece-*.json")))
def test_industrial_examples_pass_schema_and_runtime(path):
    event = json.loads(path.read_text(encoding="utf-8"))
    before = copy.deepcopy(event)
    schema = json.loads((ROOT / "shared/schemas/6c/i8-defeito-classificado.2.0.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(event)
    assert validate_piece_analysis(event, Taxonomy()) == before
    assert event["schema"] == INDUSTRIAL_SCHEMA and event["schema_version"] == "2.0"

@pytest.mark.parametrize("path", sorted((EXAMPLES / "invalid").glob("*.json")))
def test_industrial_invalid_examples_are_rejected(path):
    with pytest.raises(ContractError):
        validate_piece_analysis(json.loads(path.read_text(encoding="utf-8")), Taxonomy())

@pytest.mark.parametrize("schema,version", [(LEGACY_SCHEMA,"2.0"), (INDUSTRIAL_SCHEMA,"1.0"),
                                            (INDUSTRIAL_SCHEMA,"1.1"), (LEGACY_SCHEMA,"1.1"),
                                            (INDUSTRIAL_SCHEMA,"2.1")])
def test_crossed_and_unreleased_identities_are_rejected(sample, schema, version):
    sample.update(schema=schema, schema_version=version)
    with pytest.raises(ContractError):
        validate_piece_analysis(sample, Taxonomy())

def builder_fields(sample):
    fields = {k:v for k,v in sample.items() if k not in ("message_type","producer","schema","payload")}
    fields.update(sample["payload"])
    fields.pop("taxonomy_version")
    return fields

def test_builder_preserves_three_times_and_retry_identity(sample):
    fields = builder_fields(sample)
    event = build_piece_analysis(taxonomy=Taxonomy(), **fields)
    assert event == sample
    assert validate_piece_analysis(event, Taxonomy()) == sample
    assert SCHEMAS_BY_VERSION["2.0"] == event["schema"]

@pytest.mark.parametrize("value", [None, "2026-02-30T13:00:00.080Z", "2026-11-05T13:00:00Z"])
def test_industrial_builder_requires_actual_valid_analysis_time(sample, value):
    fields = builder_fields(sample)
    fields["occurred_at"] = value
    with pytest.raises(ContractError):
        build_piece_analysis(taxonomy=Taxonomy(), **fields)

def test_expand_default_and_explicit_legacy_remain_unchanged(sample):
    fields = builder_fields(sample)
    fields.pop("schema_version")
    fields.pop("occurred_at")
    implicit = build_piece_analysis(taxonomy=Taxonomy(), **fields)
    explicit = build_piece_analysis(taxonomy=Taxonomy(), schema_version="1.0", **fields)
    assert implicit == explicit
    assert implicit["schema"] == LEGACY_SCHEMA and implicit["schema_version"] == "1.0"
    assert "occurred_at" not in implicit
    with pytest.raises(ContractError):
        build_piece_analysis(taxonomy=Taxonomy(), occurred_at=sample["occurred_at"], **fields)

def test_superseded_candidate_builder_is_rejected(sample):
    fields = builder_fields(sample)
    fields["schema_version"] = "1.1"
    with pytest.raises(ContractError, match="superseded"):
        build_piece_analysis(taxonomy=Taxonomy(), **fields)
