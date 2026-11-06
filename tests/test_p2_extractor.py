"""P2 adapter contracts plus real CPU/ONNX equivalence on synthetic images."""
import hashlib
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest
import torch
from PIL import Image

from src.p2_extractor import P2FeatureExtractor


class P2Double:
    def __init__(self):
        self.released = 0
        self.loads = []
        self.metadata = dict(engine_version='test-1-fp32', input_shape={'images': [1,3,224,224]},
                             output_shape={'embedding': [1,512]}, precision='FP32', max_batch=1)
        self.output = np.ones((1,512), dtype=np.float32)
        self.error = None

    def load(self, engine_ref, options):
        self.loads.append((engine_ref, options))
        return object()

    def info(self, handle): return self.metadata

    def infer(self, handle, feeds):
        assert feeds['images'].shape == (1,3,224,224)
        assert feeds['images'].dtype == np.float32 and feeds['images'].flags.c_contiguous
        if self.error: raise self.error
        return {'embedding': self.output}, {'latency_ms': 1.2, 'gpu_memory_mb': 0.0}

    def release(self, handle): self.released += 1


@pytest.fixture
def fake_package(tmp_path, monkeypatch):
    root = tmp_path / 'test-1'
    root.mkdir()
    (root/'resnet18.onnx').write_bytes(b'explicit-test-double')
    metadata = dict(artifact_id='test', artifact_version='1', onnx_file='resnet18.onnx',
        hash_sha256=hashlib.sha256(b'explicit-test-double').hexdigest(), task='other',
        i8_extractor=dict(feature_extractor='resnet18', weights='IMAGENET1K_V1',
                         preprocessing_version='imagenet-resnet18-v1', embedding_dim=512))
    (root/'metadata.json').write_text(json.dumps(metadata))
    monkeypatch.setenv('P2_ENGINE_DIR', str(tmp_path))
    monkeypatch.setenv('P2_BACKEND', 'ort')
    (root/'manifest.json').write_text(json.dumps(dict(engine_ref='test-1',
        source=dict(onnx_file='resnet18.onnx',sha256=metadata['hash_sha256']),
        inputs={'images':{'shape':[1,3,224,224],'dtype':'float32'}},
        outputs={'embedding':{'shape':[1,512],'dtype':'float32'}})))
    return root, metadata


def test_lifecycle_stats_copy_and_no_fallback(fake_package):
    p2 = P2Double()
    with P2FeatureExtractor('test-1', p2_module=p2) as extractor:
        result = extractor.extract(torch.zeros(3,224,224))
        result[0] = 99
        assert p2.output[0,0] == 1
        assert extractor.last_stats['gpu_memory_mb'] == 0
        assert extractor.engine_info['engine_version'] == 'test-1-fp32'
        assert p2.loads == [('test-1', {'precision':'FP32'})]
    extractor.close()
    assert p2.released == 1
    with pytest.raises(ValueError, match='liberado'): extractor.extract(torch.zeros(3,224,224))


@pytest.mark.parametrize('change', ['shape','version','precision','batch'])
def test_incompatible_engine_is_released(fake_package, change):
    p2 = P2Double()
    if change == 'shape': p2.metadata['output_shape'] = {'embedding':[1,1000]}
    elif change == 'version': p2.metadata['engine_version'] = 'another-fp32'
    elif change == 'precision': p2.metadata['precision'] = 'FP16'
    else: p2.metadata['max_batch'] = 2
    with pytest.raises(ValueError): P2FeatureExtractor('test-1', p2_module=p2)
    assert p2.released == 1


@pytest.mark.parametrize('value', [torch.zeros(1,3,224,224), torch.zeros(3,224,224,dtype=torch.float64),
    torch.full((3,224,224),float('nan')), np.zeros((3,224,224),np.float32)])
def test_invalid_input_is_rejected(fake_package, value):
    with P2FeatureExtractor('test-1', p2_module=P2Double()) as extractor:
        with pytest.raises(ValueError): extractor.extract(value)


@pytest.mark.parametrize('change', ['shape','nan','dtype','error'])
def test_runtime_failure_is_not_replaced_by_torch(fake_package, change):
    p2 = P2Double()
    if change == 'shape': p2.output = np.zeros((1,1000),np.float32)
    elif change == 'nan': p2.output[0,0] = np.nan
    elif change == 'dtype': p2.output = p2.output.astype(np.float64)
    else: p2.error = RuntimeError('P2 RUNTIME_ERROR')
    with P2FeatureExtractor('test-1', p2_module=p2) as extractor:
        with pytest.raises((ValueError,RuntimeError)): extractor.extract(torch.zeros(3,224,224))
    assert p2.released == 1


def test_hash_and_backend_guard_before_load(fake_package, monkeypatch):
    root, metadata = fake_package
    p2 = P2Double()
    (root/'resnet18.onnx').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash'): P2FeatureExtractor('test-1', p2_module=p2)
    assert p2.loads == []
    monkeypatch.setenv('P2_BACKEND','trt')
    with pytest.raises(ValueError,match='P2_BACKEND'): P2FeatureExtractor('test-1', p2_module=p2)


@pytest.fixture(scope='module')
def real_package(tmp_path_factory):
    pytest.importorskip('p2', reason='P2 real executado no workflow Docker específico')
    from feature_extractor import FeatureExtractor
    from scripts.export_p2_extractor import export_package
    from p2.cli.build import main
    base = tmp_path_factory.mktemp('p2-real')
    official = FeatureExtractor('cpu')
    export_package(base/'package', extractor=official)
    assert main([str(base/'package'),'--cpu-only','--engine-dir',str(base/'engines')]) == 0
    measurements = []
    yield base, official, measurements
    evidence = os.environ.get('P2_EVIDENCE_DIR')
    if evidence:
        Path(evidence).mkdir(parents=True, exist_ok=True)
        (Path(evidence)/'equivalencia.json').write_text(json.dumps(dict(
            scope='P2 real CPU FP32; pesos oficiais; imagens sinteticas; sem Kafka/A1',
            engine='i8-resnet18-imagenet-1.0.0-fp32', samples=measurements,
            atol=5e-5,rtol=1e-4,torch=torch.__version__,numpy=np.__version__),indent=2))


@pytest.fixture
def real_extractor(real_package, monkeypatch):
    base, _, _ = real_package
    monkeypatch.setenv('P2_ENGINE_DIR',str(base/'engines'))
    monkeypatch.setenv('P2_BACKEND','ort')
    with P2FeatureExtractor('i8-resnet18-imagenet-1.0.0') as extractor:
        yield extractor


def synthetic_image(seed):
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0,256,size=(250+seed,310,3),dtype=np.uint8))


@pytest.mark.parametrize('seed', [1,2,3])
def test_real_p2_matches_official_torch_embeddings(real_package, real_extractor, seed):
    from preprocessing import transform_image
    image = synthetic_image(seed)
    tensor = transform_image(image)
    expected = real_package[1].extract(tensor)
    actual = real_extractor.extract(tensor)
    torch.testing.assert_close(actual, expected, rtol=1e-4, atol=5e-5)
    real_package[2].append(dict(seed=seed,max_abs_embedding_error=float((actual-expected).abs().max()),**real_extractor.last_stats))
    assert real_extractor.last_stats['latency_ms'] > 0
    assert real_extractor.last_stats['gpu_memory_mb'] == 0


def test_real_p2_flows_through_correlation_inference_and_event(real_package, real_extractor, tmp_path):
    from normal_model import NormalModel
    from src.inference import InferencePipeline, KnownDefectClassifier, DecisionPolicy
    from src.publisher import EventPublisher, MemoryTransport
    from scripts.replay import replay_rows
    from preprocessing import transform_image
    # Taxonomy double only. Both pipelines load the SAME historical real artifacts.
    class Taxonomy:
        version = 'defects-a1-1.0.0'
        def resolve(self, value, *, version):
            if version != self.version or value not in {'AMASSADO','FURADO','FURADO_AMASSADO'}:
                raise ValueError(value)
            return {'defect_class': value}
    taxonomy = Taxonomy()
    root = Path(__file__).resolve().parents[1]
    normal = NormalModel.load(root/'models/normal_caixa_papelao_normal-csv-001.json')
    classifier = KnownDefectClassifier.load(root/'models/classifier-caixa_papelao-classifier-csv-001.json',taxonomy=taxonomy)
    policy = DecisionPolicy.load(root/'models/policy-caixa_papelao-policy-csv-001.json',
        product_id=normal.product_id, normal_version=normal.model_version,
        classifier_version=classifier.artifact_version,taxonomy_version=taxonomy.version)
    def pipeline(extractor):
        return InferencePipeline(extractor=extractor,normal_model=normal,classifier=classifier,taxonomy=taxonomy,policy=policy)
    image = synthetic_image(4)
    image.save(tmp_path/'synthetic.png')
    crop = image.crop((0,0,224,224))
    baseline = pipeline(real_package[1]).infer(crop)
    candidate = pipeline(real_extractor).infer(crop)
    assert candidate.result == baseline.result and candidate.defect_class == baseline.defect_class
    assert candidate.similarity == pytest.approx(baseline.similarity,rel=1e-4,abs=5e-5)
    output = io.StringIO()
    transport = MemoryTransport()
    transport.last_delivery = {'kind':'memory-transport-no-kafka'}
    publisher = EventPublisher(taxonomy,transport)
    row = dict(source_id='synthetic-p2',session_id=str(uuid4()),frame_index=1,detection_id=0,
        captured_at='2026-11-05T12:00:00.000Z',bbox=[0,0,224,224],frame_path='synthetic.png')
    replay_rows([json.dumps(row)],output,input_dir=tmp_path,infer=pipeline(real_extractor).infer,
        publisher=publisher,artifact_version=real_extractor.engine_info['engine_version'],kafka=True)
    event=json.loads(output.getvalue())
    assert event['schema_version']=='2.0' and event['schema']=='ods.industria.defeito_classificado'
    assert event['captured_at']==row['captured_at']
    assert event['artifact_version']==real_extractor.engine_info['engine_version']
    assert event['payload']['result']==candidate.result
    assert len(publisher.transport.events)==1


def test_real_p2_missing_engine_does_not_fallback(real_package, monkeypatch):
    monkeypatch.setenv('P2_ENGINE_DIR',str(real_package[0]/'engines'))
    monkeypatch.setenv('P2_BACKEND','ort')
    with pytest.raises(FileNotFoundError): P2FeatureExtractor('missing-1')


def test_manifest_cannot_point_to_unverified_model(fake_package):
    root, _ = fake_package
    manifest = json.loads((root/'manifest.json').read_text())
    manifest['source']['onnx_file'] = 'unrelated.onnx'
    (root/'manifest.json').write_text(json.dumps(manifest))
    p2 = P2Double()
    with pytest.raises(ValueError,match='manifesto'): P2FeatureExtractor('test-1',p2_module=p2)
    assert p2.loads == []


def test_replay_releases_extractor_if_transport_initialization_fails(tmp_path, monkeypatch):
    from scripts import replay
    released = []
    pipeline = SimpleNamespace(infer=None,extractor=SimpleNamespace(close=lambda:released.append(True)))
    monkeypatch.setattr(replay,'load_pipeline',lambda *a:pipeline)
    monkeypatch.setattr(replay,'load_taxonomy',lambda *a,**k:object())
    monkeypatch.setattr(replay.KafkaSettings,'from_env',lambda:object())
    def unavailable(*args): raise RuntimeError('broker unavailable')
    monkeypatch.setattr(replay,'KafkaTransport',unavailable)
    with pytest.raises(RuntimeError,match='broker unavailable'):
        replay.main(['--input',str(tmp_path/'i'),'--output',str(tmp_path/'o'),
            '--normal-model','n','--classifier','c','--policy','p','--taxonomy','t',
            '--taxonomy-descriptor','d','--taxonomy-version','v','--artifact-version','a','--kafka'])
    assert released == [True]
