"""Mode accessibility, local assets, streamed alignment and atomic cancellation."""
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import numpy as np
import soundfile as sf
import wx
from instruments import PROFILES
from instruments.engine import separate_file, RATE

ROOT = Path(__file__).resolve().parents[1]


class InstrumentTests(unittest.TestCase):
    def test_gui_owned_staging_is_cleaned_after_real_worker_force_stop_or_crash(self):
        from audio_service import NativeAudioSession
        from ui_separator import SeparatorPanel
        for mode in ('force','crash'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                root = Path(folder)
                output = root/'outputs'; output.mkdir()
                previous = output/'previous.flac'; previous.write_bytes(b'keep previous output')
                source = root/'source.wav'
                sf.write(source,np.full((4410,2),.1),RATE)
                worker = root/'fixture_worker.py'
                worker.write_text(
                    'import sys, time, os\nfrom pathlib import Path\n'
                    f'sys.path.insert(0,{str(ROOT)!r})\n'
                    'import instruments.models\n'
                    'class Model:\n'
                    ' def __call__(self,x):\n'
                    f"  Path({str(root/'entered')!r}).touch()\n"
                    + ('  os._exit(7)\n' if mode=='crash' else '  time.sleep(60)\n')
                    + '  return x[:,None].repeat(1,4,1,1)/4\n'
                    'instruments.models.load_model=lambda *args:Model()\n'
                    'from audio_worker import main\nraise SystemExit(main())\n',encoding='utf-8')
                sessions = []
                def factory():
                    session = NativeAudioSession(command=[sys.executable,str(worker)],directory=root/'sessions')
                    sessions.append(session)
                    return session
                panel = SimpleNamespace(audio_session=None,audio_session_factory=factory,
                    is_cancelled=False,model_dir=str(root),LogMessage=Mock(),UpdateStatus=Mock())
                with patch('ui_separator.post_ui'),patch('ui_separator.finish_job') as finished:
                    thread = threading.Thread(target=SeparatorPanel.ProcessInstruments,
                        args=(panel,str(source),str(output),'scnet',('bass',),'cpu'))
                    thread.start()
                    try:
                        deadline = time.monotonic()+30
                        while thread.is_alive() and time.monotonic()<deadline:
                            if (root/'entered').exists():
                                break
                            time.sleep(.05)
                        if mode=='force':
                            self.assertTrue((root/'entered').exists())
                            panel.is_cancelled=True
                            sessions[0].request_force_stop()
                    finally:
                        if mode=='force' and sessions:
                            sessions[0].request_force_stop()
                        thread.join(15)
                    self.assertFalse(thread.is_alive())
                    finished.assert_called_once_with(panel)
                self.assertIsNone(panel.audio_session)
                self.assertTrue((root/'entered').exists(),'The real worker must reach model inference.')
                self.assertEqual([p.name for p in output.iterdir()],['previous.flac'])
                self.assertEqual(previous.read_bytes(),b'keep previous output')

    def test_gui_publishes_only_completed_stems_and_returns_final_paths(self):
        from ui_separator import SeparatorPanel
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            source = root/'source.wav';source.touch()
            output = root/'outputs';output.mkdir()
            class Session:
                closed = False
                def execute(self,kind,payload,**kwargs):
                    path = Path(payload['output_dir']);path.mkdir()
                    (path/'bass.flac').write_bytes(b'completed fixture')
                    return {'directory':str(path),'files':{'bass':str(path/'bass.flac')}}
                def close(self): self.closed=True
            session = Session()
            panel = SimpleNamespace(audio_session=None,audio_session_factory=lambda:session,
                is_cancelled=False,model_dir=str(root),LogMessage=Mock(),UpdateStatus=Mock())
            with patch('ui_separator.post_ui'),patch('ui_separator.finish_job'):
                SeparatorPanel.ProcessInstruments(panel,str(source),str(output),'scnet',('bass',),'cpu')
            result = list(output.iterdir())
            self.assertEqual(len(result),1)
            self.assertEqual('source_Enstrumanlar',result[0].name)
            self.assertEqual((result[0]/'bass.flac').read_bytes(),b'completed fixture')
            self.assertEqual([p.name for p in result[0].iterdir()], ['bass.flac'])
            self.assertTrue(session.closed)
            self.assertIn(str(result[0]),panel.UpdateStatus.call_args.args[0])

    def test_declining_six_source_terms_does_not_start_the_job(self):
        from ui_separator import SeparatorPanel
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            source = Path(folder)/'source.wav';source.touch()
            panel = SimpleNamespace(current_input_file=str(source),output_directory=folder,
                instrument_profiles=['scnet','demucs6'],instrument_profile=Mock(),
                instrument_stems={stem:Mock() for stem in PROFILES['demucs6']['stems']},
                settings=SimpleNamespace(prepare_job=Mock()))
            panel.instrument_profile.GetSelection.return_value = 1
            panel.instrument_stems['bass'].GetValue.return_value = True
            with patch('ui_separator.confirm_demucs_terms',return_value=False), \
                    patch('ui_separator.threading.Thread') as worker:
                SeparatorPanel.OnInstrumentStart(panel)
            panel.settings.prepare_job.assert_not_called()
            worker.assert_not_called()

    def test_mode_switch_hides_unrelated_controls_and_updates_tab_targets(self):
        from ui_separator import SeparatorPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None,size=(850,850))
        try:
            panel=SeparatorPanel(frame,SimpleNamespace(theme='light'))
            frame.Show();app.Yield()
            self.assertFalse(panel.instrument_panel.IsShown())
            self.assertTrue(panel.chk_step1.IsShown())
            panel.mode_choice.SetSelection(1);panel.OnMode(None);app.Yield()
            self.assertFalse(panel.chk_step1.IsShown())
            self.assertFalse(panel.chk_restore.IsShown())
            self.assertTrue(panel.instrument_panel.IsShown())
            self.assertEqual(sum(c.IsShown() for c in panel.instrument_stems.values()),4)
            self.assertIn('Enstrüman',panel.btn_start.GetName())
            panel.instrument_profile.SetFocus()
            panel.instrument_profile.Navigate(wx.NavigationKeyEvent.IsForward);app.Yield()
            self.assertIs(wx.Window.FindFocus(),panel.instrument_help)
            self.assertIsInstance(panel.instrument_help,wx.StaticText)
            panel.instrument_profile.SetSelection(0);panel.OnInstrumentProfile(None)
            self.assertFalse(panel.instrument_stems['guitar'].IsShown())
            self.assertFalse(panel.instrument_stems['piano'].IsShown())
            panel.EnableUI(False);app.Yield()
            self.assertFalse(panel.mode_choice.IsEnabled())
            self.assertFalse(panel.instrument_profile.IsEnabled())
            panel.EnableUI(True)
            panel.mode_choice.SetSelection(0);panel.OnMode(None)
            self.assertTrue(panel.chk_step1.IsShown())
            self.assertFalse(panel.instrument_panel.IsShown())
        finally:
            frame.Destroy();app.ProcessPendingEvents()

    def test_channel_toggles_expose_open_and_closed_like_vocal_controls(self):
        from ui_separator import SeparatorPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None,size=(850,1000))
        try:
            panel = SeparatorPanel(frame,SimpleNamespace(theme='light'))
            frame.Show()
            panel.mode_choice.SetSelection(1);panel.OnMode(None)
            panel.instrument_profile.SetSelection(1);panel.OnInstrumentProfile(None);app.Yield()
            panel.instrument_help.SetFocus()
            panel.instrument_help.Navigate(wx.NavigationKeyEvent.IsForward);app.Yield()
            self.assertIs(wx.Window.FindFocus(),panel.instrument_stems['bass'])
            for stem,control in panel.instrument_stems.items():
                with self.subTest(stem=stem):
                    self.assertIsInstance(control,wx.ToggleButton)
                    self.assertIs(control.GetParent(),panel.instrument_panel)
                    accessible = control.GetAccessible()
                    self.assertIs(type(accessible),type(panel.chk_step1.GetAccessible()))
                    self.assertEqual(accessible.GetRole(wx.ACC_SELF),
                                     (wx.ACC_OK,wx.ROLE_SYSTEM_CHECKBUTTON))
                    base_label = control.GetLabel().split(' - ')[0]
                    for active in (False,True):
                        with patch.object(wx.Accessible,'NotifyEvent') as notify:
                            self.assertEqual(accessible.DoDefaultAction(wx.ACC_SELF),wx.ACC_OK)
                        self.assertEqual(control.GetValue(),active)
                        label = base_label+(' - [AÇIK]' if active else ' - [KAPALI]')
                        self.assertEqual(control.GetLabel(),label)
                        self.assertEqual(control.GetName(),label)
                        self.assertEqual(accessible.GetName(wx.ACC_SELF),(wx.ACC_OK,label))
                        state = accessible.GetState(wx.ACC_SELF)[1]
                        self.assertEqual(bool(state & wx.ACC_STATE_SYSTEM_CHECKED),active)
                        self.assertEqual(accessible.GetDefaultAction(wx.ACC_SELF),
                                         (wx.ACC_OK,'İşaretini kaldır' if active else 'İşaretle'))
                        notify.assert_any_call(wx.ACC_EVENT_OBJECT_NAMECHANGE,control,
                                               wx.OBJID_CLIENT,wx.ACC_SELF)
                        notify.assert_any_call(wx.ACC_EVENT_OBJECT_STATECHANGE,control,
                                               wx.OBJID_CLIENT,wx.ACC_SELF)
            bass = panel.instrument_stems['bass']
            bass.GetAccessible().DoDefaultAction(wx.ACC_SELF)
            panel.instrument_profile.SetSelection(0);panel.OnInstrumentProfile(None)
            guitar = panel.instrument_stems['guitar'].GetAccessible()
            self.assertTrue(guitar.GetState(wx.ACC_SELF)[1] & wx.ACC_STATE_SYSTEM_INVISIBLE)
            self.assertEqual(guitar.DoDefaultAction(wx.ACC_SELF),wx.ACC_FAIL)
            panel.mode_choice.SetSelection(0);panel.OnMode(None)
            panel.mode_choice.SetSelection(1);panel.OnMode(None)
            self.assertFalse(bass.GetValue())
            self.assertIn('[KAPALI]',bass.GetAccessible().GetName(wx.ACC_SELF)[1])
            panel.EnableUI(False)
            self.assertTrue(bass.GetAccessible().GetState(wx.ACC_SELF)[1] & wx.ACC_STATE_SYSTEM_UNAVAILABLE)
            self.assertEqual(bass.GetAccessible().DoDefaultAction(wx.ACC_SELF),wx.ACC_FAIL)
        finally:
            frame.Destroy();app.ProcessPendingEvents()

    def test_instrument_models_are_opt_in_and_bad_bytes_fail_validation(self):
        from model_manager import model_catalog,default_model_selection,validate_file,ModelManager
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            for key,spec in PROFILES.items():
                self.assertIn(key,model_catalog())
                self.assertNotIn(key,default_model_selection())
                self.assertEqual(ModelManager(folder).primary_files(key),[spec['asset']])
                path=Path(folder)/'bad.th';path.write_bytes(b'not weights')
                with self.assertRaises(ValueError):validate_file(path,spec['asset'])

    def test_overlap_add_preserves_duration_stereo_balance_and_source(self):
        import torch
        class Split:
            def __call__(self,x): return x[:,None].repeat(1,4,1,1)/4
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder);source=root/'input.wav'
            t=np.arange(RATE*10)/RATE
            data=np.column_stack((.1*np.sin(2*np.pi*220*t)+.02,.05*np.cos(2*np.pi*110*t)))
            sf.write(source,data,RATE,subtype='FLOAT')
            original=source.read_bytes()
            result=separate_file(source,root/'result',root,model_factory=lambda *a:Split())
            outputs=[sf.read(p)[0] for p in result['files'].values()]
            np.testing.assert_allclose(sum(outputs),sf.read(source)[0],atol=6e-7,rtol=0)
            self.assertEqual(result['frames'],len(data))
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(sf.info(next(iter(result['files'].values()))).subtype,'PCM_24')

    def test_cancel_or_model_failure_never_publishes_partial_stems(self):
        class Broken:
            def __call__(self,x): raise RuntimeError('fixture failure')
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder);source=root/'input.wav'
            sf.write(source,np.full((RATE,2),.1),RATE)
            target=root/'result'
            with self.assertRaisesRegex(RuntimeError,'fixture failure'):
                separate_file(source,target,root,model_factory=lambda *a:Broken())
            self.assertFalse(target.exists())
            with self.assertRaises(InterruptedError):
                separate_file(source,target,root,cancelled=lambda:True)
            self.assertFalse(target.exists())
            self.assertEqual(sorted(p.name for p in root.iterdir()),['input.wav'])

    def test_invalid_channel_and_existing_output_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder)
            with self.assertRaises(ValueError):
                separate_file('unused',root/'result',root,profile='scnet',stems=['guitar'])
            with self.assertRaises(FileExistsError):
                separate_file('unused',root,root)

    def test_cancel_during_model_step_does_not_commit_results(self):
        stop=[False]
        class CancelDuringForward:
            def __call__(self,x):
                stop[0]=True
                return x[:,None].repeat(1,4,1,1)/4
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root=Path(folder);source=root/'input.wav'
            sf.write(source,np.full((RATE,2),.1),RATE)
            with self.assertRaises(InterruptedError):
                separate_file(source,root/'results',root,cancelled=lambda:stop[0],
                              model_factory=lambda *a:CancelDuringForward())
            self.assertEqual([p.name for p in root.iterdir()],['input.wav'])


if __name__=='__main__': unittest.main()
