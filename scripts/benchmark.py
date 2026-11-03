"""Functional local benchmark with warm-up, stage timings and memory method."""
import argparse,json,platform,time,tracemalloc,statistics
from pathlib import Path
from PIL import Image
from feature_extractor import FeatureExtractor
from normal_model import NormalModel
from preprocessing import transform_image
from src.contracts import build_piece_analysis
from src.inference import DecisionPolicy,InferencePipeline,KnownDefectClassifier
from src.taxonomy import load_taxonomy
def stats(values): return {"mean_ms":statistics.mean(values)*1000,"p50_ms":statistics.median(values)*1000,"p95_ms":sorted(values)[max(0,int(.95*len(values))-1)]*1000}
def main():
    p=argparse.ArgumentParser(); p.add_argument("--image",type=Path,required=True); p.add_argument("--repeat",type=int,default=10); p.add_argument("--output",type=Path,required=True); p.add_argument("--normal-model",type=Path,required=True); p.add_argument("--classifier",type=Path,required=True); p.add_argument("--policy",type=Path,required=True); p.add_argument("--taxonomy",type=Path,required=True); p.add_argument("--taxonomy-descriptor",type=Path,required=True); p.add_argument("--taxonomy-version",required=True); p.add_argument("--device",default="cpu",choices=("cpu","auto","cuda")); a=p.parse_args()
    if a.repeat<1: raise SystemExit("repeat deve ser positivo")
    normal=NormalModel.load(a.normal_model); taxonomy=load_taxonomy(a.taxonomy,a.taxonomy_descriptor,expected_version=a.taxonomy_version); extractor=FeatureExtractor(a.device); classifier=KnownDefectClassifier.load(a.classifier,taxonomy=taxonomy); policy=DecisionPolicy.load(a.policy,product_id=normal.product_id,normal_version=normal.model_version,classifier_version=classifier.artifact_version,taxonomy_version=taxonomy.version); pipeline=InferencePipeline(extractor=extractor,normal_model=normal,classifier=classifier,taxonomy=taxonomy,policy=policy)
    image=Image.open(a.image).convert("RGB"); pipeline.infer(image)
    measurements={key:[] for key in ("preprocess","extraction","decision","event_validation","total")}; memory=[]
    for _ in range(a.repeat):
        tracemalloc.start(); total=time.perf_counter(); start=time.perf_counter(); tensor=transform_image(image); measurements["preprocess"].append(time.perf_counter()-start); start=time.perf_counter(); embedding=extractor.extract(tensor).numpy(); measurements["extraction"].append(time.perf_counter()-start); start=time.perf_counter(); result=pipeline.infer_embedding(embedding); measurements["decision"].append(time.perf_counter()-start); start=time.perf_counter(); build_piece_analysis(taxonomy=taxonomy,source_id="benchmark",session_id="1c3ab594-7321-4d43-9e71-8f2cd5e1d542",sequence=0,captured_at="2026-10-20T12:00:00.000Z",published_at="2026-10-20T12:00:00.000Z",artifact_version=f"normal={normal.model_version};classifier={classifier.artifact_version};policy={policy.version}",frame_index=0,detection_id=0,bbox=[0,0,image.width,image.height],result=result.result,confidence=result.confidence,similarity=result.similarity,defect_class=result.defect_class); measurements["event_validation"].append(time.perf_counter()-start); measurements["total"].append(time.perf_counter()-total); memory.append(tracemalloc.get_traced_memory()[1]); tracemalloc.stop()
    report={"status":"measured-local","hardware":platform.platform(),"device":str(extractor.device),"samples":a.repeat,"artifacts":{"normal":normal.model_version,"classifier":classifier.artifact_version,"policy":policy.version,"taxonomy":taxonomy.version},"timing":{key:stats(value) for key,value in measurements.items()},"memory":{"method":"tracemalloc peak Python allocations","peak_bytes_max":max(memory),"peak_bytes_mean":statistics.mean(memory)}}; a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(report,ensure_ascii=False,indent=2)); image.close()
if __name__=="__main__": main()
