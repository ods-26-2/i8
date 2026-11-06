"""Run artifact-backed predictions for one manifest split."""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from feature_extractor import FeatureExtractor
from normal_model import NormalModel
from preprocessing import load_image
from src.inference import DecisionPolicy, InferencePipeline, KnownDefectClassifier
from src.taxonomy import load_taxonomy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=("calibration", "test"), required=True)
    parser.add_argument("--normal-model", type=Path, required=True)
    parser.add_argument("--classifier", type=Path, required=True)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--taxonomy-descriptor", type=Path, required=True)
    parser.add_argument("--taxonomy-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "auto", "cuda"), default="cpu")
    args = parser.parse_args()
    if args.split == "test" and args.policy is None:
        parser.error("--policy é obrigatório para o split test")

    rows = list(csv.DictReader(args.manifest.open(encoding="utf-8", newline="")))
    rows = [row for row in rows if row["split"] == args.split]
    normal = NormalModel.load(args.normal_model)
    taxonomy = load_taxonomy(args.taxonomy, args.taxonomy_descriptor,
                             expected_version=args.taxonomy_version)
    extractor = FeatureExtractor(args.device)
    classifier = KnownDefectClassifier.load(args.classifier, taxonomy=taxonomy)
    policy = (DecisionPolicy.load(
        args.policy,
        product_id=normal.product_id,
        normal_version=normal.model_version,
        classifier_version=classifier.artifact_version,
        taxonomy_version=taxonomy.version,
    ) if args.policy else DecisionPolicy())
    pipeline = InferencePipeline(extractor=extractor, normal_model=normal,
                                 classifier=classifier, taxonomy=taxonomy,
                                 policy=policy)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        for row in rows:
            path = (args.manifest.parent / row["image"]).resolve()
            embedding = extractor.extract(load_image(path)).numpy()
            result = pipeline.infer_embedding(np.asarray(embedding))
            record = {
                **row,
                "similarity": result.similarity,
                "predicted_result": result.result,
                "predicted_defect_class": result.defect_class,
                "confidence": result.confidence,
            }
            if args.split == "test":
                record["expected_result"] = (
                    "CONFORMING" if row["label"] == "CONFORMING" else "NON_CONFORMING"
                )
                record["expected_defect_class"] = (
                    None if row["label"] == "CONFORMING" else row["label"]
                )
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps({"split": args.split, "samples": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
