"""Shared job coordination and safe, main-thread UI dispatch."""
import os
import re
import sys
import threading
import tempfile
import urllib.request
import hashlib

JOB_LOCK = threading.Lock()


def app_directory():
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)


def resource_directory():
    return getattr(sys, "_MEIPASS", app_directory())


def ffmpeg_executable(tool='ffmpeg', app_dir=None):
    """Use the packaged codec, never a legacy EXE or a machine-wide install."""
    if tool not in ('ffmpeg', 'ffprobe'):
        raise ValueError('Bilinmeyen ses aracı.')
    root = (resource_directory() if getattr(sys, 'frozen', False) else
            os.path.join(app_dir or app_directory(), 'tools', 'ffmpeg'))
    path = os.path.abspath(os.path.join(root, tool + '.exe'))
    if not os.path.isfile(path):
        raise FileNotFoundError(f'Programın {tool}.exe dosyası eksik: {path}. Kurulumu onarın.')
    return path


def configure_ffmpeg_environment(app_dir=None):
    root = (resource_directory() if getattr(sys, 'frozen', False) else
            os.path.join(app_dir or app_directory(), 'tools', 'ffmpeg'))
    root = os.path.abspath(root)
    entries = [entry for entry in os.environ.get('PATH', '').split(os.pathsep)
               if entry and os.path.normcase(os.path.abspath(entry)) != os.path.normcase(root)]
    os.environ['PATH'] = os.pathsep.join([root, *entries])


def configure_pydub(app_dir=None):
    import pydub
    ffmpeg = ffmpeg_executable('ffmpeg', app_dir)
    ffprobe = ffmpeg_executable('ffprobe', app_dir)
    pydub.AudioSegment.converter = ffmpeg
    pydub.utils.get_prober_name = lambda: ffprobe


def model_directory(app_dir=None):
    """Models live alongside the installed executable (or source checkout)."""
    directory = os.path.join(app_dir or app_directory(), 'models')
    return directory


def model_cache_directories(app_dir):
    """Legacy model locations shared by the GUI and headless model management."""
    user_home = os.path.expanduser('~')
    return [
        os.path.join(app_dir, 'modeller'),
        os.path.join(os.environ.get('LOCALAPPDATA', user_home), 'GhostkillerSoundToolbox', 'modeller'),
        os.path.join(user_home, '.cache', 'audio-separator', 'models'),
        os.path.join(user_home, '.cache', 'audio-separator'),
        os.path.join(user_home, 'AppData', 'Local', 'audio-separator', 'models'),
        os.path.join(user_home, 'AppData', 'Local', 'audio-separator'),
        os.path.join(os.environ.get('TEMP', ''), 'audio-separator-models'),
    ]


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


def truncate_utf16(value, limit):
    return value.encode('utf-16-le')[:max(0,limit)*2].decode('utf-16-le',errors='ignore')


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).strip().rstrip('. ')
    value = truncate_utf16(value,120).rstrip('. ') or 'ses'
    if value.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        value = '_' + value
    return value


def output_filename(base, suffix):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', str(base)).strip().rstrip('. ') or 'ses'
    maximum = min(120,255-len(suffix.encode('utf-16-le'))//2)
    if maximum < 12 or re.search(r'[<>:"/\\|?*\x00-\x1f]',suffix):
        raise ValueError('Çıktı dosyası son eki çok uzun veya geçersiz.')
    if len(cleaned.encode('utf-16-le'))//2 > maximum:
        digest = hashlib.sha256(cleaned.encode('utf-8')).hexdigest()[:10]
        cleaned = truncate_utf16(cleaned,maximum-11).rstrip('. ')+'_'+digest
    cleaned = safe_filename(cleaned)
    return truncate_utf16(cleaned,maximum).rstrip('. ')+suffix


def configure_thread_environment(threads=None):
    threads = threads or max(1,min(8,(os.cpu_count() or 2)//2))
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        os.environ.setdefault(key,str(threads))


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
    """Keep resumable data private; publish only a complete, validated model."""
    from model_download import download
    return download(url, target, opener=urllib.request.urlopen, cancelled=cancelled,
                    progress=progress, validate=validate)


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
        if window and not window.IsBeingDeleted():
            refresh = getattr(getattr(window, 'settings', None), 'refresh_operations', None)
            if refresh:
                refresh()
    wx.CallAfter(finish)


def append_log(window, message):
    def append():
        if window.txt_log.GetLastPosition() > 48000:
            window.txt_log.SetValue(window.txt_log.GetValue()[-24000:])
        window.txt_log.AppendText(message.strip() + '\n')
        window.txt_log.ShowPosition(window.txt_log.GetLastPosition())
    post_ui(window, append)
