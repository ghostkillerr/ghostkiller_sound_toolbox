"""Motor regression tests with real dependencies, without model downloads."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('NUMBA_CACHE_DIR', str(Path(__file__).resolve().parents[1] / '__pycache__' / 'numba'))

import numpy as np
import torch
from rvc.configs.config import Config
from rvc.infer.infer import VoiceConverter
from rvc.infer.pipeline import Pipeline, Autotune
from rvc.lib.tools.split_audio import process_audio, merge_audio
import soundfile as sf
from types import SimpleNamespace
import rvc.lib.utils as audio_utils


class MotorTests(unittest.TestCase):
    def test_unreadable_index_is_an_explicit_conversion_error(self):
        pipeline = Pipeline(16000, Config(device='cpu'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            index = Path(folder) / 'broken.index'
            index.write_bytes(b'not a FAISS index')
            with self.assertRaisesRegex(ValueError, 'FAISS indeksi okunamadı'):
                pipeline.pipeline(None, None, 0, np.zeros(1600), 0, 'rmvpe', str(index), .75, True, 1., 'v2', .33, False, 1., False, 155.)

    def test_missing_custom_embedder_prepares_default_in_install_models(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            destination = root / 'models'
            def download(url, target):
                Path(target).write_bytes(b'downloaded')
            with patch.object(audio_utils, 'model_directory', return_value=str(destination)), patch.object(audio_utils, 'app_directory', return_value=folder), patch.object(audio_utils, 'download_model', side_effect=download) as fetch, patch.object(audio_utils.HubertModelWithFinalProj, 'from_pretrained') as load:
                audio_utils.load_embedding('custom', None)
                self.assertEqual(fetch.call_count, 2)
                self.assertEqual(load.call_args.args[0], str(destination / 'embedders' / 'contentvec'))

    def test_autotune_preserves_silence_and_applies_pitch(self):
        autotune = Autotune()
        np.testing.assert_array_equal(autotune.autotune_f0(np.array([0., np.nan, -1.]), 1.), 0.)
        pipeline = Pipeline(16000, Config(device='cpu'))
        predictor = SimpleNamespace(get_f0=lambda *args, **kwargs: np.r_[0., np.full(14, 98.), 0.])
        with patch('rvc.infer.pipeline.RMVPE', return_value=predictor):
            _, pitch = pipeline.get_f0(np.zeros(1600), 16, pitch=12, f0_autotune=True)
        np.testing.assert_allclose(pitch[1:-1], 196., atol=.001)
        self.assertEqual(pitch[0], 0.)
        self.assertEqual(pitch[-1], 0.)

    def test_short_pitch_contour_is_padded_without_making_silence_voiced(self):
        pipeline = Pipeline(16000, Config(device='cpu'))
        predictor = SimpleNamespace(get_f0=lambda *args, **kwargs: np.array([100., np.nan]))
        with patch('rvc.infer.pipeline.RMVPE', return_value=predictor):
            coarse, pitch = pipeline.get_f0(np.zeros(800), 5)
        self.assertEqual(len(coarse), 5)
        np.testing.assert_array_equal(pitch, [100., 0., 0., 0., 0.])

    def test_pitch_protection_truncates_features_to_same_length(self):
        pipeline = Pipeline(16000, Config(device='cpu'))
        received = []
        class Network:
            def infer(self, feats, lengths, pitch, pitchf, sid):
                received.append((feats.shape[1], pitch.shape[1], pitchf.shape[1], lengths.item()))
                return (torch.zeros(1, 1, 480),)
        model = lambda audio: {'last_hidden_state': torch.ones(1, 4, 2)}
        pipeline.voice_conversion(model, Network(), torch.tensor([0]), np.zeros(640), torch.ones(1, 3), torch.ones(1, 3), None, None, 0., 'v2', .33)
        self.assertEqual(received, [(3, 3, 3, 3)])

    def test_corrupt_index_vectors_do_not_poison_audio_features(self):
        pipeline = Pipeline(16000, Config(device='cpu'))
        features = torch.ones(1, 1, 2)
        index = SimpleNamespace(ntotal=1, search=lambda values, k: (np.ones((1, 1), dtype=np.float32), np.zeros((1, 1), dtype=int)))
        output = pipeline._retrieve_speaker_embeddings(features, index, np.array([[np.nan, 2.]], dtype=np.float32), 1.)
        self.assertTrue(torch.equal(output, features))
        with self.assertRaisesRegex(ValueError, 'uyumlu'):
            pipeline._retrieve_speaker_embeddings(features, index, np.ones((1, 3)), .75)

    def test_merge_restores_timeline_even_when_converted_chunks_are_longer(self):
        intervals = np.array([[10, 20], [40, 60]])
        result = merge_audio([np.ones(10), np.ones(20)], [np.ones(45), np.full(40, .5)], intervals, 100, 300, 100)
        self.assertEqual(len(result), 300)
        np.testing.assert_array_equal(result[:30], 0.)
        np.testing.assert_array_equal(result[30:60], 1.)
        np.testing.assert_array_equal(result[60:120], 0.)
        np.testing.assert_array_equal(result[120:160], .5)
        np.testing.assert_array_equal(result[160:], 0.)

    def test_completely_silent_split_restores_full_duration(self):
        chunks, intervals = process_audio(np.zeros(16000))
        self.assertEqual(len(chunks), 0)
        result = merge_audio(chunks, [], intervals, 16000, 48000, 16000)
        self.assertEqual(len(result), 48000)
        np.testing.assert_array_equal(result, 0.)

    def test_resampling_preserves_duration_and_model_rate_across_calls(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            source = root / 'input.wav'
            model = root / 'voice.pth'
            model.touch()
            sf.write(source, np.sin(np.arange(16000) * .1) * .2, 16000)
            converter = VoiceConverter(device='cpu')
            converter.tgt_sr = 16000
            converter.n_spk = 1
            converter.use_f0 = 0
            converter.get_vc = lambda *args: None
            converter.hubert_model = object()
            converter.last_embedder_model = ('contentvec', None)
            converter.vc = SimpleNamespace(pipeline=lambda **kwargs: np.ones(16000, dtype=np.float32) * .1)
            for rate in (32000, 24000):
                output = root / f'output_{rate}.WAV'
                result = converter.convert_audio(str(source), str(output), str(model), None, resample_sr=rate)
                info = sf.info(result)
                self.assertEqual(info.samplerate, rate)
                self.assertEqual(info.frames, rate)
                self.assertEqual(converter.tgt_sr, 16000)

    def test_format_conversion_preserves_stereo_and_propagates_errors(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            source = root / 'input.wav'
            sf.write(source, np.tile([.1, .2], (100, 1)), 22050)
            result = VoiceConverter.convert_audio_format(source, root / 'output.flac', 'FLAC')
            self.assertEqual(sf.info(result).channels, 2)
            self.assertEqual(sf.info(result).samplerate, 22050)
            with self.assertRaises(ValueError):
                VoiceConverter.convert_audio_format(source, root / 'bad', 'unsupported')

    def test_failed_model_switch_clears_previous_state(self):
        converter = VoiceConverter(device='cpu')
        converter.loaded_model = 'old'
        converter.net_g = object()
        with patch.object(converter, 'load_model', side_effect=ValueError('broken checkpoint')):
            with self.assertRaises(ValueError):
                converter.get_vc('new', 0)
        self.assertIsNone(converter.loaded_model)
        self.assertIsNone(converter.net_g)

    def test_invalid_checkpoint_configuration_is_rejected(self):
        converter = VoiceConverter(device='cpu')
        converter.cpt = {'config': [], 'weight': {}}
        with self.assertRaisesRegex(ValueError, 'yapılandırması'):
            converter.setup_network()

    def test_cpu_configuration_does_not_depend_on_cwd(self):
        original = os.getcwd()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            try:
                os.chdir(folder)
                self.assertEqual(Config(device='cpu').device, 'cpu')
            finally:
                os.chdir(original)

    def test_explicit_cuda_is_rejected_when_unavailable(self):
        with patch.object(torch.cuda, 'is_available', return_value=False):
            with self.assertRaisesRegex(RuntimeError, 'CUDA'):
                Config(device='cuda')

    def test_cleanup_is_repeatable(self):
        converter = VoiceConverter(device='cpu')
        converter.loaded_model = 'previous_model'
        converter.cleanup_model()
        converter.cleanup_model()
        self.assertIsNone(converter.loaded_model)
        self.assertIsNone(converter.net_g)

    def test_small_index_and_invalid_neighbor_preserve_features(self):
        pipeline = object.__new__(Pipeline)
        pipeline.device = 'cpu'
        features = torch.tensor([[[1., 2.], [3., 4.]]])
        class Index:
            ntotal = 1
            def search(self, values, k):
                self.k = k
                return np.array([[1.], [np.inf]], dtype=np.float32), np.array([[0], [-1]])
        index = Index()
        result = pipeline._retrieve_speaker_embeddings(features, index, np.array([[5., 6.]], dtype=np.float32), 1.)
        self.assertEqual(index.k, 1)
        self.assertTrue(torch.allclose(result, torch.tensor([[[5., 6.], [3., 4.]]])))
        index.ntotal = 0
        self.assertTrue(torch.equal(pipeline._retrieve_speaker_embeddings(features, index, np.empty((0, 2)), 1.), features))


if __name__ == '__main__':
    unittest.main()
