"""Recording integrity, channel cancellation and optional UI analysis failure paths."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace
import numpy as np
import soundfile as sf
from training.analysis import inspect_audio, analyze_sources, report_text
from app_runtime import JOB_LOCK

ROOT = Path(__file__).resolve().parents[1]


class RecordingAnalysisTests(unittest.TestCase):
    def test_ui_does_not_publish_analysis_cancelled_after_the_final_review(self):
        import ui_training
        def run_now(target, **kwargs):
            return SimpleNamespace(start=target)
        for final_stage in ('hash','after_review'):
            panel = SimpleNamespace(busy=False,sources=['voice.wav'],sample_rate=Mock(),
                Options=Mock(return_value=Mock()),EnableUI=Mock(),gauge=Mock(),txt_status=Mock(),
                OnProgress=Mock(),OnAnalyzed=Mock(),OnOperationError=Mock(),AnalysisStopped=Mock())
            panel.sample_rate.GetSelection.return_value = 1
            def review(report, options, cancelled):
                panel.analysis_cancel.set()
                if final_stage == 'hash':
                    raise InterruptedError('Kayıt incelemesi iptal edildi.')
                return {}
            with self.subTest(stage=final_stage), \
                    patch('ui_training.threading.Thread',side_effect=run_now), \
                    patch('training.analysis.analyze_sources',return_value={}), \
                    patch('ui_training.split_review',side_effect=review) as split, \
                    patch('ui_training.post_ui',side_effect=lambda parent,fn,*args:fn(*args)), \
                    patch('ui_training.finish_job',side_effect=lambda parent:JOB_LOCK.release()):
                ui_training.TrainingPanel.OnAnalyze(panel,None)
                self.assertTrue(callable(split.call_args.args[2]))
                panel.OnAnalyzed.assert_not_called()
                panel.OnOperationError.assert_called_once()
                self.assertFalse(JOB_LOCK.locked())

    def test_phase_cancellation_is_detected_without_changing_audio(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'stereo.wav'
            mono = .2*np.sin(np.arange(32000)*2*np.pi*220/16000)
            sf.write(path, np.stack([mono, -mono], axis=1), 16000, subtype='FLOAT')
            before = path.read_bytes()
            report = inspect_audio(path)
            self.assertLess(report['mono_rms_ratio'], 1e-6)
            self.assertAlmostEqual(report['seconds'], 2)
            self.assertEqual(path.read_bytes(), before)

    def test_nonfinite_and_silent_recordings_fail(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'invalid.wav'
            for wave in (np.zeros(32000), np.full(32000, np.nan)):
                sf.write(path, wave, 16000, subtype='FLOAT')
                with self.assertRaises(ValueError):
                    inspect_audio(path)

    def test_cancellation_is_checked_while_streaming(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'voice.wav'
            sf.write(path, np.ones(32000)*.1, 16000)
            with self.assertRaises(InterruptedError):
                inspect_audio(path, lambda: True)

    def test_real_decode_duplicate_and_phase_warning(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'voice.wav'
            duplicate = Path(folder)/'copy.wav'
            mono = .2*np.sin(np.arange(48000)*2*np.pi*220/16000)
            sf.write(path, np.stack([mono, -mono], axis=1), 16000, subtype='FLOAT')
            original = path.read_bytes()
            duplicate.write_bytes(original)
            with patch.dict(os.environ, {'PATH':str(ROOT/'tools/ffmpeg')+os.pathsep+os.environ['PATH']}):
                report = analyze_sources([path, duplicate], 40000)
            self.assertEqual(report['unique_recordings'], 1)
            self.assertEqual(report['duplicate_recordings'], 1)
            self.assertAlmostEqual(report['total_seconds'], 3, places=2)
            self.assertTrue(any('faz' in warning for warning in report['sources'][0]['warnings']))
            self.assertIn('kalite garantisi', report_text(report))
            self.assertEqual(original, path.read_bytes())

    def test_analysis_thread_failure_releases_lock_and_progress_keeps_percent(self):
        import wx
        import ui_training
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            panel = ui_training.TrainingPanel(frame, SimpleNamespace(open_settings=Mock()))
            panel.sources = ['voice.wav']
            with patch('ui_training.threading.Thread', side_effect=RuntimeError('thread failed')):
                panel.OnAnalyze(None)
            self.assertFalse(JOB_LOCK.locked())
            self.assertFalse(panel.busy)
            self.assertIsNone(panel.analysis_cancel)
            panel.OnProgress(dict(stage='train',message='Training',percent=42,eta_seconds=3600))
            panel.OnProgress(dict(stage='checkpoint',message='Saved'))
            self.assertEqual(panel.gauge.GetValue(), 42)
            panel.OnProgress(dict(stage='train',message='Training',percent=43))
            self.assertEqual(panel.gauge.GetValue(), 43)
        finally:
            if JOB_LOCK.locked(): JOB_LOCK.release()
            frame.Destroy()
            app.ProcessPendingEvents()
