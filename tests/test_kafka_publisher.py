import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.contracts import ContractError
from src.kafka_transport import DeliveryError, KafkaSettings, KafkaTransport
from src.publisher import EventPublisher

ROOT = Path(__file__).resolve().parents[1]


class Taxonomy:
    version = "defects-a1-1.0.0"

    def resolve(self, value, *, version):
        if version != self.version or value != "AMASSADO":
            raise ValueError("unknown class")


@pytest.fixture
def event():
    return json.loads((ROOT / "shared/mocks/kafka-2.0/i8-piece-conforming.json").read_text())


class Producer:
    def __init__(self, mode="ok"):
        self.mode, self.sent, self.flushes = mode, [], []

    def produce(self, topic, **kwargs):
        if self.mode == "queue":
            raise BufferError("queue full")
        self.sent.append((topic, kwargs))

    def flush(self, timeout):
        self.flushes.append(timeout)
        if self.mode == "exception":
            raise RuntimeError("flush failed")
        if self.mode == "timeout":
            return 1
        if self.sent and self.mode != "no_callback":
            topic, kwargs = self.sent[-1]
            callback = kwargs.pop("on_delivery", None)
            if callback:
                callback("broker error" if self.mode == "error" else None,
                         SimpleNamespace(topic=lambda: topic, partition=lambda: 0, offset=lambda: 42))
        return 0


def transport(producer):
    return KafkaTransport(KafkaSettings("kafka:9092"), producer_factory=lambda config: producer)


def test_acknowledged_utf8_event_and_metadata(event):
    event["source_id"] = "câmera"
    before = copy.deepcopy(event)
    producer = Producer()
    with transport(producer) as client:
        assert EventPublisher(Taxonomy(), client).publish_event(event) is event
        assert client.last_delivery == dict(message_id=event["message_id"],
                                            topic=event["schema"], partition=0, offset=42)
    assert json.loads(producer.sent[0][1]["value"]) == before == event
    assert producer.sent[0][1]["key"] == event["session_id"].encode()
    assert producer.flushes == [10.0, 10.0]


@pytest.mark.parametrize("mode", ["queue", "timeout", "no_callback", "error", "exception"])
def test_failures_never_report_success_or_allow_later_events(event, mode):
    producer = Producer(mode)
    client = transport(producer)
    before = copy.deepcopy(event)
    with pytest.raises(DeliveryError):
        EventPublisher(Taxonomy(), client).publish_event(event)
    assert event == before and client.last_delivery is None
    with pytest.raises(DeliveryError, match="closed or failed"):
        client.publish(event)


def test_invalid_contract_does_not_reach_producer(event):
    producer = Producer()
    event["payload"]["similarity"] = float("nan")
    with pytest.raises(ContractError):
        EventPublisher(Taxonomy(), transport(producer)).publish_event(event)
    assert not producer.sent


@pytest.mark.parametrize("version", ["1.0", "1.1", "2.1"])
def test_transport_does_not_send_other_versions_to_industrial_topic(event, version):
    event["schema_version"] = version
    producer = Producer()
    with pytest.raises(ContractError):
        transport(producer).publish(event)
    assert not producer.sent


def test_retry_uses_identical_event_bytes(event):
    first, second = Producer("error"), Producer()
    with pytest.raises(DeliveryError):
        EventPublisher(Taxonomy(), transport(first)).publish_event(event)
    EventPublisher(Taxonomy(), transport(second)).publish_event(event)
    assert first.sent[0][1]["value"] == second.sent[0][1]["value"]


def test_idempotent_client_configuration():
    configs = []
    KafkaTransport(KafkaSettings("example:9093", delivery_timeout=3),
                   producer_factory=lambda config: configs.append(config) or Producer()).close()
    assert configs[0] == {
        "bootstrap.servers": "example:9093", "client.id": "VER-1-I8-Producer",
        "enable.idempotence": True, "acks": "all", "allow.auto.create.topics": False,
        "message.timeout.ms": 3000,
    }


@pytest.mark.parametrize("kwargs", [dict(broker_url=""), dict(broker_url=" "),
    dict(broker_url="k", topic="wrong"), dict(broker_url="k", delivery_timeout=0),
    dict(broker_url="k", delivery_timeout=float("nan")),
    dict(broker_url="k", delivery_timeout=float("inf")),
    dict(broker_url="k", delivery_timeout=True), dict(broker_url="k", delivery_timeout=301)])
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        KafkaSettings(**kwargs)


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("KAFKA_BROKER_URL", "broker:9093")
    monkeypatch.setenv("KAFKA_DELIVERY_TIMEOUT", "2.5")
    monkeypatch.delenv("KAFKA_TOPIC", raising=False)
    assert KafkaSettings.from_env() == KafkaSettings("broker:9093", delivery_timeout=2.5)


def test_close_is_idempotent_and_forbids_send(event):
    producer = Producer()
    client = transport(producer)
    client.close()
    client.close()
    assert len(producer.flushes) == 1
    with pytest.raises(DeliveryError):
        client.publish(event)


def test_shutdown_failure_does_not_hide_original_error():
    with pytest.raises(ValueError, match="original"):
        with transport(Producer("timeout")):
            raise ValueError("original")
    with pytest.raises(DeliveryError, match="Shutdown"):
        with transport(Producer("timeout")):
            pass


def test_jsonl_cli_stops_at_invalid_event_without_sending_later_lines(tmp_path, monkeypatch, event, capsys):
    from scripts import publish_events

    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(event) + "\n{invalid\n" + json.dumps(event) + "\n")
    producer = Producer()
    monkeypatch.setattr(publish_events, "load_taxonomy", lambda *a, **k: Taxonomy())
    monkeypatch.setattr(publish_events.KafkaSettings, "from_env", lambda: KafkaSettings("k"))
    monkeypatch.setattr(publish_events, "KafkaTransport", lambda settings: transport(producer))
    with pytest.raises(SystemExit, match="line 2"):
        publish_events.main(["--input", str(path), "--taxonomy", "tax.json",
                             "--taxonomy-descriptor", "descriptor.json", "--taxonomy-version", Taxonomy.version])
    assert len(producer.sent) == 1
    assert json.loads(capsys.readouterr().out)["message_id"] == event["message_id"]
