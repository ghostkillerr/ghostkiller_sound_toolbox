"""Completed-session cleanup, kept separate from training and model registration."""
import json
import os
from pathlib import Path
import shutil

from app_runtime import app_directory, data_directory
from app_settings import write_json_atomic
from registry_store import registry_lock, validate_models
from training.storage import read_manifest, update_manifest


def _redirected(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def _training_job_path(job, training_root=None):
    root = Path(training_root or (Path(data_directory()) / 'training_runs')).resolve()
    path = Path(job)
    if _redirected(path) or not path.is_dir() or path.resolve().parent != root:
        raise ValueError('Temizlenecek eğitim oturumu güvenli eğitim klasöründe değil.')
    path = path.resolve()
    for base, directories, files in os.walk(path, followlinks=False):
        for name in (*directories, *files):
            if _redirected(Path(base) / name):
                raise ValueError('Eğitim oturumunda yönlendirilmiş bir yol var; otomatik temizleme durduruldu.')
    return root, path


def training_job_size(job, training_root=None):
    """Return session bytes without following redirected paths."""
    _root, path = _training_job_path(job, training_root)
    return sum((Path(base) / name).stat().st_size for base, _dirs, files in os.walk(path)
               for name in files)


def _inside(value, path):
    return bool(value) and Path(value).resolve().is_relative_to(path)


def _check_references(root, path, registry):
    """A failed child is resumable too; status alone never makes it disposable."""
    for sibling in root.iterdir():
        if not sibling.is_dir() or _redirected(sibling):
            continue
        try:
            manifest = read_manifest(sibling)
            options = manifest.get('options', {})
            sources = [*options.get('sources', ()), *options.get('comparison_sources', ())]
            initial = manifest.get('initial_from', {}).get('checkpoint')
        except (OSError, ValueError, TypeError, AttributeError) as error:
            raise ValueError(f'{sibling.name}: oturum kayıtları okunamadığı için temizlik güvenle yapılamadı.') from error
        if sibling != path and initial and _inside(initial, path) and manifest.get('status') != 'completed':
            raise ValueError(f"'{options.get('name', sibling.name)}' eğitimi bu oturumun başlangıç ağırlıklarını bekliyor; önce onu tamamlayın veya kaldırın.")
        if any(_inside(source, path) for source in sources):
            raise ValueError(f"'{options.get('name', sibling.name)}' eğitiminin kullandığı özgün veya karşılaştırma kaydı bu klasörde; temizlik durduruldu.")

    if registry.is_file():
        models = validate_models(json.loads(registry.read_text(encoding='utf-8')))
        for name, record in models.items():
            for field in ('pth', 'index'):
                value = record.get(field, '')
                # Frozen apps keep the registry in LocalAppData, but resolve
                # legacy relative model paths against the executable directory.
                bases = (registry.parent, Path(app_directory()))
                if value and any(_inside(base / value, path) for base in bases):
                    raise ValueError(f"'{name}' AI Cover modeli bu oturumu kullanıyor. Önce modeli kalıcı klasöre kaydedin ve eski kaydı listeden kaldırın.")


def _remove_cache_reference(root, path):
    catalog = root / 'preparation-cache.json'
    try:
        with registry_lock(catalog):
            if not catalog.is_file():
                return
            values = json.loads(catalog.read_text(encoding='utf-8'))
            if not isinstance(values, dict) or any(not isinstance(value, dict) for value in values.values()):
                return  # Preserve malformed cache data; restore already rejects it.
            filtered = {key: value for key, value in values.items()
                        if Path(value.get('job', '')).resolve() != path}
            if filtered != values:
                write_json_atomic(str(catalog), filtered)
    except (OSError, ValueError, TypeError):
        pass  # Removing an optional cache reference cannot undo successful cleanup.


def delete_training_job(job, training_root=None):
    """Delete one confirmed session; keep a tombstone if cleanup is interrupted."""
    root, path = _training_job_path(job, training_root)
    registry = root.parent / 'models.json'
    # Creation and dependency inspection share a root lock. The guard stays
    # outside the deleted folder so Windows can remove that folder completely.
    with registry_lock(root / 'lifecycle.guard'), registry_lock(registry):
        size = training_job_size(path, root)
        with registry_lock(path / 'controller.guard', timeout=.1), registry_lock(path / 'worker.guard', timeout=.1):
            manifest = read_manifest(path)
            if manifest.get('status') not in ('completed', 'deleting'):
                raise ValueError('Yalnız tamamlanmış eğitimlerin teknik dosyaları temizlenebilir.')
            _check_references(root, path, registry)
            _training_job_path(path, root)
            manifest = update_manifest(path, status='deleting')
        # Both entry points reject this tombstone before touching any worker state.
        try:
            shutil.rmtree(path)
        except BaseException:
            if path.is_dir():
                try:
                    write_json_atomic(str(path / 'manifest.json'), manifest)
                except OSError:
                    pass  # Preserve the original deletion error if even the marker is locked.
            raise
        _remove_cache_reference(root, path)
    return size
