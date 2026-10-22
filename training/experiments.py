"""Durable experiment metadata; model math and personal source files stay untouched."""
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

from app_settings import write_json_atomic
from model_manager import file_digest
from registry_store import registry_lock
from training.config import TrainingOptions
from training.storage import read_manifest, update_manifest


def owned_path(job, relative):
    root = Path(job).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root or Path(relative).is_absolute():
        raise ValueError("Eğitim dosyası oturum klasörü dışında.")
    return path


def selected_range(options, source, seconds):
    index = list(map(lambda p: str(Path(p).resolve()), options.sources)).index(str(Path(source).resolve()))
    start, end = options.source_ranges[index] if options.source_ranges else (0., 0.)
    end = end or seconds
    if not math.isfinite(seconds) or end > seconds + .05 or end-start < 2:
        raise ValueError(f"{Path(source).name}: seçili bölüm dosya içinde ve en az iki saniye olmalı.")
    return float(start), min(float(end), seconds)


def split_review(report, options, cancelled=None):
    from training.dataset import source_splits
    rows = source_splits(options.sources, options.holdout_fraction, options.seed,
                         cancelled=cancelled, groups=options.source_groups)
    by_path = {str(Path(r['path']).resolve()): r for r in report['sources'] if 'duplicate_of' not in r}
    result = []
    for row in rows:
        if cancelled and cancelled():
            raise InterruptedError('Kayıt incelemesi iptal edildi.')
        record = by_path[row['path']]
        start, end = selected_range(options, row['path'], record['seconds'])
        if len(rows) == 1:
            train = (end-start)*(1-options.holdout_fraction)
            holdout = end-start-train
        else:
            train, holdout = ((end-start, 0.) if row['split']=='train' else (0., end-start))
        result.append({**row, 'start_seconds':start, 'end_seconds':end,
                       'train_seconds':train, 'holdout_seconds':holdout})
    return {'sources':result, 'train_seconds':sum(r['train_seconds'] for r in result),
            'holdout_seconds':sum(r['holdout_seconds'] for r in result),
            'independent_groups':len({r['group_id'] for r in rows}), 'timeline_split':len(rows)==1}


def archive_snapshot(job, options, epoch, step, validation):
    """Only copies exports; bounded archive never prunes resume/latest/best models."""
    if not options.snapshot_limit:
        return
    job = Path(job)
    source = job/'latest.pth'
    if not source.is_file():  # Allows model-free engine fixtures.
        return
    budget = options.snapshot_budget_mb*1024**2
    if source.stat().st_size > budget:
        return
    checkpoint = job/'resume.pth'
    reserve = max(2*1024**3, 2*checkpoint.stat().st_size if checkpoint.is_file() else 0)
    if shutil.disk_usage(job).free < reserve+source.stat().st_size:
        return  # Leave enough room for the next atomic full resume checkpoint.
    root = job/'snapshots'
    root.mkdir(exist_ok=True)
    relative = f'snapshots/epoch_{epoch:06d}_step_{step:010d}.pth'
    target = owned_path(job, relative)
    fd, temporary = tempfile.mkstemp(dir=root, prefix='snapshot_', suffix='.part')
    try:
        with os.fdopen(fd, 'wb') as output, source.open('rb') as stream:
            shutil.copyfileobj(stream, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    catalog = snapshot_records(job)
    catalog = [r for r in catalog if r['file'] != relative]
    catalog.append({'file':relative, 'epoch':epoch, 'step':step, 'holdout_mel_l1':validation,
                    'sha256':file_digest(target), 'size':target.stat().st_size})
    kept = []
    for record in sorted(catalog, key=lambda r:r['step'], reverse=True):
        if len(kept)<options.snapshot_limit and sum(r['size'] for r in kept)+record['size'] <= budget:
            kept.append(record)
    write_json_atomic(str(job/'snapshots.json'), {'models':kept})
    retained = {r['file'] for r in kept}
    for record in catalog:
        if record['file'] not in retained:
            path = owned_path(job, record['file'])
            if path.parent == root.resolve():
                path.unlink(missing_ok=True)


def snapshot_records(job):
    try:
        return json.loads((Path(job)/'snapshots.json').read_text(encoding='utf-8'))['models']
    except FileNotFoundError:
        return []


def read_notes(job):
    try:
        return json.loads((Path(job)/'notes.json').read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}


def save_notes(job, note, preferred_model=None):
    if len(note)>10000:
        raise ValueError('Oturum notu en fazla 10000 karakter olabilir.')
    with registry_lock(Path(job)/'notes.guard'):
        value = read_notes(job)
        value.update(note=note, updated_at=time.time())
        if preferred_model is not None:
            owned_path(job, preferred_model)
            value['preferred_model'] = preferred_model
        write_json_atomic(str(Path(job)/'notes.json'), value)


def list_sessions(root):
    sessions = []
    if not Path(root).is_dir():
        return sessions
    for child in Path(root).iterdir():
        if not child.is_dir() or child.is_symlink():
            continue
        try:
            value = read_manifest(child)
            options = TrainingOptions.from_dict(value['options'])
            sessions.append({'path':str(child), 'name':options.name, 'status':value.get('status','created'),
                             'epoch':value.get('last_checkpoint_epoch',0), 'epochs':options.epochs,
                             'modified':(child/'manifest.json').stat().st_mtime,
                             'note':read_notes(child).get('note',''), 'options':options.to_dict()})
        except (OSError, ValueError, KeyError, TypeError):
            continue  # Damaged sessions remain on disk and can still be opened manually.
    return sorted(sessions, key=lambda r:r['modified'], reverse=True)


def save_preset(path, name, options):
    if not name.strip() or len(name)>100:
        raise ValueError('Ayar şablonunun adı 1–100 karakter olmalı.')
    with registry_lock(path):
        try:
            value = json.loads(Path(path).read_text(encoding='utf-8'))
        except FileNotFoundError:
            value = {}
        value[name] = {k:v for k,v in options.to_dict().items()
                       if k not in ('name','sources','source_groups','source_ranges','comparison_sources')}
        write_json_atomic(str(path), value)


def request_extension(job, total_epochs):
    """Record permission for precisely one checkpoint/epoch-only migration."""
    from model_manager import file_digest
    with registry_lock(Path(job)/'controller.guard', timeout=.1), registry_lock(Path(job)/'worker.guard', timeout=.1):
        manifest = read_manifest(job)
        if manifest.get('status') == 'deleting':
            raise ValueError('Bu eğitim oturumunun teknik dosyaları temizleniyor.')
        options = TrainingOptions.from_dict(manifest['options'])
        updated = replace(options, epochs=total_epochs).validate(False)
        if total_epochs <= options.epochs:
            raise ValueError('Yeni toplam tekrar sayısı mevcut hedefin üstünde olmalı.')
        checkpoint = Path(job)/'resume.pth'
        if not checkpoint.is_file():
            raise ValueError('Ek eğitim için sağlam devam kaydı bulunamadı.')
        history = manifest.get('extensions', [])
        history.append({'from_epochs':options.epochs, 'to_epochs':total_epochs,
                        'checkpoint_sha256':file_digest(checkpoint), 'time':time.time()})
        update_manifest(job, options=updated.to_dict(), extensions=history)
        return updated


def resume_options_match(job, saved, requested):
    old, new = TrainingOptions.from_dict(saved).to_dict(), requested.to_dict()
    if old == new:
        return True
    before, after = old.pop('epochs'), new.pop('epochs')
    if old != new or after <= before:
        return False
    receipt = read_manifest(job).get('extensions', [])
    digest = file_digest(Path(job)/'resume.pth')
    permitted = {before}
    for record in receipt:
        if record['checkpoint_sha256']==digest and record['from_epochs'] in permitted and record['to_epochs']>record['from_epochs']:
            permitted.add(record['to_epochs'])
    return after in permitted


class ExperimentQueue:
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except FileNotFoundError:
            return []

    def add(self, options):
        options.validate()
        with registry_lock(self.path):
            items = self.read()
            if len([r for r in items if r['status']=='waiting']) >= 20:
                raise ValueError('Kuyrukta en fazla 20 bekleyen eğitim olabilir.')
            item = {'id':uuid.uuid4().hex, 'options':options.to_dict(), 'status':'waiting', 'created_at':time.time()}
            items.append(item)
            write_json_atomic(str(self.path), items)
            return item

    def claim(self):
        with registry_lock(self.path):
            items = self.read()
            item = next((r for r in items if r['status']=='waiting'), None)
            if item:
                item['status'] = 'running'
                write_json_atomic(str(self.path), items)
            return item

    def update(self, identity, **values):
        with registry_lock(self.path):
            items = self.read()
            item = next(r for r in items if r['id']==identity)
            item.update(values)
            write_json_atomic(str(self.path), items)

    def cancel_waiting(self):
        with registry_lock(self.path):
            items = self.read()
            for item in items:
                if item['status']=='waiting':
                    item['status']='cancelled'
            write_json_atomic(str(self.path), items)
