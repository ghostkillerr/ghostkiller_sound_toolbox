"""Release scenarios for bounded inference and untrusted data-only indices."""
import gc
import os
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import weakref
import zipfile
import io
import json
import soundfile as sf

from app_runtime import configure_runtime_cache
configure_runtime_cache()
import faiss
import numpy as np
import torch
import torch.nn.functional as F
from rvc.configs.config import Config
from rvc.infer.helper_cache import InferenceHelperCache
from rvc.infer.infer import VoiceConverter
from rvc.infer.pipeline import Pipeline
from rvc.infer.quality_policy import InferenceQualityPolicy
from rvc.infer.safe_index import inspect_index, load_index
from rvc.lib.predictors.RMVPE import RMVPE0Predictor, MelSpectrogram
from rvc.lib.utils import validate_audio_memory
import rvc.lib.utils as audio_utils
from rvc.infer.model_validation import (validate_architecture, validate_meta_network,
                                       validate_weights, checkpoint_archive_precheck)
from training.config import architecture, inference_config


class IndexSafetyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "voice.index"
        faiss.omp_set_num_threads(2)

    def test_exact_flat_256_and_768_roundtrip_without_native_deserialization(self):
        for dimension in (256, 768):
            with self.subTest(dimension=dimension):
                vectors = np.random.default_rng(7).normal(size=(80, dimension)).astype("float32")
                original = faiss.IndexFlatL2(dimension)
                original.add(vectors)
                faiss.write_index(original, str(self.path))
                with patch.object(faiss, "read_index", side_effect=AssertionError("untrusted IO")), patch.object(faiss, "deserialize_index", side_effect=AssertionError("untrusted IO")):
                    self.assertEqual(inspect_index(self.path).vectors, 80)
                    loaded = load_index(self.path, dimension)
                a, b = original.search(vectors[:5], 8), loaded.search(vectors[:5], 8)
                np.testing.assert_array_equal(a[1], b[1])
                np.testing.assert_array_equal(a[0], b[0])

    def test_ivf_dense_sparse_and_direct_map_roundtrip_preserves_lists_probe_and_neighbors(self):
        vectors = np.random.default_rng(19).normal(size=(160, 256)).astype("float32")
        for sparse, direct_map in ((False, False), (True, False), (False, True)):
            with self.subTest(sparse=sparse, direct_map=direct_map):
                original = faiss.IndexIVFFlat(faiss.IndexFlatL2(256), 256, 4, faiss.METRIC_L2)
                original.train(vectors)
                original.add(vectors[:1] if sparse else vectors)
                original.nprobe = 3
                if direct_map:
                    original.make_direct_map()
                faiss.write_index(original, str(self.path))
                loaded = load_index(self.path)
                self.assertEqual(loaded.nprobe, 3)
                self.assertEqual(loaded.ntotal, original.ntotal)
                expected = original.search_and_reconstruct(vectors[:7], min(8, original.ntotal))
                actual = loaded.search_and_reconstruct(vectors[:7], min(8, original.ntotal))
                np.testing.assert_array_equal(expected[1], actual[1])
                np.testing.assert_allclose(expected[0], actual[0], rtol=0, atol=0)
                np.testing.assert_array_equal(expected[2], actual[2])

    def test_inner_product_rejected_before_native_constructor(self):
        original = faiss.IndexFlatIP(256)
        original.add(np.ones((1, 256), dtype="float32"))
        faiss.write_index(original, str(self.path))
        with patch.object(faiss, "IndexFlatL2", side_effect=AssertionError("allocation before validation")):
            with self.assertRaisesRegex(ValueError, "L2"):
                load_index(self.path)

    def test_forged_counts_truncation_trailing_data_and_nonfinite_are_rejected(self):
        original = faiss.IndexFlatL2(256)
        original.add(np.ones((3, 256), dtype="float32"))
        valid = bytes(faiss.serialize_index(original))
        cases = [valid[:44], valid[:-1], valid + b"unexpected", valid[:8] + struct.pack("<q", 2**62) + valid[16:], valid[:37] + struct.pack("<Q", 2**63) + valid[45:], valid[:45] + struct.pack("<f", float("nan")) + valid[49:]]
        for invalid in cases:
            with self.subTest(length=len(invalid)):
                self.path.write_bytes(invalid)
                with patch.object(faiss, "IndexFlatL2", side_effect=AssertionError("allocation before validation")):
                    with self.assertRaises(ValueError):
                        load_index(self.path)

    def test_index_dimension_and_available_ram_limit_are_explicit(self):
        original = faiss.IndexFlatL2(256)
        original.add(np.ones((3, 256), dtype="float32"))
        faiss.write_index(original, str(self.path))
        with self.assertRaisesRegex(ValueError, "uyumlu"):
            inspect_index(self.path, 768)
        with patch("rvc.infer.safe_index.available_memory", return_value=100):
            with self.assertRaisesRegex(ValueError, "boyut"):
                load_index(self.path)

    def test_quantized_wrapped_and_external_file_layouts_fail_closed(self):
        original = faiss.IndexFlatL2(256)
        valid = bytes(faiss.serialize_index(original))
        for tag in (b"IwPQ", b"IxPT", b"IxHN", b"ilod"):
            self.path.write_bytes(tag + valid[4:])
            with self.assertRaisesRegex(ValueError, "Desteklenmeyen"):
                inspect_index(self.path)

    def test_ivf_forged_list_counts_ids_and_quantizer_dimension_are_rejected(self):
        vectors = np.random.default_rng(2).normal(size=(80, 256)).astype("float32")
        original = faiss.IndexIVFFlat(faiss.IndexFlatL2(256), 256, 2, faiss.METRIC_L2)
        original.train(vectors)
        original.add(vectors)
        valid = bytes(faiss.serialize_index(original))
        nested_header = valid.index(b"IxF2")
        list_header = valid.index(b"ilar")
        invalid_cases = [
            valid[:37] + struct.pack("<Q", 2**63) + valid[45:],
            valid[:nested_header + 4] + struct.pack("<i", 768) + valid[nested_header + 8:],
            valid[:list_header + 12] + struct.pack("<Q", 2**63) + valid[list_header + 20:],
            valid[:-8] + struct.pack("<q", -1),
            valid[:-8] + struct.pack("<q", 2**62),
        ]
        for invalid in invalid_cases:
            self.path.write_bytes(invalid)
            with patch.object(faiss, "IndexIVFFlat", side_effect=AssertionError("native allocation before validation")):
                with self.assertRaises(ValueError):
                    load_index(self.path)

    def test_numeric_blocks_are_revalidated_if_file_changes_after_inspection(self):
        original = faiss.IndexFlatL2(256)
        original.add(np.ones((2, 256), dtype="float32"))
        faiss.write_index(original, str(self.path))
        constructor = faiss.IndexFlatL2
        def replace_after_validation(dimension):
            with self.path.open("r+b") as stream:
                stream.seek(45)
                stream.write(struct.pack("<f", float("nan")))
            return constructor(dimension)
        with patch.object(faiss, "IndexFlatL2", side_effect=replace_after_validation):
            with self.assertRaisesRegex(ValueError, "sonlu"):
                load_index(self.path)

    def test_mutation_corpus_never_enters_native_file_io(self):
        original = faiss.IndexFlatL2(256)
        original.add(np.ones((3, 256), dtype="float32"))
        valid = bytes(faiss.serialize_index(original))
        rng = np.random.default_rng(78)
        with patch.object(faiss, "read_index", side_effect=AssertionError("native file IO")), patch.object(faiss, "deserialize_index", side_effect=AssertionError("native file IO")):
            for _ in range(80):
                data = bytearray(valid)
                offset = int(rng.integers(0, len(data)))
                data[offset] ^= 1 << int(rng.integers(0, 8))
                self.path.write_bytes(data)
                try:
                    inspect_index(self.path)
                except ValueError:
                    pass

    def test_retrieval_matches_old_formula_in_bounded_query_blocks(self):
        vectors = np.random.default_rng(3).normal(size=(40, 256)).astype("float32")
        index = faiss.IndexFlatL2(256)
        index.add(vectors)
        features = torch.from_numpy(np.random.default_rng(9).normal(size=(1, 777, 256)).astype("float32"))
        pipeline = Pipeline(16000, Config("cpu"))
        distances, ids = index.search(features[0].numpy(), 8)
        weights = np.square(1 / np.maximum(distances, 1e-5))
        weights /= weights.sum(axis=1, keepdims=True)
        expected = np.sum(vectors[ids] * weights[..., None], axis=1) * .75 + features[0].numpy() * .25
        sizes = []
        method = index.search_and_reconstruct
        def retrieve(values, count):
            sizes.append(len(values))
            return method(values, count)
        with patch.object(index, "search_and_reconstruct", side_effect=retrieve), patch.object(index, "reconstruct_n", side_effect=AssertionError("full duplicated matrix")):
            actual = pipeline._retrieve_speaker_embeddings(features, index, None, .75)
        self.assertLessEqual(max(sizes), 256)
        self.assertEqual(sum(sizes), 777)
        np.testing.assert_allclose(actual[0].numpy(), expected, rtol=3e-6, atol=1e-6)


class BoundedPitchTests(unittest.TestCase):
    def predictor(self, limit=512):
        predictor = object.__new__(RMVPE0Predictor)
        predictor.device = "cpu"
        predictor.max_forward_frames = limit
        predictor.context_frames = 128
        predictor.cents_mapping = np.pad(20 * np.arange(360) + 1997.3794084376191, (4, 4))
        predictor.mel_extractor = MelSpectrogram(128, 16000, 1024, 160, None, 30, 8000)
        self.shapes = []
        def network(mel):
            self.shapes.append(mel.shape[-1])
            return mel[:, 0, :, None].repeat(1, 1, 360)
        predictor.model = network
        return predictor

    def test_short_mel_is_exactly_the_previous_padded_single_forward(self):
        predictor = self.predictor()
        mel = torch.rand(1, 128, 313)
        expected = predictor.model(F.pad(mel, (0, 7), mode="reflect"))[:, :313]
        self.shapes.clear()
        actual = predictor.mel2hidden(mel)
        self.assertTrue(torch.equal(expected, actual))
        self.assertEqual(self.shapes, [320])

    def test_long_mel_forward_and_cpu_accumulation_are_bounded_without_lost_frames(self):
        predictor = self.predictor()
        mel = torch.arange(33001).float().view(1, 1, -1).repeat(1, 128, 1)
        actual = predictor.mel2hidden(mel)
        self.assertLessEqual(max(self.shapes), 512)
        self.assertEqual(actual.device.type, "cpu")
        np.testing.assert_array_equal(actual[0, :, 0].numpy(), np.arange(33001))

    def test_streamed_mel_frames_match_full_song_at_all_boundaries(self):
        predictor = self.predictor()
        audio = np.random.default_rng(4).normal(size=16000 * 17 + 13).astype("float32") * .1
        predictor.decode = lambda hidden, thred: hidden[:, 0]
        expected = predictor.mel_extractor(torch.from_numpy(audio).unsqueeze(0))[0, 0].numpy()
        actual = predictor.infer_from_audio(audio)
        self.assertLessEqual(max(self.shapes), 512)
        np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-5)

    def test_pressure_window_selection_and_invalid_limits(self):
        predictor = self.predictor()
        predictor.max_forward_frames = None
        with patch("rvc.lib.predictors.RMVPE.memory_info", return_value=(512 * 1024**2, 8 * 1024**3)):
            self.assertEqual(predictor._window_limits()[0], 512)
        for bad in (0, 512.0, 1000, 32000, True):
            with self.assertRaises(ValueError):
                predictor.mel2hidden(torch.ones(1, 128, 100), bad)

    def test_zero_salience_decode_has_no_runtime_warning_and_remains_unvoiced(self):
        predictor = self.predictor()
        with np.errstate(all="raise"):
            np.testing.assert_array_equal(predictor.decode(np.zeros((5, 360))), 0)


class TimelineTests(unittest.TestCase):
    def test_selected_index_is_not_replaced_by_a_similarly_named_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, model, output = [root/name for name in ('source.wav', 'model.pth', 'raw.wav')]
            samples = np.full(3200, .1, dtype='float32')
            sf.write(source, samples, 16000, subtype='FLOAT')
            model.touch()
            converter = VoiceConverter('cpu', quality_policy=InferenceQualityPolicy(False, False, False))
            converter.tgt_sr, converter.n_spk, converter.use_f0 = 16000, 1, 0
            converter.get_vc = lambda *args: None
            converter.hubert_model, converter.last_embedder_model = object(), ('contentvec', None)
            pipeline = Mock(return_value=samples.copy())
            converter.vc = SimpleNamespace(pipeline=pipeline)
            for name in ('trained_models/voice.index', 'voice_trained.index', 'trained_voice.index'):
                with self.subTest(name=name):
                    chosen = root/name
                    alternate = root/name.replace('trained', 'added')
                    for index in (chosen, alternate):
                        index.parent.mkdir(parents=True, exist_ok=True)
                        index.write_bytes(b'different selected model data')
                    converter.convert_audio(str(source), str(output), str(model), str(chosen))
                    self.assertEqual(pipeline.call_args.kwargs['file_index'], str(chosen))

    def test_rvc_writer_preserves_float_until_pcm24_user_export(self):
        from audio_export import export_audio
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            source, model, output = [root/name for name in ('source.wav', 'model.pth', 'raw.wav')]
            samples = (.2*np.sin(np.arange(3200, dtype='float32')*.031)).astype('float32')
            sf.write(source, samples, 16000, subtype='FLOAT')
            model.touch()
            converter = VoiceConverter('cpu', quality_policy=InferenceQualityPolicy(False, False, False))
            converter.tgt_sr, converter.n_spk, converter.use_f0 = 16000, 1, 0
            converter.get_vc = lambda *args: None
            converter.hubert_model, converter.last_embedder_model = object(), ('contentvec', None)
            converter.vc = SimpleNamespace(pipeline=lambda **kwargs: samples.copy())
            converter.convert_audio(str(source), str(output), str(model), '')
            self.assertEqual(sf.info(output).subtype, 'FLOAT')
            np.testing.assert_array_equal(sf.read(output, dtype='float32')[0], samples)
            for format_ in ('wav', 'flac'):
                path = export_audio(output, root/('result.'+format_), format_)
                self.assertEqual(sf.info(path).subtype, 'PCM_24')
                np.testing.assert_allclose(sf.read(path)[0], samples, rtol=0, atol=2**-23)
            flac = converter.convert_audio_format(output, root/'direct.flac', 'FLAC')
            self.assertEqual(sf.info(flac).subtype, 'PCM_24')
            np.testing.assert_allclose(sf.read(flac)[0], samples, rtol=0, atol=2**-23)

    def test_resampled_source_timeline_uses_original_file_duration(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            source, model, output = [Path(folder) / name for name in ("source.wav", "model.pth", "output.wav")]
            sf.write(source, np.sin(np.arange(4411) / 50) * .2, 44100)
            model.touch()
            converter = VoiceConverter("cpu")
            converter.tgt_sr, converter.n_spk, converter.use_f0 = 16000, 1, 0
            converter.get_vc = lambda *args:None
            converter.hubert_model, converter.last_embedder_model = object(), ("contentvec", None)
            converter.vc = SimpleNamespace(pipeline=lambda **kwargs:np.ones(len(kwargs["audio"]), dtype="float32") * .1)
            result = converter.convert_audio(str(source), str(output), str(model), "", resample_sr=48000)
            self.assertEqual(sf.info(result).frames, round(4411 * 48000 / 44100))

    def pipeline(self, rate, split=False):
        pipeline = Pipeline(rate, Config("cpu"), quality_policy=InferenceQualityPolicy(False, False, False))
        if split:
            pipeline.t_center, pipeline.t_query, pipeline.t_max = 1600, 320, 2400
        pipeline.get_f0 = lambda audio, count, *args: (np.ones(count, dtype=int), np.full(count, 100., dtype="float32"))
        return pipeline

    def model_and_generator(self, rate):
        class ValidCNN:
            # Faithfully use ContentVec's 400-sample valid receptive field,
            # 320-sample stride instead of returning pre-sized dummy features.
            def __call__(self, audio):
                features = F.avg_pool1d(audio.unsqueeze(1), 400, stride=320).transpose(1, 2)
                return {"last_hidden_state":features.expand(-1, -1, 2)}
        self.generated_frames = []
        def infer(features, lengths, pitch, pitchf, sid):
            count = lengths.item()
            self.generated_frames.append(count)
            if pitch is not None:
                self.assertEqual(pitch.shape[1], count)
                self.assertEqual(pitchf.shape[1], count)
            waveform = features[0, :count, 0].repeat_interleave(rate // 100)
            return (waveform.view(1, 1, -1),)
        return ValidCNN(), SimpleNamespace(infer=infer)

    def test_valid_cnn_tail_and_partial_frames_preserve_source_timeline_for_all_rates(self):
        for rate in (16000, 32000, 40000, 48000):
            for frames in (19200, 19213):
                for f0 in (False, True):
                    with self.subTest(rate=rate, frames=frames, f0=f0):
                        pipeline = self.pipeline(rate)
                        model, generator = self.model_and_generator(rate)
                        audio = (.3 + np.linspace(0, .2, frames)).astype("float32")
                        actual = pipeline.pipeline(model, generator, 0, audio, 0, "rmvpe", "", 0., f0, 1., "v2", .5, False, 1., False, 155.)
                        self.assertEqual(len(actual), round(frames * rate / 16000))
                        self.assertTrue(np.isfinite(actual).all())
                        self.assertGreater(np.min(actual[-rate // 100:]), 0)

    def test_segment_lookahead_has_no_accumulating_f0_or_no_f0_duration_drift(self):
        for rate in (16000, 32000, 40000, 48000):
            for f0 in (False, True):
                with self.subTest(rate=rate, f0=f0):
                    pipeline = self.pipeline(rate, split=True)
                    model, generator = self.model_and_generator(rate)
                    audio = (.3 + np.sin(np.arange(5003) / 300) * .1).astype("float32")
                    actual = pipeline.pipeline(model, generator, 0, audio, 0, "rmvpe", "", 0., f0, 1., "v2", .5, False, 1., False, 155.)
                    self.assertGreaterEqual(len(self.generated_frames), 3)
                    self.assertEqual(len(actual), round(len(audio) * rate / 16000))
                    self.assertGreater(actual[-1], 0)


class CheckpointArchiveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "model.pth"

    def test_stored_torch_zip_loads_with_mmap_and_legacy_fails_before_torch_load(self):
        torch.save({"weight":torch.ones(3)}, self.path)
        self.assertTrue(checkpoint_archive_precheck(self.path))
        converter = VoiceConverter("cpu")
        converter.load_model(str(self.path))
        np.testing.assert_array_equal(converter.cpt["weight"].numpy(), 1)
        converter.cpt = None
        torch.save({"weight":torch.ones(3)}, self.path, _use_new_zipfile_serialization=False)
        with patch.object(torch, "load", side_effect=AssertionError("unsafe legacy load")):
            with self.assertRaisesRegex(ValueError, "ZIP olmayan"):
                converter.load_model(str(self.path))

    def test_oversized_metadata_and_compressed_members_are_rejected_without_extracting(self):
        with zipfile.ZipFile(self.path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("archive/data.pkl", b"x")
        data = self.path.read_bytes()
        offset = data.index(b"PK\x01\x02")
        forged = data[:offset + 24] + struct.pack("<I", 17 * 1024**2) + data[offset + 28:]
        self.path.write_bytes(forged)
        with self.assertRaisesRegex(ValueError, "metadata boyutu"):
            checkpoint_archive_precheck(self.path)
        with zipfile.ZipFile(self.path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("archive/data.pkl", b"x" * 1024)
        with self.assertRaisesRegex(ValueError, "sıkıştırılmış"):
            checkpoint_archive_precheck(self.path)

    def test_false_member_count_and_zip64_giant_counts_fail_before_zipinfo_allocation(self):
        with zipfile.ZipFile(self.path, "w") as archive:
            archive.writestr("archive/data.pkl", b"x")
            archive.writestr("archive/version", b"3")
        data = self.path.read_bytes()
        end = data.rfind(b"PK\x05\x06")
        forged = data[:end + 8] + struct.pack("<HH", 1, 1) + data[end + 12:]
        self.path.write_bytes(forged)
        with patch.object(zipfile, "ZipFile", side_effect=AssertionError("ZipInfo allocated first")):
            with self.assertRaisesRegex(ValueError, "üye sayacı"):
                checkpoint_archive_precheck(self.path)
        torch.save({"weight":torch.ones(3)}, self.path)
        data = self.path.read_bytes()
        start = data.index(b"PK\x06\x06")
        self.path.write_bytes(data[:start + 24] + struct.pack("<QQ", 2**63, 2**63) + data[start + 40:])
        with patch.object(zipfile, "ZipFile", side_effect=AssertionError("ZipInfo allocated first")):
            with self.assertRaisesRegex(ValueError, "üye/metadata"):
                checkpoint_archive_precheck(self.path)

    def test_checkpoint_native_ram_preflight_rejects_small_file_before_load(self):
        torch.save({"weight":torch.ones(3)}, self.path)
        with self.assertRaisesRegex(ValueError, "RAM sınırı"):
            checkpoint_archive_precheck(self.path, available_ram=100)


class HelperAndPolicyTests(unittest.TestCase):
    def test_custom_embedder_dimensions_stride_and_size_fail_before_pretrained_load(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            config = {'model_type':'hubert','hidden_size':768,'intermediate_size':3072,
                      'num_hidden_layers':12,'num_attention_heads':12,'classifier_proj_size':256,
                      'conv_dim':[512]*7,'conv_kernel':[10,3,3,3,3,2,2],'conv_stride':[5,2,2,2,2,2,2]}
            path = Path(folder) / "config.json"
            for updates, version in (({"hidden_size":2**30}, None), ({"conv_stride":[5,2,2,2,2,2,4]}, None), ({"hidden_size":1024,"num_attention_heads":16}, "v2"), ({"classifier_proj_size":768}, "v1")):
                path.write_text(json.dumps(config | updates), encoding="utf-8")
                with patch.object(audio_utils.HubertModelWithFinalProj, "from_pretrained", side_effect=AssertionError("unbounded or incompatible embedder load")):
                    with self.assertRaises(ValueError):
                        audio_utils.load_embedding("custom", folder, allow_download=False, rvc_version=version)
            path.write_bytes(b" " * (1024**2 + 1))
            with self.assertRaisesRegex(ValueError, "boyut sınırı"):
                audio_utils.load_embedding("custom", folder, allow_download=False)

    def test_standalone_embedder_download_rejects_wrong_publisher_digest_before_replace(self):
        class Response(io.BytesIO):
            headers = {"Content-Length":"2"}
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            with patch.object(audio_utils, "model_directory", return_value=str(root / "models")), patch.object(audio_utils, "app_directory", return_value=folder), patch("app_runtime.urllib.request.urlopen", return_value=Response(b"{}")), patch.object(audio_utils.HubertModelWithFinalProj, "from_pretrained", side_effect=AssertionError("unverified helper load")):
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    audio_utils.load_embedding("contentvec", allow_download=True)
            self.assertFalse((root / "models/embedders/contentvec/config.json").exists())
            self.assertEqual(list((root / "models/embedders/contentvec").iterdir()), [])

    def test_xpu_configuration_preserves_selected_and_detected_backend(self):
        api = SimpleNamespace(is_available=lambda:True, device_count=lambda:1,
                              get_device_name=lambda index:"Intel test device",
                              get_device_properties=lambda index:SimpleNamespace(total_memory=8 * 1024**3))
        with patch.object(torch, "xpu", api), patch.object(torch.cuda, "is_available", return_value=False):
            self.assertEqual(Config("xpu:0").device, "xpu:0")
            self.assertEqual(Config().device, "xpu:0")
            self.assertEqual(Config(torch.device("xpu")).device, "xpu:0")
        self.assertEqual(Config(torch.device("cpu")).device, "cpu")

    def test_oversized_or_inconsistent_architecture_is_rejected_before_network_allocation(self):
        valid = inference_config(architecture(40000))
        for position, invalid in ((2, 2**30), (6, 100000), (10, [3] * 100000), (12, [2] * 100000), (17, 2**31), (8, float("nan"))):
            config = list(valid)
            config[position] = invalid
            converter = VoiceConverter("cpu")
            converter.cpt = {"config":config, "weight":{"emb_g.weight":torch.zeros(1, 256)}, "version":"v2"}
            with patch("rvc.infer.infer.Synthesizer", side_effect=AssertionError("allocation before bounds")):
                with self.assertRaises(ValueError):
                    converter.setup_network()

    def test_standard_24_32_40_48k_architectures_validate_and_legacy_weightnorm_shapes_match(self):
        for rate in (24000, 32000, 40000, 48000):
            config = inference_config(architecture(rate)) if rate != 24000 else inference_config(Config("cpu").json_config["24000.json"])
            self.assertEqual(validate_architecture(config, {"emb_g.weight":torch.zeros(1, 256)})[-1], rate)
        model = torch.nn.Sequential(torch.nn.Linear(2, 3))
        torch.nn.utils.parametrizations.weight_norm(model[0])
        current = model.state_dict()
        validate_weights(model, current)
        legacy = {key.replace("parametrizations.weight.original0", "weight_g").replace("parametrizations.weight.original1", "weight_v"):value for key, value in current.items()}
        validate_weights(model, legacy)
        current["0.bias"][0] = float("nan")
        with self.assertRaisesRegex(ValueError, "sonlu"):
            validate_weights(model, current)

    def test_combined_architecture_parameter_limit_uses_meta_without_tensor_allocation(self):
        with torch.device("meta"):
            model = torch.nn.Linear(100000, 100000)
        with self.assertRaisesRegex(ValueError, "parametre bellek sınırı"):
            validate_meta_network(model)

    def test_large_decoded_audio_header_fails_before_waveform_allocation(self):
        info = SimpleNamespace(frames=48000 * 36000, channels=8, samplerate=48000)
        with patch("rvc.lib.utils.sf.info", return_value=info), patch("rvc.infer.safe_index.available_memory", return_value=8 * 1024**3), patch("rvc.lib.utils.sf.read", side_effect=AssertionError("large allocation")):
            with self.assertRaisesRegex(ValueError, "tahmini RAM.*kullanılabilir RAM"):
                validate_audio_memory("large.wav")

    def test_cache_reuses_device_and_file_key_and_releases_evicted_reference(self):
        cache = InferenceHelperCache(2)
        class Helper: pass
        first = cache.get_or_create(("cpu", "file-a"), Helper)
        reference = weakref.ref(first)
        self.assertIs(cache.get_or_create(("cpu", "file-a"), Helper), first)
        del first
        cache.get_or_create(("cuda:0", "file-a"), Helper)
        cache.get_or_create(("cpu", "file-b"), Helper)
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(len(cache), 2)
        cache.clear()
        self.assertEqual(len(cache), 0)

    def test_model_switch_preserves_helpers_but_failure_clears_generator(self):
        converter = VoiceConverter("cpu")
        helper = object()
        converter.hubert_model = helper
        converter.helper_cache.get_or_create(("cpu", "hubert"), lambda: helper)
        converter.loaded_model = "old"
        converter.net_g = object()
        with patch.object(converter, "load_model", side_effect=ValueError("invalid model")):
            with self.assertRaises(ValueError):
                converter.get_vc("new", 0)
        self.assertIsNone(converter.net_g)
        self.assertIs(converter.hubert_model, helper)
        self.assertEqual(len(converter.helper_cache), 1)
        converter.cleanup_model()
        self.assertIsNone(converter.hubert_model)
        self.assertEqual(len(converter.helper_cache), 0)

    def test_checkpoint_embedder_metadata_rejects_mismatch_and_allows_explicit_match(self):
        converter = VoiceConverter("cpu")
        converter.cpt = {"embedder_model": "spin"}
        with self.assertRaisesRegex(ValueError, "spin.*contentvec"):
            converter.validate_embedder("contentvec")
        converter.validate_embedder("spin")
        converter.cpt = {}
        converter.validate_embedder("contentvec")
        converter.cpt = {"embedder_model": "custom"}
        with self.assertRaisesRegex(ValueError, "özel embedder"):
            converter.validate_embedder("custom")

    def test_fixed_rvc_hop_rejects_ignored_api_values_before_any_model_load(self):
        converter = VoiceConverter("cpu")
        for bad in (128, 0, True, 160.5):
            with self.assertRaisesRegex(ValueError, "100 fps"):
                converter.convert_audio("none", "none", "none", "", hop_length=bad)

    def test_explicit_smoothing_policy_preserves_unvoiced_frames(self):
        f0 = np.r_[0., np.linspace(80., 250., 24), 0.].astype("float32")
        predictor = SimpleNamespace(get_f0=lambda *args, **kwargs: f0.copy())
        raw = Pipeline(16000, Config("cpu"), quality_policy=InferenceQualityPolicy(smooth_pitch=False))
        filtered = Pipeline(16000, Config("cpu"))
        with patch("rvc.infer.pipeline.RMVPE", return_value=predictor):
            _, actual = raw.get_f0(np.zeros(1600), len(f0))
            _, smoothed = filtered.get_f0(np.zeros(1600), len(f0))
        np.testing.assert_array_equal(actual, f0)
        self.assertEqual(smoothed[0], 0)
        self.assertEqual(smoothed[-1], 0)
        self.assertFalse(np.array_equal(actual, smoothed))

    def test_cpu_audio_segments_do_not_empty_global_cuda_cache(self):
        pipeline = Pipeline(16000, Config("cpu"))
        model = lambda audio: {"last_hidden_state": torch.ones(1, 4, 2)}
        generator = SimpleNamespace(infer=lambda *args: (torch.zeros(1, 1, 480),))
        with patch.object(torch.cuda, "empty_cache", side_effect=AssertionError("unselected GPU")):
            pipeline.voice_conversion(model, generator, torch.tensor([0]), np.zeros(640), None, None, None, None, 0., "v2", .5)


if __name__ == "__main__":
    unittest.main()
