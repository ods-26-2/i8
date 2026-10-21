"""Load an A1-owned immutable DEFECT_TAXONOMY package without Torch."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from urllib.parse import urlparse

from src.contracts import ContractError, require_keys, require_text, require_timestamp


class TaxonomyError(ValueError):
    """Invalid, incompatible, unknown or tampered taxonomy."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TaxonomyError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              TaxonomyError(f"Invalid JSON number: {value}")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TaxonomyError(f"Invalid UTF-8 JSON: {exc}") from exc


@dataclass(frozen=True)
class Taxonomy:
    version: str
    descriptor: object
    classes: object

    def resolve(self, defect_class, *, version):
        """Resolve only this exact historical version; never silently use latest."""
        if version != self.version:
            raise TaxonomyError(f"Unknown taxonomy version: {version}")
        if not isinstance(defect_class, str) or defect_class not in self.classes:
            raise TaxonomyError(f"Unknown defect class: {defect_class}")
        return self.classes[defect_class]


def load_taxonomy(content_path, descriptor_path, *, expected_version):
    """Read explicit local files exported by A1/B5 and verify original bytes.

    URI is metadata, not an instruction to download arbitrary content. This
    loader neither writes artifacts nor registers/publishes anything in B5.
    """
    try:
        raw = Path(content_path).read_bytes()
        descriptor = _read_json(Path(descriptor_path).read_bytes())
        require_keys(descriptor, ("artifact_id", "artifact_version", "kind", "owner",
                                 "uri", "hash_sha256", "valid_from", "schema_version"),
                     field="descriptor")
        for field in ("artifact_id", "artifact_version", "uri"):
            require_text(descriptor[field], field)
        require_text(expected_version, "expected_version")
        if descriptor["owner"] != "A1" or descriptor["kind"] != "DEFECT_TAXONOMY":
            raise TaxonomyError("Expected owner A1 and kind DEFECT_TAXONOMY")
        if descriptor["schema_version"] != "1.0":
            raise TaxonomyError("Unsupported taxonomy content schema_version")
        if descriptor["artifact_version"] != expected_version:
            raise TaxonomyError("Artifact version differs from expected_version")
        if (not urlparse(descriptor["uri"]).scheme
                or any(character.isspace() for character in descriptor["uri"])):
            raise TaxonomyError("uri must be an absolute URI")
        require_timestamp(descriptor["valid_from"], "valid_from")
        digest = descriptor["hash_sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise TaxonomyError("hash_sha256 must have 64 hexadecimal characters")
        if hashlib.sha256(raw).hexdigest() != digest.lower():
            raise TaxonomyError("SHA-256 mismatch: artifact bytes were modified")
        content = _read_json(raw)
        require_keys(content, ("classes",), field="taxonomy")
        if not isinstance(content["classes"], list) or not content["classes"]:
            raise TaxonomyError("classes must be a non-empty array")
        classes = {}
        for entry in content["classes"]:
            require_keys(entry, ("defect_class", "name", "description", "severity"),
                         field="class")
            for field, value in entry.items():
                require_text(value, field)
            identifier = entry["defect_class"]
            if identifier in classes:
                raise TaxonomyError(f"Duplicate defect_class: {identifier}")
            if identifier == "NORMAL":
                raise TaxonomyError("NORMAL is legacy; use result CONFORMING")
            classes[identifier] = MappingProxyType(dict(entry))
        return Taxonomy(expected_version, MappingProxyType(dict(descriptor)),
                        MappingProxyType(classes))
    except (OSError, ContractError) as exc:
        raise TaxonomyError(str(exc)) from exc
