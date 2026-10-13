"""Owned VR tail context and strict 24-bit FLAC writing for native jobs."""
import os
from pathlib import Path
import tempfile


def finite_values(data):
    import numpy as np
    data = np.asarray(data)
    if not data.size:
        raise ValueError('Ses motoru boş veri üretti.')
    for block in np.nditer(data,flags=['external_loop','buffered'],buffersize=65536,order='K'):
        if not np.isfinite(block).all():
            raise ValueError('Ses motoru NaN veya sonsuz değer üretti.')


def finite_audio(data):
    import numpy as np
    if data.ndim not in (1,2) or not len(data):
        raise ValueError('Ses motoru boş veya yanlış şekilli ses üretti.')
    for start in range(0,len(data),65536):
        if not np.isfinite(data[start:start+65536]).all():
            raise ValueError('Ses motoru NaN veya sonsuz değer üretti.')


def write_flac24(engine, stem_path, stem_source):
    import numpy as np
    import soundfile as sf
    from audio_separator.separator.uvr_lib_v5 import spec_utils
    data = np.asarray(stem_source)
    finite_audio(data)
    data = spec_utils.normalize(wave=data,max_peak=engine.normalization_threshold,
                               min_peak=engine.amplification_threshold)
    finite_audio(data)
    root = os.path.realpath(engine.output_dir)
    target = os.path.realpath(stem_path if os.path.isabs(stem_path) else os.path.join(root,stem_path))
    if os.path.normcase(os.path.commonpath([root,target])) != os.path.normcase(root):
        raise ValueError('Ayrıştırma çıktısı bu işin klasörü dışında olamaz.')
    # No int16 intermediate, no near-silence skip, and write errors propagate.
    sf.write(target,data,engine.sample_rate,format='FLAC',subtype='PCM_24')


def reflected_vr_input(source, directory):
    import numpy as np
    import soundfile as sf
    target = Path(directory)/'input.wav'
    with sf.SoundFile(source) as audio:
        rate,channels,frames = audio.samplerate,audio.channels,audio.frames
        context = max(1,round(rate*.1))
        tail = np.empty((0,channels),dtype=np.float32)
        count = 0
        with sf.SoundFile(target,'w',samplerate=rate,channels=channels,format='WAV',subtype='FLOAT') as output:
            while True:
                data = audio.read(65536,dtype='float32',always_2d=True)
                if not len(data):
                    break
                finite_audio(data)
                output.write(data)
                tail = np.concatenate((tail,data),axis=0)[-(context+1):]
                count += len(data)
            if not count or count != frames:
                raise ValueError('Giriş sesi boş veya eksik çözümlendi.')
            extension = np.pad(tail,((0,context),(0,0)),mode='reflect' if len(tail)>1 else 'edge')[-context:]
            output.write(extension)
    return str(target)


def trim_to_source_duration(path, source_info):
    import soundfile as sf
    path = Path(path)
    temporary = None
    try:
        with sf.SoundFile(path) as audio:
            expected = round(source_info.frames*audio.samplerate/source_info.samplerate)
            if expected <= 0 or audio.frames < expected:
                raise ValueError('Ayrıştırma motoru kaynak süresinden kısa ses üretti; eksik kuyruk sıfırla doldurulmadı.')
            if audio.frames==expected:
                return
            fd,temporary = tempfile.mkstemp(prefix='trim_',suffix='.flac',dir=path.parent)
            os.close(fd)
            with sf.SoundFile(temporary,'w',samplerate=audio.samplerate,channels=audio.channels,
                              format='FLAC',subtype=audio.subtype) as output:
                remaining = expected
                while remaining:
                    data = audio.read(min(65536,remaining),dtype='float32',always_2d=True)
                    if not len(data):
                        raise ValueError('Ayrıştırma çıktısı eksik çözümlendi.')
                    finite_audio(data)
                    output.write(data)
                    remaining -= len(data)
        os.replace(temporary,path)
        temporary = None
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.remove(temporary)
