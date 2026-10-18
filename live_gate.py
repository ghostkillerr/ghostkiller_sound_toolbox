"""Microphone noise measurement and gate DSP; never stores or plays audio."""
from dataclasses import dataclass
import math
import time

from live_audio import RATE, WaveInput

FRAME = RATE // 100
CALIBRATION_SECONDS = 10
HYSTERESIS_DB = 6.
ATTACK_MS = 5
HOLD_MS = 150
RELEASE_MS = 120


def validate_gate(enabled, threshold_db):
    if (type(enabled) is not bool or type(threshold_db) not in (int, float)
            or not math.isfinite(threshold_db) or threshold_db > 0):
        raise ValueError('Ses eşiği açık/kapalı olmalı ve 0 dB veya altında sonlu bir sayı olmalı; alt sınır yoktur.')


class NoiseGate:
    """10 ms RMS, separate opening/closing thresholds and cosine gain ramps."""
    def __init__(self, enabled=True, threshold_db=-45.):
        self.enabled = self.threshold_db = None
        self.configure(enabled, threshold_db)

    def configure(self, enabled, threshold_db):
        validate_gate(enabled, threshold_db)
        changed = (enabled, threshold_db) != (self.enabled, self.threshold_db)
        if changed:
            self.enabled, self.threshold_db = enabled, threshold_db
            self.envelope, self.hold = 0., 0
            self.open = False
            self.ramp_start, self.ramp_position, self.ramp_length = 0., 0, 0
            self.last_mask = None
        return changed

    def process(self, samples):
        import numpy as np
        samples = np.asarray(samples, dtype='float32')
        if samples.ndim != 1 or not len(samples) or not np.isfinite(samples).all():
            raise ValueError('Ses eşiği için mikrofon verisi geçersiz.')
        result, mask = np.empty_like(samples), np.empty_like(samples)
        maximum = 0.
        close_threshold = self.threshold_db-HYSTERESIS_DB
        for start in range(0, len(samples), FRAME):
            frame = samples[start:start+FRAME]
            rms = float(np.sqrt(np.mean(frame.astype('float64')**2)))
            maximum = max(maximum, rms)
            if not self.enabled:
                result[start:start+len(frame)] = frame
                mask[start:start+len(frame)] = 1
                continue
            opened = self.open
            # Compare in dB: very low thresholds must not underflow to zero
            # amplitude and inadvertently open the gate on digital silence.
            db = 20*math.log10(rms) if rms else -math.inf
            if db >= (close_threshold if opened else self.threshold_db):
                self.hold, self.open = round(RATE*HOLD_MS/1000), True
            elif self.hold > 0:
                self.hold = max(0, self.hold-len(frame))
            else:
                self.open = False
            if self.open != opened:
                self.ramp_start, self.ramp_position = self.envelope, 0
                self.ramp_length = round(RATE*(ATTACK_MS if self.open else RELEASE_MS)/1000)
            target = float(self.open)
            if self.ramp_length:
                position = np.minimum(1., (self.ramp_position+np.arange(1, len(frame)+1))/self.ramp_length)
                envelope = self.ramp_start+(target-self.ramp_start)*(.5-.5*np.cos(np.pi*position))
                self.ramp_position += len(frame)
                if self.ramp_position >= self.ramp_length:
                    self.ramp_length = 0
            else:
                envelope = np.full(len(frame), target)
            self.envelope = float(envelope[-1])
            result[start:start+len(frame)] = frame*envelope
            mask[start:start+len(frame)] = envelope
        level_db = 20*math.log10(maximum) if maximum else -math.inf
        self.last_mask = mask
        return result, (not self.enabled or bool(np.any(mask))), level_db


@dataclass(frozen=True)
class CalibrationOptions:
    input_device: int = -1
    input_name: str = ''

    def validate(self):
        if (type(self.input_device) is not int or not -1 <= self.input_device <= 65535
                or not isinstance(self.input_name, str)):
            raise ValueError('Ölçüm için mikrofon seçimi geçersiz.')
        return self


class NoiseMeasurement:
    """Only 1000 scalar RMS levels are retained, with at most one pending frame."""
    def __init__(self):
        import numpy as np
        self.pending = np.empty(0, dtype='float32')
        self.levels = []
        self.clipped = 0
        self.frames = 0

    def feed(self, samples):
        import numpy as np
        samples = np.asarray(samples, dtype='float32')
        if (samples.ndim != 1 or not 0 < len(samples) <= RATE or not np.isfinite(samples).all()
                or np.max(np.abs(samples)) > 1):
            raise ValueError('Ölçüm sırasında mikrofondan geçersiz ses alındı.')
        remaining = CALIBRATION_SECONDS*RATE-self.frames
        samples = samples[:remaining]
        self.frames += len(samples)
        self.clipped += int(np.count_nonzero(np.abs(samples) >= .999))
        samples = np.concatenate((self.pending, samples))
        complete = len(samples)//FRAME*FRAME
        if complete:
            rms = np.sqrt(np.mean(samples[:complete].reshape(-1, FRAME).astype('float64')**2, axis=1))
            # The numerical floor represents exact zeros, not a minimum dB setting.
            self.levels.extend((20*np.log10(np.maximum(rms, np.finfo('float64').tiny))).tolist())
        self.pending = samples[complete:].copy()

    def result(self):
        import numpy as np
        if self.frames != CALIBRATION_SECONDS*RATE or len(self.levels) != CALIBRATION_SECONDS*100:
            raise ValueError('10 saniyelik mikrofon ölçümü tamamlanmadı; eşik değiştirilmedi.')
        # Ignore isolated clicks, but reject prolonged speech or a changing room.
        levels = np.asarray(self.levels)
        median, upper, floor = np.percentile(levels, [50, 90, 95])
        if floor <= 20*math.log10(np.finfo('float64').tiny):
            raise ValueError('Mikrofon sinyali alınamadı veya mikrofon sessizde. Sesi açıp ölçümü tekrarlayın; eşik değiştirilmedi.')
        if self.clipped or floor > -25:
            raise ValueError('Ölçümde ses çok yüksek. Konuşmadan, mikrofon kazancını ve ortamı kontrol ederek tekrar deneyin; eşik değiştirilmedi.')
        if upper-median > 10:
            raise ValueError('Ölçüm sırasında konuşma veya değişken gürültü algılandı. 10 saniye sessiz kalarak tekrar deneyin; eşik değiştirilmedi.')
        floor_db = round(float(floor), 1)
        opening = min(0, math.ceil(floor_db+10))
        return {'noise_db': floor_db, 'threshold_db': opening,
                'close_db': opening-HYSTERESIS_DB, 'seconds': CALIBRATION_SECONDS}


def calibrate_gate(options, *, cancelled=lambda: False, progress=lambda message: None,
                   input_factory=None, clock=time.monotonic):
    """Capture exactly ten seconds, close the mic, then return a fixed profile."""
    options.validate()
    if cancelled():
        raise InterruptedError('Otomatik eşik ayarı iptal edildi.')
    measurement = NoiseMeasurement()
    with (input_factory(options.input_device) if input_factory else
          WaveInput(options.input_device, expected_name=options.input_name)) as source:
        device = getattr(source, 'actual_device', None)
        name = device.name if device else options.input_name
        deadline = clock()+CALIBRATION_SECONDS+3

        def stopped():
            if cancelled():
                return True
            if clock() >= deadline:
                raise TimeoutError('Mikrofon ölçümü zamanında tamamlanmadı; eşik değiştirilmedi.')
            return False

        progress(f'Mikrofon açıldı. Giriş: {name}; yalnız gürültü ölçümü; ses çıkışı kapalı.')
        remaining = CALIBRATION_SECONDS
        progress(f'Konuşmayın. Ortam ölçülüyor: {remaining} saniye kaldı.')
        while measurement.frames < CALIBRATION_SECONDS*RATE:
            if stopped():
                raise InterruptedError('Otomatik eşik ayarı iptal edildi.')
            measurement.feed(source.read(stopped))
            current = math.ceil(CALIBRATION_SECONDS-measurement.frames/RATE)
            if current and current != remaining:
                progress(f'Konuşmayın. Ortam ölçülüyor: {current} saniye kaldı.')
            remaining = current
        if stopped():
            raise InterruptedError('Otomatik eşik ayarı iptal edildi.')
    # Device is already released before either success or invalid-measurement UI.
    result = measurement.result()
    result.update(input_device=device.id if device else options.input_device, input_name=name)
    return result
