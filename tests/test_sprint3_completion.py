import json, subprocess, sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from src.inference import DecisionPolicy, InferencePipeline, KnownDefectClassifier
from src.publisher import EventPublisher
from src.runtime import Detection, Frame, FrameCorrelator, FrameMissing, FrameExpired
from normal_model import NormalModel

class TaxonomyDouble:
    version="defects-a1-1.0.0"
    def resolve(self, value, *, version):
        if version != self.version or value not in {"AMASSADO", "FURADO"}: raise ValueError(value)
        return {"defect_class": value}

def test_classifier_trains_persists_and_validates_inputs(tmp_path):
    taxonomy=TaxonomyDouble(); x=np.array([[2.,0.],[2.1,0.],[0.,2.],[0.,2.1]])
    classifier=KnownDefectClassifier.train(x,["AMASSADO","AMASSADO","FURADO","FURADO"],product_id="p",artifact_version="classifier-1",taxonomy=taxonomy,seed=3)
    path=tmp_path/"classifier.json"; classifier.save(path); loaded=KnownDefectClassifier.load(path,taxonomy=taxonomy)
    assert loaded.predict(np.array([2.,0.]))[0] == "AMASSADO"
    with pytest.raises(ValueError): loaded.predict(np.array([np.nan,0.]))
    invalid=json.loads(path.read_text()); invalid["classes"]=["NORMAL"]; path.write_text(json.dumps(invalid))
    with pytest.raises(ValueError): KnownDefectClassifier.load(path,taxonomy=taxonomy)

def test_policy_persists_all_versions_and_rejects_mismatch(tmp_path):
    policy=DecisionPolicy(conforming_similarity=.8,uncertain_margin=.1); path=tmp_path/"policy.json"
    policy.save(path,product_id="p",normal_version="normal-1",classifier_version="classifier-1",taxonomy_version="defects-a1-1.0.0")
    assert DecisionPolicy.load(path,product_id="p",normal_version="normal-1",classifier_version="classifier-1",taxonomy_version="defects-a1-1.0.0").uncertain_margin == .1
    with pytest.raises(ValueError): DecisionPolicy.load(path,product_id="p",normal_version="normal-2",classifier_version="classifier-1",taxonomy_version="defects-a1-1.0.0")

def test_manifest_rejects_same_piece_across_sessions(tmp_path):
    image=tmp_path/"same.png"; Image.new("RGB",(4,4),"red").save(image)
    manifest=tmp_path/"manifest.csv"; manifest.write_text("product_id,image,label,piece_id,session_id,split\np,%s,CONFORMING,piece-1,s1,train\np,%s,CONFORMING,piece-1,s2,test\n"%(image.name,image.name),encoding="utf-8")
    result=subprocess.run([sys.executable,"scripts/prepare_dataset.py",str(manifest)],capture_output=True,text=True)
    assert result.returncode and "peça" in result.stderr+result.stdout

def test_runtime_ttl_and_duplicate_frame_with_injected_clock():
    now=[0.0]; correlator=FrameCorrelator(ttl_seconds=2,clock=lambda:now[0]); image=Image.new("RGB",(10,10)); frame=Frame("s","session",1,"2026-10-20T12:00:00.000Z",image); correlator.add(frame)
    correlator.add(frame); now[0]=3
    with pytest.raises(FrameMissing): correlator.get(Detection("s","session",1,0,frame.captured_at,[0,0,1,1]))
    assert correlator.evictions["expired"] == 1

def test_publisher_retries_same_event_identity():
    class Transport:
        def __init__(self): self.calls=0; self.events=[]
        def publish(self,event):
            self.calls+=1
            if self.calls==1: raise RuntimeError("temporary")
            self.events.append(event)
    transport=Transport(); publisher=EventPublisher(TaxonomyDouble(),transport)
    fields=dict(source_id="cam",session_id="1c3ab594-7321-4d43-9e71-8f2cd5e1d542",sequence=1,captured_at="2026-10-20T12:00:00.000Z",published_at="2026-10-20T12:00:00.000Z",artifact_version="composition-1",frame_index=1,detection_id=1,bbox=[0,0,2,2],result="CONFORMING",confidence=.9,similarity=.9,message_id="1c3ab594-7321-4d43-9e71-8f2cd5e1d542")
    event=publisher.build(**fields)
    with pytest.raises(RuntimeError): publisher.publish_event(event)
    publisher.publish_event(event)
    assert transport.events[0]["message_id"]==event["message_id"] and transport.events[0]["published_at"]==event["published_at"]
