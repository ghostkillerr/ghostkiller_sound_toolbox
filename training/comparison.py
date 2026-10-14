"""Fixed held-out listening bank shared by every archived candidate."""
import json
from pathlib import Path

from app_settings import write_json_atomic
from model_manager import file_digest
from training.dataset import check_cancel
from training.experiments import owned_path, snapshot_records


def comparison_bank(job, dataset, options=None):
    job = Path(job)
    candidates = [p for p in dataset['pieces'] if p['split']=='holdout']
    if not candidates:
        raise ValueError('Karşılaştırma için ayrılmış değerlendirme sesi yok.')
    # Prefer distinct recordings, then separated portions of the remaining data.
    selected, seen = [], set()
    for piece in candidates:
        if piece['source_sha256'] not in seen:
            selected.append(piece)
            seen.add(piece['source_sha256'])
        if len(selected)==3:
            break
    for index in (len(candidates)//2, len(candidates)-1):
        if len(selected)<3 and candidates[index] not in selected:
            selected.append(candidates[index])
    bank = [{'id':f'clip_{i+1}', 'label':f'Kontrol kaydı {i+1}', 'audio':p['audio'],
             'sha256':file_digest(p['audio']), 'source_sha256':p['source_sha256'],
             'start_frame':p['start'], 'frames':p['frames']} for i,p in enumerate(selected)]
    if options and options.comparison_sources:
        from app_runtime import ffmpeg_executable
        from training.analysis import _command
        training_hashes={r['source_sha256'] for r in dataset['pieces']}
        folder=job/'comparison-inputs'
        folder.mkdir(exist_ok=True)
        for i,source in enumerate(options.comparison_sources):
            check_cancel(job)
            digest=file_digest(source)
            if digest in training_hashes:
                raise ValueError(f'{Path(source).name}: ayrı test kaydı eğitimdeki kaydın kopyası. Başka bir kayıt seçin.')
            path=folder/f'external_{i+1}.wav'
            _command([ffmpeg_executable(),'-nostdin','-v','error','-y','-i',source,'-t','12','-vn',
                      '-ar',str(options.sample_rate),'-ac','1','-c:a','pcm_f32le',str(path)],folder,
                     lambda:(job/'cancel.request').exists())
            if file_digest(source)!=digest:
                raise ValueError('Ayrı test kaydı okuma sırasında değişti.')
            bank.append({'id':f'external_{i+1}','label':f'Ayrı test {i+1}: {Path(source).name}',
                         'audio':str(path),'sha256':file_digest(path),'source_sha256':digest,
                         'preview_max_seconds':12})
    write_json_atomic(str(job/'comparison-inputs.json'), {'inputs':bank})
    return bank


def test_candidates(job, dataset, options, device, index, emit):
    from rvc.infer.infer import VoiceConverter
    from app_runtime import validate_audio_file
    job = Path(job)
    bank = comparison_bank(job, dataset, options)
    candidates = [{'file':'latest.pth'}, {'file':'best_validation.pth'}]+snapshot_records(job)
    converter = VoiceConverter(device=device, allow_model_download=False)
    models = []
    try:
        for number, candidate in enumerate(candidates):
            check_cancel(job)
            path = owned_path(job, candidate['file'])
            digest = file_digest(path)
            if candidate.get('sha256', digest) != digest:
                raise ValueError('Arşivlenmiş model değişmiş; karşılaştırma durduruldu.')
            tests = []
            for clip in bank:
                if file_digest(clip['audio']) != clip['sha256']:
                    raise ValueError('Karşılaştırma girdisi değişmiş.')
                record = {'input_id':clip['id'], 'label':clip['label']}
                for field, ratio in (('test_audio_no_index',0.), ('test_audio',.75)):
                    check_cancel(job)
                    folder = job/'comparison'
                    folder.mkdir(exist_ok=True)
                    output = folder/f'model_{number}_{clip["id"]}_{int(ratio*100)}.wav'
                    emit('smoke', message=f'Karşılaştırma: {candidate["file"]}, {clip["label"]}, index {ratio:.2f}')
                    converter.convert_audio(clip['audio'], str(output), str(path), index if ratio else '',
                                            f0_method=options.f0_method, index_rate=ratio, clean_audio=False)
                    validate_audio_file(output)
                    record[field] = str(output)
                tests.append(record)
            models.append({**candidate, 'pth':str(path), 'sha256':digest, 'smoke_passed':True,
                           'tests':tests, 'test_audio':tests[0]['test_audio'],
                           'test_audio_no_index':tests[0]['test_audio_no_index'], 'test_index_rate':.75})
    finally:
        converter.cleanup_model()
    return models, bank
