import math
from pathlib import Path

import numpy as np
from PIL import Image
import pytest
import torch

from normal_model import NormalModel
from preprocessing import load_image, transform_image
import similarities_extractor as module
from similarities_extractor import ImageProcessingError, MotorSimilaridade
from src.inference import InferencePipeline


class ExtractorDouble:
    name = "resnet18"
    embedding_dim = 512
    weights_name = "IMAGENET1K_V1"
    preprocessing_version = "imagenet-resnet18-v1"
    device = torch.device("cpu")

    def __init__(self):
        self.model = object()
        self.inputs = []

    def extract(self, image):
        self.inputs.append(image.clone())
        return torch.ones(512)


@pytest.fixture
def motor():
    return MotorSimilaridade(extractor=ExtractorDouble())


@pytest.mark.parametrize('left,right,expected', [
    ([1., 0.], [1., 0.], 1.), ([1., 0.], [-1., 0.], 0.),
    ([1., 0.], [0., 1.], .5), ([2., 4.], [1., 2.], 1.),
])
def test_versioned_pairwise_score(motor, left, right, expected):
    assert motor.calcular_score(torch.tensor(left), torch.tensor([right])) == pytest.approx(expected)
    assert motor.score_metric == "cosine-affine-v1"


@pytest.mark.parametrize('bad', [
    torch.tensor([float('nan'), 1.]), torch.tensor([float('inf'), 1.]),
    torch.tensor([float('-inf'), 1.]), torch.zeros(2), torch.tensor([]),
    torch.ones(2, 2), torch.ones(1, 1, 2), torch.tensor([1, 2]), None,
])
def test_invalid_vectors_are_errors_not_perfect_matches(motor, bad):
    for left, right in [(bad, torch.ones(2)), (torch.ones(2), bad)]:
        with pytest.raises(ValueError):
            motor.calcular_score(left, right)


def test_mismatched_dimensions_do_not_broadcast(motor):
    with pytest.raises(ValueError, match='dimensões'):
        motor.calcular_score(torch.tensor([[1., 2.]]), torch.tensor([[1.]]))


def test_path_and_pil_use_same_preprocessing_and_one_existing_extractor(tmp_path, monkeypatch):
    image = Image.new('RGB', (320, 240), (32, 64, 128))
    path = tmp_path / 'frame.png'
    image.save(path)
    extractor = ExtractorDouble()
    monkeypatch.setattr(module, 'FeatureExtractor', lambda *a, **k: pytest.fail('second extractor created'))
    motor = MotorSimilaridade(extractor=extractor)
    first, second = motor.extrair_vetor(path), motor.extrair_vetor(image)
    assert first.shape == (1, 512) and torch.equal(first, second)
    assert torch.equal(load_image(path), transform_image(image))
    assert torch.equal(extractor.inputs[0], extractor.inputs[1])
    assert motor.modelo is extractor.model and motor.extractor is extractor
    assert image.getpixel((0, 0)) == (32, 64, 128)


def test_default_constructor_creates_one_canonical_extractor(monkeypatch):
    calls = []
    monkeypatch.setattr(module, 'FeatureExtractor', lambda device: calls.append(device) or ExtractorDouble())
    motor = MotorSimilaridade(device_mode='cpu')
    assert calls == ['cpu'] and motor.extractor.model is motor.modelo


@pytest.mark.parametrize('value', [None, 'missing.png', 5])
def test_invalid_images_are_reported(motor, value):
    with pytest.raises(ImageProcessingError):
        motor.extrair_vetor(value)


def test_legacy_import_is_the_same_implementation():
    from src.similarities_extractor import MotorSimilaridade as CompatibilityMotor
    assert CompatibilityMotor is MotorSimilaridade


def test_pipeline_reuses_extractor_and_preserves_normal_score():
    extractor = ExtractorDouble()
    normal = NormalModel.build(np.ones((2, 512)), 'p', 'normal-1', 'resnet18', 'IMAGENET1K_V1')
    pipeline = InferencePipeline(extractor=extractor, normal_model=normal, classifier=None, taxonomy=object())
    image = Image.new('RGB', (240, 320))
    expected = pipeline.infer_embedding(np.ones(512))
    actual = pipeline.infer(image)
    assert actual == expected and actual.similarity == 1.
    assert pipeline.similarity.extractor is pipeline.extractor
    assert pipeline.similarity.modelo is extractor.model
    assert len(extractor.inputs) == 1


def test_normal_distance_is_not_replaced_by_pairwise_cosine():
    extractor = ExtractorDouble()
    normal = NormalModel.build(np.array([[0.] * 512, [2.] * 512]), 'p', 'n', 'resnet18', 'IMAGENET1K_V1')
    pipeline = InferencePipeline(extractor=extractor, normal_model=normal, classifier=None, taxonomy=object())
    assert pipeline.infer_embedding(np.ones(512) * 2).similarity == pytest.approx(math.exp(-1))
