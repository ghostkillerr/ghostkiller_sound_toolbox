"""Bounded-memory overlap/add, offline inference and atomic stem publication."""
from contextlib import ExitStack
from pathlib import Path
import os
import shutil
import tempfile
import math
import subprocess
from . import profile_for, STEM_LABELS

RATE = 44100


def separate_file(input_file, output_dir, model_root, profile='scnet', stems=None,
                  device='cpu', cancelled=None, progress=None, model_factory=None, output_format='flac', output_channels='original'):
    import numpy as np
    import soundfile as sf
    import torch
    from app_runtime import ffmpeg_executable, same_path
    from training.analysis import _command
    from .models import load_model
    from audio_export import normalize_output_format, normalize_output_channels, export_audio
    output_format = normalize_output_format(output_format)
    output_channels = normalize_output_channels(output_channels)
    spec = profile_for(profile)
    selected = tuple(spec['stems'] if stems is None else stems)
    if not selected or len(set(selected)) != len(selected) or any(s not in spec['stems'] for s in selected):
        raise ValueError('Kaydedilecek enstrüman kanallarını seçin.')
    target = Path(output_dir)
    if target.exists() or same_path(input_file,target):
        raise FileExistsError('Enstrüman sonuçları için yeni bir klasör gerekli.')
    target.parent.mkdir(parents=True,exist_ok=True)
    def check():
        if cancelled and cancelled():
            raise InterruptedError('Enstrüman ayırma iptal edildi; giriş dosyası korundu.')
    def notice(text):
        if progress: progress(text)
    check()
    # Everything is staged on the destination volume. Only a complete group
    # of stems is made visible; cancellation never replaces earlier results.
    with tempfile.TemporaryDirectory(prefix='instruments_',dir=target.parent) as temporary:
        work = Path(temporary)
        decoded = work/'input.wav'
        notice('Enstrüman ayırma için ses hazırlanıyor.')
        probe = subprocess.run([ffmpeg_executable('ffprobe'),'-v','error','-show_entries',
            'format=duration','-of','default=noprint_wrappers=1:nokey=1',str(input_file)],
            capture_output=True,timeout=30,check=True,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        seconds = float(probe.stdout.decode().strip())
        if not math.isfinite(seconds) or seconds<=0:
            raise ValueError('Ses kaydının süresi geçersiz.')
        reserve = math.ceil(seconds*RATE)*2*(4+len(selected)*8)+256*1024**2
        if shutil.disk_usage(work).free < reserve:
            raise OSError(f'Enstrüman ayırma için en az {reserve/1024**3:.2f} GB boş disk alanı gerekli.')
        check()
        _command([ffmpeg_executable(),'-nostdin','-v','error','-y','-i',str(input_file),
                  '-vn','-ac','2','-af','aresample=44100:resampler=soxr:precision=28',
                  '-c:a','pcm_f32le','-rf64','auto',str(decoded)], work,lambda:bool(cancelled and cancelled()))
        check()
        info = sf.info(decoded)
        if not info.frames:
            raise ValueError('Ses kaydı boş.')
        # Float intermediate stems plus final PCM24 exports, with headroom.
        needed = info.frames*2*len(selected)*8 + 256*1024**2
        if shutil.disk_usage(work).free < needed:
            raise OSError(f'Enstrüman çıktıları için en az {needed/1024**3:.2f} GB boş alan gerekli.')
        notice('Enstrüman modeli hazırlanıyor.')
        model = (model_factory or load_model)(profile,model_root,device,cancelled)
        window = round((7.8 if profile=='demucs6' else 8.)*RATE)
        hop = window//2
        n = len(spec['stems'])
        buffer = np.zeros((n,window,2),dtype='float32')
        divisor = np.zeros(window,dtype='float32')
        weights = np.hanning(window+2)[1:-1].astype('float32')
        peak = 0.
        raw_paths = {s:work/(s+'.wav') for s in selected}
        try:
            with ExitStack() as stack:
                source = stack.enter_context(sf.SoundFile(decoded))
                streams = {s:stack.enter_context(sf.SoundFile(p,'w',samplerate=RATE,channels=2,
                           format='RF64',subtype='FLOAT')) for s,p in raw_paths.items()}
                for start in range(0,info.frames,hop):
                    check()
                    source.seek(start)
                    block = source.read(window,dtype='float32',always_2d=True)
                    length = len(block)
                    if not np.isfinite(block).all():
                        raise ValueError('Giriş sesinde geçersiz örnek var.')
                    # Use the same normalisation and sample clock for every stem.
                    mono = block.mean(axis=1,dtype='float64')
                    mean, std = float(mono.mean()), float(mono.std())
                    if float(np.max(np.abs(block))) < 1e-8:
                        prediction = np.zeros((n,length,2),dtype='float32')
                    else:
                        std = max(std,1e-5)
                        audio = (block-mean)/std
                        padded = np.pad(audio,((0,window-length),(0,0)),mode='constant')
                        with torch.inference_mode():
                            tensor = torch.from_numpy(padded.T.copy()).unsqueeze(0).to(device)
                            prediction = model(tensor)[0,:,:,:length].float().cpu().numpy().transpose(0,2,1)
                        prediction = prediction*std+mean/n
                    if prediction.shape != (n,length,2) or not np.isfinite(prediction).all():
                        raise ValueError('Model geçersiz enstrüman çıktısı üretti.')
                    buffer[:,:length] += prediction*weights[:length,None]
                    divisor[:length] += weights[:length]
                    count = min(hop,info.frames-start)
                    samples = buffer[:,:count]/divisor[:count,None]
                    for stem,stream in streams.items():
                        data = samples[spec['stems'].index(stem)]
                        peak = max(peak,float(np.max(np.abs(data))))
                        stream.write(data)
                    buffer[:,:window-hop] = buffer[:,hop:]
                    buffer[:,window-hop:] = 0
                    divisor[:window-hop] = divisor[hop:]
                    divisor[window-hop:] = 0
                    notice(f'Enstrümanlar ayrılıyor: %{min(95,round(95*(start+count)/info.frames))}')
            check()
            export = work/'results'
            export.mkdir()
            # One shared gain preserves relative stem levels, never individual
            # normalisation. Float intermediates preserve peaks until this pass.
            gain = min(1.,.999/peak) if peak else 1.
            for stem,path in raw_paths.items():
                check()
                export_audio(path, export/(stem+'.'+output_format), output_format,
                             cancelled=cancelled, gain=gain, output_channels=output_channels)
            check()
            os.rename(export,target)
        finally:
            del model
            from compute_backend import clear_cache
            clear_cache(device)
    notice('Enstrüman ayırma tamamlandı: %100')
    return {'directory':str(target),'files':{s:str(target/(s+'.'+output_format)) for s in selected},
            'shared_gain':gain,'frames':info.frames,'sample_rate':RATE}
