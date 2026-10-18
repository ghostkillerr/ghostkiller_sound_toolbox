"""Native singleton and diagnostics before heavy dependencies are loaded."""
import logging
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
import warnings
from startup_diagnostics import SingleInstance,install,LogStream,SafeRotatingFileHandler
ROOT = Path(__file__).resolve().parents[1]


class StartupReleaseTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows file sharing rollback contract')
    def test_log_rollover_failure_does_not_recurse_into_windowed_stderr(self):
        logger = logging.getLogger()
        handlers,level = list(logger.handlers),logger.level
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'locked.log'
            handler = SafeRotatingFileHandler(path,maxBytes=128,backupCount=1,encoding='utf-8')
            try:
                logger.handlers = [handler]
                logger.setLevel(logging.INFO)
                with path.open('a',encoding='utf-8') as held,patch.object(sys,'stderr',LogStream(logging.ERROR)),patch.object(sys,'__stderr__',None):
                    sys.stderr.write('x'*300)
                self.assertTrue(path.exists())
            finally:
                logger.handlers = handlers
                logger.setLevel(level)
                handler.close()

    def test_gui_modules_do_not_import_torch_or_audio_engine(self):
        result = subprocess.run([sys.executable,'-c',
            "import sys; import main,ui_cover,ui_separator,ui_training,ui_settings,ui_live_cover; "
            "assert 'torch' not in sys.modules; assert 'audio_separator.separator' not in sys.modules; "
            "print('GUI imports are independent of motor DLLs')"],cwd=ROOT,
            capture_output=True,text=True,timeout=30,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    @unittest.skipUnless(os.name=='nt','Windows named mutex contract')
    def test_named_mutex_lifetime_and_distinct_data_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            first = SingleInstance(folder)
            second = SingleInstance(folder)
            other = SingleInstance(Path(folder)/'other')
            try:
                self.assertFalse(first.existing)
                self.assertTrue(second.existing)
                self.assertFalse(other.existing)
            finally:
                first.close()
                second.close()
                other.close()
            third = SingleInstance(folder)
            try:
                self.assertFalse(third.existing)
            finally:
                third.close()

    def test_windowed_none_streams_log_import_failure_without_gui_import(self):
        root_logger = logging.getLogger()
        previous_handlers = list(root_logger.handlers)
        previous_level = root_logger.level
        old_hook,old_thread,old_warning = sys.excepthook,threading.excepthook,warnings.showwarning
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder, \
                 patch('app_runtime.data_directory',return_value=folder),patch.object(sys,'stdout',None),patch.object(sys,'stderr',None):
                log_path = install(quiet=True)
                self.assertIsInstance(sys.stdout,LogStream)
                self.assertIsInstance(sys.stderr,LogStream)
                sys.stdout.write('native windowed stdout\n')
                sys.excepthook(ImportError,ImportError('missing backend DLL'),None)
                for handler in root_logger.handlers:
                    handler.flush()
                self.assertIn('missing backend DLL',(Path(folder)/'Ghostkiller_CrashLog.txt').read_text(encoding='utf-8'))
                self.assertIn('native windowed stdout',log_path.read_text(encoding='utf-8'))
                for handler in set(root_logger.handlers)-set(previous_handlers):
                    handler.close()
                    root_logger.removeHandler(handler)
        finally:
            sys.excepthook,threading.excepthook = old_hook,old_thread
            warnings.showwarning = old_warning
            root_logger.setLevel(previous_level)


if __name__=='__main__': unittest.main()
