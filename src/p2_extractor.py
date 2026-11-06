"""Explicit FP32/CPU bridge to the published P2 library; no Torch fallback."""
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import torch


class P2FeatureExtractor:
    name = "resnet18"
    weights_name = "IMAGENET1K_V1"
    embedding_dim = 512
    preprocessing_version = "imagenet-resnet18-v1"

    def __init__(self, engine_ref, *, p2_module=None):
        if not isinstance(engine_ref, str) or not engine_ref or any(x in engine_ref for x in ('/', '\\')) or engine_ref in {'.', '..'}:
            raise ValueError("engine_ref P2 inválido")
        if os.environ.get('P2_BACKEND') != 'ort':
            raise ValueError("Esta integração exige P2_BACKEND=ort; TensorRT precisa de validação própria")
        root = Path(os.environ.get('P2_ENGINE_DIR', '/opt/ods/engines')) / engine_ref
        metadata = json.loads((root / 'metadata.json').read_text())
        provenance = metadata['i8_extractor']
        expected = dict(feature_extractor=self.name, weights=self.weights_name,
                        preprocessing_version=self.preprocessing_version, embedding_dim=512)
        if provenance != expected or metadata['task'] != 'other':
            raise ValueError("pacote P2 incompatível com os artefatos I8")
        if f"{metadata['artifact_id']}-{metadata['artifact_version']}" != engine_ref:
            raise ValueError("identidade do pacote P2 incompatível")
        if metadata['onnx_file'] != 'resnet18.onnx':
            raise ValueError("nome ONNX incompatível")
        actual = hashlib.sha256((root / 'resnet18.onnx').read_bytes()).hexdigest()
        if actual != metadata['hash_sha256']:
            raise ValueError("hash do extrator ONNX incompatível")
        manifest = json.loads((root / 'manifest.json').read_text())
        if (manifest['engine_ref'] != engine_ref
                or manifest['source']['onnx_file'] != 'resnet18.onnx'
                or manifest['source']['sha256'] != actual
                or manifest['inputs'] != {'images': {'shape': [1,3,224,224], 'dtype': 'float32'}}
                or manifest['outputs'] != {'embedding': {'shape': [1,512], 'dtype': 'float32'}}):
            raise ValueError("manifesto P2 diverge do pacote I8 verificado")
        if p2_module is None:
            import p2 as p2_module
        self._p2 = p2_module
        self._handle = None
        self.device = torch.device('cpu')
        self.last_stats = None
        handle = self._p2.load(engine_ref, {'precision': 'FP32'})
        try:
            info = self._p2.info(handle)
            if (info['input_shape'] != {'images': [1, 3, 224, 224]}
                    or info['output_shape'] != {'embedding': [1, 512]}
                    or info['precision'] != 'FP32' or info['max_batch'] != 1
                    or info['engine_version'] != engine_ref + '-fp32'):
                raise ValueError("I/O ou versão P2 incompatível com ResNet18 I8")
            self.engine_info = info
            self._handle = handle
            # Historical MotorSimilaridade alias; the model is the same P2 handle.
            self.model = handle
        except BaseException:
            self._p2.release(handle)
            raise

    def extract(self, image):
        if self._handle is None:
            raise ValueError("extrator P2 já liberado")
        if (not isinstance(image, torch.Tensor) or image.dtype != torch.float32
                or image.shape != (3, 224, 224) or not torch.isfinite(image).all()):
            raise ValueError("entrada P2 deve ser tensor float32 finito C×224×224")
        batch = np.ascontiguousarray(image.detach().cpu().unsqueeze(0).numpy())
        outputs, stats = self._p2.infer(self._handle, {'images': batch})
        vector = outputs.get('embedding')
        if (set(outputs) != {'embedding'} or not isinstance(vector, np.ndarray)
                or vector.shape != (1, 512) or vector.dtype != np.float32
                or not np.isfinite(vector).all()):
            raise ValueError("saída P2 deve ser embedding float32 finito [1,512]")
        self.last_stats = dict(stats)
        return torch.from_numpy(vector[0].copy())

    def close(self):
        if self._handle is not None:
            self._p2.release(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
