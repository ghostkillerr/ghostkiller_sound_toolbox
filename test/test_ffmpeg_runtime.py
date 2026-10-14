"""Upgrades must use the bundled codecs even with old EXEs in cwd/PATH."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import app_runtime


class CodecPathTests(unittest.TestCase):
    def test_frozen_uses_internal_and_pins_pydub_despite_legacy_codecs(self):
        import pydub
        old_converter, old_prober = pydub.AudioSegment.converter, pydub.utils.get_prober_name
        try:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                internal = root/'_internal'
                internal.mkdir()
                for name in ('ffmpeg.exe', 'ffprobe.exe'):
                    (root/name).write_bytes(b'legacy fixture')
                    (internal/name).write_bytes(b'packaged fixture')
                with patch.object(sys, 'frozen', True, create=True), \
                     patch.object(sys, '_MEIPASS', str(internal), create=True), \
                     patch.dict(os.environ, {'PATH':str(root)}):
                    app_runtime.configure_ffmpeg_environment()
                    app_runtime.configure_pydub()
                    self.assertEqual(app_runtime.ffmpeg_executable(), str(internal/'ffmpeg.exe'))
                    self.assertEqual(pydub.AudioSegment.converter, str(internal/'ffmpeg.exe'))
                    self.assertEqual(pydub.utils.get_prober_name(), str(internal/'ffprobe.exe'))
                    self.assertEqual(os.environ['PATH'].split(os.pathsep)[0], str(internal))
        finally:
            pydub.AudioSegment.converter, pydub.utils.get_prober_name = old_converter, old_prober

    def test_missing_packaged_codec_cannot_fall_back_to_legacy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'ffmpeg.exe').write_bytes(b'legacy fixture')
            with patch.object(sys, 'frozen', True, create=True), \
                 patch.object(sys, '_MEIPASS', str(root/'_internal'), create=True):
                with self.assertRaises(FileNotFoundError):
                    app_runtime.ffmpeg_executable()

    def test_source_codec_comes_from_tools_and_environment_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            codecs = root/'tools/ffmpeg'
            codecs.mkdir(parents=True)
            (codecs/'ffmpeg.exe').write_bytes(b'source fixture')
            with patch.object(sys, 'frozen', False, create=True), patch.dict(os.environ, {'PATH':str(root)}):
                self.assertEqual(app_runtime.ffmpeg_executable(app_dir=str(root)),str(codecs/'ffmpeg.exe'))
                app_runtime.configure_ffmpeg_environment(str(root))
                first = os.environ['PATH']
                app_runtime.configure_ffmpeg_environment(str(root))
                self.assertEqual(os.environ['PATH'],first)

    def test_separator_version_check_uses_absolute_packaged_codec(self):
        from separator_backend import LocalSeparator
        from types import SimpleNamespace
        from unittest.mock import Mock
        with patch('app_runtime.ffmpeg_executable', return_value='C:/bundle/_internal/ffmpeg.exe'), \
             patch('app_runtime.configure_pydub'), \
             patch('subprocess.check_output',return_value='ffmpeg version fixture\n') as execute:
            LocalSeparator.check_ffmpeg_installed(SimpleNamespace(logger=Mock()))
            self.assertEqual(execute.call_args.args[0][0],'C:/bundle/_internal/ffmpeg.exe')

    def test_missing_codec_does_not_prevent_gui_settings_from_opening(self):
        from ui_separator import setup_ffmpeg_paths
        with patch('app_runtime.configure_ffmpeg_environment'), \
             patch('app_runtime.configure_pydub',side_effect=FileNotFoundError('packaged codec missing')):
            setup_ffmpeg_paths('C:/bundle')
