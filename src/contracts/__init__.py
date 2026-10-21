"""Strict 6c 1.0 producer contract; deliberately independent of ML runtimes."""

from datetime import datetime, timezone
import math
import re
from uuid import UUID, uuid4


class ContractError(ValueError):
    """A message must not be published because its contract is invalid."""


def require_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{field}: expected a non-empty string")


def require_timestamp(value, field):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value
    ):
        raise ContractError(f"{field}: expected UTC timestamp with milliseconds")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise ContractError(f"{field}: invalid date/time") from exc


def require_uuid(value, field):
    try:
        parsed = UUID(value) if isinstance(value, str) else None
    except ValueError as exc:
        raise ContractError(f"{field}: expected UUID v4") from exc
    if parsed is None or parsed.version != 4 or str(parsed) != value.lower():
        raise ContractError(f"{field}: expected UUID v4")


def require_keys(value, required, optional=(), field="object"):
    if not isinstance(value, dict):
        raise ContractError(f"{field}: expected object")
    missing = set(required) - value.keys()
    extra = value.keys() - set(required) - set(optional)
    if missing or extra:
        raise ContractError(f"{field}: missing={sorted(missing)}, extra={sorted(extra)}")


def require_integer(value, field):
    if type(value) is not int or value < 0:
        raise ContractError(f"{field}: expected non-negative integer")


def validate_piece_analysis(event, taxonomy):
    """Validate structure and the loaded taxonomy before publication; return event.

    This is a strict 1.0 producer gate, not the forward-compatible A1 consumer.
    A taxonomy is required because JSON Schema alone cannot validate class IDs.
    """
    required = (
        "message_type", "message_id", "schema", "schema_version", "producer",
        "published_at", "captured_at", "source_id", "session_id", "sequence",
        "artifact_version", "payload",
    )
    require_keys(event, required, ("correlation_id",), "event")
    constants = {"message_type": "event", "schema": "ods.i8.piece_analysis",
                 "schema_version": "1.0", "producer": "I8"}
    for field, expected in constants.items():
        if event[field] != expected:
            raise ContractError(f"{field}: expected {expected}")
    for field in ("message_id", "session_id"):
        require_uuid(event[field], field)
    if "correlation_id" in event:
        require_uuid(event["correlation_id"], "correlation_id")
    for field in ("published_at", "captured_at"):
        require_timestamp(event[field], field)
    for field in ("source_id", "artifact_version"):
        require_text(event[field], field)
    require_integer(event["sequence"], "sequence")
    payload = event["payload"]
    require_keys(payload, ("frame_index", "detection_id", "bbox", "result",
                          "taxonomy_version", "confidence", "similarity"),
                 ("defect_class",), "payload")
    for field in ("frame_index", "detection_id"):
        require_integer(payload[field], field)
    bbox = payload["bbox"]
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ContractError("bbox: expected four integers")
    for value in bbox:
        require_integer(value, "bbox")
    if bbox[0] >= bbox[2] or bbox[1] >= bbox[3]:
        raise ContractError("bbox: expected positive area")
    for field in ("confidence", "similarity"):
        value = payload[field]
        if (type(value) not in (int, float) or not 0 <= value <= 1
                or not math.isfinite(value)):
            raise ContractError(f"{field}: expected finite number in [0,1]")
    result = payload["result"]
    if result not in ("CONFORMING", "NON_CONFORMING", "ANOMALY", "UNCERTAIN"):
        raise ContractError("result: invalid enum")
    if payload["taxonomy_version"] != taxonomy.version:
        raise ContractError("taxonomy_version: does not match loaded artifact")
    if result == "NON_CONFORMING":
        if "defect_class" not in payload:
            raise ContractError("defect_class: required for NON_CONFORMING")
        try:
            taxonomy.resolve(payload["defect_class"], version=taxonomy.version)
        except ValueError as exc:
            raise ContractError(f"defect_class: {exc}") from exc
    elif "defect_class" in payload:
        # Explicit application decision: no known class when conforming,
        # anomalous, or uncertain. Avoid pretending that ANOMALY is a class.
        raise ContractError("defect_class: only allowed for NON_CONFORMING")
    return event


def build_piece_analysis(*, taxonomy, source_id, session_id, sequence,
                         captured_at, artifact_version, frame_index,
                         detection_id, bbox, result, confidence, similarity,
                         defect_class=None, message_id=None, published_at=None,
                         correlation_id=None):
    """Build a validated observation, not an inference or business decision.

    Caller owns the monotonically increasing per-producer/session sequence.
    artifact_version must identify the model actually used, not the taxonomy.
    """
    payload = dict(frame_index=frame_index, detection_id=detection_id,
                   bbox=list(bbox) if isinstance(bbox, (list, tuple)) else bbox,
                   result=result, taxonomy_version=taxonomy.version,
                   confidence=confidence, similarity=similarity)
    if defect_class is not None:
        payload["defect_class"] = defect_class
    event = dict(message_type="event", message_id=str(uuid4()) if message_id is None else message_id,
                 schema="ods.i8.piece_analysis", schema_version="1.0", producer="I8",
                 published_at=published_at if published_at is not None else
                 datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                 captured_at=captured_at, source_id=source_id, session_id=session_id,
                 sequence=sequence, artifact_version=artifact_version, payload=payload)
    if correlation_id is not None:
        event["correlation_id"] = correlation_id
    return validate_piece_analysis(event, taxonomy)
