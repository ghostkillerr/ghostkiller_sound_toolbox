"""Shared, streaming audio exports with cancellation and atomic publication."""
import math
import os
from pathlib import Path
import tempfile

OUTPUT_FORMATS = ('mp3', 'wav', 'flac', 'ogg')
DEFAULT_OUTPUT_FORMAT = 'flac'
OUTPUT_CHANNELS = ('original', 'mono', 'stereo')
DEFAULT_OUTPUT_CHANNELS = 'original'


def normalize_output_format(value):
    if not isinstance(value, str) or value.lower() not in OUTPUT_FORMATS:
        raise ValueError('Ses dosyası biçimi MP3, WAV, FLAC veya OGG olmalı.')
    return value.lower()


def selected_output_format(settings):
    return normalize_output_format(getattr(settings, 'output_format', DEFAULT_OUTPUT_FORMAT))


def normalize_output_channels(value):
    if not isinstance(value, str) or value.lower() not in OUTPUT_CHANNELS:
        raise ValueError('Ses kanalı düzeni mevcut düzen, mono veya stereo olmalı.')
    return value.lower()


def selected_output_channels(settings):
    return normalize_output_channels(getattr(settings, 'output_channels', DEFAULT_OUTPUT_CHANNELS))


def publish_unique(temporary, target):
    """Publish a completed file without replacing any existing directory entry."""
    from app_runtime import truncate_utf16
    target = Path(target)
    number = 1
    while True:
        extra = '' if number == 1 else f' ({number})'
        limit = 255 - len((extra + target.suffix).encode('utf-16-le')) // 2
        candidate = target.with_name(truncate_utf16(target.stem, limit) + extra + target.suffix)
        try:
            if os.name == 'nt':
                os.rename(temporary, candidate)  # Windows rename never replaces an existing entry.
            else:
                os.link(temporary, candidate)
                os.unlink(temporary)
            return str(candidate)
        except FileExistsError:
            number += 1


def publish_directory(source, target):
    """Reserve a numbered result folder and move only this job's finished files."""
    source, target = Path(source), Path(target)
    number = 1
    while True:
        candidate = target if number == 1 else target.with_name(f'{target.name} ({number})')
        try:
            candidate.mkdir()
            break
        except FileExistsError:
            number += 1
    moved = []
    try:
        for path in source.iterdir():
            destination = candidate / path.name
            os.rename(path, destination)
            moved.append(destination)
    except BaseException:
        for path in reversed(moved):
            os.rename(path, source / path.name)
        candidate.rmdir()
        raise
    return str(candidate)


def export_audio(source, target, output_format, cancelled=None, gain=1., output_channels='original'):
    """Encode once at the output boundary; preserve existing results on failure."""
    import soundfile as sf
    from app_runtime import same_path
    from separation_audio import finite_audio

    output_format = normalize_output_format(output_format)
    output_channels = normalize_output_channels(output_channels)
    source, target = Path(source), Path(target)
    if target.suffix.lower() != '.' + output_format:
        raise ValueError('Çıktı dosyasının uzantısı seçilen ses biçimiyle eşleşmiyor.')
    if same_path(source, target):
        raise ValueError('Çıktı giriş dosyasının üzerine yazamaz.')
    if not math.isfinite(gain) or not 0 < gain <= 1:
        raise ValueError('Ses çıktı düzeyi geçersiz.')

    def check():
        if cancelled and cancelled():
            raise InterruptedError('Ses dosyası kaydedilirken işlem iptal edildi.')

    check()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='audio_export_', suffix=target.suffix, dir=target.parent)
    os.close(fd)
    try:
        with sf.SoundFile(source) as audio:
            if audio.frames <= 0:
                raise ValueError('Kaydedilecek ses boş.')
            rate, channels = audio.samplerate, audio.channels
            if output_channels == 'mono':
                channels = 1
            elif output_channels == 'stereo':
                if audio.channels > 2:
                    raise ValueError('Stereo dönüşümü için mono veya stereo bir ses gerekli.')
                channels = 2
            encoding = {'format': output_format.upper()}
            if output_format in ('wav', 'flac'):
                encoding['subtype'] = 'PCM_24'
            elif output_format == 'mp3':
                encoding.update(subtype='MPEG_LAYER_III', bitrate_mode='CONSTANT', compression_level=0.)
                rates = (8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)
                rate = min(rates, key=lambda value: abs(value - rate))
            else:
                encoding.update(subtype='VORBIS', compression_level=.1)
            expected = round(audio.frames * rate / audio.samplerate)
            resampler = None
            if rate != audio.samplerate:
                import soxr
                resampler = soxr.ResampleStream(audio.samplerate, rate, channels,
                                                dtype='float32', quality='VHQ')
            with sf.SoundFile(temporary, 'w', samplerate=rate, channels=channels, **encoding) as output:
                for block in audio.blocks(blocksize=65536, dtype='float32', always_2d=True):
                    check()
                    finite_audio(block)
                    if channels == 1 and audio.channels > 1:
                        block = block.mean(axis=1, keepdims=True, dtype='float32')
                    elif channels == 2 and audio.channels == 1:
                        block = block.repeat(2, axis=1)
                    if resampler is not None:
                        block = resampler.resample_chunk(block, last=audio.tell() == audio.frames)
                    if len(block):
                        output.write(block * gain)
        check()
        with sf.SoundFile(temporary) as encoded:
            if (encoded.format != output_format.upper() or encoded.channels != channels
                    or encoded.samplerate != rate):
                raise ValueError('Kaydedilen sesin biçimi veya kanal bilgileri geçersiz.')
            decoded = 0
            for block in encoded.blocks(blocksize=65536, dtype='float32', always_2d=True):
                check()
                finite_audio(block)
                decoded += len(block)
            if decoded <= 0 or abs(decoded - expected) > 1:
                raise ValueError('Kaydedilen sesin süresi kaynak sesle eşleşmiyor.')
        check()
        return publish_unique(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
