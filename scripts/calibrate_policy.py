"""Select policy thresholds only from calibration predictions."""
import argparse,json
from pathlib import Path
from src.inference import DecisionPolicy
def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--product",required=True); p.add_argument("--normal-version",required=True); p.add_argument("--classifier-version",required=True); p.add_argument("--taxonomy-version",required=True); a=p.parse_args()
    rows=[json.loads(line) for line in a.input.open(encoding="utf-8") if line.strip()]
    if not rows or any("label" not in r or "similarity" not in r for r in rows): raise SystemExit("calibração requer label e similarity")
    normal=[float(r["similarity"]) for r in rows if r["label"]=="CONFORMING"]; defective=[float(r["similarity"]) for r in rows if r["label"]!="CONFORMING"]
    if not normal or not defective: raise SystemExit("calibração requer normais e defeituosas")
    candidates=sorted(set(normal+defective)); best=max(candidates,key=lambda t:sum(x>=t for x in normal)/len(normal)-sum(x>=t for x in defective)/len(defective))
    anomaly=min(defective); policy=DecisionPolicy(conforming_similarity=float(best),anomaly_similarity=float(anomaly),uncertain_margin=.05)
    policy.save(a.output,product_id=a.product,normal_version=a.normal_version,classifier_version=a.classifier_version,taxonomy_version=a.taxonomy_version)
if __name__=="__main__": main()
