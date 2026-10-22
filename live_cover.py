"""Bounded, in-memory microphone -> RVC -> headphone monitoring session."""
from contextlib import ExitStack
from dataclasses import dataclass
import math
from pathlib import Path
import queue
import threading
import time

from live_audio import RATE
from live_gate import NoiseGate, validate_gate


READY_TONE_SECONDS = .16


def ready_tone():
    """Return a short rising cue for a fully opened live audio route."""
    import numpy as np
    first_frames = round(RATE * READY_TONE_SECONDS / 2)
    second_frames = round(RATE * READY_TONE_SECONDS) - first_frames
    parts = []
    for frames, frequency in ((first_frames, 660.), (second_frames, 880.)):
        time_axis = np.arange(frames, dtype='float32') / RATE
        envelope = np.sin(np.linspace(0., np.pi, frames, dtype='float32')) ** 2
        parts.append((.12 * envelope * np.sin(2 * np.pi * frequency * time_axis)).astype('float32'))
    return np.concatenate(parts)


@dataclass(frozen=True)
class LiveOptions:
    model_path: str
    index_path: str = ''
    device: str = 'cpu'
    input_device: int = -1
    output_device: int = -1
    pitch: int = 0
    index_rate: float = .75
    f0_method: str = 'rmvpe'
    block_seconds: float = .5
    gain: float = .5
    gate_enabled: bool = True
    gate_db: float = -45.
    input_name: str = ''
    output_name: str = ''

    def validate(self):
        for name in ('model_path', 'index_path', 'device', 'input_name', 'output_name'):
            if not isinstance(getattr(self, name), str):
                raise ValueError('Canlı ses modeli veya cihaz ayarı geçersiz.')
        if not self.model_path or not Path(self.model_path).is_file():
            raise FileNotFoundError('Ses modeli bulunamadı. AI Cover sekmesinden modeli yeniden ekleyin.')
        if self.index_path and not Path(self.index_path).is_file():
            raise FileNotFoundError('Modelin index dosyası bulunamadı. Model kaydını kontrol edin.')
        for name in ('input_device', 'output_device'):
            if type(getattr(self, name)) is not int or not -1 <= getattr(self, name) <= 65535:
                raise ValueError('Mikrofon veya dinleme aygıtı seçimi geçersiz.')
        if type(self.pitch) is not int or not -24 <= self.pitch <= 24:
            raise ValueError('Perde -24 ile 24 arasında olmalı.')
        if (type(self.index_rate) not in (int, float) or not math.isfinite(self.index_rate)
                or not 0 <= self.index_rate <= 1):
            raise ValueError('Ses benzerlik oranı 0 ile 1 arasında olmalı.')
        if self.f0_method not in ('rmvpe', 'crepe'):
            raise ValueError('Desteklenmeyen canlı perde yöntemi.')
        if type(self.block_seconds) not in (int, float) or self.block_seconds not in (.25, .5, 1.):
            raise ValueError('Canlı ses parçası 250, 500 veya 1000 milisaniye olmalı.')
        if type(self.gain) not in (int, float) or not math.isfinite(self.gain) or not .1 <= self.gain <= 1:
            raise ValueError('Dinleme düzeyi yüzde 10 ile 100 arasında olmalı.')
        validate_gate(self.gate_enabled, self.gate_db)
        return self



class LiveRVC:
    """One generator, feature/pitch helpers and validated index per session."""
    def __init__(self, options):
        from rvc.infer.infer import VoiceConverter
        from rvc.infer.safe_index import load_index
        self.options = options
        self.converter = VoiceConverter(device=options.device, allow_model_download=False)
        try:
            self.converter.get_vc(options.model_path, 0)
            self.converter.validate_embedder('contentvec')
            self.converter.load_hubert('contentvec')
            self.index = (load_index(options.index_path, 768 if self.converter.version == 'v2' else 256)
                          if options.index_path and options.index_rate else None)
        except BaseException:
            self.close()
            raise

    def convert(self, audio):
        import numpy as np
        import soxr
        from scipy.signal import butter, filtfilt
        converter, options = self.converter, self.options
        audio = np.asarray(audio, dtype='float32')
        if audio.ndim != 1 or not np.isfinite(audio).all():
            raise ValueError('Canlı giriş sesi geçersiz.')
        source_frames = len(audio)
        audio = soxr.resample(audio, RATE, 16000, quality='VHQ')
        if converter.quality_policy.input_highpass_80hz:
            b, a = butter(4, 80 / 8000, btype='highpass')
            audio = filtfilt(b, a, audio)
        peak = float(np.max(np.abs(audio))) / .95
        if peak > 1:
            audio = audio / peak
        converted = converter.vc.pipeline(
            model=converter.hubert_model, net_g=converter.net_g, sid=0, audio=audio,
            pitch=options.pitch, f0_method=options.f0_method, file_index='',
            index_rate=options.index_rate, pitch_guidance=converter.use_f0,
            volume_envelope=1., version=converter.version, protect=.33,
            f0_autotune=False, f0_autotune_strength=1., proposed_pitch=False,
            proposed_pitch_threshold=155., retrieval_index=self.index)
        converted = soxr.resample(converted, converter.tgt_sr, RATE, quality='VHQ')
        if len(converted) < source_frames or not np.isfinite(converted).all():
            raise ValueError('Canlı ses motoru eksik veya geçersiz çıktı üretti.')
        return converted[:source_frames].astype('float32', copy=False)

    def warmup(self):
        import numpy as np
        # Warm all helpers before the microphone is opened; never play this tone.
        self.convert((.01 * np.sin(np.arange(RATE, dtype='float32') * (2 * np.pi * 150 / RATE))))

    def close(self):
        self.index = None
        self.converter.cleanup_model()


class LiveWindow:
    """Keep real left context and crossfade the same 20 ms across conversions."""
    def __init__(self, block_frames):
        import numpy as np
        self.block_frames = block_frames
        self.context_frames, self.overlap = RATE // 2, RATE // 50
        self.history = np.zeros(self.context_frames, dtype='float32')
        self.tail = None
        self.fade = np.linspace(0, 1, self.overlap, dtype='float32')

    def process(self, block, convert):
        import numpy as np
        block = np.asarray(block, dtype='float32')
        if block.shape != (self.block_frames,) or not np.isfinite(block).all():
            raise ValueError('Canlı mikrofon parçası geçersiz.')
        window = np.concatenate((self.history, block))
        converted = np.asarray(convert(window), dtype='float32')
        if converted.shape != window.shape or not np.isfinite(converted).all():
            raise ValueError('Canlı dönüştürme sonucu geçersiz.')
        start, end = self.context_frames, len(window) - self.overlap
        core = converted[start:end].copy()
        if self.tail is None:
            core[:self.overlap] *= self.fade
            result = core
        else:
            shared = converted[start-self.overlap:start]
            result = np.concatenate((self.tail * (1-self.fade) + shared * self.fade, core))
        self.tail = converted[end:].copy()
        self.history = window[-self.context_frames:].copy()
        return result

    def silence(self):
        import numpy as np
        result = np.zeros(self.block_frames, dtype='float32')
        if self.tail is not None:
            result[:self.overlap] = self.tail*(1-self.fade)
        self.tail = None
        self.history.fill(0)
        return result


class LatestBlocks:
    """Keep at most two unconverted blocks, dropping oldest audio on overload."""
    def __init__(self):
        self.queue = queue.Queue(maxsize=2)
        self.dropped = 0

    def put(self, item):
        while True:
            try:
                self.queue.put_nowait(item)
                return
            except queue.Full:
                try:
                    self.queue.get_nowait()
                    self.dropped += 1
                except queue.Empty:
                    pass


def run_live(options, *, cancelled=lambda: False, progress=lambda message: None,
             converter_factory=LiveRVC, input_factory=None, output_factory=None, controls=None):
    """Only the owned audio worker calls this. No personal audio is persisted."""
    import numpy as np
    from live_audio import WaveInput, WaveOutput
    options.validate()
    if cancelled():
        raise InterruptedError('Canlı dinleme durduruldu.')
    progress('Canlı ses modeli hazırlanıyor; mikrofon henüz açılmadı.')
    converter = converter_factory(options)
    stop = threading.Event()
    pending, errors = LatestBlocks(), []
    blocks = 0
    gated_blocks = 0
    dropped_playback = 0
    block_frames = round(options.block_seconds * RATE)
    window = LiveWindow(block_frames)
    gate = NoiseGate(options.gate_enabled, options.gate_db)
    mask_tail = np.zeros(window.overlap, dtype='float32')
    thread = None

    def stopped():
        return stop.is_set() or bool(cancelled())

    try:
        converter.warmup()
        if stopped():
            raise InterruptedError('Canlı dinleme durduruldu.')
        with ExitStack() as stack:
            output = stack.enter_context(output_factory(options.output_device) if output_factory else
                                         WaveOutput(options.output_device, expected_name=options.output_name))
            source = stack.enter_context(input_factory(options.input_device) if input_factory else
                                         WaveInput(options.input_device, expected_name=options.input_name))

            # Model warm-up can take several seconds. Confirm through the selected
            # output that both devices are now open before capture processing starts.
            output.write(ready_tone())

            def capture():
                data = np.empty(0, dtype='float32')
                sequence = 0
                try:
                    while not stopped():
                        chunk = np.asarray(source.read(stopped), dtype='float32')
                        if chunk.ndim != 1 or not 0 < len(chunk) <= RATE or not np.isfinite(chunk).all():
                            raise ValueError('Mikrofondan geçersiz veri alındı.')
                        data = np.concatenate((data, chunk))
                        while len(data) >= block_frames:
                            pending.put((sequence, time.monotonic(), data[:block_frames].copy()))
                            data = data[block_frames:]
                            sequence += 1
                except InterruptedError:
                    if not stopped():
                        errors.append(RuntimeError('Mikrofon bağlantısı kesildi.'))
                except BaseException as error:
                    errors.append(error)
                finally:
                    stop.set()

            thread = threading.Thread(target=capture, name='live-microphone', daemon=True)
            thread.start()
            previous = -1
            notice = 0.
            try:
                input_name = getattr(getattr(source, 'actual_device', None), 'name', options.input_name or str(options.input_device))
                output_name = getattr(getattr(output, 'actual_device', None), 'name', options.output_name or str(options.output_device))
                progress(f'Mikrofon açıldı. Giriş: {input_name}; dönüştürülmüş çıkış: {output_name}; işlem cihazı: {options.device}.')
                while not stopped():
                    try:
                        sequence, captured, block = pending.queue.get(timeout=.05)
                    except queue.Empty:
                        continue
                    if sequence != previous + 1:
                        window = LiveWindow(block_frames)
                        mask_tail.fill(0)
                        output.clear()
                    previous = sequence
                    if controls:
                        values = controls()
                        if values is not None and gate.configure(values['enabled'], values['threshold_db']):
                            window = LiveWindow(block_frames)
                            mask_tail.fill(0)
                    started = time.monotonic()
                    gated, active, level_db = gate.process(block)
                    if active:
                        fresh = window.tail is None
                        converted = window.process(gated, converter.convert)
                        if fresh:
                            # The held tail costs 20 ms. Prime that delay once.
                            converted = np.concatenate((np.zeros(window.overlap, dtype='float32'), converted))
                    else:
                        # Never synthesize background hiss from a closed microphone gate.
                        # No neural network call, F0 extraction or GPU allocation here.
                        converted = window.silence()
                        gated_blocks += 1
                    # A model can synthesize hiss inside a partly voiced block.
                    # Apply the gate at the same delayed timeline as the RVC tail.
                    mask = np.concatenate((mask_tail, gate.last_mask[:-window.overlap]))
                    mask_tail = gate.last_mask[-window.overlap:].copy()
                    converted *= mask
                    duration = time.monotonic() - started
                    if stopped():
                        break
                    queued = output.queued_frames()
                    if queued + len(converted) > block_frames * 2:
                        output.clear()
                        queued = 0
                        dropped_playback += 1
                    output.write(converted * options.gain)
                    blocks += 1
                    now = time.monotonic()
                    if now-notice >= 1:
                        # Estimate queue + capture block + inference; not an acoustic measurement.
                        delay = (options.block_seconds + now-captured + queued/RATE + window.overlap/RATE) * 1000
                        level = f'{level_db:.0f} dB' if math.isfinite(level_db) else 'sessiz'
                        text = (f'Canlı dinleme: tahmini gecikme {delay:.0f} ms; '
                                f'dönüştürme {duration*1000:.0f} ms; '
                                f'giriş {level}; eşik {gate.threshold_db:g} dB; '
                                f'atlanan parça {pending.dropped + dropped_playback}.')
                        if not active:
                            text = f'Ses eşiğinin altında; dönüştürme bekliyor. Giriş {level}; eşik {gate.threshold_db:g} dB.'
                        if duration > options.block_seconds:
                            text += ' Donanım yetişemiyor; daha uzun ses parçası veya ekran kartı seçin.'
                        progress(text)
                        notice = now
            finally:
                stop.set()
                thread.join(timeout=2)
                if thread.is_alive():
                    raise RuntimeError('Mikrofon thread’i durmadı; Zorla durdur düğmesini kullanın.')
            if errors:
                raise errors[0]
    finally:
        stop.set()
        converter.close()
    return {'blocks': blocks, 'dropped': pending.dropped + dropped_playback, 'gated_blocks': gated_blocks}
