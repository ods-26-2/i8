import io
import json
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
import pytest

from scripts.replay import replay_rows
from src.kafka_transport import DeliveryError
from src.publisher import EventPublisher, MemoryTransport
from test_kafka_publisher import Taxonomy


def test_replay_builds_2_0_after_inference_and_journals_before_send(tmp_path):
    Image.new("RGB", (10, 10)).save(tmp_path / "frame.png")
    session = str(uuid4())
    rows = [dict(source_id="cam", session_id=session, frame_index=i,
                 detection_id=0, captured_at="2026-01-01T00:00:00.000Z",
                 published_at="2026-01-01T00:00:00.001Z", bbox=[1, 2, 6, 7],
                 frame_path="frame.png") for i in range(2)]
    output = io.StringIO()
    calls = []

    class Transport:
        last_delivery = {"offset": 0}

        def publish(self, event):
            assert json.loads(output.getvalue().splitlines()[-1]) == event
            calls.append("publish")

    def infer(crop):
        assert crop.size == (5, 5)
        calls.append("infer")
        return SimpleNamespace(result="CONFORMING", confidence=.9, similarity=.9, defect_class=None)

    times = iter(["2026-11-05T12:00:00.010Z", "2026-11-05T12:00:00.011Z"] * 2)
    replay_rows(map(json.dumps, rows), output, input_dir=tmp_path, infer=infer,
                publisher=EventPublisher(Taxonomy(), Transport()), artifact_version="composition-1",
                kafka=True, clock=lambda: next(times))
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert calls == ["infer", "publish", "infer", "publish"]
    assert [e["sequence"] for e in events] == [0, 1]
    assert len({e["message_id"] for e in events}) == 2
    assert all(e["schema_version"] == "2.0" and e["occurred_at"] == "2026-11-05T12:00:00.010Z"
               and e["published_at"] == "2026-11-05T12:00:00.011Z"
               and e["captured_at"] == rows[0]["captured_at"] for e in events)


@pytest.mark.parametrize("kafka", [False, True])
def test_offline_compatibility_and_failed_send_journal(tmp_path, kafka):
    Image.new("RGB", (2, 2)).save(tmp_path / "frame.png")
    row = dict(source_id="cam", session_id=str(uuid4()), frame_index=0, detection_id=0,
               captured_at="2026-01-01T00:00:00.000Z", bbox=[0, 0, 2, 2], frame_path="frame.png")
    output = io.StringIO()

    class FailedTransport:
        def publish(self, event):
            raise DeliveryError("retain event")

    client = FailedTransport() if kafka else MemoryTransport()
    kwargs = dict(input_dir=tmp_path, publisher=EventPublisher(Taxonomy(), client),
                  artifact_version="a", kafka=kafka, infer=lambda crop: SimpleNamespace(
                      result="UNCERTAIN", confidence=.5, similarity=.5, defect_class=None))
    if kafka:
        with pytest.raises(DeliveryError):
            replay_rows([json.dumps(row)], output, **kwargs)
    else:
        replay_rows([json.dumps(row)], output, **kwargs)
    event = json.loads(output.getvalue())
    assert event["schema_version"] == ("2.0" if kafka else "1.0")
    assert ("occurred_at" in event) is kafka
    assert event["captured_at"] == row["captured_at"]


def test_transport_and_replay_import_without_torch_or_kafka_dependency():
    result = subprocess.run([sys.executable, "-c",
        "import sys; import scripts.replay, scripts.publish_events; "
        "assert 'torch' not in sys.modules; assert 'confluent_kafka' not in sys.modules"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_kafka_replay_refuses_to_overwrite_retry_journal(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from scripts import replay

    source, output = tmp_path / "input.jsonl", tmp_path / "events.jsonl"
    source.write_text("")
    output.write_text("original event\n")
    monkeypatch.setattr(replay.KafkaSettings, "from_env", lambda: object())
    monkeypatch.setattr(replay, "load_taxonomy", lambda *a, **k: Taxonomy())
    monkeypatch.setattr(replay, "load_pipeline", lambda *a: SimpleNamespace(infer=None))
    monkeypatch.setattr(replay, "KafkaTransport", lambda settings: nullcontext(MemoryTransport()))
    with pytest.raises(FileExistsError):
        replay.main(["--input", str(source), "--output", str(output), "--normal-model", "normal.json",
                     "--classifier", "classifier.json", "--policy", "policy.json", "--taxonomy", "tax.json",
                     "--taxonomy-descriptor", "descriptor.json", "--taxonomy-version", Taxonomy.version,
                     "--artifact-version", "a", "--kafka"])
    assert output.read_text() == "original event\n"
