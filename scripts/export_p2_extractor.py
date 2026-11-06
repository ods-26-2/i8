"""Export official I8 ResNet18 embedding model to a P2 MODEL package.

Only exports the feature extractor. Normal model, classifier, policy and image
preprocessing remain in I8. No dataset, calibration or TensorRT claim is made.
"""
import argparse
import hashlib
import json
from pathlib import Path

import torch

from feature_extractor import FeatureExtractor


def export_package(output, *, version='1.0.0', extractor=None):
    if not version or any(c not in '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-_' for c in version):
        raise ValueError('versão inválida')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    extractor = extractor if extractor is not None else FeatureExtractor('cpu')
    if (extractor.name != 'resnet18' or extractor.weights_name != 'IMAGENET1K_V1'
            or str(extractor.device) != 'cpu' or extractor.embedding_dim != 512
            or extractor.preprocessing_version != 'imagenet-resnet18-v1'):
        raise ValueError('exportação exige extrator oficial CPU compatível')
    path = output / 'resnet18.onnx'
    torch.onnx.export(extractor.model, torch.zeros(1, 3, 224, 224), str(path),
                      input_names=['images'], output_names=['embedding'],
                      opset_version=17, dynamo=False)
    metadata = dict(artifact_id='i8-resnet18-imagenet', artifact_version=version,
        onnx_file=path.name, hash_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        precision='FP32', task='other', input_shape={'images': [1, 3, 224, 224]},
        i8_extractor=dict(feature_extractor=extractor.name, weights=extractor.weights_name,
                         preprocessing_version=extractor.preprocessing_version,
                         embedding_dim=extractor.embedding_dim))
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', default='1.0.0')
    args = parser.parse_args()
    print(json.dumps(export_package(args.output, version=args.version)))


if __name__ == '__main__':
    main()
