"""Opt-in real local broker proof; no inference model or shared broker."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import pytest

from src.kafka_transport import DeliveryError, KafkaSettings, KafkaTransport
from src.publisher import EventPublisher
from src.taxonomy import load_taxonomy

pytestmark = pytest.mark.skipif(os.environ.get("I8_KAFKA_LOCAL_TEST") != "1",
                                reason="requires the isolated publisher Compose laboratory")
ROOT = Path(__file__).resolve().parents[1]


def test_cli_delivery_four_results_and_same_event_retry(tmp_path):
    from confluent_kafka import Consumer, TopicPartition

    settings = KafkaSettings.from_env()
    directory = Path(os.environ["I8_TEST_TAXONOMY_DIR"])
    session = str(uuid4())
    events = []
    for sequence, path in enumerate(sorted((ROOT / "shared/mocks/kafka-2.0").glob("i8-piece-*.json"))):
        event = json.loads(path.read_text())
        event.update(message_id=str(uuid4()), session_id=session, sequence=sequence)
        events.append(event)
    events.append(copy.deepcopy(events[0]))
    source = tmp_path / "events.jsonl"
    source.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    result = subprocess.run([
        sys.executable, "-m", "scripts.publish_events", "--input", str(source),
        "--taxonomy", str(directory / "content.json"),
        "--taxonomy-descriptor", str(directory / "descriptor.json"),
        "--taxonomy-version", "defects-a1-1.0.0",
    ], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    receipts = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(receipts) == 5
    assert [r["message_id"] for r in receipts] == [e["message_id"] for e in events]
    assert all(r["topic"] == settings.topic and r["partition"] == 0 and r["offset"] >= 0
               for r in receipts)
    assert [r["offset"] for r in receipts] == sorted({r["offset"] for r in receipts})
    consumer = Consumer({"bootstrap.servers": settings.broker_url,
                         "group.id": f"i8-publisher-proof-{uuid4()}", "enable.auto.commit": False})
    received, keys = [], []
    ids = {e["message_id"] for e in events}
    try:
        consumer.assign([TopicPartition(settings.topic, 0, 0)])
        deadline = time.monotonic() + 20
        while len(received) < len(events) and time.monotonic() < deadline:
            message = consumer.poll(.5)
            if message is None:
                continue
            assert not message.error(), str(message.error())
            event = json.loads(message.value())
            if event["message_id"] in ids:
                received.append(event)
                keys.append(message.key().decode())
    finally:
        consumer.close()
    assert received == events
    assert keys == [session] * 5
    report = {"status": "publisher-kafka-local-aprovado", "synthetic_events": True,
              "real_inference": False, "shared_broker": False, "a1_persistence_tested": False,
              "schema": settings.topic, "schema_version": "2.0", "publications": 5,
              "unique_events": 4, "receipts": receipts, "received_events_equal_input": True}
    destination = os.environ.get("I8_TEST_REPORT")
    if destination:
        Path(destination).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def test_real_client_reports_unavailable_broker():
    directory = Path(os.environ["I8_TEST_TAXONOMY_DIR"])
    taxonomy = load_taxonomy(directory / "content.json", directory / "descriptor.json",
                             expected_version="defects-a1-1.0.0")
    event = json.loads((ROOT / "shared/mocks/kafka-2.0/i8-piece-conforming.json").read_text())
    started = time.monotonic()
    with pytest.raises(DeliveryError):
        with KafkaTransport(KafkaSettings("127.0.0.1:1", delivery_timeout=1)) as transport:
            EventPublisher(taxonomy, transport).publish_event(event)
    assert time.monotonic() - started < 5
