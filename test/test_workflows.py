"""Regression checks without loading model weights or starting GUI dialogs."""
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import ui_cover
import ui_separator
import updater
from app_runtime import JOB_LOCK, safe_filename
from app_runtime import download_model
import app_runtime
import numpy as np
import soundfile as sf

UPDATE_TEST_URL = 'https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/download/v2.1.0/Ghostkiller_V2_Setup_cpu.exe'


def update_manifest(payload=b'MZtest'):
    import hashlib
    return {'version': '2.1.0', 'backend': 'cpu', 'download_url': UPDATE_TEST_URL,
            'sha256': hashlib.sha256(payload).hexdigest()}


class Harness:
    def __init__(self, root):
        self.output_directory = self.output_folder_path = str(root)
        self.current_input_file = self.input_audio_path = str(root / 'input.wav')
        Path(self.input_audio_path).write_bytes(b'original')
        self.is_cancelled = False
        self.messages = []
        self.statuses = []
        self.enabled = []
        self.app_dir = str(root)

    def LogMessage(self, message):
        self.messages.append(message)

    def UpdateStatus(self, message, percent=None):
        self.statuses.append(message)

    def EnableUI(self, enabled):
        self.enabled.append(enabled)

    def IsBeingDeleted(self):
        return False


class Workflows(unittest.TestCase):
    def test_cancel_during_audio_validation_preserves_outputs_in_both_tabs(self):
        for tab in ('cover', 'separator'):
            with self.subTest(tab=tab), tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
                root = Path(folder)
                job = Harness(root)
                suffix = '_voice.wav' if tab == 'cover' else '_Ghostkiller_1_Ayrilmis_Vokal.flac'
                old = root / ('input' + suffix)
                old.write_bytes(b'previous result')
                def validate_and_cancel(path):
                    app_runtime.validate_audio_file(path)
                    job.is_cancelled = True
                if tab == 'cover':
                    weight = root / 'voice.pth'
                    weight.touch()
                    job.models = {'voice': {'pth': str(weight), 'index': ''}}
                    class Converter:
                        def __init__(self, **kwargs): pass
                        def convert_audio(self, **kwargs):
                            sf.write(kwargs['audio_output_path'], np.full(160, .1), 16000)
                        def cleanup_model(self): pass
                    fake = types.ModuleType('rvc.infer.infer')
                    fake.VoiceConverter = Converter
                    with patch.dict(sys.modules, {'rvc.infer.infer': fake}), patch.object(ui_cover, 'post_ui'), patch.object(ui_cover, 'ensure_rvc_prerequisites'), patch.object(ui_cover, 'validate_audio_file', side_effect=validate_and_cancel):
                        ui_cover.CoverPanel._run_inference_queue(job, ['voice'], {'device': 'cpu', 'pitch': 0, 'index_rate': .75, 'f0_method': 'rmvpe'})
                else:
                    def separate(source, model, label, stage):
                        output = Path(stage) / 'input_(Vocals).flac'
                        sf.write(output, np.full(160, .1), 16000)
                        return [str(output)]
                    job.RunSeparatorCommand = separate
                    JOB_LOCK.acquire()
                    with patch.object(ui_separator, 'post_ui'), patch.object(ui_separator, 'validate_audio_file', side_effect=validate_and_cancel):
                        ui_separator.SeparatorPanel.ProcessChain(job, (False, True, False, False, False))
                self.assertEqual(old.read_bytes(), b'previous result')
                self.assertIn('iptal', job.statuses[-1].lower().replace('\u0307', ''))
                self.assertEqual(list(root.glob('ghostkiller_*')), [])

    def setUp(self):
        self.dispatch = patch.object(ui_cover.wx, 'CallAfter', side_effect=lambda fn, *args: fn(*args))
        self.dispatch.start()

    def tearDown(self):
        self.dispatch.stop()
        if JOB_LOCK.locked():
            JOB_LOCK.release()

    def cover_job(self, root, converter, names=('voice',), settings=None):
        job = Harness(root)
        weight = root / 'voice.pth'
        weight.write_bytes(b'test model')
        job.models = {name: {'pth': str(weight), 'index': ''} for name in names}
        fake = types.ModuleType('rvc.infer.infer')
        fake.VoiceConverter = converter
        options = {'device': 'cpu', 'pitch': 0, 'index_rate': .75, 'f0_method': 'rmvpe'}
        options.update(settings or {})
        with patch.dict(sys.modules, {'rvc.infer.infer': fake}), patch.object(ui_cover, 'post_ui'), patch.object(ui_cover, 'ensure_rvc_prerequisites'):
            ui_cover.CoverPanel._run_inference_queue(job, names, options)
        return job

    def test_large_corrupt_cover_output_is_not_success(self):
        class Converter:
            def __init__(self, **kwargs): pass
            def convert_audio(self, **kwargs):
                Path(kwargs['audio_output_path']).write_bytes(b'garbage' * 100)
            def cleanup_model(self): pass
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            old = root / 'input_voice.wav'
            old.write_bytes(b'previous')
            job = self.cover_job(root, Converter)
            self.assertEqual(old.read_bytes(), b'previous')
            self.assertIn('Başarılı: 0, başarısız: 1', job.statuses[-1])

    def test_cleanup_failure_does_not_abort_remaining_models(self):
        class Converter:
            def __init__(self, **kwargs): pass
            def convert_audio(self, **kwargs):
                sf.write(kwargs['audio_output_path'], np.full(160, .1), 16000)
            def cleanup_model(self):
                raise RuntimeError('cleanup failed')
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            job = self.cover_job(Path(folder), Converter, ('first', 'second'))
            self.assertIn('Başarılı: 2, başarısız: 0', job.statuses[-1])
            self.assertEqual(len([msg for msg in job.messages if 'Model temizliği başarısız' in msg]), 2)

    def test_cancel_during_conversion_preserves_previous_output(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            job = Harness(root)
            weight = root / 'voice.pth'
            weight.touch()
            job.models = {'voice': {'pth': str(weight)}}
            old = root / 'input_voice.wav'
            old.write_bytes(b'previous')
            class Converter:
                def __init__(self, **kwargs): pass
                def convert_audio(self, **kwargs):
                    sf.write(kwargs['audio_output_path'], np.ones(160), 16000)
                    job.is_cancelled = True
                def cleanup_model(self): pass
            fake = types.ModuleType('rvc.infer.infer')
            fake.VoiceConverter = Converter
            with patch.dict(sys.modules, {'rvc.infer.infer': fake}), patch.object(ui_cover, 'post_ui'), patch.object(ui_cover, 'ensure_rvc_prerequisites'):
                ui_cover.CoverPanel._run_inference_queue(job, ['voice'], {'device': 'cpu', 'pitch': 0, 'index_rate': .75, 'f0_method': 'rmvpe'})
            self.assertEqual(old.read_bytes(), b'previous')
            self.assertIn('İptal', job.statuses[-1])

    def test_missing_voice_model_does_not_download_prerequisites(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_cover, 'post_ui'), patch.object(ui_cover, 'ensure_rvc_prerequisites') as prepare:
            job = Harness(Path(folder))
            job.models = {'missing': {'pth': 'missing.pth'}}
            ui_cover.CoverPanel._run_inference_queue(job, ['missing'], {'device': 'cpu', 'f0_method': 'rmvpe'})
            prepare.assert_not_called()
            self.assertIn('başarısız: 1', job.statuses[-1])

    def test_ambiguous_model_basename_requires_explicit_path(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            for name in ('one', 'two'):
                directory = Path(folder) / 'modeller' / name
                directory.mkdir(parents=True)
                (directory / 'voice.pth').touch()
            with self.assertRaisesRegex(ValueError, 'birden fazla'):
                ui_cover.resolve_model_file_path(folder, 'old/voice.pth')
            exact = Path(folder) / 'modeller' / 'one' / 'voice.pth'
            self.assertEqual(ui_cover.resolve_model_file_path(folder, str(exact)), str(exact))

    def test_registry_path_failure_is_reported_without_crashing(self):
        with patch.object(ui_cover, 'get_models_file_path', side_effect=PermissionError('read only')), patch.object(ui_cover.wx, 'MessageBox') as message:
            self.assertEqual(ui_cover.load_models('unused'), {})
            self.assertFalse(ui_cover.save_models('unused', {}))
            self.assertEqual(message.call_count, 2)

    def test_frozen_separation_uses_install_models_and_reuses_portable_model(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            app = root / 'program'
            (app / 'modeller').mkdir(parents=True)
            (app / 'modeller' / 'model.ckpt').write_bytes(b'weights')
            (app / 'modeller' / 'config.yaml').write_text('config')
            (app / 'modeller' / 'empty.json').touch()
            with patch.object(sys, 'frozen', True, create=True):
                target = ui_separator.get_model_directory(str(app))
                self.assertEqual(target, str(app / 'models'))
                ui_separator.prepare_separator_model(str(app), target, 'model.ckpt')
            self.assertEqual((app / 'models' / 'model.ckpt').read_bytes(), b'weights')
            self.assertTrue((app / 'models' / 'config.yaml').exists())
            self.assertFalse((app / 'models' / 'empty.json').exists())

    def test_failed_cache_copy_preserves_target(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            target = root / 'model.pt'
            target.write_bytes(b'previous')
            def partial(source, temporary):
                Path(temporary).write_bytes(b'partial')
                raise OSError('disk full')
            with patch('shutil.copyfile', side_effect=partial), self.assertRaises(OSError):
                app_runtime.copy_model('unused', str(target))
            self.assertEqual(target.read_bytes(), b'previous')
            self.assertEqual(list(root.glob('*.part')), [])

    def test_job_lock_waits_for_final_ui_callback(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_cover, 'post_ui'), patch.object(ui_cover.wx, 'CallAfter') as dispatch:
            job = Harness(Path(folder))
            job._run_inference_queue = lambda *args: None
            JOB_LOCK.acquire()
            ui_cover.CoverPanel.run_inference_queue(job, [], {})
            self.assertTrue(JOB_LOCK.locked())
            dispatch.call_args.args[0]()
            self.assertFalse(JOB_LOCK.locked())
            self.assertTrue(job.enabled[-1])

    def test_corrupt_separation_output_preserves_previous_result(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_separator, 'post_ui'):
            root = Path(folder)
            job = Harness(root)
            destination = root / 'input_Ghostkiller_1_Ayrilmis_Vokal.flac'
            destination.write_bytes(b'previous')
            def separate(source, model, label, directory):
                bad = Path(directory) / 'input_(Vocals).flac'
                bad.write_bytes(b'corrupt' * 100)
                return [str(bad)]
            job.RunSeparatorCommand = separate
            JOB_LOCK.acquire()
            ui_separator.SeparatorPanel.ProcessChain(job, (False, True, False, False, False))
            self.assertEqual(destination.read_bytes(), b'previous')
            self.assertIn('başarısız', job.statuses[-1])

    def test_instrumental_branch_does_not_feed_vocal_chain(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_separator, 'post_ui'):
            root = Path(folder)
            job = Harness(root)
            sources = []
            def separate(source, model, label, directory):
                sources.append(source)
                stem = '(Instrumental)' if 'inst_v2' in model else '(Vocals)'
                output = Path(directory) / f'input_{stem}.flac'
                sf.write(output, np.ones(160), 16000)
                return [str(output)]
            job.RunSeparatorCommand = separate
            JOB_LOCK.acquire()
            ui_separator.SeparatorPanel.ProcessChain(job, (True, True, True, False, False))
            self.assertEqual(sources[:2], [job.current_input_file] * 2)
            self.assertTrue(sources[2].endswith('input_Ghostkiller_1_Ayrilmis_Vokal.flac'))

    def test_nan_audio_and_reserved_filenames(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path = Path(folder) / 'nan.wav'
            sf.write(path, [np.nan], 16000, subtype='FLOAT')
            with self.assertRaises(ValueError):
                app_runtime.validate_audio_file(path)
        self.assertEqual(safe_filename('CON.txt'), '_CON.txt')
        self.assertFalse(safe_filename('a' * 119 + ' .' + 'b').endswith(' '))

    def test_unknown_length_update_can_cancel_during_download(self):
        import io
        class Progress:
            def IsBeingDeleted(self): return False
            def Pulse(self, *args): return False, False
            def Update(self, *args): return True, False
            def Destroy(self): pass
        class Thread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            response = io.BytesIO(b'MZ' + b'x' * 30000)
            response.headers = {}
            response.geturl = lambda: UPDATE_TEST_URL
            # BytesIO closes on context exit; record the amount consumed before closing.
            positions = []
            real_read = response.read
            def read(size=-1):
                result = real_read(size)
                positions.append(response.tell())
                return result
            response.read = read
            with patch.object(updater.tempfile, 'mkdtemp', return_value=folder), patch.object(updater.wx, 'ProgressDialog', return_value=Progress()), patch.object(updater.threading, 'Thread', Thread), patch.object(updater.urllib.request, 'urlopen', return_value=response), patch.object(updater, '_launch_setup_and_exit') as launch:
                updater._download_and_run_installer(Harness(Path(folder)), update_manifest(b'MZ' + b'x' * 30000), backend='cpu')
            launch.assert_not_called()
            self.assertEqual(positions, [8192])
            self.assertFalse(JOB_LOCK.locked())

    def test_malformed_update_manifest_is_not_reported_as_current(self):
        import io
        class Thread:
            def __init__(self, target, **kwargs): self.target = target
            def start(self): self.target()
        for body in (b'{}', b'{"version":"broken"}', b'[]'):
            response = io.BytesIO(body)
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(updater.threading, 'Thread', Thread), patch.object(updater.urllib.request, 'urlopen', return_value=response), patch.object(updater.wx, 'MessageBox') as message:
                updater.check_for_updates(Harness(Path(folder)))
                self.assertIn('kontrol edilemedi', message.call_args.args[0])
                self.assertFalse(updater.CHECK_LOCK.locked())

    def test_version_trailing_zeroes_do_not_trigger_update(self):
        self.assertEqual(updater.parse_version('2.0.0.0'), updater.parse_version('2.0'))

    def test_model_download_cancel_keeps_target(self):
        import io
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            target = Path(folder) / 'model.pt'
            target.write_bytes(b'previous')
            response = io.BytesIO(b'new')
            response.headers = {}
            with patch('app_runtime.urllib.request.urlopen', return_value=response), self.assertRaises(InterruptedError):
                download_model('https://example.test/model', str(target), cancelled=lambda: True)
            self.assertEqual(target.read_bytes(), b'previous')

    def test_input_stem_label_does_not_confuse_output_selection(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_separator, 'post_ui'):
            root = Path(folder)
            job = Harness(root)
            job.current_input_file = str(root / 'song_(Vocals).wav')
            Path(job.current_input_file).write_bytes(b'original')
            def separate(source, model, label, directory):
                outputs = []
                for stem, value in (('Vocals', .2), ('Instrumental', .8)):
                    output = Path(directory) / f'song_(Vocals)_({stem})_model.flac'
                    sf.write(output, np.full(160, value), 16000)
                    outputs.append(str(output))
                return outputs
            job.RunSeparatorCommand = separate
            JOB_LOCK.acquire()
            ui_separator.SeparatorPanel.ProcessChain(job, (False, True, False, False, False))
            result, _ = sf.read(root / 'song_(Vocals)_Ghostkiller_1_Ayrilmis_Vokal.flac')
            np.testing.assert_allclose(result, .2, atol=1e-4)

    def test_output_hardlink_to_input_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_separator, 'post_ui'):
            root = Path(folder)
            job = Harness(root)
            destination = root / 'input_Ghostkiller_1_Ayrilmis_Vokal.flac'
            destination.write_bytes(b'original')
            # Windows sandbox denies creating hard links; simulate the filesystem identity query.
            def separate(source, model, label, directory):
                output = Path(directory) / 'input_(Vocals).flac'
                sf.write(output, np.ones(160), 16000)
                return [str(output)]
            job.RunSeparatorCommand = separate
            JOB_LOCK.acquire()
            with patch.object(app_runtime.os.path, 'samefile', return_value=True):
                ui_separator.SeparatorPanel.ProcessChain(job, (False, True, False, False, False))
            self.assertEqual(Path(job.current_input_file).read_bytes(), b'original')
            self.assertEqual(destination.read_bytes(), b'original')
            self.assertIn('başarısız', job.statuses[-1])

    def test_frozen_model_root_is_beside_exe_not_internal_resources(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(Path(folder) / 'tool.exe')), patch.object(sys, '_MEIPASS', str(Path(folder) / '_internal'), create=True):
            self.assertEqual(app_runtime.model_directory(), str(Path(folder) / 'models'))
            self.assertEqual(app_runtime.resource_directory(), str(Path(folder) / '_internal'))

    def test_legacy_download_api_delegates_to_pinned_model_manager(self):
        with patch('model_manager.ModelManager') as manager:
            manager.return_value.process.return_value = {}
            ui_cover.ensure_rvc_prerequisites('application', allow_download=True)
            manager.assert_called_once_with('application')
            manager.return_value.process.assert_called_once_with(
                ['contentvec','rmvpe'], 'install', cancelled=None, log=None)

    def test_crash_log_write_error_does_not_hide_error_dialog(self):
        import main
        with patch.object(main, 'data_directory', side_effect=PermissionError('read only')), patch.object(main.wx, 'MessageBox') as message, patch.object(main.sys, '__excepthook__'):
            main.global_exception_handler(ValueError, ValueError('original error'), None)
            self.assertIn('original error', message.call_args.args[0])
            self.assertIn('kaydedilemedi', message.call_args.args[0])

    def test_update_thread_start_failure_releases_lock_and_cleans_temp(self):
        class Progress:
            def IsBeingDeleted(self): return False
            def Update(self, *args): return True, False
            def Destroy(self): pass
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(updater.tempfile, 'mkdtemp', return_value=folder), patch.object(updater.wx, 'ProgressDialog', return_value=Progress()), patch.object(updater.threading, 'Thread', side_effect=RuntimeError('thread unavailable')), patch.object(updater.wx, 'MessageBox') as message:
            parent = Harness(Path(folder))
            updater._download_and_run_installer(parent, update_manifest(), backend='cpu')
            self.assertFalse(JOB_LOCK.locked())
            self.assertFalse(Path(folder).exists())
            self.assertIn('thread unavailable', message.call_args.args[0])

    def test_parallel_update_checks_do_not_start_multiple_workers(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(updater.threading, 'Thread') as thread:
            parent = Harness(Path(folder))
            try:
                updater.check_for_updates(parent)
                updater.check_for_updates(parent)
                self.assertEqual(thread.call_count, 1)
            finally:
                updater.CHECK_LOCK.release()

    def test_separation_repeated_runs_preserve_unrelated_files(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_separator, 'post_ui'):
            root = Path(folder)
            job = Harness(root)
            unrelated = root / 'keep.txt'
            unrelated.write_text('keep')
            def separate(source, model, step, directory):
                output = Path(directory) / 'input_(Vocals).flac'
                sf.write(output, np.full(160, .2), 16000)
                (root / 'concurrent.txt').write_text('another job')
                return [str(output)]
            job.RunSeparatorCommand = separate
            for _ in range(2):
                JOB_LOCK.acquire()
                ui_separator.SeparatorPanel.ProcessChain(job, (False, True, False, False, False))
                self.assertFalse(JOB_LOCK.locked())
            self.assertEqual(unrelated.read_text(), 'keep')
            self.assertTrue((root / 'concurrent.txt').exists())
            audio, rate = sf.read(root / 'input_Ghostkiller_1_Ayrilmis_Vokal.flac')
            self.assertEqual(rate, 16000)
            np.testing.assert_allclose(audio, .2, atol=1e-4)
            self.assertEqual(list(root.glob('ghostkiller_*')), [])

    def test_separation_failure_is_not_success_and_releases_lock(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_separator, 'post_ui'):
            job = Harness(Path(folder))
            job.RunSeparatorCommand = lambda *args: False
            JOB_LOCK.acquire()
            ui_separator.SeparatorPanel.ProcessChain(job, (False, True, False, False, False))
            self.assertIn('başarısız', job.statuses[-1])
            self.assertFalse(JOB_LOCK.locked())
            self.assertTrue(job.enabled[-1])

    def test_separation_cancel_keeps_existing_output(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_separator, 'post_ui'):
            root = Path(folder)
            job = Harness(root)
            old = root / 'input_Ghostkiller_1_Ayrilmis_Vokal.flac'
            old.write_bytes(b'old')
            def separate(*args):
                job.is_cancelled = True
                return False
            job.RunSeparatorCommand = separate
            JOB_LOCK.acquire()
            ui_separator.SeparatorPanel.ProcessChain(job, (False, True, False, False, False))
            self.assertEqual(old.read_bytes(), b'old')
            self.assertIn('iptal', job.statuses[-1])

    def test_cover_failure_preserves_old_output_and_counts_failure(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            job = Harness(root)
            weight = root / 'voice.pth'
            weight.write_bytes(b'test')
            job.models = {'voice': {'pth': str(weight), 'index': ''}}
            old = root / 'input_voice.wav'
            old.write_bytes(b'previous good result')
            devices = []
            class Converter:
                def __init__(self, device):
                    devices.append(device)
                def convert_audio(self, **kwargs):
                    Path(kwargs['audio_output_path']).write_bytes(b'partial')
                    raise RuntimeError('test error')
                def cleanup_model(self):
                    pass
            fake = types.ModuleType('rvc.infer.infer')
            fake.VoiceConverter = Converter
            with patch.dict(sys.modules, {'rvc.infer.infer': fake}), patch.object(ui_cover, 'post_ui'), patch.object(ui_cover, 'ensure_rvc_prerequisites'):
                ui_cover.CoverPanel._run_inference_queue(job, ['voice'], {'device': 'cpu', 'pitch': 0, 'index_rate': .75, 'f0_method': 'rmvpe'})
            self.assertEqual(devices, ['cpu'])
            self.assertEqual(old.read_bytes(), b'previous good result')
            self.assertIn('başarısız: 1', job.statuses[-1])
            self.assertEqual(sorted(path.name for path in root.glob('*.wav')), ['input.wav', 'input_voice.wav'])

    def test_cover_outer_failure_releases_lock(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_cover, 'post_ui'):
            job = Harness(Path(folder))
            job._run_inference_queue = lambda *args: (_ for _ in ()).throw(OSError('cannot write'))
            JOB_LOCK.acquire()
            ui_cover.CoverPanel.run_inference_queue(job, [], {})
            self.assertFalse(JOB_LOCK.locked())
            self.assertTrue(job.enabled[-1])
            self.assertIn('başarısız', job.statuses[-1])

    def test_registry_atomic_write_and_corrupt_file_preservation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_cover.wx, 'MessageBox'):
            registry = Path(folder) / 'models.json'
            data = {'voice': {'pth': 'voice.pth', 'index': ''}}
            self.assertTrue(ui_cover.save_models(folder, data))
            self.assertEqual(ui_cover.load_models(folder), data)
            registry.write_text('{broken', encoding='utf-8')
            self.assertFalse(ui_cover.save_models(folder, data))
            self.assertEqual(registry.read_text(), '{broken')
            self.assertEqual(ui_cover.load_models(folder), {})

    def test_relative_model_path_independent_of_cwd(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path = Path(folder) / 'voice.pth'
            path.touch()
            self.assertEqual(ui_cover.resolve_model_file_path(folder, 'voice.pth'), str(path))

    def test_version_normalization_and_filename(self):
        self.assertEqual(updater.parse_version('v2.0'), updater.parse_version('2.0.0'))
        self.assertEqual(updater.parse_version('-1.2'), (0, 0, 0))
        self.assertNotIn('/', safe_filename('voice/name:invalid'))

    def test_semantically_invalid_registry_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_cover.wx, 'MessageBox'):
            registry = Path(folder) / 'models.json'
            registry.write_text('{"bad": 42}', encoding='utf-8')
            self.assertFalse(ui_cover.save_models(folder, {}))
            self.assertEqual(registry.read_text(), '{"bad": 42}')

    def test_pitch_smoothing_does_not_cross_silent_boundary(self):
        import numpy as np
        from rvc.infer.f0_utils import smooth_f0
        pitch = np.r_[np.full(14, 100.), np.zeros(4), np.full(14, 300.)]
        result = smooth_f0(pitch)
        np.testing.assert_allclose(result[:14], 100.)
        np.testing.assert_array_equal(result[14:18], 0.)
        np.testing.assert_allclose(result[18:], 300.)

    def test_separation_rejects_output_outside_owned_directory(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            job = Harness(root)
            job.model_dir = folder
            external = root / 'external_(Vocals).flac'
            external.write_bytes(b'keep')
            class Separator:
                def __init__(self, **kwargs):
                    pass
                def load_model(self, **kwargs):
                    pass
                def separate(self, source):
                    return [str(external)]
            with tempfile.TemporaryDirectory(dir=root) as stage, patch.object(ui_separator, 'Separator', Separator):
                result = ui_separator.SeparatorPanel.RunSeparatorCommand(job, job.input_audio_path, 'model', 'test', stage)
            self.assertFalse(result)
            self.assertEqual(external.read_bytes(), b'keep')

    def test_incomplete_model_download_preserves_existing_file(self):
        import io
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            target = Path(folder) / 'model.pt'
            target.write_bytes(b'old model')
            response = io.BytesIO(b'partial')
            response.headers = {'Content-Length': '100'}
            with patch('app_runtime.urllib.request.urlopen', return_value=response):
                with self.assertRaises(RuntimeError):
                    download_model('https://example.test/model', str(target))
            self.assertEqual(target.read_bytes(), b'old model')
            self.assertEqual(list(Path(folder).glob('*.part')), [])

    def test_cancelled_update_does_not_launch_installer(self):
        import io
        class Progress:
            def IsBeingDeleted(self):
                return False
            def Update(self, *args):
                return False, False
            def Destroy(self):
                pass
        class Parent:
            def IsBeingDeleted(self):
                return False
        class Thread:
            def __init__(self, target, **kwargs):
                self.target = target
            def start(self):
                self.target()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            response = io.BytesIO(b'MZ' + b'x' * 100)
            response.headers = {'Content-Length': '102'}
            response.geturl = lambda: UPDATE_TEST_URL
            with patch.object(updater.tempfile, 'mkdtemp', return_value=folder), patch.object(updater.wx, 'ProgressDialog', return_value=Progress()), patch.object(updater.wx, 'CallAfter', side_effect=lambda fn, *args: fn(*args)), patch.object(updater.threading, 'Thread', Thread), patch.object(updater.urllib.request, 'urlopen', return_value=response), patch.object(updater, '_launch_setup_and_exit') as launch:
                updater._download_and_run_installer(Parent(), update_manifest(b'MZ' + b'x' * 100), backend='cpu')
            launch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
