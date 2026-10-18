"""Real codecs, shared settings and final exports across the audio workflows."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf

from audio_export import OUTPUT_FORMATS, OUTPUT_CHANNELS, export_audio
from app_settings import AppSettings

ROOT = Path(__file__).resolve().parents[1]


class AudioExportTests(unittest.TestCase):
    def signal(self, frames=4411, channels=2):
        data = .2*np.sin(np.arange(frames, dtype='float32')*.031)
        return np.column_stack([data*(1-index*.2) for index in range(channels)])

    def test_real_formats_preserve_duration_channels_and_lossless_precision(self):
        for output_format in OUTPUT_FORMATS:
            for rate in (40000, 44100):
                for channels in (1, 2):
                    with self.subTest(format=output_format, rate=rate, channels=channels), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                        root = Path(folder)
                        source, target = root/'source.wav', root/('result.'+output_format)
                        data = self.signal(channels=channels)
                        sf.write(source, data, rate, subtype='FLOAT')
                        original = source.read_bytes()
                        export_audio(source, target, output_format)
                        info = sf.info(target)
                        self.assertEqual(info.format, output_format.upper())
                        self.assertEqual(info.channels, channels)
                        self.assertLessEqual(abs(info.duration-len(data)/rate), 1/info.samplerate)
                        if output_format in ('wav', 'flac'):
                            self.assertEqual(info.subtype, 'PCM_24')
                            actual, _ = sf.read(target, always_2d=True)
                            np.testing.assert_allclose(actual, data, atol=2**-23, rtol=0)
                        self.assertEqual(source.read_bytes(), original)
                        self.assertEqual(sorted(p.name for p in root.iterdir()), sorted([source.name, target.name]))

    def test_cancel_and_invalid_samples_preserve_previous_outputs_and_clean_staging(self):
        for output_format in OUTPUT_FORMATS:
            with self.subTest(format=output_format), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                root = Path(folder)
                source, target = root/'source.wav', root/('result.'+output_format)
                sf.write(source, self.signal(200000), 44100, subtype='FLOAT')
                target.write_bytes(b'previous successful result')
                calls = 0
                def cancelled():
                    nonlocal calls
                    calls += 1
                    return calls >= 3
                with self.assertRaises(InterruptedError):
                    export_audio(source, target, output_format, cancelled=cancelled)
                self.assertEqual(target.read_bytes(), b'previous successful result')
                sf.write(source, np.array([.1, np.nan]), 44100, subtype='FLOAT')
                with self.assertRaisesRegex(ValueError, 'NaN'):
                    export_audio(source, target, output_format)
                self.assertEqual(target.read_bytes(), b'previous successful result')
                self.assertEqual(set(p.name for p in root.iterdir()), {source.name, target.name})

    def test_mono_and_stereo_conversion_preserves_both_channels_in_every_format(self):
        for output_format in OUTPUT_FORMATS:
            for source_channels in (1, 2):
                for mode, channels in (('mono', 1), ('stereo', 2)):
                    with self.subTest(format=output_format, source=source_channels, mode=mode), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                        root = Path(folder)
                        source, target = root/'source.wav', root/('output.'+output_format)
                        data = self.signal(channels=source_channels)
                        sf.write(source, data, 44100, subtype='FLOAT')
                        export_audio(source, target, output_format, output_channels=mode)
                        actual, rate = sf.read(target, always_2d=True)
                        self.assertEqual(actual.shape, (len(data), channels))
                        self.assertEqual(rate, 44100)
                        if output_format in ('wav', 'flac'):
                            expected = data.mean(axis=1, keepdims=True) if channels == 1 else np.repeat(data, 2, axis=1) if source_channels == 1 else data
                            np.testing.assert_allclose(actual, expected, atol=2**-23, rtol=0)

    def test_setting_persists_without_overwriting_other_preferences_or_failed_save(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'settings.json'
            settings = AppSettings(str(path), Mock())
            self.assertEqual(settings.output_format, 'flac')
            self.assertEqual(settings.output_channels, 'original')
            settings.select_theme('dark')
            for output_format in OUTPUT_FORMATS:
                settings.select_output_format(output_format.upper())
                restored = AppSettings(str(path), Mock())
                self.assertEqual(restored.output_format, output_format)
                self.assertEqual(restored.theme, 'dark')
            for output_channels in OUTPUT_CHANNELS:
                settings.select_output_channels(output_channels)
                self.assertEqual(AppSettings(str(path), Mock()).output_channels, output_channels)
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                settings.select_output_format('aac')
            with self.assertRaises(ValueError):
                settings.select_output_channels('surround')
            with patch('app_settings.os.replace', side_effect=PermissionError('read only')):
                with self.assertRaises(PermissionError):
                    settings.select_output_format('mp3')
                with self.assertRaises(PermissionError):
                    settings.select_output_channels('mono')
            self.assertEqual(settings.output_format, 'ogg')
            self.assertEqual(settings.output_channels, 'stereo')
            self.assertEqual(path.read_bytes(), original)

    def test_settings_control_saves_and_rejects_changes_during_an_active_job(self):
        import wx
        from app_runtime import JOB_LOCK
        from model_manager import ModelManager
        from ui_settings import SettingsPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                settings = AppSettings(str(Path(folder)/'settings.json'), ModelManager(folder))
                panel = SettingsPanel(frame, settings, auto_detect=False)
                self.assertEqual(panel.output_format_choice.GetStrings(), ['MP3','WAV','FLAC','OGG'])
                panel.output_format_choice.SetSelection(0)
                panel.OnOutputFormat(None)
                self.assertEqual(settings.output_format, 'mp3')
                panel.output_channels_choice.SetSelection(1)
                panel.OnOutputChannels(None)
                self.assertEqual(settings.output_channels, 'mono')
                JOB_LOCK.acquire()
                try:
                    panel.output_format_choice.SetSelection(3)
                    with patch.object(wx, 'MessageBox'):
                        panel.OnOutputFormat(None)
                    self.assertEqual(settings.output_format, 'mp3')
                    self.assertEqual(panel.output_format_choice.GetSelection(), 0)
                    panel.output_channels_choice.SetSelection(2)
                    with patch.object(wx, 'MessageBox'):
                        panel.OnOutputChannels(None)
                    self.assertEqual(settings.output_channels, 'mono')
                    self.assertEqual(panel.output_channels_choice.GetSelection(), 1)
                finally:
                    JOB_LOCK.release()
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_instrument_outputs_contain_only_the_requested_audio_format(self):
        from instruments.engine import separate_file
        class Split:
            def __call__(self, data):
                return data[:,None].repeat(1,4,1,1)/4
        for output_format in OUTPUT_FORMATS:
            with self.subTest(format=output_format), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                root = Path(folder)
                source = root/'source.wav'
                sf.write(source, self.signal(), 44100, subtype='FLOAT')
                result = separate_file(source, root/'output', root, stems=('bass','vocals'),
                    model_factory=lambda *args:Split(), output_format=output_format, output_channels='mono')
                outputs = list((root/'output').iterdir())
                self.assertEqual(len(outputs), 2)
                self.assertTrue(all(p.suffix == '.'+output_format for p in outputs))
                self.assertFalse((root/'output'/'separation.json').exists())
                for path in result['files'].values():
                    self.assertEqual(sf.info(path).format, output_format.upper())
                    self.assertEqual(sf.info(path).channels, 1)

    def test_vocal_chain_and_repair_use_lossless_intermediates_with_mp3_exports(self):
        from ui_separator import SeparatorPanel
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            source, output = root/'source.wav', root/'outputs'
            output.mkdir()
            sf.write(source, self.signal(channels=1), 44100, subtype='FLOAT')
            seen = []
            expected_inputs = []
            def separate(path, model, label, stage):
                data, rate = sf.read(path, always_2d=True)
                seen.append(Path(path).suffix)
                if expected_inputs:
                    np.testing.assert_array_equal(data, expected_inputs[-1])
                target = Path(stage)/('source_(No Reverb).flac' if 'Yankı' in label else 'source_(Vocals).flac')
                sf.write(target, data*.9, rate, subtype='PCM_24')
                expected_inputs.append(sf.read(target, always_2d=True)[0])
                return [str(target)]
            def repair(reference, cleaned, stage):
                self.assertEqual(sf.info(cleaned).format, 'FLAC')
                path = Path(stage)/'restored.flac'
                data, rate = sf.read(cleaned)
                sf.write(path, data*.8, rate, subtype='PCM_24')
                expected_inputs[-1] = sf.read(path, always_2d=True)[0]
                return {'output':str(path),'repaired_intervals':1}
            job = SimpleNamespace(current_input_file=str(source), output_directory=str(output),
                is_cancelled=False, RunSeparatorCommand=separate, RunVocalRestoration=repair,
                LogMessage=Mock(), UpdateStatus=Mock())
            with patch('hardware.configure_runtime'), patch('ui_separator.post_ui'), patch('ui_separator.finish_job'):
                SeparatorPanel.ProcessChain(job, (False,True,True,True,False), restore_vocal=True,
                    output_format='mp3', output_channels='stereo')
            self.assertEqual(seen, ['.wav','.flac','.flac'])
            paths = list(output.iterdir())
            self.assertEqual(len(paths), 4, job.LogMessage.call_args_list)
            self.assertTrue(all(p.suffix == '.mp3' for p in paths))
            self.assertTrue(all(sf.info(p).format == 'MP3' for p in paths))
            self.assertTrue(all(sf.info(p).channels == 2 for p in paths))

    def test_cover_and_training_listening_examples_follow_each_format(self):
        from ui_cover import CoverPanel
        from training.comparison import test_candidates
        class Session:
            def execute(self, kind, payload, **kwargs):
                source = payload['options']['audio_input_path']
                target = payload['options']['audio_output_path']
                data, rate = sf.read(source)
                sf.write(target, data, rate, format='WAV')
        class Converter:
            def __init__(self, **kwargs): pass
            def convert_audio(self, source, target, *args, **kwargs):
                data, rate = sf.read(source)
                sf.write(target, data, rate, format='WAV')
            def cleanup_model(self): pass
        for output_format in OUTPUT_FORMATS:
            with self.subTest(format=output_format), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                root = Path(folder)
                source, output = root/'source.wav', root/'outputs'
                output.mkdir()
                sf.write(source, self.signal(channels=1), 40000, subtype='FLOAT')
                weight = root/'voice.pth';weight.touch()
                job = SimpleNamespace(input_audio_path=str(source), output_folder_path=str(output),
                    models={'voice':{'pth':str(weight),'index':''}}, app_dir=str(root),
                    is_cancelled=False, audio_session_factory=Session, LogMessage=Mock(), UpdateStatus=Mock())
                options = dict(device='cpu', pitch=0, index_rate=.75, f0_method='rmvpe',
                    output_format=output_format, output_channels='stereo')
                with patch('ui_cover.ensure_rvc_prerequisites'), patch('ui_cover.post_ui'):
                    CoverPanel._run_inference_queue(job, ['voice'], options)
                self.assertEqual(sf.info(output/f'source_voice.{output_format}').format, output_format.upper())
                self.assertEqual(sf.info(output/f'source_voice.{output_format}').channels, 2)
                for filename in ('latest.pth','best_validation.pth'):
                    (root/filename).touch()
                from model_manager import file_digest
                bank = [{'id':'clip_1','label':'Test','audio':str(source),'sha256':file_digest(source)}]
                with patch('training.comparison.comparison_bank', return_value=bank), \
                        patch('training.comparison.snapshot_records', return_value=[]), \
                        patch('rvc.infer.infer.VoiceConverter', Converter):
                    models, _ = test_candidates(root, {}, SimpleNamespace(f0_method='rmvpe'),
                        'cpu', '', Mock(), output_format=output_format, output_channels='stereo')
                for model in models:
                    for key in ('test_audio','test_audio_no_index'):
                        path = Path(model[key])
                        self.assertEqual(path.suffix, '.'+output_format)
                        self.assertEqual(sf.info(path).format, output_format.upper())
                        self.assertEqual(sf.info(path).channels, 2)
                self.assertTrue(all(p.suffix == '.'+output_format for p in (root/'comparison').iterdir()))


if __name__ == '__main__':
    unittest.main()
