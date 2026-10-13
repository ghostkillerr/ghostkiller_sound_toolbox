"""Complete managed-network schemas, trust pinning and cache concurrency."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import torch
from model_manager import ModelManager, validate_file, validate_weight_schema

ROOT = Path(__file__).resolve().parents[1]


class ModelIntegrityReleaseTests(unittest.TestCase):
    def test_roformer_module_products_are_bounded_before_meta_construction(self):
        from model_manager import validate_separator_model_config
        for config in ({'num_stems':1_000_000},{'linear_transformer_depth':1_000_000},
                       {'depth':128,'time_transformer_depth':128,'freq_transformer_depth':128},
                       {'num_bands':2048,'num_stems':16,'mask_estimator_depth':128}):
            with self.subTest(config=config),self.assertRaisesRegex(ValueError,'sınır'):
                validate_separator_model_config(config)
        validate_separator_model_config({'linear_transformer_depth':0,'dim':384,'depth':12,'num_bands':60})

    def tiny_roformer(self):
        from audio_separator.separator.uvr_lib_v5.roformer.bs_roformer import BSRoformer
        config = {'dim':8,'depth':1,'stereo':True,'num_stems':1,'time_transformer_depth':1,
                  'freq_transformer_depth':1,'freqs_per_bands':(4,5),'dim_head':8,'heads':1,
                  'stft_n_fft':16,'stft_hop_length':4,'stft_win_length':16}
        with torch.device('meta'):
            expected = BSRoformer(**config).state_dict()
        return config,{key:torch.zeros(tensor.shape,dtype=tensor.dtype) for key,tensor in expected.items()}

    def test_full_roformer_schema_rejects_single_missing_or_wrong_weight(self):
        config,weights = self.tiny_roformer()
        validate_weight_schema(weights,'unit.ckpt',config)
        key = next(key for key in weights if key.startswith('layers.'))
        for broken in ({name:tensor for name,tensor in weights.items() if name!=key},
                       {**weights,key:torch.zeros(1)}):
            with self.assertRaisesRegex(ValueError,'ağırlığı eksik|boyutu uyumsuz'):
                validate_weight_schema(broken,'unit.ckpt',config)
        with self.assertRaisesRegex(ValueError,'yapılandırma gerekli'):
            validate_weight_schema(weights,'unit.ckpt')

    def test_nonfinite_separator_weight_rejected_before_schema(self):
        config,weights = self.tiny_roformer()
        key = next(key for key,tensor in weights.items() if tensor.numel())
        weights[key].reshape(-1)[0] = float('nan')
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'unit.ckpt'
            torch.save({'state_dict':weights},path)
            with self.assertRaisesRegex(ValueError,'NaN'):
                validate_file(path,'unit.ckpt',config=config)

    def test_only_pinned_rmvpe_unused_scalar_positive_inf_counter_is_exempt(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch('model_manager.validate_weight_schema',new=lambda *args:None):
            path = Path(folder)/'rmvpe.pt'
            cases = [({'bn.num_batches_tracked':torch.tensor(float('inf'))},True),
                     ({'bn.num_batches_tracked':torch.tensor(float('nan'))},False),
                     ({'bn.running_mean':torch.tensor(float('inf'))},False),
                     ({'bn.num_batches_tracked':torch.tensor([float('inf')])},False)]
            for weights,allowed in cases:
                torch.save(weights,path)
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.subTest(weights=list(weights),allowed=allowed),patch('model_manager.PUBLISHED_ASSET_HASHES',{'predictors/rmvpe.pt':digest}):
                    if allowed:
                        validate_file(path,'predictors/rmvpe.pt')
                    else:
                        with self.assertRaisesRegex(ValueError,'NaN|sonsuz'):
                            validate_file(path,'predictors/rmvpe.pt')
            torch.save(cases[0][0],path)
            with patch('model_manager.PUBLISHED_ASSET_HASHES',{'predictors/rmvpe.pt':'0'*64}),self.assertRaises(ValueError):
                validate_file(path,'predictors/rmvpe.pt')

    def test_published_hash_failure_preserves_old_model_without_first_record(self):
        from test_settings import Response,checkpoint_bytes
        import app_runtime
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch('model_manager.validate_weight_schema',new=lambda *args:None):
            manager = ModelManager(folder)
            path = Path(manager.path('predictors/rmvpe.pt'))
            path.parent.mkdir(parents=True)
            path.write_bytes(b'old damaged model')
            with patch.object(app_runtime.urllib.request,'urlopen',return_value=Response(checkpoint_bytes())):
                failures = manager.process(['rmvpe'],'repair')
            self.assertIn('SHA-256',failures['rmvpe'])
            self.assertEqual(path.read_bytes(),b'old damaged model')

    def test_stale_integrity_writers_merge_only_their_changed_model(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            first,second = ModelManager(folder),ModelManager(folder)
            first.records['contentvec'] = {'files':{},'schema_version':2}
            second.records['rmvpe'] = {'files':{},'schema_version':2}
            first.save('contentvec')
            second.save('rmvpe')
            self.assertEqual(set(ModelManager(folder).records),{'contentvec','rmvpe'})

    def test_stale_full_integrity_save_cannot_restore_an_older_record(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            first,second = ModelManager(folder),ModelManager(folder)
            first.records['shared'] = {'files':{},'schema_version':2,'tag':'new'}
            second.records['shared'] = {'files':{},'schema_version':2,'tag':'old'}
            first.save('shared')
            with self.assertRaisesRegex(ValueError,'başka işlemde'):
                second.save()
            self.assertEqual(ModelManager(folder).records['shared']['tag'],'new')


if __name__=='__main__': unittest.main()
