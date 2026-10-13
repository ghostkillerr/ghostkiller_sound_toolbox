"""VR framing, sample precision and strict native stem writing."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import numpy as np
import soundfile as sf
from separation_audio import reflected_vr_input,trim_to_source_duration,write_flac24,finite_values
ROOT = Path(__file__).resolve().parents[1]


class SeparationAudioTests(unittest.TestCase):
    def test_raw_complex_spectrum_rejects_nonfinite_before_library_sanitizes_it(self):
        data = np.ones((2,64,17),dtype=np.complex64)
        finite_values(data)
        data[1,5,4] = complex(float('nan'),0.)
        with self.assertRaisesRegex(ValueError,'NaN'):
            finite_values(data)
    def test_owned_tail_context_preserves_original_samples_and_metadata(self):
        for rate in (32000,44100,48000):
            for channels in (1,2):
                with self.subTest(rate=rate,channels=channels),tempfile.TemporaryDirectory(dir=ROOT) as folder:
                    root = Path(folder)
                    source = root/'source.wav'
                    data = np.tile(np.linspace(-.5,.5,1777,dtype=np.float32)[:,None],(1,channels))
                    sf.write(source,data,rate,subtype='FLOAT')
                    original = source.read_bytes()
                    stage = root/'stage'
                    stage.mkdir()
                    path = reflected_vr_input(source,stage)
                    actual,sr = sf.read(path,dtype='float32',always_2d=True)
                    np.testing.assert_array_equal(actual[:len(data)],data)
                    self.assertEqual(sr,rate)
                    self.assertEqual(len(actual),len(data)+round(rate*.1))
                    self.assertTrue(np.any(actual[len(data):]))
                    self.assertEqual(source.read_bytes(),original)

    def test_crop_target_duration_and_refuse_short_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'output.flac'
            source = SimpleNamespace(frames=48001,samplerate=48000)
            expected = round(48001*44100/48000)
            signal = np.sin(np.arange(expected+500)*.02).astype('float32')*.5
            sf.write(path,signal,44100,subtype='PCM_24')
            before,_ = sf.read(path,dtype='float32')
            trim_to_source_duration(path,source)
            actual,_ = sf.read(path,dtype='float32')
            np.testing.assert_array_equal(actual,before[:expected])
            sf.write(path,signal[:expected-1],44100,subtype='PCM_24')
            with self.assertRaisesRegex(ValueError,'kısa ses'):
                trim_to_source_duration(path,source)

    def test_native_writer_preserves_sub_16bit_details_and_mono_silence(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            engine = SimpleNamespace(output_dir=folder,sample_rate=44100,
                                     normalization_threshold=.9,amplification_threshold=0.)
            data = (.1+np.arange(32,dtype='float32')/2**23)[:,None]
            write_flac24(engine,'details.flac',data)
            actual,_ = sf.read(Path(folder)/'details.flac',dtype='float32',always_2d=True)
            self.assertEqual(sf.info(Path(folder)/'details.flac').subtype,'PCM_24')
            self.assertGreater(len(np.unique(actual)),24)
            write_flac24(engine,'silence.flac',np.zeros((33,1),dtype='float32'))
            self.assertEqual(sf.info(Path(folder)/'silence.flac').frames,33)
            with self.assertRaisesRegex(ValueError,'NaN'):
                write_flac24(engine,'bad.flac',np.array([[np.nan]],dtype='float32'))


if __name__=='__main__': unittest.main()
