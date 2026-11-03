"""6c construction, validation and stable retry publication."""
from src.contracts import build_piece_analysis,validate_piece_analysis
class EventPublisher:
    def __init__(self,taxonomy,transport): self.taxonomy,self.transport=taxonomy,transport
    def build(self,**fields): return build_piece_analysis(taxonomy=self.taxonomy,**fields)
    def publish_event(self,event):
        validate_piece_analysis(event,self.taxonomy); self.transport.publish(event); return event
    def publish(self,**fields): return self.publish_event(self.build(**fields))
class MemoryTransport:
    def __init__(self): self.events=[]
    def publish(self,event): self.events.append(event)
