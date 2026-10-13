"""Install diagnostics before native dependencies and GUI imports."""
from pathlib import Path
import ctypes
import hashlib
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import threading
import traceback


class LogStream:
    encoding = "utf-8"
    def __init__(self, level):
        self.level = level
        self._local = threading.local()
    def write(self, text):
        text = str(text)
        if getattr(self._local,'active',False):
            return len(text)
        self._local.active = True
        try:
            for line in text.replace("\r","\n").splitlines():
                if line.strip():
                    logging.getLogger("motor").log(self.level,line.strip())
        finally:
            self._local.active = False
        return len(text)
    def flush(self):
        for handler in logging.getLogger().handlers:
            handler.flush()
    def isatty(self):
        return False


class SafeRotatingFileHandler(RotatingFileHandler):
    def handleError(self, record):
        # Logging's default handler writes to sys.stderr. In a windowed app
        # that stream logs back into this handler; never enter that cycle.
        stream = sys.__stderr__
        if stream is not None and not isinstance(stream,LogStream):
            try:
                stream.write('Ghostkiller diagnostic log could not be written.\n')
            except Exception:
                pass


def install(quiet=False, directory=None, worker=False):
    from app_runtime import data_directory
    try:
        directory = Path(directory or data_directory())
        directory.mkdir(parents=True,exist_ok=True)
        probe = directory/('worker_runtime.log' if worker else 'Ghostkiller_Runtime.log')
        with probe.open('a',encoding='utf-8'):
            pass
    except OSError:
        import tempfile
        directory = Path(tempfile.gettempdir())/'GhostkillerSoundToolbox'
        directory.mkdir(parents=True,exist_ok=True)
    filename = f'worker_runtime_{os.getpid()}.log' if worker else f'Ghostkiller_Runtime_{os.getpid()}.log'
    log_path = directory/filename
    handler = SafeRotatingFileHandler(log_path,maxBytes=2*1024**2,backupCount=2,encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    logging.captureWarnings(True)
    if sys.stdout is None:
        sys.stdout = LogStream(logging.INFO)
    if sys.stderr is None:
        sys.stderr = LogStream(logging.ERROR)
    def exception(exc_type, value, tb):
        details = "".join(traceback.format_exception(exc_type,value,tb))
        crash = directory/(f'worker_crash_{os.getpid()}.log' if worker else 'Ghostkiller_CrashLog.txt')
        try:
            if crash.exists() and crash.stat().st_size > 2*1024**2:
                os.replace(crash, crash.with_suffix('.previous.log'))
            with crash.open("a",encoding="utf-8") as stream:
                stream.write(details+"\n")
        except OSError:
            logging.getLogger(__name__).exception("Çökme günlüğü yazılamadı")
        logging.getLogger(__name__).error(details)
        if not quiet and os.name == "nt":
            ctypes.windll.user32.MessageBoxW(None,f"Uygulama başlatılamadı veya beklenmeyen hata oluştu.\n{value}\n\nGünlük: {directory / 'Ghostkiller_CrashLog.txt'}","Ghostkiller Sound Toolbox",0x10)
    sys.excepthook = exception
    threading.excepthook = lambda args: exception(args.exc_type,args.exc_value,args.exc_traceback)
    return log_path


class SingleInstance:
    """Same user/session/data directory shares one GUI, without affecting workers."""
    def __init__(self, directory):
        self.handle = None
        self.existing = False
        if os.name == "nt":
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32",use_last_error=True)
            kernel.CreateMutexW.argtypes = [ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
            kernel.CreateMutexW.restype = wintypes.HANDLE
            identity = os.path.normcase(str(Path(directory).resolve()))
            name = "Local\\GhostkillerSoundToolbox_"+hashlib.sha256(identity.encode("utf-8")).hexdigest()
            self.handle = kernel.CreateMutexW(None,False,name)
            error = ctypes.get_last_error()
            if not self.handle:
                raise ctypes.WinError(error)
            self.existing = error == 183
    def close(self):
        if self.handle:
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32",use_last_error=True)
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            kernel.CloseHandle(self.handle)
            self.handle = None
