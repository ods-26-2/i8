"""Measure the shared extractor on two explicit images in a Linux CPU process."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import statistics
import time

import torch
from feature_extractor import FeatureExtractor
from similarities_extractor import MotorSimilaridade


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    for path in (args.reference, args.image):
        if not path.is_file():
            parser.error(f"Image does not exist: {path}")

    extractor = FeatureExtractor("cpu")
    motor = MotorSimilaridade(extractor=extractor)
    # Warm-up is excluded from the timings; no second model is constructed.
    motor.calcular_score(motor.extrair_vetor(args.reference), motor.extrair_vetor(args.image))
    measurements = {"reference_extraction": [], "target_extraction": [], "pairwise_score": []}
    scores = []
    for _ in range(args.repeat):
        start = time.perf_counter()
        reference = motor.extrair_vetor(args.reference)
        measurements["reference_extraction"].append(time.perf_counter() - start)
        start = time.perf_counter()
        target = motor.extrair_vetor(args.image)
        measurements["target_extraction"].append(time.perf_counter() - start)
        start = time.perf_counter()
        scores.append(motor.calcular_score(target, reference))
        measurements["pairwise_score"].append(time.perf_counter() - start)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "scope": "local CPU measurement; pairwise metric; not industrial evaluation or end-to-end latency",
        "device": str(extractor.device), "platform": platform.platform(),
        "machine": platform.machine(), "torch": torch.__version__,
        "threads": torch.get_num_threads(), "samples": args.repeat,
        "inputs": {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                   for name, path in (("reference", args.reference), ("target", args.image))},
        "extractor": extractor.name, "weights": extractor.weights_name,
        "embedding_dim": extractor.embedding_dim,
        "preprocessing_version": extractor.preprocessing_version,
        "score_metric": motor.score_metric, "scores": scores,
        "same_extractor_instance": motor.extractor is extractor,
        "same_model_instance": motor.modelo is extractor.model,
        "model_parameter_bytes": sum(p.numel() * p.element_size() for p in extractor.model.parameters()),
        "process_peak_rss_bytes": peak if platform.system() == "Darwin" else peak * 1024,
        "memory_method": "ru_maxrss: whole-process peak including imports and weight loading; includes native Torch allocations",
        "timing_ms": {name: {"min": min(values) * 1000,
                             "median": statistics.median(values) * 1000,
                             "max": max(values) * 1000} for name, values in measurements.items()},
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
