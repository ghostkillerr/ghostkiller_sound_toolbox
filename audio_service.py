"""Persistent native audio worker, owned by the calling job."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from native_process import NativeProcessGroup


def write_message(path, value):
    path = Path(path)
    temporary = path.with_suffix('.part')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class NativeAudioSession:
    def __init__(self, command=None, directory=None):
        from app_runtime import data_directory
        root = Path(directory or Path(data_directory())/'cache'/'audio_sessions')
        root.mkdir(parents=True, exist_ok=True)
        self._temporary = tempfile.TemporaryDirectory(prefix='audio_', dir=root)
        self.directory = Path(self._temporary.name)
        self._command = command
        self._group = NativeProcessGroup()
        self.process = None
        self._log = None
        self._sequence = 0
        self._force = threading.Event()
        self._control_lock = threading.Lock()
        self._closed = False

    def _start(self):
        if self._closed:
            raise RuntimeError('Ses worker oturumu kapalı.')
        if self.process is not None:
            return
        from app_runtime import app_directory
        command = self._command or ([sys.executable, '--audio-worker'] if getattr(sys, 'frozen', False)
                                   else [sys.executable, '-u', '-m', 'audio_worker'])
        self._log = (self.directory/'worker.log').open('wb')
        try:
            environment = os.environ.copy()
            environment['PYTHONIOENCODING'] = 'utf-8'
            environment['PYTHONUTF8'] = '1'
            self.process = self._group.spawn([*command, str(self.directory)], cwd=app_directory(),
                stdin=subprocess.DEVNULL, stdout=self._log, stderr=self._log,
                env=environment,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                start_new_session=os.name != 'nt')
        except BaseException:
            self.close()
            raise

    def request_force_stop(self):
        self._force.set()

    def set_live_gate(self, enabled, threshold_db):
        from live_cover import validate_gate
        validate_gate(enabled, threshold_db)
        with self._control_lock:
            if self._closed:
                raise RuntimeError('Canlı dinleme oturumu kapalı.')
            write_message(self.directory/'live_controls.json', {'enabled': enabled, 'threshold_db': threshold_db})

    def execute(self, kind, payload, cancelled=None, progress=None):
        self._start()
        self._sequence += 1
        sequence = self._sequence
        response_path = self.directory/f'response_{sequence}.json'
        try:
            write_message(self.directory/f'request_{sequence}.json', {'kind':kind, 'payload':payload})
        except BaseException:
            self.close()
            raise
        last_notice = time.monotonic()
        live_cancel_started = None
        microphone_announced = False
        while True:
            try:
                if kind == 'hardware_probe' and cancelled and cancelled():
                    # No outputs, checkpoints or microphone belong to this check.
                    # DLL initialization need not finish before Cancel can return.
                    self._group.terminate(timeout=3.)
                    self.close()
                    raise InterruptedError('Donanım kontrolü iptal edildi.')
                if kind in ('restore_vocal','instruments','live_cover','calibrate_gate') and cancelled and cancelled():
                    (self.directory/f'cancel_{sequence}').touch(exist_ok=True)
                    if kind in ('live_cover', 'calibrate_gate'):
                        if live_cancel_started is None:
                            live_cancel_started = time.monotonic()
                        elif time.monotonic()-live_cancel_started >= 1.5:
                            # Monitoring has no checkpoint/output to save. A long GPU
                            # kernel must not keep the microphone/playback open.
                            self._group.terminate(timeout=3.)
                            self.close()
                            raise InterruptedError('Otomatik eşik ayarı iptal edildi.' if kind == 'calibrate_gate' else 'Canlı dinleme durduruldu.')
            except BaseException:
                self.close()
                raise
            if self._force.is_set():
                self._group.terminate(timeout=3.)
                self.close()
                raise InterruptedError('Ses worker kullanıcı isteğiyle zorla durduruldu; bu adımın çıktısı kaydedilmedi.')
            opened_path = self.directory/f'live_started_{sequence}.json'
            if kind in ('live_cover', 'calibrate_gate') and progress and not microphone_announced and opened_path.is_file():
                try:
                    progress(json.loads(opened_path.read_text(encoding='utf-8'))['message'])
                    microphone_announced = True
                except BaseException:
                    self.close()
                    raise
            if response_path.exists():
                result = json.loads(response_path.read_text(encoding='utf-8'))
                if not result.get('ok'):
                    raise RuntimeError(result.get('error') or 'Ses motoru açıklama döndürmeden başarısız oldu.')
                try:
                    is_cancelled = cancelled and cancelled()
                except BaseException:
                    self.close()
                    raise
                if is_cancelled:
                    raise InterruptedError('Ses işlemi iptal edildi; bu adımın çıktısı kaydedilmedi.')
                return result.get('result')
            code = self.process.poll()
            if code is not None:
                paths = [self.directory/'worker.log',*self.directory.glob('worker_runtime_*.log'),
                         *self.directory.glob('worker_crash_*.log')]
                paths = sorted((path for path in paths if path.is_file()),key=lambda path:path.stat().st_mtime)[-3:]
                details = []
                for log_path in paths:
                    with log_path.open('rb') as stream:
                        stream.seek(max(0,log_path.stat().st_size-2000))
                        details.append(stream.read().decode('utf-8',errors='replace').strip())
                detail = '\n'.join(details).strip()
                self.close()
                raise RuntimeError(f'Native ses worker beklenmeden sonlandı (çıkış kodu {code}).\n{detail or "Motor günlüğü boş."}')
            if progress and time.monotonic()-last_notice >= (1. if kind in ('live_cover', 'calibrate_gate') else 5.):
                heartbeat = self.directory/'heartbeat'
                age = time.time()-heartbeat.stat().st_mtime if heartbeat.exists() else None
                try:
                    notice = None
                    progress_path = self.directory/f'progress_{sequence}.json'
                    if progress_path.is_file() and progress_path.stat().st_size < 4096:
                        notice = json.loads(progress_path.read_text(encoding='utf-8')).get('message')
                    progress(str(notice)[:1000] if notice else
                             'Motor çalışıyor.' if age is not None and age < 10. else
                             'Motor yanıtı bekleniyor. Gerekirse İptal Et ardından Zorla Durdur kullanın.')
                except BaseException:
                    self.close()
                    raise
                last_notice = time.monotonic()
            time.sleep(.08)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self.process is not None and self.process.poll() is None:
                (self.directory/'stop').touch()
                try:
                    self.process.wait(timeout=3.)
                except subprocess.TimeoutExpired:
                    self._group.terminate(timeout=3.)
        finally:
            try:
                self._group.close()
            finally:
                if self._log is not None:
                    self._log.close()
                self._temporary.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
