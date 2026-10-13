"""Fail a release build early on mixed runtimes, unpinned wheels or private data."""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
ORT_NAMES = {'onnxruntime', 'onnxruntime-gpu', 'onnxruntime-directml'}
BACKENDS = {'cpu', 'cuda', 'xpu', 'rocm'}
LIBRARY_MODEL_ALLOWLIST = {'torchcrepe/assets/full.pth', 'torchcrepe/assets/tiny.pth',
                           'torchfcpe/assets/fcpe_c_v001.pt',
                           'audio_separator/separator/uvr_lib_v5/mixer.ckpt'}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def locked_versions(path, seen=None):
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name, parse_wheel_filename
    seen = set() if seen is None else seen
    path = Path(path).resolve()
    if path in seen:
        raise ValueError(f'Recursive lock include: {path}')
    seen.add(path)
    result = {}
    text = path.read_text(encoding='utf-8').replace('\\\n', ' ')
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('-r '):
            result.update(locked_versions(path.parent / line[3:].strip(), seen))
            continue
        if '--hash=sha256:' not in line:
            raise ValueError(f'Unhashed release requirement: {line}')
        requirement = Requirement(line.split(' --hash=', 1)[0].strip())
        if requirement.url:
            wheel = unquote(urlsplit(requirement.url).path.rsplit('/', 1)[-1])
            _, version, _, _ = parse_wheel_filename(wheel)
            version = str(version)
        elif len(requirement.specifier) == 1 and next(iter(requirement.specifier)).operator == '==':
            version = next(iter(requirement.specifier)).version
        else:
            raise ValueError(f'Unpinned release requirement: {requirement}')
        name = canonicalize_name(requirement.name)
        if name in result and result[name] != version:
            raise ValueError(f'Conflicting release versions: {name}')
        result[name] = version
    seen.remove(path)
    return result


def validate_environment(backend, *, expected=None, installed=None, torch_module=None,
                         ort_module=None, hardware_check=False, require_clean=True):
    from packaging.utils import canonicalize_name
    if backend not in BACKENDS:
        raise ValueError('GHOSTKILLER_BACKEND must be cpu, cuda, rocm or xpu.')
    if installed is None:
        installed = {canonicalize_name(d.metadata['Name']): d.version for d in metadata.distributions()}
    active_ort = ORT_NAMES.intersection(installed)
    required_ort = 'onnxruntime-gpu' if backend == 'cuda' else 'onnxruntime'
    if active_ort != {required_ort}:
        raise ValueError(f'Exactly one ORT distribution ({required_ort}) required; found {sorted(active_ort)}.')
    if expected is None:
        lock = ROOT / 'requirements' / f'{backend}.lock'
        if not lock.is_file():
            raise ValueError('A reviewed native Windows ROCm lock is required; no validated ROCm release lock is bundled.')
        expected = locked_versions(lock)
    differences = [f'{name}: expected {version}, found {installed.get(name, "missing")}'
                   for name, version in expected.items() if installed.get(name) != version]
    if differences:
        raise ValueError('Build environment differs from lock:\n' + '\n'.join(differences))
    if require_clean:
        extra = set(installed) - set(expected) - {'pip', 'wheel', 'cmake'}
        if extra:
            raise ValueError('Unreviewed packages in release environment: ' + ', '.join(sorted(extra)))
    if torch_module is None:
        import torch as torch_module
    actual = ('rocm' if getattr(torch_module.version, 'hip', None) else
              'cuda' if getattr(torch_module.version, 'cuda', None) else
              'xpu' if '+xpu' in torch_module.__version__ else 'cpu')
    if actual != backend:
        raise ValueError(f'Torch runtime is {actual}; requested package is {backend}.')
    if ort_module is None:
        import onnxruntime as ort_module
    # CUDA DLL preload must happen after torch import; older ORT versions lack it.
    if backend == 'cuda' and hasattr(ort_module, 'preload_dlls'):
        ort_module.preload_dlls()
    providers = ort_module.get_available_providers()
    if backend == 'cuda' and 'CUDAExecutionProvider' not in providers:
        raise ValueError('CUDA package has no ONNX CUDAExecutionProvider.')
    if hardware_check:
        device = {'cpu': 'cpu', 'cuda': 'cuda:0', 'rocm': 'cuda:0', 'xpu': 'xpu:0'}[backend]
        x = torch_module.randn(8, 8, device=device, requires_grad=True)
        loss = (x @ x.T).square().mean()
        loss.backward()
        if not bool(torch_module.isfinite(x.grad).all().item()):
            raise ValueError('Native GPU forward/backward produced non-finite gradients.')
    return {'backend': backend, 'python': platform.python_version(), 'torch': torch_module.__version__,
            'onnx_providers': providers, 'packages': dict(sorted(installed.items()))}


def validate_onnx_session(backend):
    """A real tiny session detects DLL initialization fallback that metadata misses."""
    import numpy as np
    import onnx
    import onnxruntime as ort
    model = onnx.helper.make_model(onnx.helper.make_graph(
        [onnx.helper.make_node('MatMul', ['x', 'x'], ['y'])], 'release-smoke',
        [onnx.helper.make_tensor_value_info('x', onnx.TensorProto.FLOAT, [2, 2])],
        [onnx.helper.make_tensor_value_info('y', onnx.TensorProto.FLOAT, [2, 2])]),
        opset_imports=[onnx.helper.make_opsetid('', 13)])
    model.ir_version = 8
    provider = 'CUDAExecutionProvider' if backend == 'cuda' else 'CPUExecutionProvider'
    options = ort.SessionOptions()
    if provider != 'CPUExecutionProvider':
        options.add_session_config_entry('session.disable_cpu_ep_fallback', '1')
    session = ort.InferenceSession(model.SerializeToString(), options, providers=[provider])
    if provider not in session.get_providers():
        raise ValueError(f'ONNX initialization silently lost {provider}.')
    x = np.array([[1., 2.], [3., 4.]], dtype=np.float32)
    np.testing.assert_allclose(session.run(None, {'x': x})[0], x @ x)


def checked_local_asset(root, item):
    if not isinstance(item, dict) or not isinstance(item.get('path'), str):
        raise ValueError('Release asset path missing.')
    path = (root / item['path']).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Release asset missing or outside bundle: ' + item['path'])
    if not re.fullmatch('[0-9a-f]{64}', item.get('sha256', '')) or sha256(path) != item['sha256']:
        raise ValueError('Release asset SHA-256 mismatch: ' + item['path'])
    return path


def validate_ffmpeg_bundle(directory, *, allow_incomplete_source=False):
    """Validate provenance and required distribution material, never invent it."""
    root = Path(directory).resolve()
    manifest_path = root / 'manifest.json'
    if not manifest_path.is_file():
        raise ValueError('FFmpeg manifest.json, licenses and corresponding source bundle are required; see docs/RELEASE_BUILD.md.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    version = manifest.get('version')
    if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]{0,127}', version):
        raise ValueError('FFmpeg version identifier missing or invalid.')
    if manifest.get('source_completeness') != 'complete' and not (
            allow_incomplete_source and manifest.get('source_completeness') == 'ffmpeg-only'):
        raise ValueError('FFmpeg linked dependency sources are incomplete; a source link alone is insufficient.')
    binaries = manifest.get('binaries', [])
    paths = {str(checked_local_asset(root, item).relative_to(root)).replace('\\', '/') for item in binaries}
    if not {'ffmpeg.exe', 'ffprobe.exe'}.issubset(paths):
        raise ValueError('FFmpeg/FFprobe binaries missing from manifest.')
    for key in ('licenses', 'sources', 'build_recipes'):
        entries = manifest.get(key)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f'FFmpeg {key} distribution material missing.')
        for item in entries:
            checked_local_asset(root, item)
    flags = manifest.get('configure', '')
    if not isinstance(flags, str) or '--enable-nonfree' in flags:
        raise ValueError('Nonfree or undocumented FFmpeg build cannot be distributed.')
    if '--enable-libsoxr' not in flags:
        raise ValueError('FFmpeg build must include libsoxr for training resampling.')
    if manifest.get('license') not in {'GPL-3.0-or-later', 'LGPL-3.0-or-later', 'LGPL-2.1-or-later'}:
        raise ValueError('FFmpeg license identifier missing or unsupported.')
    inferred_license = ('GPL-3.0-or-later' if '--enable-gpl' in flags and '--enable-version3' in flags
                        else 'LGPL-3.0-or-later' if '--enable-version3' in flags and '--enable-gpl' not in flags
                        else 'LGPL-2.1-or-later' if '--enable-gpl' not in flags else None)
    if manifest.get('license') != inferred_license:
        raise ValueError('FFmpeg license differs from configured GPL/version flags.')
    actual = subprocess.run([str(root / 'ffmpeg.exe'), '-version'], capture_output=True,
                            text=True, errors='replace', check=True, timeout=15).stdout
    if not re.match(r'ffmpeg version ' + re.escape(version) + r'(?=[+\-\s]|$)', actual.splitlines()[0]) or flags not in actual:
        raise ValueError('FFmpeg version/configure differs from provenance manifest.')
    return manifest


def validate_package_tree(directory):
    root = Path(directory)
    problems = []
    for path in root.rglob('*'):
        relative = path.relative_to(root).as_posix()
        normalized = relative.removeprefix('_internal/')
        if not path.is_file():
            continue
        if normalized.split('/')[0] in {'models', 'modeller', 'training_runs', 'trained_models', 'deneme', 'test', 'tests'}:
            problems.append(relative)
        elif path.name in {'models.json', 'settings.json', '.integrity.json'}:
            if normalized != 'audio_separator/models.json':
                problems.append(relative)
        elif path.suffix.lower() in {'.pt', '.pth', '.ckpt', '.index', '.wav', '.mp3', '.flac', '.ogg'}:
            if normalized not in LIBRARY_MODEL_ALLOWLIST:
                problems.append(relative)
    if problems:
        raise ValueError('Private/test/model files in package:\n' + '\n'.join(problems))
    info = next(iter(root.rglob('build-info.json')), None)
    if info is None:
        raise ValueError('Packaged backend build-info.json missing.')
    if json.loads(info.read_text(encoding='utf-8')).get('backend') not in BACKENDS:
        raise ValueError('Packaged backend build-info.json is invalid.')
    if not any(root.rglob('THIRD_PARTY_NOTICES.md')):
        raise ValueError('Packaged third-party notices missing.')
    return {'files': sum(1 for item in root.rglob('*') if item.is_file()),
            'bytes': sum(item.stat().st_size for item in root.rglob('*') if item.is_file())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=sorted(BACKENDS), default=os.environ.get('GHOSTKILLER_BACKEND'))
    parser.add_argument('--hardware-check', action='store_true')
    parser.add_argument('--ffmpeg-dir', type=Path)
    parser.add_argument('--package-dir', type=Path)
    args = parser.parse_args()
    if args.package_dir:
        report = validate_package_tree(args.package_dir)
    else:
        if os.name != 'nt' or platform.machine().lower() not in {'amd64', 'x86_64'} or sys.version_info[:2] != (3, 12):
            raise ValueError('Release builds require native Windows x64 / CPython 3.12.')
        report = validate_environment(args.backend, hardware_check=args.hardware_check)
        if args.hardware_check:
            validate_onnx_session(args.backend)
        if args.ffmpeg_dir:
            report['ffmpeg'] = validate_ffmpeg_bundle(args.ffmpeg_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
