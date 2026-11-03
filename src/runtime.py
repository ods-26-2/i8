"""S3-06 local boundary with bounded storage, TTL and deterministic correlation."""
from dataclasses import dataclass
from collections import OrderedDict
import time
from typing import Callable

class FrameMissing(LookupError): pass
class FrameExpired(LookupError): pass
class FrameCapacityEvicted(LookupError): pass

@dataclass(frozen=True)
class Detection:
    source_id:str; session_id:str; frame_index:int; detection_id:int; captured_at:str; bbox:list[int]
@dataclass
class Frame:
    source_id:str; session_id:str; frame_index:int; captured_at:str; image:object; arrival_time:float|None=None

class FrameCorrelator:
    """TTL uses local arrival time; captured_at is preserved and compared separately."""
    def __init__(self,max_frames=128,ttl_seconds=5.0,clock:Callable[[],float]=time.monotonic):
        if type(max_frames) is not int or max_frames<1 or ttl_seconds<=0: raise ValueError("limites inválidos")
        self.max_frames,self.ttl_seconds,self.clock=max_frames,float(ttl_seconds),clock; self.frames=OrderedDict(); self.evictions={"capacity":0,"expired":0}
    def add(self,frame:Frame):
        if not all(isinstance(x,str) and x.strip() for x in (frame.source_id,frame.session_id,frame.captured_at)) or type(frame.frame_index) is not int or frame.frame_index<0: raise ValueError("metadados do quadro inválidos")
        key=(frame.source_id,frame.session_id,frame.frame_index); frame.arrival_time=self.clock(); self.frames[key]=frame; self.frames.move_to_end(key)
        while len(self.frames)>self.max_frames: self.frames.popitem(last=False); self.evictions["capacity"]+=1
    def _purge(self):
        now=self.clock()
        for key,frame in list(self.frames.items()):
            if now-frame.arrival_time>self.ttl_seconds: del self.frames[key]; self.evictions["expired"]+=1
    def get(self,detection:Detection)->Frame:
        self._purge(); key=(detection.source_id,detection.session_id,detection.frame_index)
        if key not in self.frames: raise FrameMissing("quadro ausente, expirado ou removido por capacidade")
        frame=self.frames[key]
        if frame.captured_at!=detection.captured_at: raise ValueError("captured_at incompatível")
        if type(detection.detection_id) is not int or detection.detection_id<0: raise ValueError("detection_id inválido")
        if len(detection.bbox)!=4 or any(type(x) is not int for x in detection.bbox): raise ValueError("bbox deve ser [x_min,y_min,x_max,y_max]")
        x_min,y_min,x_max,y_max=detection.bbox; width,height=frame.image.size
        if not (0<=x_min<x_max<=width and 0<=y_min<y_max<=height): raise ValueError("bbox fora do quadro ou sem área")
        return frame
    def crop(self,detection):
        frame=self.get(detection); x_min,y_min,x_max,y_max=detection.bbox
        return frame.image.crop((x_min,y_min,x_max,y_max))

class ReplayRuntime:
    def __init__(self,infer:Callable): self.infer=infer
    def execute(self,detection,correlator):
        crop=correlator.crop(detection)
        try: return self.infer(crop)
        finally:
            close=getattr(crop,"close",None)
            if close: close()
