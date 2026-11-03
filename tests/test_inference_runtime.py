import numpy as np
import pytest
from PIL import Image
from src.inference import DecisionPolicy
from src.runtime import Detection, Frame, FrameCorrelator
from src.publisher import EventPublisher, MemoryTransport
from normal_model import NormalModel

def test_policy_boundaries_are_explicit():
    with pytest.raises(ValueError): DecisionPolicy(anomaly_similarity=.9, conforming_similarity=.8)

def test_correlation_uses_same_source_session_frame_and_validates_crop():
    c=FrameCorrelator(max_frames=1); image=Image.new("RGB", (20,20)); c.add(Frame("a","s",4,"t",image))
    assert c.crop(Detection("a","s",4,0,"t",[2,3,10,12])).size == (8,9)
    with pytest.raises(LookupError): c.get(Detection("b","s",4,0,"t",[0,0,1,1]))
    with pytest.raises(ValueError): c.get(Detection("a","s",4,0,"other",[0,0,1,1]))

def test_normal_model_metadata_is_persistable():
    model=NormalModel.build(np.zeros((2,2)),"p","v","resnet18","IMAGENET1K_V1")
    assert model.embedding_dim == 2

def test_publisher_validates_before_transport_and_preserves_identity():
    class Tax:
        version="defects-a1-1.0.0"
        def resolve(self, value, *, version): return {"defect_class": value}
    transport=MemoryTransport(); publisher=EventPublisher(Tax(), transport)
    fields=dict(source_id="cam",session_id="1c3ab594-7321-4d43-9e71-8f2cd5e1d542",sequence=1,captured_at="2026-10-20T12:00:00.000Z",artifact_version="piece-1",frame_index=2,detection_id=3,bbox=[0,0,2,2],result="CONFORMING",confidence=.9,similarity=.9,message_id="1c3ab594-7321-4d43-9e71-8f2cd5e1d542",published_at="2026-10-20T12:00:00.000Z")
    first=publisher.publish(**fields); second=publisher.publish(**fields)
    assert first["message_id"] == second["message_id"] and len(transport.events)==2
