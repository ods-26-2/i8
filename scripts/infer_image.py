"""Run the artifact-backed local inference flow."""
import argparse,json
from pathlib import Path
from feature_extractor import FeatureExtractor
from normal_model import NormalModel
from src.inference import DecisionPolicy,InferencePipeline,KnownDefectClassifier
from src.taxonomy import load_taxonomy
def main():
    p=argparse.ArgumentParser(); p.add_argument("--image",required=True); p.add_argument("--normal-model",type=Path,required=True); p.add_argument("--classifier",type=Path); p.add_argument("--policy",type=Path); p.add_argument("--taxonomy",type=Path,required=True); p.add_argument("--taxonomy-descriptor",type=Path,required=True); p.add_argument("--taxonomy-version",required=True); p.add_argument("--normal-only",action="store_true"); p.add_argument("--device",default="cpu",choices=("cpu","auto","cuda")); a=p.parse_args()
    if not a.normal_only and (a.classifier is None or a.policy is None): raise SystemExit("modo completo requer --classifier e --policy; use --normal-only explicitamente")
    normal=NormalModel.load(a.normal_model); taxonomy=load_taxonomy(a.taxonomy,a.taxonomy_descriptor,expected_version=a.taxonomy_version); extractor=FeatureExtractor(a.device); classifier=None if a.normal_only else KnownDefectClassifier.load(a.classifier,taxonomy=taxonomy)
    policy=DecisionPolicy() if a.normal_only else DecisionPolicy.load(a.policy,product_id=normal.product_id,normal_version=normal.model_version,classifier_version=classifier.artifact_version,taxonomy_version=taxonomy.version)
    result=InferencePipeline(extractor=extractor,normal_model=normal,classifier=classifier,taxonomy=taxonomy,policy=policy).infer(a.image); print(json.dumps(result.__dict__,ensure_ascii=False))
if __name__=="__main__": main()
