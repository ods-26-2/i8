"""Publish existing validated 2.0 JSONL events; preserve identities on retries."""

import argparse
import json
from pathlib import Path

from src.kafka_transport import KafkaSettings, KafkaTransport
from src.publisher import EventPublisher
from src.taxonomy import load_taxonomy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--taxonomy-descriptor", type=Path, required=True)
    parser.add_argument("--taxonomy-version", required=True)
    args = parser.parse_args(argv)
    taxonomy = load_taxonomy(args.taxonomy, args.taxonomy_descriptor,
                             expected_version=args.taxonomy_version)
    with args.input.open(encoding="utf-8") as source:
        with KafkaTransport(KafkaSettings.from_env()) as transport:
            publisher = EventPublisher(taxonomy, transport)
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                try:
                    publisher.publish_event(json.loads(line))
                except (ValueError, RuntimeError) as exc:
                    raise SystemExit(f"line {line_number}: {exc}") from exc
                print(json.dumps(transport.last_delivery), flush=True)


if __name__ == "__main__":
    main()
