"""Report-driven safeguards: grouped splits, pitch summaries and backend policy."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from training.config import TrainingOptions
from training.dataset import source_splits, prepare
from training.pitch_quality import PitchSummary
from training.index import build_index

ROOT=Path(__file__).resolve().parents[1]


class ReportSafeguardTests(unittest.TestCase):
    def test_song_variants_stay_together(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            paths=[Path(folder)/f'{i}.wav' for i in range(4)]
            for i,path in enumerate(paths): path.write_bytes(str(i).encode())
            rows=source_splits(paths,.5,1234,groups=('song1','song1','song2','song2'))
            assignments={row['path']:row['split'] for row in rows}
            self.assertEqual(assignments[str(paths[0])],assignments[str(paths[1])])
            self.assertEqual(assignments[str(paths[2])],assignments[str(paths[3])])
            self.assertNotEqual(assignments[str(paths[0])],assignments[str(paths[2])])

    def test_duplicate_links_manual_groups_transitively(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            paths=[Path(folder)/f'{i}.wav' for i in range(5)]
            for path,content in zip(paths,[b'a',b'b',b'a',b'c',b'd']): path.write_bytes(content)
            rows=source_splits(paths,.5,3,groups=('one','one','two','two','other'))
            groups={row['path']:row['group_id'] for row in rows}
            self.assertEqual(groups[str(paths[0])],groups[str(paths[1])])
            self.assertEqual(groups[str(paths[0])],groups[str(paths[3])])
            self.assertNotEqual(groups[str(paths[0])],groups[str(paths[4])])

    def test_only_one_group_cannot_be_split_between_variants(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            paths=[Path(folder)/f'{i}.wav' for i in range(2)]
            for i,path in enumerate(paths): path.write_bytes(str(i).encode())
            with self.assertRaisesRegex(ValueError,'Bağımsız değerlendirme'):
                prepare(folder,TrainingOptions('voice',tuple(map(str,paths)),source_groups=('song','song')),lambda *a,**k:None)

    def test_pitch_summary_keeps_unvoiced_and_flags_bounds(self):
        summary=PitchSummary()
        f0=np.array([0,0,40,220,220,220,1200],dtype=np.float32)
        original=f0.copy()
        summary.add(f0)
        result=summary.result()
        self.assertEqual(result['frames'],7)
        self.assertEqual(result['voiced_frames'],5)
        self.assertAlmostEqual(result['out_of_range_fraction'],.4)
        self.assertAlmostEqual(result['median_hz'],220,delta=2)
        np.testing.assert_array_equal(f0,original)
        self.assertEqual(sum(result['histogram']),5)
        self.assertIn('benzersiz',result['note'])

    def test_silent_pitch_has_no_fake_pitch_percentile(self):
        summary=PitchSummary()
        summary.add(np.zeros(100))
        self.assertIsNone(summary.result()['median_hz'])

    def test_legacy_options_normalize_and_bad_groups_reject(self):
        previous=TrainingOptions('voice',('x.wav',)).to_dict()
        previous.pop('source_groups')
        self.assertEqual(TrainingOptions.from_dict(previous).source_groups,())
        with self.assertRaises(ValueError):
            TrainingOptions('voice',('x.wav',),source_groups=('one','two')).validate(False)
        with self.assertRaises(ValueError):
            TrainingOptions.from_dict({**previous,'source_groups':'x'})

    def test_index_rejects_shared_train_validation_features(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            shared=Path(folder)/'features.npy'
            np.save(shared,np.zeros((10,768),np.float32))
            with self.assertRaisesRegex(ValueError,'değerlendirmede'):
                build_index(folder,{'pieces':[{'split':'train','features':str(shared)},
                                             {'split':'holdout','features':str(shared)}]},1,lambda *a,**k:None)
            self.assertFalse((Path(folder)/'voice.index').exists())

    def test_windows_rocm_is_not_treated_as_training_support(self):
        import hardware
        with patch.object(hardware.os,'name','nt'),patch('torch.version.hip','7.2'),patch('torch.__version__','2.11.0'):
            with self.assertRaisesRegex(RuntimeError,'resmi eğitim desteği doğrulanmamış'):
                hardware.ensure_training_backend('cuda:0')
            hardware.ensure_training_backend('cpu')
