"""Generate immutable backend metadata and third-party material for PyInstaller."""
from importlib import metadata
import json
from pathlib import Path
import sys
from packaging.utils import canonicalize_name
from app_version import read_application_version
from tools.release.source_identity import source_digest
from tools.release.preflight import (ROOT, checked_local_asset, locked_versions, sha256,
                                     validate_environment, validate_ffmpeg_bundle, validate_build_runtime)


def prepare_build(backend, ffmpeg_directory, *, purpose='release'):
    if purpose not in {'release', 'diagnostic'}:
        raise ValueError('Build purpose must be release or diagnostic.')
    validate_build_runtime()
    report = validate_environment(backend)
    ffmpeg_directory = Path(ffmpeg_directory).resolve()
    ffmpeg = validate_ffmpeg_bundle(ffmpeg_directory, allow_incomplete_source=purpose == 'diagnostic')
    output = ROOT / 'build' / 'release_material' / f'{purpose}_{backend}'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'build-info.json').write_text(json.dumps({
        'backend': backend, 'purpose': purpose, 'release_eligible': purpose == 'release',
        'application_version': read_application_version(ROOT/'version.json'),
        'python': report['python'], 'torch': report['torch'],
        'dependency_lock_sha256': sha256(ROOT / 'requirements' / f'{backend}.lock'),
        'common_lock_sha256': sha256(ROOT / 'requirements' / 'common.lock'),
        'application_source_sha256': source_digest(),
        'ffmpeg': {'version': ffmpeg['version'], 'license': ffmpeg['license']},
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    datas = [(str(output / 'build-info.json'), '.')]
    runtime_root=ROOT/'third_party/runtime'
    runtime=json.loads((runtime_root/'manifest.json').read_text(encoding='utf-8'))
    if runtime.get('python')!=report['python'] or runtime.get('python_dll_sha256')!=sha256(Path(sys.base_prefix)/'python312.dll'):
        raise ValueError('CPython runtime differs from its vendored license/provenance material.')
    runtime_files=runtime.get('files',[])
    if not {'LICENSE.txt','LICENSE.cpython.txt','PYTHON.json'}.issubset({item.get('path') for item in runtime_files}):
        raise ValueError('CPython runtime license material is incomplete.')
    datas.append((str(runtime_root/'manifest.json'),'third_party/runtime'))
    for item in runtime_files:
        datas.append((str(checked_local_asset(runtime_root,item)),'third_party/runtime'))
    declarations = ['# Third-party components\n',
                    'These components retain their own licenses. The application EULA does not restrict rights granted by those licenses.\n',
                    f"CPython {report['python']}: PSF license and native dependency notices from the exact runtime build are in third_party/runtime.\n",
                    f"FFmpeg {ffmpeg['version']}: {ffmpeg['license']}. Exact binaries, sources, licenses and build recipes are described in third_party/ffmpeg/manifest.json.\n"]
    missing = []
    vendor_path = ROOT / 'third_party' / 'python' / 'manifest.json'
    vendor = json.loads(vendor_path.read_text(encoding='utf-8')) if vendor_path.is_file() else {}
    expected = locked_versions(ROOT / 'requirements' / f'{backend}.lock')
    for name, version in sorted(expected.items()):
        dist = metadata.distribution(name)
        declarations.append(f'\n## {name} {version}\n')
        license_metadata = dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See included license files.'
        declarations.append(license_metadata.strip() + '\n')
        count = 0
        for relative in dist.files or []:
            filename = Path(str(relative)).name.lower()
            if (filename.startswith(('license', 'licence', 'copying', 'notice', 'copyright'))
                    and not filename.endswith(('.py', '.pyc'))):
                source = Path(dist.locate_file(relative))
                if source.is_file():
                    target = f'third_party/python/{canonicalize_name(name)}/{Path(str(relative)).parent.as_posix()}'
                    datas.append((str(source), target))
                    count += 1
        if not count:
            fallback = vendor.get(name, {})
            if fallback.get('version') == version:
                for item in fallback.get('files', []):
                    source = checked_local_asset(ROOT, item)
                    datas.append((str(source), f'third_party/python/{name}'))
                    declarations.append(f"License source: {item['source']}\n")
                    count += 1
            if not count:
                missing.append(name)
    if missing:
        raise ValueError('License files absent from wheels; vendor reviewed copies before release: ' + ', '.join(missing))
    (output / 'THIRD_PARTY_NOTICES.md').write_text(''.join(declarations), encoding='utf-8')
    datas.append((str(output / 'THIRD_PARTY_NOTICES.md'), '.'))
    datas.append((str(vendor_path), 'third_party/python'))
    datas.append((str(ffmpeg_directory / 'manifest.json'), 'third_party/ffmpeg'))
    for key in ('licenses', 'sources', 'build_recipes'):
        for item in ffmpeg[key]:
            source = ffmpeg_directory / item['path']
            target = ('third_party/ffmpeg/' + str(Path(item['path']).parent)).replace('\\', '/')
            datas.append((str(source), target))
    binaries = [(str(ffmpeg_directory / item['path']), str(Path(item['path']).parent))
                for item in ffmpeg['binaries']]
    return datas, binaries


def external_backend_files(backend):
    """Preserve oneAPI wheel layout instead of losing Intel runtime DLLs."""
    if backend != 'xpu':
        return [], []
    from tools.release.generate_locks import XPU_VERSIONS
    datas, binaries = [], []
    seen = {}
    for name in XPU_VERSIONS:
        dist = metadata.distribution(name)
        for relative in dist.files or []:
            relative = Path(str(relative))
            if relative.is_absolute() or '..' in relative.parts:
                # Wheel RECORD may reference Scripts outside site-packages. They
                # are command line build helpers and are not a runtime payload.
                continue
            source = Path(dist.locate_file(relative))
            if not source.is_file() or source.suffix.lower() in {'.py', '.pyc', '.lib', '.a', '.h', '.hpp'}:
                continue
            destination = ('oneapi/' + relative.parent.as_posix()).rstrip('/')
            key = (destination, source.name)
            digest = sha256(source)
            if key in seen:
                if seen[key] != digest:
                    raise ValueError(f'Conflicting oneAPI runtime file: {relative}')
                continue
            seen[key] = digest
            (binaries if source.suffix.lower() in {'.dll', '.pyd'} else datas).append((str(source), destination))
    return datas, binaries
