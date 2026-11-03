"""Replay frames/detections through correlation, real inference and 6c validation."""
import argparse,json,uuid
from pathlib import Path
from PIL import Image
from feature_extractor import FeatureExtractor
from normal_model import NormalModel
from src.contracts import build_piece_analysis
from src.inference import DecisionPolicy,InferencePipeline,KnownDefectClassifier
from src.publisher import EventPublisher,MemoryTransport
from src.runtime import Detection,Frame,FrameCorrelator,ReplayRuntime
from src.taxonomy import load_taxonomy
def main():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--normal-model",type=Path,required=True); p.add_argument("--classifier",type=Path,required=True); p.add_argument("--policy",type=Path,required=True); p.add_argument("--taxonomy",type=Path,required=True); p.add_argument("--taxonomy-descriptor",type=Path,required=True); p.add_argument("--taxonomy-version",required=True); p.add_argument("--artifact-version",required=True); a=p.parse_args()
    normal=NormalModel.load(a.normal_model); taxonomy=load_taxonomy(a.taxonomy,a.taxonomy_descriptor,expected_version=a.taxonomy_version); classifier=KnownDefectClassifier.load(a.classifier,taxonomy=taxonomy); policy=DecisionPolicy.load(a.policy,product_id=normal.product_id,normal_version=normal.model_version,classifier_version=classifier.artifact_version,taxonomy_version=taxonomy.version); pipeline=InferencePipeline(extractor=FeatureExtractor("cpu"),normal_model=normal,classifier=classifier,taxonomy=taxonomy,policy=policy)
    correlator=FrameCorrelator(); events=[]
    for sequence,line in enumerate(a.input.open(encoding="utf-8"),1):
        if not line.strip(): continue
        row=json.loads(line); session=row["session_id"]; frame=Frame(row["source_id"],session,int(row["frame_index"]),row["captured_at"],Image.open((a.input.parent/row["frame_path"]).resolve())); correlator.add(frame); detection=Detection(row["source_id"],session,int(row["frame_index"]),int(row["detection_id"]),row["captured_at"],list(row["bbox"]))
        result=ReplayRuntime(pipeline.infer).execute(detection,correlator); event=build_piece_analysis(taxonomy=taxonomy,source_id=row["source_id"],session_id=session,sequence=sequence,captured_at=row["captured_at"],artifact_version=a.artifact_version,frame_index=detection.frame_index,detection_id=detection.detection_id,bbox=detection.bbox,result=result.result,confidence=result.confidence,similarity=result.similarity,defect_class=result.defect_class,message_id=str(uuid.uuid4()),published_at=row.get("published_at",row["captured_at"])); events.append(event); frame.image.close()
    a.output.write_text("\n".join(json.dumps(event,ensure_ascii=False) for event in events)+"\n",encoding="utf-8")
if __name__=="__main__": main()
