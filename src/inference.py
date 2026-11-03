"""S3-05 inference, deterministic classifier and versioned policy."""
from dataclasses import dataclass
import json, math
from pathlib import Path
import numpy as np
from PIL import Image
from feature_extractor import FeatureExtractor
from normal_model import NormalModel
from normal_model.runtime import distance_to_normal
from preprocessing import transform_image
from src.taxonomy import Taxonomy

RESULTS=("CONFORMING","NON_CONFORMING","ANOMALY","UNCERTAIN")
POLICY_VERSION="policy-1.0.0"

@dataclass(frozen=True)
class DecisionPolicy:
    conforming_similarity: float=.85
    known_confidence: float=.80
    anomaly_similarity: float=.45
    uncertain_margin: float=.05
    version: str=POLICY_VERSION
    def __post_init__(self):
        values=(self.conforming_similarity,self.known_confidence,self.anomaly_similarity,self.uncertain_margin)
        if any(not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in values) or self.anomaly_similarity>=self.conforming_similarity or not self.version.strip(): raise ValueError("política inválida")
    def save(self,path:Path,*,product_id,normal_version,classifier_version,taxonomy_version):
        data={"policy_version":self.version,"product_id":product_id,"normal_model_version":normal_version,"classifier_version":classifier_version,"taxonomy_version":taxonomy_version,"parameters":{key:getattr(self,key) for key in ("conforming_similarity","known_confidence","anomaly_similarity","uncertain_margin")}}
        Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    @classmethod
    def load(cls,path:Path,*,product_id,normal_version,classifier_version,taxonomy_version):
        data=json.loads(Path(path).read_text(encoding="utf-8")); required={"policy_version","product_id","normal_model_version","classifier_version","taxonomy_version","parameters"}
        if set(data)!=required or data["policy_version"]!=POLICY_VERSION or data["product_id"]!=product_id or data["normal_model_version"]!=normal_version or data["classifier_version"]!=classifier_version or data["taxonomy_version"]!=taxonomy_version: raise ValueError("política incompatível")
        return cls(version=data["policy_version"],**data["parameters"])

@dataclass(frozen=True)
class InferenceResult:
    result: str
    confidence: float
    similarity: float
    defect_class: str|None=None
    model_version: str=""

class KnownDefectClassifier:
    """Multinomial linear classifier trained on embeddings, not fixed scores."""
    def __init__(self,product_id,artifact_version,classes,weights,bias,feature_extractor="resnet18",weights_name="IMAGENET1K_V1",preprocessing_version="imagenet-resnet18-v1",taxonomy_version=""):
        if not product_id.strip() or not artifact_version.strip() or not classes or len(set(classes))!=len(classes): raise ValueError("metadados/classes inválidos")
        self.product_id,self.artifact_version,self.classes=product_id,artifact_version,list(classes); self.weights=np.asarray(weights,dtype=np.float64); self.bias=np.asarray(bias,dtype=np.float64)
        if self.weights.ndim!=2 or self.weights.shape[0]!=len(self.classes) or self.bias.shape!=(len(self.classes),) or not np.isfinite(self.weights).all() or not np.isfinite(self.bias).all(): raise ValueError("dimensões/valores inválidos")
        self.feature_extractor,self.weights_name,self.preprocessing_version,self.taxonomy_version=feature_extractor,weights_name,preprocessing_version,taxonomy_version
    @classmethod
    def train(cls,embeddings,labels,*,product_id,artifact_version,taxonomy,seed=0,epochs=300,learning_rate=.05):
        x=np.asarray(embeddings,dtype=np.float64); labels=list(labels)
        if x.ndim!=2 or not len(x) or len(labels)!=len(x) or not np.isfinite(x).all(): raise ValueError("embeddings/labels inválidos")
        classes=sorted(set(labels));
        if len(classes)<2: raise ValueError("são necessárias duas classes")
        for label in classes: taxonomy.resolve(label,version=taxonomy.version)
        y=np.array([classes.index(label) for label in labels]); rng=np.random.default_rng(seed); weights=rng.normal(0,.01,(len(classes),x.shape[1])); bias=np.zeros(len(classes))
        for _ in range(epochs):
            logits=x@weights.T+bias; logits-=logits.max(axis=1,keepdims=True); probs=np.exp(logits); probs/=probs.sum(axis=1,keepdims=True); probs[np.arange(len(x)),y]-=1; weights-=learning_rate*(probs.T@x/len(x)); bias-=learning_rate*probs.mean(axis=0)
        return cls(product_id,artifact_version,classes,weights,bias,taxonomy_version=taxonomy.version)
    def save(self,path:Path):
        data={"artifact_type":"known_defect_classifier","artifact_version":self.artifact_version,"product_id":self.product_id,"classes":self.classes,"feature_extractor":self.feature_extractor,"weights":self.weights_name,"preprocessing_version":self.preprocessing_version,"taxonomy_version":self.taxonomy_version,"weights_matrix":self.weights.tolist(),"bias":self.bias.tolist()}; Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    @classmethod
    def load(cls,path:Path,*,taxonomy:Taxonomy):
        data=json.loads(Path(path).read_text(encoding="utf-8")); required={"artifact_type","artifact_version","product_id","classes","feature_extractor","weights","preprocessing_version","taxonomy_version","weights_matrix","bias"}
        if set(data)!=required or data["artifact_type"]!="known_defect_classifier" or data["taxonomy_version"]!=taxonomy.version: raise ValueError("classificador incompatível")
        for label in data["classes"]: taxonomy.resolve(label,version=taxonomy.version)
        return cls(data["product_id"],data["artifact_version"],data["classes"],data["weights_matrix"],data["bias"],data["feature_extractor"],data["weights"],data["preprocessing_version"],data["taxonomy_version"])
    def predict(self,embedding):
        x=np.asarray(embedding,dtype=np.float64)
        if x.ndim!=1 or x.shape[0]!=self.weights.shape[1] or not np.isfinite(x).all(): raise ValueError("embedding incompatível")
        logits=self.weights@x+self.bias; logits-=logits.max(); probs=np.exp(logits); probs/=probs.sum(); index=int(probs.argmax()); return self.classes[index],float(probs[index])

class InferencePipeline:
    def __init__(self,*,extractor:FeatureExtractor,normal_model:NormalModel,classifier:KnownDefectClassifier|None,taxonomy:Taxonomy,policy=DecisionPolicy()):
        if normal_model.feature_extractor!=extractor.name or normal_model.embedding_dim!=extractor.embedding_dim or normal_model.weights!=extractor.weights_name or normal_model.preprocessing_version!=extractor.preprocessing_version: raise ValueError("extrator incompatível")
        if classifier and (classifier.product_id!=normal_model.product_id or classifier.weights_name!=extractor.weights_name or classifier.preprocessing_version!=extractor.preprocessing_version or classifier.weights.shape[1]!=extractor.embedding_dim): raise ValueError("classificador incompatível")
        for defect in classifier.classes if classifier else []: taxonomy.resolve(defect,version=taxonomy.version)
        self.extractor,self.normal_model,self.classifier,self.taxonomy,self.policy=extractor,normal_model,classifier,taxonomy,policy
    def infer_embedding(self,embedding):
        normal=distance_to_normal(embedding,self.normal_model); similarity=float(np.clip(normal.score,0,1)); known,known_confidence=self.classifier.predict(embedding) if self.classifier else (None,0.0); margin=self.policy.uncertain_margin
        if known is not None and known_confidence>=self.policy.known_confidence and similarity<self.policy.conforming_similarity: result,confidence,defect="NON_CONFORMING",known_confidence,known
        elif similarity>=self.policy.conforming_similarity and similarity-self.policy.conforming_similarity>margin: result,confidence,defect="CONFORMING",similarity,None
        elif similarity<=self.policy.anomaly_similarity and self.policy.anomaly_similarity-similarity>margin: result,confidence,defect="ANOMALY",1-similarity,None
        else: result,confidence,defect="UNCERTAIN",max(0,1-abs(similarity-self.policy.conforming_similarity)),None
        return InferenceResult(result,float(np.clip(confidence,0,1)),similarity,defect,self.normal_model.model_version)
    def infer(self,image):
        with Image.open(image) if isinstance(image,(str,Path)) else _image_context(image) as loaded: embedding=self.extractor.extract(transform_image(loaded)).numpy()
        return self.infer_embedding(embedding)
class _image_context:
    def __init__(self,image): self.image=image.convert("RGB")
    def __enter__(self): return self.image
    def __exit__(self,*args): self.image.close()
