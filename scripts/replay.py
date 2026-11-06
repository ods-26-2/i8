"""Replay frames/detections through correlation, real inference and 6c validation."""
import argparse
from contextlib import nullcontext, ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path

from src.kafka_transport import KafkaSettings, KafkaTransport
from src.publisher import EventPublisher, MemoryTransport
from src.runtime import Detection, Frame, FrameCorrelator, ReplayRuntime
from src.taxonomy import load_taxonomy


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def replay_rows(source, output, *, input_dir, infer, publisher, artifact_version,
                kafka=False, clock=utc_now):
    """Journal before sending so failed publication can retry identical JSON.

    This journal is a replay aid, not a transactional/durable outbox. A new
    inference replay creates new events; retry publication with publish-events.
    """
    from PIL import Image

    correlator = FrameCorrelator()
    sequences = {}
    for line_number, line in enumerate(source, 1):
        if not line.strip():
            continue
        row = json.loads(line)
        session = row["session_id"]
        sequence = sequences.get(session, 0) if kafka else line_number
        with Image.open((input_dir / row["frame_path"]).resolve()) as image:
            frame = Frame(row["source_id"], session, int(row["frame_index"]),
                          row["captured_at"], image)
            correlator.add(frame)
            detection = Detection(row["source_id"], session, int(row["frame_index"]),
                                  int(row["detection_id"]), row["captured_at"], list(row["bbox"]))
            result = ReplayRuntime(infer).execute(detection, correlator)
            times = ({"schema_version": "2.0", "occurred_at": clock(),
                      "published_at": clock()} if kafka else
                     {"published_at": row.get("published_at", row["captured_at"])})
            event = publisher.build(
                source_id=row["source_id"], session_id=session, sequence=sequence,
                captured_at=row["captured_at"], artifact_version=artifact_version,
                frame_index=detection.frame_index, detection_id=detection.detection_id,
                bbox=detection.bbox, result=result.result, confidence=result.confidence,
                similarity=result.similarity, defect_class=result.defect_class, **times,
            )
            output.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            output.flush()
            publisher.publish_event(event)
            sequences[session] = sequence + 1
            if kafka:
                print(json.dumps(publisher.transport.last_delivery), flush=True)


def load_pipeline(args, taxonomy):
    # Keep CLI help and transport tests independent of Torch and model downloads.
    from feature_extractor import FeatureExtractor
    from normal_model import NormalModel
    from src.inference import DecisionPolicy, InferencePipeline, KnownDefectClassifier

    normal = NormalModel.load(args.normal_model)
    classifier = KnownDefectClassifier.load(args.classifier, taxonomy=taxonomy)
    policy = DecisionPolicy.load(
        args.policy, product_id=normal.product_id, normal_version=normal.model_version,
        classifier_version=classifier.artifact_version, taxonomy_version=taxonomy.version,
    )
    engine = getattr(args, "p2_engine", None)
    if engine:
        from src.p2_extractor import P2FeatureExtractor
        extractor = P2FeatureExtractor(engine)
    else:
        extractor = FeatureExtractor("cpu")
    try:
        if engine and args.artifact_version != extractor.engine_info["engine_version"]:
            raise ValueError("--artifact-version deve identificar o engine_version P2 efetivo")
        return InferencePipeline(extractor=extractor, normal_model=normal,
                                 classifier=classifier, taxonomy=taxonomy, policy=policy)
    except BaseException:
        close = getattr(extractor, "close", None)
        if close:
            close()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "output", "normal-model", "classifier", "policy", "taxonomy", "taxonomy-descriptor"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--taxonomy-version", required=True)
    parser.add_argument("--artifact-version", required=True)
    parser.add_argument("--p2-engine", help="Engine ResNet18 P2 FP32/CPU instalado; exige P2_BACKEND=ort")
    parser.add_argument("--kafka", action="store_true", help="Publish industrial 2.0 with delivery confirmation")
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        parser.error("--input and --output must be different files")
    settings = KafkaSettings.from_env() if args.kafka else None
    taxonomy = load_taxonomy(args.taxonomy, args.taxonomy_descriptor,
                             expected_version=args.taxonomy_version)
    pipeline = load_pipeline(args, taxonomy)
    with ExitStack() as stack:
        close = getattr(getattr(pipeline, "extractor", None), "close", None)
        if close:
            stack.callback(close)
        context = KafkaTransport(settings) if args.kafka else nullcontext(MemoryTransport())
        transport = stack.enter_context(context)
        publisher = EventPublisher(taxonomy, transport)
        mode = "x" if args.kafka else "w"
        with args.input.open(encoding="utf-8") as source, args.output.open(mode, encoding="utf-8") as output:
            replay_rows(source, output, input_dir=args.input.parent, infer=pipeline.infer,
                        publisher=publisher, artifact_version=args.artifact_version, kafka=args.kafka)


if __name__ == "__main__":
    main()
