"""User-visible output safety, conditional preparation and recovery flows."""
from concurrent.futures import ThreadPoolExecutor
import errno
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import numpy as np
import soundfile as sf
import wx
from app_runtime import JOB_LOCK, download_model
from app_settings import AppSettings
from audio_export import export_audio, publish_directory
from model_manager import ModelManager
from ui_operation import show_result, operation_error

ROOT = Path(__file__).resolve().parents[1]


class Response(io.BytesIO):
    def __init__(self, body, *, status=200, total=None, start=None, etag='"fixture-v1"'):
        super().__init__(body)
        self.status = status
        self.headers = {'Content-Length': str(len(body)), 'ETag': etag}
        if start is not None:
            self.headers['Content-Range'] = f'bytes {start}-{total-1}/{total}'
    def read(self, size=-1):
        return super().read(min(size, 8))


class OutputSafetyTests(unittest.TestCase):
    def test_parallel_exports_number_new_files_and_keep_existing_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root/'source.wav', root/'song.wav'
            sf.write(source, np.full(1600, .25), 16000)
            target.write_bytes(b'previous user result')
            with ThreadPoolExecutor(max_workers=4) as pool:
                outputs = list(pool.map(lambda _: export_audio(source, target, 'wav'), range(8)))
            self.assertEqual(len(set(outputs)), 8)
            self.assertEqual(target.read_bytes(), b'previous user result')
            self.assertEqual({Path(p).name for p in outputs}, {f'song ({n}).wav' for n in range(2,10)})
            self.assertTrue(all(sf.info(p).frames == 1600 for p in outputs))
            self.assertEqual(list(root.glob('audio_export_*')), [])

    def test_numbered_instrument_directories_preserve_previous_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root/'song_Enstrumanlar'
            target.mkdir()
            (target/'bass.flac').write_bytes(b'old result')
            for number in (2,3):
                stage = root/'stage'; stage.mkdir(exist_ok=True)
                (stage/'bass.flac').write_bytes(b'new result')
                path = Path(publish_directory(stage, target))
                self.assertEqual(path.name, f'song_Enstrumanlar ({number})')
                self.assertEqual((path/'bass.flac').read_bytes(), b'new result')
            self.assertEqual((target/'bass.flac').read_bytes(), b'old result')

    def test_result_folder_opens_after_notification_and_failure_keeps_result(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []
            window = SimpleNamespace(LogMessage=Mock())
            with patch.object(wx, 'MessageBox', side_effect=lambda *a, **k: calls.append('message')), \
                 patch.object(wx, 'LaunchDefaultApplication', side_effect=lambda path: calls.append(path) or True):
                show_result(window, 'Tamamlandı', 'Sonuç', wx.OK, folder)
            self.assertEqual(calls, ['message', folder])
            with patch.object(wx, 'MessageBox'), patch.object(wx, 'LaunchDefaultApplication', return_value=False):
                show_result(window, 'Tamamlandı', 'Sonuç', wx.OK, folder)
            self.assertTrue(Path(folder).is_dir())
            self.assertIn('Sonuçlar kaydedildi', window.LogMessage.call_args.args[0])

    def test_common_errors_offer_a_next_action(self):
        self.assertIn('çıktı klasörü', operation_error(PermissionError('denied')))
        self.assertIn('Yer açın', operation_error(OSError(errno.ENOSPC, 'no space')))
        self.assertIn('işlemciyi seç', operation_error(RuntimeError('CUDA out of memory')))


class PreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def tearDown(self):
        if JOB_LOCK.locked():
            JOB_LOCK.release()

    def test_button_tracks_only_the_selected_operation_and_disappears_when_ready(self):
        from ui_separator import SeparatorPanel
        from ui_cover import CoverPanel
        from ui_training import TrainingPanel
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory() as folder:
                manager = ModelManager(folder)
                settings = AppSettings(str(Path(folder)/'settings.json'), manager)
                settings.prepare_models = Mock()
                ready = set()
                with patch.object(manager, 'status', side_effect=lambda key: 'Hazır' if key in ready else 'Eksik'), \
                     patch('ui_cover.load_models', return_value={}):
                    separator = SeparatorPanel(frame, settings)
                    cover = CoverPanel(frame, settings)
                    training = TrainingPanel(frame, settings)
                    for panel in (separator, cover, training):
                        self.assertTrue(panel.preparation.button.IsShown())
                        ready.update(panel.RequiredModels())
                        panel.preparation.RefreshReadiness()
                        self.assertFalse(panel.preparation.button.IsShown())
                    from training.config import TrainingOptions
                    ready.add('training_v2_32k')
                    ready.discard('rmvpe')
                    training.ShowOptions(TrainingOptions(name='Deneme',sources=(),sample_rate=32000,f0_method='crepe'))
                    self.assertFalse(training.preparation.button.IsShown())
                    separator.mode_choice.SetSelection(1)
                    separator.instrument_profile.SetSelection(0)
                    separator.OnMode(None)
                    self.assertTrue(separator.preparation.button.IsShown())
                    separator.preparation.OnPrepare(None)
                    settings.prepare_models.assert_called_once_with(('scnet',))
                    settings.output_format, settings.output_channels, settings.preference = 'mp3','stereo','gpu'
                    separator.preparation.RefreshReadiness()
                    self.assertIn('MP3 · Stereo · Ekran kartı', separator.preparation.summary.GetLabel())
                    JOB_LOCK.acquire()
                    separator.preparation.RefreshReadiness()
                    self.assertFalse(separator.preparation.button.IsEnabled())
        finally:
            frame.Destroy()
            self.app.ProcessPendingEvents()

    def test_prepare_selects_only_missing_models_and_retains_repair_checks(self):
        from ui_settings import SettingsPanel
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory() as folder:
                manager = ModelManager(folder)
                settings = AppSettings(str(Path(folder)/'settings.json'), manager)
                with patch.object(manager, 'status', side_effect=lambda key: 'Hazır' if key == 'rmvpe' else 'Eksik'):
                    panel = SettingsPanel(frame, settings, auto_detect=False)
                    with patch.object(panel, 'OnModels') as start:
                        panel.PrepareRequiredModels(('contentvec','rmvpe'))
                    start.assert_called_once_with('repair')
                    self.assertEqual(panel.model_list.GetCheckedModels(), ['contentvec'])
        finally:
            frame.Destroy()
            self.app.ProcessPendingEvents()

    def test_estimate_discovers_all_selected_assets_without_downloading_weights(self):
        from model_manager import model_catalog
        with tempfile.TemporaryDirectory() as folder:
            manager = ModelManager(folder)
            requests = []
            def head(request, **kwargs):
                requests.append(request)
                self.assertEqual(request.get_method(), 'HEAD')
                return Response(b'12345678')
            with patch('app_runtime.urllib.request.urlopen', side_effect=head):
                total, unknown = manager.download_estimate(tuple(model_catalog()))
            self.assertGreater(len(requests), 13)
            self.assertEqual(total, len(requests) * 8)
            self.assertEqual(unknown, 0)
            self.assertEqual(list(Path(folder).rglob('*.pth')), [])
            self.assertEqual(list(Path(folder).rglob('*.ckpt')), [])

    def test_turkish_decimal_is_passed_to_the_cover_worker(self):
        from ui_cover import CoverPanel
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory() as folder, patch('ui_cover.load_models', return_value={}):
                root = Path(folder)
                settings = AppSettings(str(root/'settings.json'), ModelManager(folder))
                settings.prepare_job = Mock(return_value='cpu')
                panel = CoverPanel(frame, settings)
                panel.models = {'voice': {'pth': 'voice.pth'}}
                panel.UpdateModelCheckList()
                panel.model_list.buttons[0].SetValue(True)
                panel.index_rate_ctrl.SetValue('0,75')
                source = root/'source.wav'; source.touch()
                panel.input_audio_path, panel.output_folder_path = str(source), folder
                with patch('ui_cover.threading.Thread') as worker, patch.object(wx, 'MessageBox') as message:
                    panel.OnStart(None)
                message.assert_not_called()
                self.assertEqual(worker.call_args.kwargs['args'][1]['index_rate'], .75)
        finally:
            frame.Destroy()
            self.app.ProcessPendingEvents()


class ResumableDownloadTests(unittest.TestCase):
    def interrupted(self, target, data):
        stopped = [False]
        def progress(done, total):
            stopped[0] = done >= 8
        with patch('app_runtime.urllib.request.urlopen', return_value=Response(data)), self.assertRaises(InterruptedError):
            download_model('https://example.test/model', str(target), cancelled=lambda: stopped[0], progress=progress)
        self.assertEqual(target.read_bytes(), b'old model')
        partial, = (target.parent/'.downloads').glob('*.part')
        self.assertEqual(partial.read_bytes(), data[:8])

    def test_resume_requests_the_exact_range_and_validates_the_complete_model(self):
        data = b'a complete model with a stable etag'
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'model.pth'; target.write_bytes(b'old model')
            self.interrupted(target, data)
            validate = Mock(side_effect=lambda path: self.assertEqual(Path(path).read_bytes(), data))
            with patch('app_runtime.urllib.request.urlopen', return_value=Response(data[8:], status=206, start=8, total=len(data))) as fetch:
                download_model('https://example.test/model', str(target), validate=validate)
            request = fetch.call_args.args[0]
            self.assertEqual(request.get_header('Range'), 'bytes=8-')
            self.assertEqual(request.get_header('If-range'), '"fixture-v1"')
            validate.assert_called_once()
            self.assertEqual(target.read_bytes(), data)
            self.assertEqual(list((target.parent/'.downloads').glob('*.part')), [])

    def test_server_without_ranges_restarts_and_never_mixes_old_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'model.pth'; target.write_bytes(b'old model')
            self.interrupted(target, b'first remote representation')
            fresh = b'a different complete representation'
            with patch('app_runtime.urllib.request.urlopen', return_value=Response(fresh, etag='"fixture-v2"')):
                download_model('https://example.test/model', str(target))
            self.assertEqual(target.read_bytes(), fresh)

    def test_bad_ranges_and_failed_validation_preserve_the_previous_model(self):
        for scenario in ('range','validator','corrupt'):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as folder:
                target = Path(folder)/'model.pth'; target.write_bytes(b'old model')
                data = b'complete remote model fixture'
                self.interrupted(target, data)
                response = Response(data[8:], status=206, start=8, total=len(data))
                if scenario == 'range': response.headers['Content-Range'] = f'bytes 9-{len(data)-1}/{len(data)}'
                if scenario == 'validator': response.headers['ETag'] = '"changed"'
                validate = Mock(side_effect=ValueError('corrupt')) if scenario == 'corrupt' else None
                with patch('app_runtime.urllib.request.urlopen', return_value=response), self.assertRaises(ValueError):
                    download_model('https://example.test/model', str(target), validate=validate)
                self.assertEqual(target.read_bytes(), b'old model')
                self.assertEqual(list((target.parent/'.downloads').glob('*.part')), [])

    def test_insufficient_disk_space_is_detected_before_writing_the_download(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'model.pth'; target.write_bytes(b'old model')
            response = Response(b'new model')
            with patch('app_runtime.urllib.request.urlopen', return_value=response), \
                 patch('model_download.shutil.disk_usage', return_value=SimpleNamespace(free=0)), \
                 self.assertRaises(OSError) as failure:
                download_model('https://example.test/model', str(target))
            self.assertEqual(failure.exception.errno, errno.ENOSPC)
            self.assertEqual(target.read_bytes(), b'old model')

    def test_expired_range_is_discarded_before_a_fresh_download(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'model.pth'; target.write_bytes(b'old model')
            self.interrupted(target, b'old server representation')
            fresh = b'replacement server representation'
            with patch('app_runtime.urllib.request.urlopen', side_effect=[
                    HTTPError('https://example.test/model',416,'Range expired',{},None),
                    Response(fresh,etag='"replacement"')]) as fetch:
                download_model('https://example.test/model', str(target))
            self.assertEqual(fetch.call_count, 2)
            self.assertIsNone(fetch.call_args.args[0].get_header('Range'))
            self.assertEqual(target.read_bytes(), fresh)

    def test_cancel_during_validation_can_revalidate_complete_cache_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'model.pth'; target.write_bytes(b'old model')
            data = b'fully downloaded fixture'
            with patch('app_runtime.urllib.request.urlopen', return_value=Response(data)), \
                 self.assertRaises(InterruptedError):
                download_model('https://example.test/model',str(target),
                               validate=Mock(side_effect=InterruptedError('cancel validation')))
            self.assertEqual(target.read_bytes(),b'old model')
            validated = Mock(side_effect=lambda path: self.assertEqual(Path(path).read_bytes(),data))
            with patch('app_runtime.urllib.request.urlopen') as fetch:
                download_model('https://example.test/model',str(target),validate=validated)
            fetch.assert_not_called()
            validated.assert_called_once()
            self.assertEqual(target.read_bytes(),data)


if __name__ == '__main__':
    unittest.main()
