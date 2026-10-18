"""Owned Windows microphone/playback streams; no recording files or extra DLLs.

WinMM buffers stay alive until reset/unprepare succeeds. Only the audio worker
opens streams; the GUI can enumerate device names without opening a microphone.
"""
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import os
import time

RATE = 48000
WHDR_DONE = 1
WHDR_PREPARED = 2
_quarantined = []  # Keep driver-owned memory alive on a fatal cleanup failure.


class WaveFormat(C.Structure):
    _pack_ = 2
    _fields_ = [('tag', W.WORD), ('channels', W.WORD), ('rate', W.DWORD),
                ('bytes_per_second', W.DWORD), ('align', W.WORD),
                ('bits', W.WORD), ('extra', W.WORD)]


class WaveHeader(C.Structure):
    _fields_ = [('data', C.c_void_p), ('length', W.DWORD), ('recorded', W.DWORD),
                ('user', C.c_size_t), ('flags', W.DWORD), ('loops', W.DWORD),
                ('next', C.c_void_p), ('reserved', C.c_size_t)]


class InputCaps(C.Structure):
    _fields_ = [('manufacturer', W.WORD), ('product', W.WORD), ('version', W.UINT),
                ('name', W.WCHAR * 32), ('formats', W.DWORD),
                ('channels', W.WORD), ('reserved', W.WORD)]


class OutputCaps(C.Structure):
    _fields_ = InputCaps._fields_ + [('support', W.DWORD)]


@dataclass(frozen=True)
class AudioDevice:
    id: int
    name: str


def winmm():
    if os.name != 'nt':
        raise RuntimeError('Canlı mikrofon dinleme Windows üzerinde kullanılabilir.')
    api = C.WinDLL('winmm')
    for direction, caps in (('In', InputCaps), ('Out', OutputCaps)):
        count = getattr(api, f'wave{direction}GetNumDevs')
        count.argtypes, count.restype = [], W.UINT
        query = getattr(api, f'wave{direction}GetDevCapsW')
        query.argtypes, query.restype = [C.c_size_t, C.POINTER(caps), W.UINT], W.UINT
        opener = getattr(api, f'wave{direction}Open')
        opener.argtypes = [C.POINTER(W.HANDLE), W.UINT, C.POINTER(WaveFormat),
                           C.c_size_t, C.c_size_t, W.DWORD]
        opener.restype = W.UINT
        identity = getattr(api, f'wave{direction}GetID')
        identity.argtypes, identity.restype = [W.HANDLE, C.POINTER(W.UINT)], W.UINT
        for suffix in ('PrepareHeader', 'UnprepareHeader', 'AddBuffer' if direction == 'In' else 'Write'):
            method = getattr(api, f'wave{direction}{suffix}')
            method.argtypes, method.restype = [W.HANDLE, C.POINTER(WaveHeader), W.UINT], W.UINT
        for suffix in ('Reset', 'Close', *(['Start'] if direction == 'In' else [])):
            method = getattr(api, f'wave{direction}{suffix}')
            method.argtypes, method.restype = [W.HANDLE], W.UINT
        message = getattr(api, f'wave{direction}GetErrorTextW')
        message.argtypes, message.restype = [W.UINT, W.LPWSTR, W.UINT], W.UINT
    return api


def check(api, code, direction, operation):
    if code:
        message = C.create_unicode_buffer(256)
        getattr(api, f'wave{direction}GetErrorTextW')(code, message, len(message))
        raise RuntimeError(f'{operation}: {message.value or "Windows ses aygıtı hatası"} '
                           f'(kod {code}). Cihaz seçimini ve Windows mikrofon izinlerini kontrol edin.')


def enumerate_devices():
    api = winmm()
    result = {}
    for key, direction, caps_type in (('inputs', 'In', InputCaps), ('outputs', 'Out', OutputCaps)):
        devices = [AudioDevice(-1, 'Windows varsayılan aygıtı')]
        for identity in range(getattr(api, f'wave{direction}GetNumDevs')()):
            caps = caps_type()
            code = getattr(api, f'wave{direction}GetDevCapsW')(identity, C.byref(caps), C.sizeof(caps))
            if not code and caps.channels:
                devices.append(AudioDevice(identity, caps.name))
        result[key] = devices
    return result


class _Buffer:
    def __init__(self, size, data=None):
        self.memory = C.create_string_buffer(size)
        if data is not None:
            C.memmove(self.memory, data, size)
        self.header = WaveHeader(data=C.addressof(self.memory), length=size)


class _WaveStream:
    direction = ''

    def __init__(self, device, channels, *, api=None, expected_name=''):
        self.api = api or winmm()
        self.handle = W.HANDLE()
        self.buffers = []
        self.channels = channels
        self.requested_device = device
        align = channels * 2
        format_ = WaveFormat(1, channels, RATE, RATE * align, align, 16, 0)
        if device >= 0 and expected_name:
            self.verify_name(device, expected_name)
        check(self.api, self.call('Open', C.byref(self.handle), device & 0xffffffff,
                                 C.byref(format_), 0, 0, 0), self.direction, 'Ses aygıtı açılamadı')
        try:
            actual = W.UINT()
            check(self.api, self.call('GetID', self.handle, C.byref(actual)), self.direction, 'Açılan ses aygıtı doğrulanamadı')
            if device >= 0 and actual.value != device:
                raise RuntimeError('Windows seçilen ses aygıtı yerine başka bir aygıt açtı; ses gönderilmedi. Aygıt listesini yenileyin.')
            name = self.verify_name(actual.value, expected_name if device >= 0 else '')
            self.actual_device = AudioDevice(actual.value, name)
        except BaseException:
            self.close()
            raise

    def verify_name(self, device, expected):
        caps = InputCaps() if self.direction == 'In' else OutputCaps()
        check(self.api, self.call('GetDevCapsW', device, C.byref(caps), C.sizeof(caps)),
              self.direction, 'Seçilen ses aygıtı bulunamadı')
        if expected and caps.name != expected:
            raise RuntimeError('Ses aygıtı listesi değişti; seçilen aygıt açılamadı. Listeyi yenileyip aygıtı yeniden seçin.')
        return caps.name

    def call(self, name, *args):
        return getattr(self.api, f'wave{self.direction}{name}')(*args)

    def header_call(self, name, buffer):
        check(self.api, self.call(name, self.handle, C.byref(buffer.header), C.sizeof(WaveHeader)),
              self.direction, 'Ses tamponu işlemi başarısız')

    def reset(self):
        check(self.api, self.call('Reset', self.handle), self.direction, 'Ses aygıtı durdurulamadı')

    def close(self):
        if not self.handle:
            return
        try:
            self.reset()
            for buffer in self.buffers:
                if buffer.header.flags & WHDR_PREPARED:
                    self.header_call('UnprepareHeader', buffer)
            check(self.api, self.call('Close', self.handle), self.direction, 'Ses aygıtı kapatılamadı')
            self.handle = W.HANDLE()
            self.buffers.clear()
        except BaseException:
            _quarantined.append(self)
            raise  # The owned worker exits; never free buffers still used by a driver.

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class WaveInput(_WaveStream):
    direction = 'In'

    def __init__(self, device=-1, *, api=None, expected_name=''):
        super().__init__(device, 1, api=api, expected_name=expected_name)
        self.cursor = 0
        try:
            # Eight 20 ms buffers keep capture polling independent of inference.
            for _ in range(8):
                buffer = _Buffer(RATE // 50 * 2)
                self.buffers.append(buffer)
                self.header_call('PrepareHeader', buffer)
                self.header_call('AddBuffer', buffer)
            check(self.api, self.call('Start', self.handle), 'In', 'Mikrofon başlatılamadı')
        except BaseException:
            self.close()
            raise

    def read(self, stopped):
        import numpy as np
        buffer = self.buffers[self.cursor]
        deadline = time.monotonic() + 10
        while not buffer.header.flags & WHDR_DONE:
            if stopped():
                raise InterruptedError('Canlı dinleme durduruldu.')
            if time.monotonic() > deadline:
                raise RuntimeError('Mikrofondan ses alınamıyor. Aygıtı ve Windows mikrofon izinlerini kontrol edin.')
            time.sleep(.005)
        if stopped():
            raise InterruptedError('Canlı dinleme durduruldu.')
        size = buffer.header.recorded
        if not 0 < size <= buffer.header.length or size % 2:
            raise ValueError('Mikrofon geçersiz ses tamponu döndürdü.')
        data = np.frombuffer(buffer.memory, dtype='<i2', count=size // 2).astype('float32') / 32768.
        buffer.header.recorded = 0
        self.header_call('AddBuffer', buffer)
        self.cursor = (self.cursor + 1) % len(self.buffers)
        return data


class WaveOutput(_WaveStream):
    direction = 'Out'

    def __init__(self, device=-1, *, api=None, expected_name=''):
        super().__init__(device, 2, api=api, expected_name=expected_name)

    def queued_frames(self):
        remaining = []
        for buffer in self.buffers:
            if buffer.header.flags & WHDR_DONE:
                self.header_call('UnprepareHeader', buffer)
            else:
                remaining.append(buffer)
        self.buffers = remaining
        return sum(buffer.header.length // 4 for buffer in remaining)

    def clear(self):
        self.reset()
        self.queued_frames()

    def write(self, audio):
        import numpy as np
        audio = np.asarray(audio, dtype='float32')
        if audio.ndim != 1 or not 0 < len(audio) <= RATE or not np.isfinite(audio).all():
            raise ValueError('Canlı dinleme çıktısı geçersiz.')
        if self.queued_frames() + len(audio) > RATE * 2:
            raise RuntimeError('Dinleme cihazının ses kuyruğu doldu; başka bir aygıt seçin.')
        pcm = np.rint(np.clip(audio, -1., 32767 / 32768) * 32768).astype('<i2')
        data = np.repeat(pcm[:, None], 2, axis=1).tobytes()
        buffer = _Buffer(len(data), data)
        self.buffers.append(buffer)
        self.header_call('PrepareHeader', buffer)
        self.header_call('Write', buffer)
