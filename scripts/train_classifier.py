"""Train the known-defect classifier from the manifest's train split."""
import argparse, csv
from pathlib import Path
import numpy as np
from feature_extractor import FeatureExtractor
from preprocessing import load_image
from src.inference import KnownDefectClassifier
from src.taxonomy import load_taxonomy
def main():
    p=argparse.ArgumentParser(); p.add_argument("--manifest",type=Path,required=True); p.add_argument("--taxonomy",type=Path,required=True); p.add_argument("--taxonomy-descriptor",type=Path,required=True); p.add_argument("--taxonomy-version",required=True); p.add_argument("--product",required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--artifact-version",default="classifier-1.0.0"); p.add_argument("--seed",type=int,default=0); a=p.parse_args()
    taxonomy=load_taxonomy(a.taxonomy,a.taxonomy_descriptor,expected_version=a.taxonomy_version); rows=list(csv.DictReader(a.manifest.open(encoding="utf-8",newline=""))); rows=[r for r in rows if r["split"]=="train" and r["product_id"]==a.product and r["label"]!="CONFORMING"]
    if not rows: raise SystemExit("treino do classificador requer defeitos conhecidos no split train")
    extractor=FeatureExtractor("cpu"); vectors=[extractor.extract(load_image((a.manifest.parent/row["image"]).resolve())).numpy() for row in rows]; labels=[row["label"] for row in rows]
    classifier=KnownDefectClassifier.train(np.stack(vectors),labels,product_id=a.product,artifact_version=a.artifact_version,taxonomy=taxonomy,seed=a.seed); classifier.save(a.output)
if __name__=="__main__": main()
