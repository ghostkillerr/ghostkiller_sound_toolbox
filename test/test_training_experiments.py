"""Experiment regressions: source integrity, exact extension, cache isolation and selection."""
from contextlib import ExitStack
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import numpy as np
import soundfile as sf

from app_settings import write_json_atomic
from model_manager import file_digest
from training.config import TrainingOptions
from training.experiments import (archive_snapshot, snapshot_records, save_notes, split_review,
                                  request_extension, resume_options_match, ExperimentQueue, save_preset)

ROOT = Path(__file__).resolve().parents[1]


class ExperimentTests(unittest.TestCase):
    def test_old_options_remain_readable_and_ranges_reject_nonfinite_or_short_audio(self):
        old = TrainingOptions('voice',('x.wav',)).to_dict()
        for key in ('source_ranges','snapshot_limit','snapshot_budget_mb','reuse_preparation','comparison_sources'):
            old.pop(key)
        self.assertEqual(TrainingOptions.from_dict(old).snapshot_limit,3)
        for intervals in (((-1,0),),((0,float('nan')),),((5,6),),((0,3),(0,4))):
            with self.assertRaises(ValueError):
                TrainingOptions('voice',('x.wav',),source_ranges=intervals).validate(False)

    def test_selected_timeline_segments_cannot_include_excluded_audio_or_cross_holdout(self):
        from training.dataset import prepare
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root=Path(temporary)
            source=root/'source.wav'
            audio=.1*np.sin(np.arange(32000*30)*2*np.pi*220/32000)
            sf.write(source,audio,32000,subtype='FLOAT')
            digest=file_digest(source)
            job=root/'job';job.mkdir()
            options=TrainingOptions('voice',(str(source),),sample_rate=32000,source_ranges=((5,25),))
            import shutil
            with patch('training.dataset.decode',side_effect=lambda s,t,*_:shutil.copyfile(s,t)),patch('training.dataset.subprocess.run',return_value=SimpleNamespace(stdout=b'30\n',returncode=0)):
                dataset=prepare(job,options,lambda *a,**k:None)
            train=[p for p in dataset['pieces'] if p['split']=='train']
            holdout=[p for p in dataset['pieces'] if p['split']=='holdout']
            self.assertGreaterEqual(min(p['start'] for p in train),5*32000)
            self.assertLessEqual(max(p['start']+p['frames'] for p in holdout),25*32000)
            self.assertLessEqual(max(p['start']+p['frames'] for p in train),min(p['start'] for p in holdout))
            self.assertEqual(file_digest(source),digest)

    def test_split_review_reports_selected_unique_time_and_real_group_fraction(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            paths=[Path(temporary)/f'{i}.wav' for i in range(3)]
            for i,path in enumerate(paths):path.write_bytes(str(i).encode())
            report={'sources':[{'path':str(p.resolve()),'seconds':n} for p,n in zip(paths,(100.,20.,20.))]}
            options=TrainingOptions('voice',tuple(map(str,paths)),source_groups=('a','b','b'),source_ranges=((10,90),(0,0),(0,0)))
            review=split_review(report,options)
            self.assertEqual(review['train_seconds']+review['holdout_seconds'],120)
            self.assertEqual(review['independent_groups'],2)
            self.assertIn(review['holdout_seconds'],(40.,80.))

    def test_split_review_cancels_during_the_final_source_hash_read(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            path = Path(temporary)/'large-source.wav'
            path.write_bytes(b'x'*(2*1024**2))
            options = TrainingOptions('voice',(str(path),))
            report = {'sources':[{'path':str(path.resolve()),'seconds':10.}]}
            checks = []
            def cancelled():
                checks.append(True)
                return len(checks)>=2
            with self.assertRaises(InterruptedError):
                split_review(report,options,cancelled)
            self.assertEqual(len(checks),2)

    def test_archive_retention_keeps_exactly_the_newest_requested_snapshots(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root=Path(temporary)
            for name in ('resume.pth','latest.pth','best_validation.pth'):(root/name).write_bytes(b'unchanged')
            options=TrainingOptions('voice',('unused',),snapshot_limit=2)
            archive_snapshot(root,options,1,10,1.)
            preferred=snapshot_records(root)[0]['file']
            save_notes(root,'sounds clearer',preferred)
            for epoch in (2,3,4):
                (root/'latest.pth').write_bytes(bytes([epoch]))
                archive_snapshot(root,options,epoch,epoch*10,1/epoch)
            records=snapshot_records(root)
            self.assertEqual(len(records),2)
            self.assertEqual({r['epoch'] for r in records},{3,4})
            self.assertEqual((root/'resume.pth').read_bytes(),b'unchanged')
            self.assertEqual((root/'best_validation.pth').read_bytes(),b'unchanged')
            self.assertEqual(len(list((root/'snapshots').glob('*.pth'))),2)

    def test_extension_authorizes_only_epoch_increase_for_the_recorded_checkpoint(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            job=Path(temporary)
            options=TrainingOptions('voice',('unused',),epochs=5)
            write_json_atomic(str(job/'manifest.json'),{'options':options.to_dict()})
            (job/'resume.pth').write_bytes(b'original checkpoint')
            requested=request_extension(job,10)
            self.assertTrue(resume_options_match(job,options.to_dict(),requested))
            self.assertFalse(resume_options_match(job,options.to_dict(),replace(requested,learning_rate=.0002)))
            (job/'resume.pth').write_bytes(b'changed checkpoint')
            self.assertFalse(resume_options_match(job,options.to_dict(),requested))
            with self.assertRaises(ValueError):request_extension(job,9)

    def test_queue_never_reclaims_running_jobs_after_reopen(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            source=Path(temporary)/'source.wav';source.touch()
            queue=ExperimentQueue(Path(temporary)/'queue.json')
            first=queue.add(TrainingOptions('first',(str(source),)))
            second=queue.add(TrainingOptions('second',(str(source),)))
            self.assertEqual(queue.claim()['id'],first['id'])
            reopened=ExperimentQueue(queue.path)
            self.assertEqual(reopened.claim()['id'],second['id'])
            self.assertIsNone(reopened.claim())
            self.assertEqual([r['status'] for r in reopened.read()],['running','running'])

    def test_templates_do_not_store_personal_recording_paths_or_groups(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            target=Path(temporary)/'presets.json'
            save_preset(target,'small',TrainingOptions('personal',('private.wav',),source_groups=('private song',)))
            value=target.read_text(encoding='utf-8')
            self.assertNotIn('private',value)
            self.assertNotIn('sources',json.loads(value)['small'])

    def test_epoch_extension_matches_uninterrupted_optimizer_weights_and_rng(self):
        import torch
        import training.engine as engine
        from training.storage import read_manifest
        options=TrainingOptions('exact',('unused',),epochs=3,batch_size=3,save_every=1)
        def step(info,g,d,og,od,config):
            x=torch.rand(1,1)
            for net,opt in ((g,og),(d,od)):
                opt.zero_grad();net(x).square().sum().backward();opt.step()
            return {'loss_g':1.,'loss_d':1.}
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary,ExitStack() as stack:
            for key,value in {'TextAudioLoaderMultiNSFsid':Mock(return_value=[1,2,3]),
                              'TextAudioCollateMultiNSFsid':Mock(return_value=lambda b:[torch.ones(1)]),
                              'model_pair':Mock(side_effect=lambda *a:(torch.nn.Linear(1,1),torch.nn.Linear(1,1))),
                              'load_pretrained':Mock(),'train_step':Mock(side_effect=step),'evaluate':Mock(return_value=1.),
                              'export_model':Mock(),'ResourceMonitor':Mock()}.items():
                stack.enter_context(patch.object(engine,key,value))
            baseline=Path(temporary)/'baseline';baseline.mkdir()
            extended=Path(temporary)/'extended';extended.mkdir()
            short=replace(options,epochs=2)
            for path,value in ((baseline,options),(extended,short)):
                write_json_atomic(str(path/'manifest.json'),{'options':value.to_dict()})
                engine.run_training(path,value,'cpu',temporary,lambda *a,**k:None)
            requested=request_extension(extended,3)
            engine.run_training(extended,requested,'cpu',temporary,lambda *a,**k:None,resume=True)
            expected=torch.load(baseline/'resume.pth',weights_only=True)
            actual=torch.load(extended/'resume.pth',weights_only=True)
            for key in ('generator','discriminator'):
                for name,tensor in expected[key].items():torch.testing.assert_close(actual[key][name],tensor,rtol=0,atol=0)
            self.assertEqual(expected['scheduler_g'],actual['scheduler_g'])
            torch.testing.assert_close(expected['torch_rng'],actual['torch_rng'],rtol=0,atol=0)
            self.assertEqual(read_manifest(extended)['extensions'][0]['to_epochs'],3)

    def test_fixed_listening_bank_uses_only_holdout_and_preserves_sources(self):
        from training.comparison import comparison_bank
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root=Path(temporary)
            pieces=[]
            for i in range(5):
                path=root/f'{i}.wav';path.write_bytes(bytes([i]))
                pieces.append({'audio':str(path),'split':'train' if i==0 else 'holdout',
                               'source_sha256':str(i//2),'start':i*100,'frames':100})
            bank=comparison_bank(root,{'pieces':pieces})
            self.assertEqual(len(bank),3)
            self.assertNotIn(str(root/'0.wav'),[r['audio'] for r in bank])
            self.assertEqual(len({r['source_sha256'] for r in bank}),3)

    def test_cache_copy_is_independent_and_corruption_falls_back_without_publishing_lists(self):
        from training.preparation_cache import publish,restore
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            parent=Path(temporary)
            source=parent/'source';source.mkdir()
            target=parent/'target';target.mkdir()
            piece={'split':'train','name':'train_0'}
            for field in ('audio','features','pitch','pitchf'):
                path=source/f'{field}.npy';path.write_bytes(field.encode());piece[field]=str(path)
            for name,value in (('dataset.json',{'pieces':[piece]}),('pitch_report.json',{}),('quality_report.json',{}),('manifest.json',{'status':'completed'})):
                write_json_atomic(str(source/name),value)
            publish(source,'key')
            self.assertTrue(restore(target,'key',lambda *a,**k:None))
            copied=json.loads((target/'dataset.json').read_text())['pieces'][0]
            self.assertTrue(all(Path(copied[k]).parent==target for k in ('audio','features','pitch','pitchf')))
            Path(copied['audio']).write_bytes(b'new session edit')
            self.assertEqual(Path(piece['audio']).read_bytes(),b'audio')
            Path(piece['features']).write_bytes(b'corrupt')
            third=parent/'third';third.mkdir()
            self.assertFalse(restore(third,'key',lambda *a,**k:None))
            self.assertFalse((third/'train.txt').exists())

    def test_native_ui_selects_archived_model_and_same_test_clip_with_index_off(self):
        import wx
        from ui_training import TrainingPanel
        app=wx.GetApp() or wx.App(False)
        frame=wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
                root=Path(temporary);audio=root/'listen.wav';audio.touch()
                panel=TrainingPanel(frame,SimpleNamespace(theme='light'))
                panel.job=str(root)
                panel.result={'models':[{'file':'snapshots/epoch_1.pth','epoch':1,'step':10,
                                          'tests':[{'label':'Same input','test_audio_no_index':str(audio)}]}]}
                panel.RefreshCandidates()
                with patch('ui_training.wx.LaunchDefaultApplication') as launch:
                    panel.OnListen(None)
                launch.assert_called_once_with(str(audio))
                panel.EnableUI(False)
                self.assertFalse(panel.btn_review.IsEnabled())
                self.assertFalse(panel.test_clip.IsEnabled())
                panel.EnableUI(True)
                self.assertTrue(panel.test_clip.IsEnabled())
        finally:
            frame.Destroy();app.ProcessPendingEvents()

    def test_external_listening_input_rejects_a_training_recording_copy(self):
        from training.comparison import comparison_bank
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root=Path(temporary)
            source=root/'source.wav';source.write_bytes(b'training recording')
            copied=root/'copy.wav';copied.write_bytes(source.read_bytes())
            piece={'audio':str(source),'split':'holdout','source_sha256':file_digest(source),'start':0,'frames':100}
            with self.assertRaisesRegex(ValueError,'kopyası'):
                comparison_bank(root,{'pieces':[piece]},TrainingOptions('voice',(str(source),),comparison_sources=(str(copied),)))
            self.assertEqual(copied.read_bytes(),b'training recording')

    def test_preparation_key_ignores_optimizer_but_tracks_data_pitch_and_backend(self):
        from training.preparation_cache import cache_key
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root=Path(temporary)
            source=root/'source.wav';source.write_bytes(b'audio')
            options=TrainingOptions('voice',(str(source),))
            manifest={'device':'cpu','torch_version':'fixture','asset_records':{},'trainer_revision':'same'}
            original=cache_key(root,options,manifest)
            self.assertEqual(original,cache_key(root,replace(options,learning_rate=.0002,epochs=400),manifest))
            for changed in (replace(options,f0_method='crepe'),replace(options,source_ranges=((2,10),)),
                            replace(options,source_groups=('same song',))):
                self.assertNotEqual(original,cache_key(root,changed,manifest))
            self.assertNotEqual(original,cache_key(root,options,{**manifest,'device':'cuda:0'}))
            source.write_bytes(b'changed audio')
            self.assertNotEqual(original,cache_key(root,options,manifest))

    def test_interrupted_fine_tune_setup_recovers_weights_before_resume_and_never_uses_pretrain_fallback(self):
        import torch
        from training.storage import freeze_initial_weights,read_manifest
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root=Path(temporary)
            parent=root/'parent';parent.mkdir()
            checkpoint=parent/'resume.pth'
            torch.save({'generator':{'weight':torch.tensor([7.])},'discriminator':{'weight':torch.tensor([9.])},
                        'optimizer_g':{'must_not_be_copied':True}},checkpoint)
            job=root/'new';job.mkdir()
            write_json_atomic(str(job/'manifest.json'),{'initial_from':{'checkpoint':str(checkpoint),'sha256':file_digest(checkpoint)}})
            # A power loss can leave either no initial file or a replaced file
            # without the follow-up manifest hash; both must be reconstructed.
            for partial in (False,True):
                (job/'initial_weights.pth').unlink(missing_ok=True)
                if partial:(job/'initial_weights.pth').write_bytes(b'uncommitted initial file')
                manifest=read_manifest(job);manifest.pop('initial_weights_sha256',None)
                write_json_atomic(str(job/'manifest.json'),manifest)
                self.assertTrue(freeze_initial_weights(job))
                state=torch.load(job/'initial_weights.pth',weights_only=True)
                self.assertEqual(set(state),{'generator','discriminator'})
                self.assertEqual(state['generator']['weight'].item(),7.)
                self.assertFalse(freeze_initial_weights(job))
            (job/'initial_weights.pth').write_bytes(b'corrupt committed state')
            with self.assertRaisesRegex(ValueError,'değişmiş'):freeze_initial_weights(job)
