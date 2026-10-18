"""Optional restoration: native accessibility, real files and workflow ordering."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf
import wx

from app_runtime import JOB_LOCK
from restoration import MODEL_ID
from restoration.audio import RATE, candidate_intervals
from restoration.engine import restore_file
import ui_separator
from test.test_workflows import Harness

ROOT = Path(__file__).resolve().parents[1]


def toggle(panel, control, active):
    control.SetValue(active)
    event = wx.CommandEvent(wx.EVT_TOGGLEBUTTON.typeId, control.GetId())
    event.SetEventObject(control)
    panel.OnCheckToggle(event)


class RestorationUI(unittest.TestCase):
    def setUp(self):
        self.terms = patch('ui_separator.confirm_restoration_terms',return_value=True)
        self.terms.start()
        self.addCleanup(self.terms.stop)

    def test_declining_model_terms_does_not_prepare_or_start_restoration(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                source = Path(folder)/'input.wav'
                source.touch()
                prepare = Mock(return_value='cpu')
                panel = ui_separator.SeparatorPanel(frame,SimpleNamespace(theme='light',prepare_job=prepare))
                panel.current_input_file = str(source)
                panel.output_directory = folder
                panel.chk_step2.SetValue(True)
                panel.chk_restore.SetValue(True)
                with patch('ui_separator.confirm_restoration_terms',return_value=False), \
                        patch('ui_separator.threading.Thread') as worker:
                    panel.OnStart(None)
                prepare.assert_not_called()
                worker.assert_not_called()
                self.assertFalse(JOB_LOCK.locked())
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_conditional_visibility_native_states_and_keyboard_order(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None,size=(850,850))
        try:
            panel = ui_separator.SeparatorPanel(frame,SimpleNamespace(theme='dark'))
            layout=wx.BoxSizer(wx.VERTICAL)
            layout.Add(panel,1,wx.EXPAND)
            frame.SetSizer(layout)
            frame.Show()
            app.Yield()
            child=panel.chk_restore
            self.assertFalse(child.IsShown())
            self.assertFalse(child.GetValue())
            panel.chk_step2.SetFocus()
            panel.chk_step2.Navigate(wx.NavigationKeyEvent.IsForward)
            app.Yield()
            self.assertIs(wx.Window.FindFocus(),panel.chk_step3)
            toggle(panel,panel.chk_step2,True)
            panel.chk_step2.SetFocus()
            panel.chk_step2.Navigate(wx.NavigationKeyEvent.IsForward)
            app.Yield()
            self.assertIs(wx.Window.FindFocus(),child)
            self.assertTrue(child.IsShown())
            self.assertEqual(child.GetAccessible().GetRole(wx.ACC_SELF),(wx.ACC_OK,wx.ROLE_SYSTEM_PUSHBUTTON))
            self.assertIn('mono',child.GetAccessible().GetHelpText(wx.ACC_SELF)[1])
            self.assertEqual(child.GetAccessible().DoDefaultAction(wx.ACC_SELF),wx.ACC_OK)
            self.assertIn('[AÇIK]',child.GetAccessible().GetName(wx.ACC_SELF)[1])
            self.assertTrue(child.GetAccessible().GetState(wx.ACC_SELF)[1]&wx.ACC_STATE_SYSTEM_PRESSED)
            child.Navigate(wx.NavigationKeyEvent.IsForward)
            app.Yield()
            self.assertIs(wx.Window.FindFocus(),panel.chk_step3)
            child.SetFocus()
            toggle(panel,panel.chk_step2,False)
            app.Yield()
            self.assertFalse(child.IsShown())
            self.assertFalse(child.GetValue())
            self.assertIn('[KAPALI]',child.GetAccessible().GetName(wx.ACC_SELF)[1])
            self.assertFalse(child.GetAccessible().GetState(wx.ACC_SELF)[1]&wx.ACC_STATE_SYSTEM_PRESSED)
            self.assertIs(wx.Window.FindFocus(),panel.chk_step2)
            toggle(panel,panel.chk_step2,True)
            panel.EnableUI(False)
            app.Yield()
            self.assertFalse(child.IsEnabled())
            self.assertTrue(child.GetAccessible().GetState(wx.ACC_SELF)[1]&wx.ACC_STATE_SYSTEM_UNAVAILABLE)
            self.assertEqual(child.GetAccessible().DoDefaultAction(wx.ACC_SELF),wx.ACC_FAIL)
            frame.Hide()
            app.Yield()
            self.assertTrue(child.GetAccessible().GetState(wx.ACC_SELF)[1]&wx.ACC_STATE_SYSTEM_INVISIBLE)
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_model_requested_only_when_parent_and_restoration_are_enabled(self):
        app=wx.GetApp() or wx.App(False)
        frame=wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=ROOT) as folder:
                prepare=Mock(return_value='cpu')
                panel=ui_separator.SeparatorPanel(frame,SimpleNamespace(theme='light',prepare_job=prepare))
                source=Path(folder)/'input.wav'
                source.touch()
                panel.current_input_file=str(source)
                panel.output_directory=folder
                for parent,child in ((False,True),(True,False),(True,True)):
                    panel.chk_step2.SetValue(parent)
                    panel.chk_restore.SetValue(child)
                    with patch('ui_separator.threading.Thread') as thread:
                        panel.OnStart(None)
                        self.assertEqual(MODEL_ID in prepare.call_args.args[0],parent and child)
                        self.assertEqual(thread.call_args.kwargs['kwargs']['restore_vocal'],parent and child)
                    JOB_LOCK.release()
                    panel.EnableUI(True)
        finally:
            if JOB_LOCK.locked(): JOB_LOCK.release()
            frame.Destroy()
            app.ProcessPendingEvents()


class RestorationFiles(unittest.TestCase):
    def test_duration_has_no_hour_cap_with_scaled_working_rate(self):
        # 3601 real seconds at 1 Hz; scale the working rate to avoid a multi-GB
        # fixture. The former 3600*RATE guard rejected this exact code path.
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            source=root/'long.wav'
            sf.write(source,np.zeros(3601),1,subtype='FLOAT')
            with patch('restoration.engine.RATE',1), patch('training.resources.memory_status',return_value={'available_ram_mb':1000}):
                result=restore_file(source,source,root/'long.flac',root,repair_factory=Mock())
            self.assertEqual(result['frames'],3601)
            self.assertEqual(sf.info(root/'long.flac').frames,3601)

    def test_combined_resampled_memory_is_checked_before_decoding(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            source=root/'voice.wav'
            sf.write(source,np.zeros(16000),16000)
            with patch('training.resources.memory_status',return_value={'available_ram_mb':1}), patch('soundfile.SoundFile') as decode:
                # sf.info itself uses SoundFile; provide metadata independently.
                with patch('soundfile.info',return_value=SimpleNamespace(frames=16000,samplerate=16000,channels=1)):
                    with self.assertRaises(MemoryError):
                        restore_file(source,source,root/'out.flac',root)
                decode.assert_not_called()
            self.assertFalse((root/'out.flac').exists())

    def test_streaming_resampling_keeps_length_and_output_samples(self):
        import soxr
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            source=root/'voice.wav'
            signal=.1*np.sin(np.arange(16000*5)*2*np.pi*220/16000)
            sf.write(source,signal,16000,subtype='FLOAT')
            result=restore_file(source,source,root/'out.flac',root)
            expected=soxr.resample(sf.read(source)[0],16000,RATE,quality='VHQ')
            actual=sf.read(root/'out.flac')[0]
            self.assertEqual(result['frames'],len(expected))
            np.testing.assert_allclose(actual,expected,atol=2e-7,rtol=0)

    def test_short_recording_supplies_full_sampler_window_and_trims_context(self):
        import torch
        from restoration.engine import A2SBRepair
        class Sampler:
            def fast_inpaint_ddpm_sample(owner,x,**kwargs):
                self.assertGreaterEqual(x.shape[-1],256)
                return [x]
        repair=A2SBRepair.__new__(A2SBRepair)
        repair.device,repair.sampler='cpu',Sampler()
        audio=np.sin(np.arange(RATE//2)*2*np.pi*220/RATE)*.1
        generated,left=repair.synthesize(audio,(.2,.3),1234)
        self.assertEqual(left,0)
        self.assertEqual(len(generated),len(audio))
        self.assertTrue(np.isfinite(generated).all())

    def test_mapped_archive_keeps_fixed_limits_and_rejects_legacy(self):
        import torch
        from rvc.infer.model_validation import checkpoint_archive_precheck
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            p=Path(folder)/'weights.pt'
            torch.save({'weight':torch.ones(4)},p)
            self.assertTrue(checkpoint_archive_precheck(p,mmap_only=True))
            with self.assertRaises(ValueError):
                checkpoint_archive_precheck(p,mmap_only=True,max_file_bytes=p.stat().st_size-1)
            torch.save({'weight':torch.ones(4)},p,_use_new_zipfile_serialization=False)
            with self.assertRaises(ValueError):
                checkpoint_archive_precheck(p,mmap_only=True,allow_legacy=True)

    def test_registered_network_shape_validation_rejects_missing_layer(self):
        import torch
        from restoration.engine import build_model
        from model_manager import validate_weight_schema
        with torch.device('meta'):
            model=build_model()
        self.assertEqual(sum(p.numel() for p in model.parameters()),565544851)
        weights={'vf_model.'+k:v for k,v in model.state_dict().items()}
        validate_weight_schema(weights,MODEL_ID)
        weights.pop(next(iter(weights)))
        with self.assertRaises(ValueError):
            validate_weight_schema(weights,MODEL_ID)

    def fixture(self,root):
        t=np.arange(3*RATE)/RATE
        reference=.2*np.sin(2*np.pi*220*t)
        cleaned=reference.copy()
        cleaned[round(1.3*RATE):round(1.5*RATE)] *= .05
        paths=[root/'reference.wav',root/'cleaned.wav']
        for p,x in zip(paths,(reference,cleaned)):
            sf.write(p,np.column_stack((x,x)),RATE,subtype='PCM_24')
        return paths

    def test_only_short_losses_are_selected_and_long_losses_are_reported(self):
        reference=np.full(5*RATE,.2)
        cleaned=reference.copy()
        cleaned[round(.8*RATE):round(1.0*RATE)]=0
        cleaned[round(2*RATE):round(3.3*RATE)]=0
        intervals,skipped=candidate_intervals(reference,cleaned)
        self.assertEqual(len(intervals),1)
        self.assertLess(intervals[0][0],1)
        self.assertGreaterEqual(skipped,1)

    def test_real_flac_preserves_inputs_and_samples_outside_local_patches(self):
        spans=[]
        class Repair:
            def __init__(self,*args): pass
            def synthesize(self,cleaned,interval,seed):
                spans.append(interval)
                return np.full_like(cleaned,.08),0
            def close(self): pass
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            ref,clean=self.fixture(root)
            original=[p.read_bytes() for p in (ref,clean)]
            output=root/'restored.flac'
            result=restore_file(ref,clean,output,root,repair_factory=Repair)
            data,rate=sf.read(output)
            baseline=sf.read(clean,always_2d=True)[0].mean(axis=1)
            outside=np.ones(len(data),bool)
            for a,b in spans:
                outside[max(0,round((a-.035)*RATE)):round((b+.035)*RATE)]=False
            self.assertEqual(result['repaired_intervals'],len(spans))
            self.assertTrue(spans)
            self.assertEqual(rate,RATE)
            self.assertEqual(data.ndim,1)
            self.assertEqual(sf.info(output).subtype,'PCM_24')
            np.testing.assert_array_equal(data[outside],baseline[outside])
            self.assertGreater(float(np.max(np.abs(data-baseline))),.01)
            self.assertEqual([p.read_bytes() for p in (ref,clean)],original)

    def test_model_failure_or_cancellation_leaves_no_partial_file(self):
        class Broken:
            def __init__(self,*args): pass
            def synthesize(self,*args): raise RuntimeError('model failed')
            def close(self): pass
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            ref,clean=self.fixture(root)
            output=root/'restored.flac'
            with self.assertRaisesRegex(RuntimeError,'model failed'):
                restore_file(ref,clean,output,root,repair_factory=Broken)
            self.assertFalse(output.exists())
            with self.assertRaises(InterruptedError):
                restore_file(ref,clean,output,root,cancelled=lambda:True)
            self.assertFalse(output.exists())
            with self.assertRaises(ValueError):
                restore_file(ref,clean,clean,root)

    def test_no_candidates_does_not_load_model(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            source=root/'voice.wav'
            sf.write(source,np.zeros(RATE),RATE)
            factory=Mock(side_effect=AssertionError('model must not load'))
            result=restore_file(source,source,root/'mono.flac',root,repair_factory=factory)
            self.assertEqual(result['repaired_intervals'],0)
            factory.assert_not_called()


class RestorationWorkflow(unittest.TestCase):
    def test_standard_and_repaired_are_saved_and_next_step_uses_repaired(self):
        for enabled in (False,True):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory(dir=ROOT) as folder, patch.object(ui_separator,'post_ui'), patch.object(wx,'CallAfter',side_effect=lambda fn,*args:fn(*args)):
                root=Path(folder)
                job=Harness(root)
                seen=[]
                next_inputs=[]
                def separate(source,model,label,stage):
                    seen.append(source)
                    if len(seen)>1:
                        next_inputs.append(sf.read(source)[0])
                    keyword='(No Reverb)' if 'DeReverb' in model else '(Vocals)'
                    path=Path(stage)/f'input_{keyword}.flac'
                    sf.write(path,np.full(160,.1),16000)
                    return [str(path)]
                def restore(reference,cleaned,stage):
                    self.assertEqual(reference,job.current_input_file)
                    self.assertTrue(Path(cleaned).is_file())
                    path=Path(stage)/'restored.flac'
                    sf.write(path,np.full(160,.2),16000)
                    return {'output':str(path),'repaired_intervals':1}
                job.RunSeparatorCommand=separate
                job.RunVocalRestoration=Mock(side_effect=restore)
                JOB_LOCK.acquire()
                ui_separator.SeparatorPanel.ProcessChain(job,(False,False,True,True,False),restore_vocal=enabled)
                standard=root/'input_2_ArkaSes_Silinmis.flac'
                repaired=root/'input_2_Onarilmis_Vokal.flac'
                self.assertTrue(standard.is_file())
                self.assertEqual(repaired.is_file(),enabled)
                self.assertEqual(job.RunVocalRestoration.call_count,int(enabled))
                self.assertEqual(Path(seen[1]).name,(repaired if enabled else standard).name)
                np.testing.assert_array_equal(next_inputs[0],sf.read(repaired if enabled else standard)[0])
                self.assertFalse(JOB_LOCK.locked())


if __name__=='__main__':
    unittest.main()
