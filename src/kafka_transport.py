"""Synchronous, acknowledged industrial-event publication without ML imports."""

from dataclasses import dataclass
import json
import math
import os

from src.contracts import ContractError, INDUSTRIAL_SCHEMA


class DeliveryError(RuntimeError):
    """Delivery failed or is uncertain; retain the original event for retry."""


@dataclass(frozen=True)
class KafkaSettings:
    broker_url: str
    topic: str = INDUSTRIAL_SCHEMA
    delivery_timeout: float = 10.0

    def __post_init__(self):
        if not isinstance(self.broker_url, str) or not self.broker_url.strip():
            raise ValueError("KAFKA_BROKER_URL is required")
        if self.topic != INDUSTRIAL_SCHEMA:
            raise ValueError("KAFKA_TOPIC must equal the industrial 2.0 schema")
        if (type(self.delivery_timeout) not in (int, float)
                or not math.isfinite(self.delivery_timeout)
                or not 1 <= self.delivery_timeout <= 300):
            raise ValueError("KAFKA_DELIVERY_TIMEOUT must be between 1 and 300 seconds")

    @classmethod
    def from_env(cls):
        return cls(
            broker_url=os.environ.get("KAFKA_BROKER_URL", ""),
            topic=os.environ.get("KAFKA_TOPIC", INDUSTRIAL_SCHEMA),
            delivery_timeout=float(os.environ.get("KAFKA_DELIVERY_TIMEOUT", "10")),
        )


class KafkaTransport:
    """One in-flight event per caller; not thread-safe.

    EventPublisher owns full contract/taxonomy validation. This adapter also
    refuses routing a legacy identity to the industrial topic. Success requires
    the delivery callback, not merely an empty queue. A failed send makes this
    instance unusable so later events cannot bypass an uncertain one.
    """

    def __init__(self, settings, *, producer_factory=None):
        self.settings = settings
        if producer_factory is None:
            try:
                from confluent_kafka import Producer
            except ImportError as exc:
                raise RuntimeError("Install the kafka extra or requirements-kafka.txt") from exc
            producer_factory = Producer
        self._producer = producer_factory({
            "bootstrap.servers": settings.broker_url,
            "client.id": "VER-1-I8-Producer",
            "enable.idempotence": True,
            "acks": "all",
            "allow.auto.create.topics": False,
            "message.timeout.ms": int(settings.delivery_timeout * 1000),
        })
        self._closed = False
        self._failed = False
        self.last_delivery = None

    def publish(self, event):
        if self._closed or self._failed:
            raise DeliveryError("Transport closed or failed; retry the original event with a new transport")
        if (event.get("schema") != self.settings.topic
                or event.get("schema_version") != "2.0"):
            raise ContractError("Kafka publication requires the industrial 2.0 event")
        payload = json.dumps(event, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
        self.last_delivery = None
        outcome = []

        def delivered(error, message):
            outcome.append((error, message))

        try:
            self._producer.produce(
                self.settings.topic, key=event["session_id"].encode("utf-8"),
                value=payload, on_delivery=delivered,
            )
            remaining = self._producer.flush(self.settings.delivery_timeout)
            if remaining or not outcome:
                raise DeliveryError("Delivery unconfirmed; the event may have reached Kafka")
            error, message = outcome[0]
            if error is not None:
                raise DeliveryError(f"Kafka delivery failed: {error}")
            self.last_delivery = {
                "message_id": event["message_id"], "topic": message.topic(),
                "partition": message.partition(), "offset": message.offset(),
            }
        except Exception as exc:
            self._failed = True
            if isinstance(exc, DeliveryError):
                raise
            raise DeliveryError(f"Kafka publication failed: {exc}") from exc

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._producer.flush(self.settings.delivery_timeout):
            raise DeliveryError("Shutdown left unconfirmed messages; retain original events")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.close()
        except Exception:
            if exc_type is None:
                raise
