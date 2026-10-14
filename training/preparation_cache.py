"""Reuse only verified prepared data; never share mutable files or trained weights."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from app_settings import write_json_atomic
from model_manager import file_digest
from registry_store import registry_lock
from training.dataset import check_cancel
from training.experiments import owned_path


def cache_key(job, options, manifest):
    keys = ('sample_rate','segment_seconds','overlap_seconds','holdout_fraction','seed',
            'f0_method','sources','source_groups','source_ranges')
    settings = options.to_dict()
    value = {key:settings[key] for key in keys}
    value.update(schema=1, trainer=manifest.get('trainer_revision'), device=manifest['device'],
                 torch=manifest.get('torch_version'), assets=manifest['asset_records'],
                 sources_sha256=[file_digest(p, lambda:(Path(job)/'cancel.request').exists()) for p in options.sources])
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def catalog_path(job):
    return Path(job).parent/'preparation-cache.json'


def publish(job, key):
    job = Path(job).resolve()
    dataset = json.loads((job/'dataset.json').read_text(encoding='utf-8'))
    files = {str(Path(piece[k]).resolve().relative_to(job))
             for piece in dataset['pieces'] for k in ('audio','features','pitch','pitchf')}
    files.update(('dataset.json','pitch_report.json','quality_report.json'))
    records = {name:file_digest(owned_path(job, name)) for name in files}
    path = catalog_path(job)
    with registry_lock(path):
        try:
            catalog = json.loads(path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            catalog = {}
        catalog[key] = {'job':str(job), 'files':records}
        # This catalog owns references only; it never deletes other sessions.
        write_json_atomic(str(path), dict(list(catalog.items())[-100:]))


def restore(job, key, emit):
    job = Path(job).resolve()
    path = catalog_path(job)
    try:
        with registry_lock(path):
            entry = json.loads(path.read_text(encoding='utf-8')).get(key)
        if not entry:
            return False
        source = Path(entry['job']).resolve()
        if source == job or source.parent != job.parent or source.is_symlink():
            return False
        from training.storage import read_manifest
        if read_manifest(source).get('status') != 'completed':
            return False
        total = sum(owned_path(source, name).stat().st_size for name in entry['files'])
        if shutil.disk_usage(job).free < total+3*1024**3:
            return False
        with tempfile.TemporaryDirectory(prefix='.reuse_', dir=job) as temporary:
            stage = Path(temporary)
            for name, digest in entry['files'].items():
                check_cancel(job)
                original = owned_path(source, name)
                target = owned_path(stage, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                if file_digest(target) != digest:
                    raise ValueError('Hazırlık önbelleği değişmiş; veriler yeniden hazırlanacak.')
            dataset = json.loads((stage/'dataset.json').read_text(encoding='utf-8'))
            for piece in dataset['pieces']:
                for field in ('audio','features','pitch','pitchf'):
                    relative = str(Path(piece[field]).resolve().relative_to(source))
                    if relative not in entry['files']:
                        raise ValueError('Önbellek veri kaydı eksik.')
                    piece[field] = str(owned_path(job, relative))
            write_json_atomic(str(stage/'dataset.json'), dataset)
            for name in entry['files']:
                target = owned_path(job, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(owned_path(stage, name), target)
            for split in ('train','holdout'):
                lines = ['|'.join([p['audio'],p['features'],p['pitch'],p['pitchf'],'0'])
                         for p in dataset['pieces'] if p['split']==split]
                (job/f'{split}.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
        emit('prepare', message='Aynı verinin doğrulanmış hazırlığı kopyalandı; eski oturum değiştirilmedi.', percent=100)
        return True
    except (OSError, ValueError, KeyError, TypeError) as error:
        emit('quality', message=f'Hazırlık önbelleği kullanılamadı; kaynaklar yeniden işlenecek. {error}')
        return False
