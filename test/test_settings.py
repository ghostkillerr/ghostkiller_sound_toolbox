"""Hardware and model-maintenance scenarios with small real PyTorch checkpoints."""
import io
import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

import torch
import wx
import app_runtime
import hardware
from app_settings import AppSettings
from hardware import DeviceSupport, HardwareReport
from model_manager import ModelManager, file_digest, validate_file, default_model_selection
from separator_backend import LocalSeparator
from ui_settings import SettingsPanel
import ui_cover
import ui_separator

ROOT = Path(__file__).resolve().parents[1]


def checkpoint_bytes():
    stream = io.BytesIO()
    torch.save({'weight': torch.ones(2, 3)}, stream)
    return stream.getvalue()


class Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {'Content-Length': str(len(data))}


class SettingsTests(unittest.TestCase):
    def test_uvr_band_stages_accept_real_layout_and_reject_missing_groups(self):
        from model_manager import validate_weight_schema
        from audio_separator.separator.uvr_lib_v5.vr_network.nets_new import CascadedNet
        with torch.device('meta'):
            weights = CascadedNet(1344,218409,nout=64,nout_lstm=128).state_dict()
        for relative in ('UVR-DeNoise.pth', 'UVR-DeEcho-DeReverb.pth'):
            validate_weight_schema(weights, relative)
            for key in ('out.weight','aux_out.weight','stg3_full_band_net.lstm_dec2.dense.0.weight',next(iter(weights))):
                with self.subTest(relative=relative, missing=key), self.assertRaises(ValueError):
                    validate_weight_schema({name: tensor for name, tensor in weights.items() if name != key}, relative)

    def test_missing_separator_backend_keeps_catalog_and_panels_available(self):
        import importlib.util
        import sys
        from model_manager import model_catalog
        spec = importlib.util.spec_from_file_location('separator_without_backend', ROOT / 'ui_separator.py')
        module = importlib.util.module_from_spec(spec)
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with patch.dict(sys.modules, {'separator_backend': None}), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                spec.loader.exec_module(module)
                self.assertIsNone(module.Separator)
                self.assertEqual(len(model_catalog()), 11)
                settings = AppSettings(str(Path(folder) / 'settings.json'), ModelManager(folder))
                panel = module.SeparatorPanel(frame, settings)
                maintenance = SettingsPanel(frame, settings, auto_detect=False)
                self.assertEqual(len(maintenance.model_list.buttons), 11)
                with patch.object(panel, 'LogMessage') as log:
                    self.assertFalse(panel.RunSeparatorCommand('unused', 'unused', 'test', folder))
                    self.assertIn('audio-separator', log.call_args.args[0])
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_unrelated_metadata_and_weights_are_rejected_before_first_record(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / 'config.json'
            path.write_text('{"unrelated": true}')
            with self.assertRaisesRegex(ValueError, 'ContentVec'):
                validate_file(path, 'embedders/contentvec/config.json')
            path.write_text('model: {dim: 8}')
            with self.assertRaisesRegex(ValueError, 'audio'):
                validate_file(path, 'roformer.yaml')
            path = Path(folder) / 'model.pt'
            torch.save({'unrelated': torch.ones(2, 3)}, path)
            for relative in ('predictors/rmvpe.pt', 'UVR-DeNoise.pth', 'example.ckpt'):
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    validate_file(path, relative)
            manager = ModelManager(folder)
            target = Path(manager.path('predictors/rmvpe.pt'))
            target.parent.mkdir(parents=True)
            target.write_bytes(path.read_bytes())
            with patch.object(app_runtime.urllib.request, 'urlopen', side_effect=AssertionError('network forbidden')):
                self.assertIn('rmvpe', manager.process(['rmvpe'], 'verify'))
            self.assertNotEqual(manager.status('rmvpe'), 'Hazır')

    def test_helper_weight_shapes_match_their_networks(self):
        from model_manager import validate_weight_schema
        from rvc.lib.predictors.RMVPE import E2E
        from rvc.lib.utils import HubertModelWithFinalProj
        from transformers import HubertConfig
        config = {'model_type': 'hubert', 'hidden_size': 8, 'intermediate_size': 16,
                  'num_hidden_layers': 1, 'num_attention_heads': 2, 'classifier_proj_size': 4,
                  'conv_dim': [4], 'conv_kernel': [3], 'conv_stride': [2],
                  'num_conv_pos_embedding_groups': 2, 'num_conv_pos_embeddings': 4}
        with torch.device('meta'):
            rmvpe = E2E(4, 1, (2, 2)).state_dict()
            contentvec = HubertModelWithFinalProj(HubertConfig(**config)).state_dict()
        for relative, weights, metadata in (('predictors/rmvpe.pt', rmvpe, None),
                                            ('embedders/contentvec/pytorch_model.bin', contentvec, config)):
            with self.subTest(relative=relative):
                validate_weight_schema(weights, relative, metadata)
                broken = dict(weights)
                key = next(iter(broken))
                broken[key] = torch.empty(0)
                with self.assertRaisesRegex(ValueError, 'uyumsuz'):
                    validate_weight_schema(broken, relative, metadata)
                del broken[key]
                with self.assertRaisesRegex(ValueError, 'eksik'):
                    validate_weight_schema(broken, relative, metadata)

    def test_old_integrity_records_require_schema_reverification(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            manager = ModelManager(folder)
            target = Path(manager.path('predictors/rmvpe.pt'))
            target.parent.mkdir(parents=True)
            target.write_bytes(checkpoint_bytes())
            stat = target.stat()
            manager.records['rmvpe'] = {'files': {'predictors/rmvpe.pt': {
                'sha256': file_digest(target), 'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns}}}
            self.assertIn('şeması', manager.status('rmvpe'))

    def test_frozen_numba_cache_uses_user_data_before_motor_import(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(app_runtime, 'data_directory', return_value=folder), patch.object(app_runtime.sys, 'frozen', True, create=True), patch.dict(os.environ):
            os.environ.pop('NUMBA_CACHE_DIR', None)
            app_runtime.configure_runtime_cache()
            self.assertEqual(os.environ['NUMBA_CACHE_DIR'], str(Path(folder) / 'cache' / 'numba'))
            self.assertTrue(Path(os.environ['NUMBA_CACHE_DIR']).is_dir())

    def test_cpu_and_gpu_choices_use_supported_backend_and_largest_usable_gpu(self):
        for name in ('AMD Ryzen', 'Intel Core'):
            report = HardwareReport(DeviceSupport('cpu', name, True), [
                DeviceSupport('cuda:0', 'NVIDIA', True, memory_gb=8),
                DeviceSupport('cuda:1', 'AMD ROCm', True, memory_gb=16, backend='ROCm'),
                DeviceSupport('cuda:2', 'Broken', False, memory_gb=24),
            ])
            self.assertEqual(report.selected('cpu').device, 'cpu')
            self.assertEqual(report.selected('gpu').device, 'cuda:1')
        with self.assertRaisesRegex(RuntimeError, 'İşlemci'):
            HardwareReport(DeviceSupport('cpu', 'CPU', True)).selected('gpu')

    def test_hardware_probe_rejects_failed_kernel_and_keeps_other_card(self):
        def probe(device):
            if device == 'cuda:0':
                raise RuntimeError('unsupported kernel')
        with patch.object(hardware, 'windows_cards', return_value=['Two GPUs']), patch.object(hardware, 'probe_operations', side_effect=probe), patch.object(torch.cuda, 'is_available', return_value=True), patch.object(torch.cuda, 'device_count', return_value=2), patch.object(torch.cuda, 'get_device_name', side_effect=lambda index: f'card{index}'), patch.object(torch.cuda, 'get_device_properties', return_value=SimpleNamespace(total_memory=8 * 1024 ** 3)), patch.object(torch.cuda, 'device', return_value=nullcontext()), patch.object(torch.cuda, 'empty_cache'):
            report = hardware.detect_hardware()
        self.assertFalse(report.gpus[0].available)
        self.assertIn('unsupported kernel', report.gpus[0].reason)
        self.assertEqual(report.selected('gpu').device, 'cuda:1')

    def test_preference_persists_and_failed_save_keeps_current_value(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            settings = AppSettings(str(root / 'settings.json'), ModelManager(folder))
            settings.report = HardwareReport(DeviceSupport('cpu', 'CPU', True), [DeviceSupport('cuda:0', 'GPU', True)])
            settings.select('gpu')
            self.assertEqual(AppSettings(settings.path, settings.manager).preference, 'gpu')
            with patch('app_settings.os.replace', side_effect=PermissionError('read only')), self.assertRaises(PermissionError):
                settings.select('cpu')
            self.assertEqual(settings.preference, 'gpu')
            self.assertEqual(list(root.glob('*.part')), [])

    def test_bad_settings_and_integrity_record_require_reverification(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            (root / 'settings.json').write_text('[]')
            (root / 'models').mkdir()
            (root / 'models' / '.integrity.json').write_text('[]')
            manager = ModelManager(folder)
            settings = AppSettings(str(root / 'settings.json'), manager)
            self.assertEqual(settings.preference, 'cpu')
            self.assertTrue(settings.error)
            self.assertTrue(manager.warning)

    @patch('model_manager.PUBLISHED_ASSET_HASHES', new={})
    @patch('model_manager.validate_weight_schema', new=lambda *args: None)
    def test_model_install_verify_corruption_and_repair_are_offline_except_download(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            manager = ModelManager(folder)
            weights = checkpoint_bytes()
            with patch.object(app_runtime.urllib.request, 'urlopen', side_effect=lambda url, **kwargs: Response(weights)) as fetch:
                self.assertEqual(manager.process(['rmvpe'], 'install'), {})
                self.assertEqual(fetch.call_count, 1)
            self.assertEqual(manager.status('rmvpe'), 'Hazır')
            path = Path(manager.path('predictors/rmvpe.pt'))
            original = file_digest(path)
            with patch.object(app_runtime.urllib.request, 'urlopen', side_effect=AssertionError('network forbidden')):
                self.assertEqual(manager.process(['rmvpe'], 'verify'), {})
            path.write_bytes(b'broken model')
            self.assertNotEqual(manager.status('rmvpe'), 'Hazır')
            with patch.object(app_runtime.urllib.request, 'urlopen') as fetch:
                self.assertIn('rmvpe', manager.process(['rmvpe'], 'verify'))
                self.assertIn('rmvpe', manager.process(['rmvpe'], 'install'))
                fetch.assert_not_called()
            with patch.object(app_runtime.urllib.request, 'urlopen', return_value=Response(weights)):
                self.assertEqual(manager.process(['rmvpe'], 'repair'), {})
            self.assertEqual(manager.status('rmvpe'), 'Hazır')
            self.assertEqual(file_digest(path), original)
            self.assertEqual(ModelManager(folder).status('rmvpe'), 'Hazır')

    @patch('model_manager.PUBLISHED_ASSET_HASHES', new={})
    @patch('model_manager.validate_weight_schema', new=lambda *args: None)
    def test_changed_weight_with_preserved_file_stat_is_detected_by_sha256(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            manager = ModelManager(folder)
            with patch.object(app_runtime.urllib.request, 'urlopen', return_value=Response(checkpoint_bytes())):
                manager.process(['rmvpe'], 'install')
            path = Path(manager.path('predictors/rmvpe.pt'))
            stat = path.stat()
            # A valid but different tensor file must fail even if its timestamp is restored.
            torch.save({'weight': torch.zeros(2, 3)}, path)
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            failures = manager.process(['rmvpe'], 'verify')
            self.assertIn('SHA-256', failures['rmvpe'])

    @patch('model_manager.PUBLISHED_ASSET_HASHES', new={})
    @patch('model_manager.validate_weight_schema', new=lambda *args: None)
    def test_repair_invalid_download_preserves_existing_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            manager = ModelManager(folder)
            path = Path(manager.path('predictors/rmvpe.pt'))
            path.parent.mkdir(parents=True)
            path.write_bytes(b'old broken model')
            with patch.object(app_runtime.urllib.request, 'urlopen', return_value=Response(b'<html>server error</html>')):
                failures = manager.process(['rmvpe'], 'repair')
            self.assertIn('rmvpe', failures)
            self.assertEqual(path.read_bytes(), b'old broken model')
            self.assertEqual(list(path.parent.glob('*.part')), [])

    @patch('model_manager.PUBLISHED_ASSET_HASHES', new={})
    @patch('model_manager.validate_weight_schema', new=lambda *args: None)
    def test_repair_different_valid_weight_cannot_replace_known_model(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            manager = ModelManager(folder)
            with patch.object(app_runtime.urllib.request, 'urlopen', return_value=Response(checkpoint_bytes())):
                manager.process(['rmvpe'], 'install')
            path = Path(manager.path('predictors/rmvpe.pt'))
            path.write_bytes(b'damaged original')
            stream = io.BytesIO()
            torch.save({'weight': torch.zeros(2, 3)}, stream)
            with patch.object(app_runtime.urllib.request, 'urlopen', return_value=Response(stream.getvalue())):
                failures = manager.process(['rmvpe'], 'repair')
            self.assertIn('SHA-256', failures['rmvpe'])
            self.assertEqual(path.read_bytes(), b'damaged original')

    def test_checkpoint_crc_detects_damage_before_first_integrity_record(self):
        import zipfile
        import struct
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / 'model.pt'
            path.write_bytes(checkpoint_bytes())
            with zipfile.ZipFile(path) as archive:
                member = next(info for info in archive.infolist() if info.filename.endswith('/data/0'))
            content = bytearray(path.read_bytes())
            filename_size, extra_size = struct.unpack_from('<HH', content, member.header_offset + 26)
            content[member.header_offset + 30 + filename_size + extra_size] ^= 1
            path.write_bytes(content)
            with self.assertRaises(zipfile.BadZipFile):
                validate_file(path, 'model.pt')

    def test_cancel_after_transfer_prevents_replacement(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / 'model.pt'
            path.write_bytes(b'old')
            cancelled = [False]
            def progress(done, total):
                cancelled[0] = True
            with patch.object(app_runtime.urllib.request, 'urlopen', return_value=Response(checkpoint_bytes())), self.assertRaises(InterruptedError):
                app_runtime.download_model('https://example.org/model', str(path), cancelled=lambda: cancelled[0], progress=progress)
            self.assertEqual(path.read_bytes(), b'old')
            self.assertEqual(list(Path(folder).glob('*.part')), [])

    def test_model_paths_cannot_escape_install_folder(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            with self.assertRaises(ValueError):
                ModelManager(folder).path('../outside.pt')

    def test_metadata_accepts_official_tuples_but_rejects_executable_yaml(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder) / 'config.yaml'
            path.write_text('audio: {chunk_size: 16000, sample_rate: 16000, num_channels: 2}\nmodel: {dim: 8, depth: 1, heads: 2, stft_n_fft: 512, stft_hop_length: 128, bands: !!python/tuple [2, 4]}\ntraining: {instruments: [Vocals], target_instrument: Vocals}\ninference: {batch_size: 1, num_overlap: 2}\n')
            validate_file(path, 'config.yaml')
            path.write_text('!!python/object/apply:os.system [echo invalid]')
            with self.assertRaises(Exception):
                validate_file(path, 'config.yaml')

    def test_cpu_preference_and_app_model_path_override_library_auto_selection(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.dict(os.environ, {'AUDIO_SEPARATOR_MODEL_DIR': 'nonexistent_external_path'}):
            separator = LocalSeparator(model_file_dir=folder, device='cpu', info_only=True)
            with patch.object(torch.cuda, 'is_available', return_value=True):
                separator.setup_torch_device(None)
            self.assertEqual(str(separator.torch_device), 'cpu')
            self.assertEqual(separator.model_file_dir, os.path.realpath(folder))
            self.assertEqual(separator.onnx_execution_provider, ['CPUExecutionProvider'])
            with self.assertRaisesRegex(FileNotFoundError, 'Ayarlar'):
                separator.download_file_if_not_exists('https://example.org/model', str(Path(folder) / 'missing.pth'))

    def test_cover_missing_prerequisites_does_not_download(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(ui_cover, 'download_model') as download:
            with self.assertRaisesRegex(FileNotFoundError, 'Ayarlar'):
                ui_cover.ensure_rvc_prerequisites(folder)
            download.assert_not_called()

    def test_gui_embedder_mode_rejects_missing_files_without_network(self):
        import rvc.lib.utils as utils
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(utils, 'model_directory', return_value=folder), patch.object(utils, 'download_model') as download:
            with self.assertRaisesRegex(FileNotFoundError, 'Ayarlar'):
                utils.load_embedding('contentvec', allow_download=False)
            download.assert_not_called()

    def test_settings_controls_and_job_constructor_failure_restore_lock(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                settings = AppSettings(str(Path(folder) / 'settings.json'), ModelManager(folder))
                panel = SettingsPanel(frame, settings, auto_detect=False)
                self.assertEqual(panel.device_choice.GetCount(), 2)
                self.assertEqual(panel.model_list.GetCheckedModels(), default_model_selection())
                first = panel.model_list.buttons[0]
                self.assertIsInstance(first, wx.ToggleButton)
                self.assertIn('[AÇIK]', first.GetLabel())
                first.SetValue(False)
                event = wx.CommandEvent(wx.EVT_TOGGLEBUTTON.typeId, first.GetId())
                event.SetEventObject(first)
                first.GetEventHandler().ProcessEvent(event)
                self.assertIn('[KAPALI]', first.GetLabel())
                panel.RefreshModels()
                self.assertIs(panel.model_list.buttons[0], first)
                self.assertNotIn(panel.model_ids[0], panel.model_list.GetCheckedModels())
                with patch.object(panel, 'StartJob') as start:
                    panel.OnModels('verify')
                    self.assertEqual(start.call_args.args, ('verify', default_model_selection()[1:]))
                self.assertIn('dosya durumları', panel.model_list.GetName())
                with patch('ui_settings.threading.Thread', side_effect=RuntimeError('thread unavailable')), self.assertRaisesRegex(RuntimeError, 'thread unavailable'):
                    panel.OnHardware(None)
                self.assertFalse(app_runtime.JOB_LOCK.locked())
                self.assertTrue(panel.btn_install.IsEnabled())
                self.assertFalse(panel.btn_cancel.IsEnabled())
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_optional_downloads_require_selection_and_refresh_preserves_user_choices(self):
        from restoration import MODEL_ID
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                settings = AppSettings(str(Path(folder) / 'settings.json'), ModelManager(folder))
                panel = SettingsPanel(frame, settings, auto_detect=False)
                optional = [MODEL_ID, 'training_v2_32k', 'training_v2_40k', 'training_v2_48k']
                self.assertTrue(set(optional).isdisjoint(panel.model_list.GetCheckedModels()))
                with patch.object(settings, 'device_for', return_value='cpu'), patch.object(panel, 'StartJob') as start:
                    panel.OnModels('install')
                    self.assertEqual(start.call_args.args, ('install', default_model_selection()))
                    for name in (MODEL_ID, 'training_v2_40k'):
                        panel.model_list.buttons[panel.model_ids.index(name)].SetValue(True)
                    panel.model_list.buttons[0].SetValue(False)
                    selected = panel.model_list.GetCheckedModels()
                    panel.RefreshModels()
                    self.assertEqual(panel.model_list.GetCheckedModels(), selected)
                    panel.OnModels('install')
                    self.assertEqual(start.call_args.args, ('install', selected))
                    self.assertIn(MODEL_ID, selected)
                    self.assertIn('training_v2_40k', selected)
                    self.assertNotIn('training_v2_32k', selected)
                    self.assertNotIn('training_v2_48k', selected)
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_both_processing_tabs_capture_the_shared_device(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(ui_cover, 'load_models', return_value={}):
                root = Path(folder)
                source = root / 'input.wav'
                source.touch()
                settings = AppSettings(str(root / 'settings.json'), ModelManager(folder))
                settings.prepare_job = Mock(return_value='cuda:1')
                cover = ui_cover.CoverPanel(frame, settings)
                separator = ui_separator.SeparatorPanel(frame, settings)
                cover.models = {'voice': {'pth': 'voice.pth', 'index': ''}}
                cover.UpdateModelCheckList()
                cover.model_list.buttons[0].SetValue(True)
                cover.input_audio_path = separator.current_input_file = str(source)
                cover.output_folder_path = separator.output_directory = folder
                for panel in (cover, separator):
                    with patch('ui_cover.threading.Thread') as thread:
                        panel.OnStart(None)
                        args = thread.call_args.kwargs['args']
                        device = args[1]['device'] if panel is cover else args[-1]
                        self.assertEqual(device, 'cuda:1')
                    app_runtime.JOB_LOCK.release()
                self.assertEqual(settings.prepare_job.call_count, 2)
        finally:
            if app_runtime.JOB_LOCK.locked():
                app_runtime.JOB_LOCK.release()
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_missing_models_open_settings_without_starting_audio_worker(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(ui_cover, 'load_models', return_value={}):
                root = Path(folder)
                source = root / 'input.wav'
                source.touch()
                settings = AppSettings(str(root / 'settings.json'), ModelManager(folder))
                settings.report = HardwareReport(DeviceSupport('cpu', 'CPU', True))
                settings.open_settings = Mock()
                cover = ui_cover.CoverPanel(frame, settings)
                separator = ui_separator.SeparatorPanel(frame, settings)
                cover.models = {'voice': {'pth': 'voice.pth'}}
                cover.UpdateModelCheckList()
                cover.model_list.buttons[0].SetValue(True)
                cover.input_audio_path = separator.current_input_file = str(source)
                cover.output_folder_path = separator.output_directory = folder
                with patch.object(wx, 'MessageBox'), patch('ui_cover.threading.Thread') as thread:
                    cover.OnStart(None)
                    separator.OnStart(None)
                    thread.assert_not_called()
                self.assertEqual(settings.open_settings.call_count, 2)
                self.assertFalse(app_runtime.JOB_LOCK.locked())
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_main_frame_has_settings_tab_and_one_shared_preference(self):
        import main
        app = wx.GetApp() or wx.App(False)
        with patch.object(wx, 'CallAfter'), patch.object(ui_cover, 'load_models', return_value={}):
            frame = main.GhostkillerMainFrame()
            try:
                self.assertEqual(frame.notebook.GetPageCount(), 4)
                self.assertIs(frame.separator_tab.settings, frame.cover_tab.settings)
                self.assertIs(frame.settings_tab.settings, frame.settings)
                self.assertIs(frame.training_tab.settings, frame.settings)
                frame.OpenSettings()
                self.assertEqual(frame.notebook.GetSelection(), 3)
            finally:
                frame.Destroy()
        app.ProcessPendingEvents()


if __name__ == '__main__':
    unittest.main()
