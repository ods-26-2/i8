"""The inference wheel must include the canonical similarity module it imports."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def test_wheel_imports_outside_repository(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'source'
    shutil.copytree(root, source, ignore=shutil.ignore_patterns(
        '.git', '__pycache__', '.pytest_cache', '*.egg-info', 'dist', 'build', 'evidencias'))
    wheels = tmp_path / 'wheels'
    build = subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps',
        '--no-build-isolation', '--no-index', '--wheel-dir', str(wheels), str(source)],
        capture_output=True, text=True, timeout=120)
    assert build.returncode == 0, build.stdout + build.stderr
    target = tmp_path / 'installed'
    install = subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps',
        '--no-index', '--target', str(target), str(next(wheels.glob('*.whl')))],
        capture_output=True, text=True, timeout=60)
    assert install.returncode == 0, install.stdout + install.stderr
    result = subprocess.run([sys.executable, '-c',
        "import similarities_extractor, src.inference, src.similarities_extractor, scripts.benchmark_similarity; "
        "assert src.similarities_extractor.MotorSimilaridade is similarities_extractor.MotorSimilaridade; "
        f"assert similarities_extractor.__file__.startswith({str(target)!r})"],
        cwd=tmp_path, env={**os.environ, 'PYTHONPATH': str(target)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
