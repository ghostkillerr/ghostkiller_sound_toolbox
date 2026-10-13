"""Training isolation, holdout leakage, checkpoint and registration regressions."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch, Mock
import numpy as np
import soundfile as sf
from app_runtime import configure_runtime_cache, JOB_LOCK
configure_runtime_cache()
from training.config import TrainingOptions, architecture, inference_config
from training.dataset import prepare, source_splits, check_cancel
from training.storage import atomic_torch_save
from training.index import build_index
from training.service import TrainingProcess, register_model, create_job, validate_resume

ROOT = Path(__file__).resolve().parents[1]


class TrainingTests(unittest.TestCase):
    def test_invalid_settings_fail_before_launch(self):
        for values in ({"epochs":0},{"learning_rate":float('nan')},{"sample_rate":44100},
                       {"overlap_seconds":1,"segment_seconds":1},{"cpu_threads":0}):
            with self.assertRaises(ValueError):
                TrainingOptions("voice",("x.wav",),**values).validate(False)

    def test_single_speaker_export_config_matches_each_rate(self):
        for rate in (32000,40000,48000):
            cfg = inference_config(architecture(rate))
            self.assertEqual(len(cfg),18)
            self.assertEqual(cfg[-3],1)
            self.assertEqual(cfg[-1],rate)
            self.assertEqual(np.prod(cfg[12]),architecture(rate)["data"]["hop_length"])

    def test_duplicate_sources_cannot_leak_across_holdout(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            paths = [Path(folder)/f"{i}.wav" for i in range(3)]
            for i,p in enumerate(paths):
                p.write_bytes(b"same" if i<2 else b"other")
            rows = source_splits(paths,.1,1234)
            self.assertEqual(len(rows),2)
            self.assertEqual({p['split'] for p in rows},{'train','holdout'})

    def test_timeline_holdout_never_overlaps_training_segments(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            source = root/'source.wav'
            audio = .1*np.sin(2*np.pi*220*np.arange(40000*30)/40000)
            sf.write(source,audio,40000,subtype='FLOAT')
            job = root/'job'
            job.mkdir()
            def decode_copy(source,target,rate,job):
                import shutil
                shutil.copyfile(source,target)
            with patch('training.dataset.decode',side_effect=decode_copy), patch('training.dataset.subprocess.run',return_value=SimpleNamespace(stdout=b'30\n',returncode=0)):
                result = prepare(job,TrainingOptions('voice',(str(source),)),lambda *a,**k:None)
            train = [p for p in result['pieces'] if p['split']=='train']
            holdout = [p for p in result['pieces'] if p['split']=='holdout']
            self.assertLessEqual(max(p['start']+p['frames'] for p in train),min(p['start'] for p in holdout))
            self.assertEqual(sf.info(train[0]['audio']).subtype,'FLOAT')

    def test_missing_pretrained_prevents_job_creation(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            source=Path(folder)/'source.wav'
            source.touch()
            settings=SimpleNamespace(prepare_job=Mock(return_value='cpu'),
                                     manager=SimpleNamespace(require_ready=Mock(side_effect=RuntimeError('missing G/D'))))
            with patch('training.service.data_directory',return_value=folder):
                with self.assertRaisesRegex(RuntimeError,'missing G/D'):
                    create_job(TrainingOptions('voice',(str(source),)),settings)
            self.assertFalse((Path(folder)/'training_runs').exists())

    def test_changed_pretrained_identity_rejects_resume(self):
        from training.config import BACKEND_COMMIT,FORMAT_VERSION
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            manifest={'format_version':FORMAT_VERSION,'backend_commit':BACKEND_COMMIT,
                      'options':TrainingOptions('voice',('removed_source.wav',)).to_dict(),
                      'asset_records':{'contentvec':{'files':{'x.bin':{'sha256':'old'}}}}}
            (Path(folder)/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            settings=SimpleNamespace(prepare_job=Mock(return_value='cpu'),
                                     manager=SimpleNamespace(require_ready=Mock(),records={'contentvec':{'files':{'x.bin':{'sha256':'changed'}}}}))
            with self.assertRaises(ValueError):
                validate_resume(folder,settings)

    def test_cover_registry_controls_block_while_training_is_running(self):
        import wx
        import ui_cover
        app=wx.GetApp() or wx.App(False)
        frame=wx.Frame(None)
        try:
            with patch.object(ui_cover,'load_models',return_value={}):
                panel=ui_cover.CoverPanel(frame)
            JOB_LOCK.acquire()
            with patch.object(wx,'MessageBox'),patch.object(wx,'TextEntryDialog') as dialog,patch.object(ui_cover,'save_models') as save:
                panel.OnAddModel(None)
                panel.OnDelModel(None)
                dialog.assert_not_called()
                save.assert_not_called()
        finally:
            if JOB_LOCK.locked():
                JOB_LOCK.release()
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_flat_index_small_dataset_excludes_holdout(self):
        import faiss
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            paths=[]
            for name,value in (('train',1),('holdout',100)):
                path=root/f'{name}.npy'
                np.save(path,np.full((8,768),value,dtype='float32'))
                paths.append({'features':str(path),'split':name})
            index_path,count=build_index(root,{'pieces':paths},1,lambda *a,**k:None)
            index=faiss.read_index(index_path)
            self.assertEqual(count,8)
            self.assertEqual(index.ntotal,8)
            np.testing.assert_array_equal(index.reconstruct(0),np.ones(768,dtype='float32'))

    def test_exact_index_keeps_all_vectors_and_finds_true_neighbors(self):
        import faiss
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path=Path(folder)/'features.npy'
            features=np.random.default_rng(1).normal(size=(100,768)).astype('float32')
            np.save(path,features)
            index_path,count=build_index(folder,{'pieces':[{'features':str(path),'split':'train'}]},1,lambda *a,**k:None)
            self.assertEqual(count,100)
            index=faiss.read_index(index_path)
            self.assertEqual(index.ntotal,100)
            query=np.random.default_rng(5).normal(size=(1,768)).astype('float32')
            _,ids=index.search(query,8)
            reference=np.argsort(np.sum((features-query)**2,axis=1))[:8]
            np.testing.assert_array_equal(ids[0],reference)

    def test_atomic_checkpoint_failure_preserves_previous(self):
        import torch
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path=Path(folder)/'resume.pth'
            atomic_torch_save({'step':1,'tensor':torch.ones(3)},path)
            before=path.read_bytes()
            with patch('torch.save',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    atomic_torch_save({'step':2},path)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(list(Path(folder).glob('*.part')),[])

    def test_evaluation_before_resume_does_not_poison_backward_cache(self):
        import torch
        from training.engine import evaluate,mel
        from training.vendor import mel_processing
        mel_processing.hann_window.clear()
        mel_processing.mel_basis.clear()
        class Generator(torch.nn.Module):
            def infer(self,phone,lengths,pitch,pitchf,sid):
                return torch.ones(1,1,16000)*.01,None,None
        sample=(torch.ones(1025,40),torch.ones(1,16000)*.01,
                torch.ones(40,768),torch.ones(40,dtype=torch.long),torch.ones(40)*220,
                torch.tensor([0]))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            cfg=architecture(40000)
            score=evaluate(Generator(),[sample],cfg,'cpu',folder)
            self.assertTrue(np.isfinite(score))
            audio=torch.randn(1,1,16000,requires_grad=True)
            mel(audio,cfg).sum().backward()
            self.assertTrue(torch.isfinite(audio.grad).all())
        mel_processing.hann_window.clear()
        mel_processing.mel_basis.clear()

    def test_cancel_survives_subprocess_startup(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            runner=TrainingProcess()
            runner.job=folder
            runner.cancel()
            with self.assertRaises(InterruptedError):
                check_cancel(folder)

    def test_file_ipc_skips_old_events_and_keeps_stage_order(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            (root/'manifest.json').write_text(json.dumps({'options':TrainingOptions('voice',('x',)).to_dict()}))
            events=root/'events.jsonl'
            events.write_text(json.dumps({'stage':'old','time':0})+'\n')
            (root/'result.json').write_text(json.dumps({'success':True}))
            def spawn(*args,**kwargs):
                with events.open('a') as stream:
                    for value in ({'stage':'features','time':1},{'stage':'features','time':2},
                                  {'stage':'smoke','time':3},{'stage':'completed','time':4}):
                        stream.write(json.dumps(value)+'\n')
                return SimpleNamespace(poll=lambda:0,returncode=0)
            received=[]
            with patch('training.service.subprocess.Popen',side_effect=spawn):
                result=TrainingProcess().run(folder,received.append)
            self.assertTrue(result['success'])
            self.assertEqual([r['stage'] for r in received],['features','smoke','completed'])
            self.assertEqual(received[0]['time'],2)

    def test_registration_refuses_changed_model_and_duplicate_name(self):
        from model_manager import file_digest
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            model,index=root/'latest.pth',root/'voice.index'
            model.write_bytes(b'model')
            index.write_bytes(b'index')
            (root/'manifest.json').write_text(json.dumps({'status':'completed','options':{'name':'voice'}}))
            record={'file':'latest.pth','pth':str(model),'sha256':file_digest(model),'smoke_passed':True}
            result={'models':[record],'index':str(index),'index_sha256':file_digest(index)}
            (root/'result.json').write_text(json.dumps(result))
            registry=root/'registry.json'
            model.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                register_model(root,'latest.pth',registry)
            self.assertFalse(registry.exists())
            model.write_bytes(b'model')
            register_model(root,'latest.pth',registry)
            saved=json.loads(registry.read_text())['voice']
            self.assertNotEqual(saved['pth'],str(model))
            self.assertEqual(Path(saved['pth']).read_bytes(),b'model')
            self.assertEqual(Path(saved['index']).read_bytes(),b'index')
            before=registry.read_bytes()
            with self.assertRaises(ValueError):
                register_model(root,'latest.pth',registry)
            self.assertEqual(registry.read_bytes(),before)

    def test_training_ui_shared_settings_and_thread_failure(self):
        import wx
        import ui_training
        app=wx.GetApp() or wx.App(False)
        frame=wx.Frame(None)
        try:
            settings=SimpleNamespace(open_settings=Mock())
            panel=ui_training.TrainingPanel(frame,settings)
            self.assertIs(panel.settings,settings)
            self.assertEqual(panel.batch.GetValue(),0)
            panel.advanced_toggle.SetValue(True)
            panel.OnAdvanced(None)
            self.assertTrue(panel.advanced.IsShown())
            panel.EnableUI(False)
            self.assertFalse(panel.btn_start.IsEnabled())
            panel.EnableUI(True)
            with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch.object(panel,'Options'),patch('ui_training.create_job',return_value=folder),patch('ui_training.threading.Thread',side_effect=RuntimeError('thread failed')),patch.object(wx,'MessageBox'):
                panel.Start(False)
                self.assertFalse(JOB_LOCK.locked())
                self.assertTrue(panel.btn_start.IsEnabled())
                self.assertFalse(panel.btn_cancel.IsEnabled())
        finally:
            if JOB_LOCK.locked():
                JOB_LOCK.release()
            frame.Destroy()
            app.ProcessPendingEvents()


if __name__=='__main__':
    unittest.main()
