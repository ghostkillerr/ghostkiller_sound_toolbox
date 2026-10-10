"""Shared job coordination and safe, main-thread UI dispatch."""
import os
import re
import sys
import threading
import tempfile
import urllib.request

JOB_LOCK = threading.Lock()


def app_directory():
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)


def resource_directory():
    return getattr(sys, "_MEIPASS", app_directory())


def model_directory(app_dir=None):
    """Models live alongside the installed executable (or source checkout)."""
    directory = os.path.join(app_dir or app_directory(), 'models')
    return directory


def data_directory():
    if not getattr(sys, "frozen", False):
        return app_directory()
    root = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    directory = os.path.join(root, "GhostkillerSoundToolbox")
    os.makedirs(directory, exist_ok=True)
    return directory


def configure_runtime_cache():
    """Numba must not create cache files in read-only site-packages/Program Files."""
    if not os.environ.get("NUMBA_CACHE_DIR"):
        root = data_directory()
        cache = os.path.join(root, "cache" if getattr(sys, "frozen", False) else "__pycache__", "numba")
        os.makedirs(cache, exist_ok=True)
        os.environ["NUMBA_CACHE_DIR"] = cache


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip().rstrip('. ')
    value = value[:120].rstrip('. ') or 'ses'
    if value.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        value = '_' + value
    return value


def same_path(first, second):
    if os.path.normcase(os.path.realpath(first)) == os.path.normcase(os.path.realpath(second)):
        return True
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def validate_audio_file(path):
    """Check decoded samples before replacing a previous successful result."""
    import numpy as np
    import soundfile as sf
    with sf.SoundFile(path) as audio:
        if audio.frames <= 0 or audio.samplerate <= 0 or audio.channels <= 0:
            raise ValueError("Çıktı ses dosyası boş veya geçersiz.")
        expected = audio.frames
        decoded = 0
        while True:
            samples = audio.read(65536, dtype='float32', always_2d=True)
            if not len(samples):
                break
            if not np.isfinite(samples).all():
                raise ValueError("Çıktı ses dosyasında geçersiz örnekler var.")
            decoded += len(samples)
        if decoded != expected:
            raise ValueError("Çıktı ses dosyası eksik.")


def copy_model(source, target):
    import shutil
    fd, temporary_path = tempfile.mkstemp(dir=os.path.dirname(target), suffix='.part')
    os.close(fd)
    try:
        shutil.copyfile(source, temporary_path)
        if not os.path.getsize(temporary_path):
            raise ValueError("Önbellekteki model dosyası boş.")
        os.replace(temporary_path, target)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def download_model(url, target, cancelled=None, progress=None, validate=None):
    """Never leave a partial download at the model's final path."""
    fd, temporary_path = tempfile.mkstemp(dir=os.path.dirname(target), suffix=".part")
    try:
        with os.fdopen(fd, "wb") as output:
            with urllib.request.urlopen(url, timeout=30) as response:
                expected = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                while True:
                    if cancelled and cancelled():
                        raise InterruptedError("Model indirmesi iptal edildi.")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    if progress:
                        progress(downloaded, expected)
        if not downloaded or (expected and downloaded != expected):
            raise RuntimeError("Model indirmesi boş veya eksik.")
        if cancelled and cancelled():
            raise InterruptedError("Model indirmesi iptal edildi.")
        if validate:
            validate(temporary_path)
        if cancelled and cancelled():
            raise InterruptedError("Model indirmesi iptal edildi.")
        os.replace(temporary_path, target)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def post_ui(window, callback, *args):
    import wx
    def invoke():
        if window and not window.IsBeingDeleted():
            callback(*args)
    if wx.IsMainThread():
        invoke()
    else:
        wx.CallAfter(invoke)


def finish_job(window):
    """Keep the lock until preceding UI updates have reached the main thread."""
    import wx
    def finish():
        try:
            if window and not window.IsBeingDeleted():
                window.EnableUI(True)
        finally:
            JOB_LOCK.release()
    wx.CallAfter(finish)


def append_log(window, message):
    def append():
        window.txt_log.AppendText(message.strip() + '\n')
        window.txt_log.ShowPosition(window.txt_log.GetLastPosition())
    post_ui(window, append)
