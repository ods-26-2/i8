"""Build a product-specific normal reference using official weights only."""
import argparse, json
from pathlib import Path
import numpy as np
from scripts.prepare_dataset import validate_manifest

def main():
    p = argparse.ArgumentParser(); p.add_argument("--product", required=True); inputs = p.add_mutually_exclusive_group(required=True); inputs.add_argument("--images", type=Path); inputs.add_argument("--manifest", type=Path); p.add_argument("--output", type=Path, required=True); p.add_argument("--model-version", default="normal-1.0.0"); p.add_argument("--device", default="cpu", choices=("cpu","auto","cuda"))
    a = p.parse_args()
    if a.manifest:
        inventory = validate_manifest(a.manifest)
        paths = [(a.manifest.parent / row["image"]).resolve() for row in inventory["images"]
                 if row["product_id"] == a.product and row["split"] == "train" and row["label"] == "CONFORMING"]
        if not paths:
            raise SystemExit("BLOQUEADO: treino normal sem CONFORMING no manifesto/produto")
    from preprocessing import list_images, load_image
    from feature_extractor import FeatureExtractor
    from normal_model import NormalModel
    if not a.manifest:
        paths = list_images(a.images)
    extractor = FeatureExtractor(a.device); vectors = []
    for path in paths:
        vectors.append(extractor.extract(load_image(path)).numpy())
    model = NormalModel.build(np.stack(vectors), a.product, a.model_version, extractor.name, extractor.weights_name)
    output = a.output / f"normal_{a.product}_{a.model_version}.json"; model.save(output)
    print(json.dumps({"product_id": a.product, "images": len(vectors), "artifact": str(output), "weights": extractor.weights_name}))
if __name__ == "__main__": main()
