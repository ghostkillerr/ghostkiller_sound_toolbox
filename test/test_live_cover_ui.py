"""Five-tab integration and live UI job ownership, with no hardware capture."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

import wx

from app_runtime import JOB_LOCK
from live_audio import AudioDevice
from ui_live_cover import LiveCoverPanel

ROOT = Path(__file__).resolve().parents[1]
DEVICES = {'inputs': [AudioDevice(-1, 'Varsayılan'), AudioDevice(2, 'Test mikrofonu')],
           'outputs': [AudioDevice(-1, 'Varsayılan'), AudioDevice(3, 'Test kulaklığı')]}


class LiveUIContracts(unittest.TestCase):
    def setUp(self):
        self.app = wx.GetApp() or wx.App(False)
        self.frame = wx.Frame(None)
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.model = Path(self.temporary.name)/'voice.pth'
        self.model.touch()
        self.settings = SimpleNamespace(preference='cpu', theme='light',
            manager=SimpleNamespace(status=lambda key: 'Hazır'), prepare_job=Mock(return_value='cpu'),
            refresh_operations=Mock(), open_cover=Mock(), open_settings=Mock())
        self.device_patch = patch('ui_live_cover.enumerate_devices', return_value=DEVICES)
        self.device_patch.start()
        self.notice_patch = patch.object(wx, 'MessageBox')
        self.notice = self.notice_patch.start()
        self.panel = LiveCoverPanel(self.frame, self.settings, models={'voice': {'pth': str(self.model), 'index': ''}})

    def tearDown(self):
        if JOB_LOCK.locked(): JOB_LOCK.release()
        self.frame.Destroy()
        self.app.ProcessPendingEvents()
        self.device_patch.stop()
        self.notice_patch.stop()
        self.temporary.cleanup()

    def test_native_controls_defaults_and_context_appropriate_summary(self):
        panel = self.panel
        self.assertEqual(panel.model_choice.GetStringSelection(), 'voice')
        self.assertEqual(panel.block.GetStringSelection(), '500 ms')
        self.assertEqual(panel.gain.GetValue(), 50)
        self.assertTrue(panel.gate_enabled.GetValue())
        self.assertEqual(panel.GateThreshold(), -45)
        self.assertFalse(panel.btn_stop.IsEnabled())
        self.assertIn('Dosyaya kayıt yapılmaz', panel.preparation.summary.GetLabel())
        self.assertNotIn('FLAC', panel.preparation.summary.GetLabel())
        self.assertEqual(panel.txt_status.GetName(), 'Canlı dinleme durumu ve gecikme')
        self.assertEqual(panel.model_choice.GetPrevSibling().GetLabel(), 'Kullanılacak ses modeli')

    def test_options_freeze_model_devices_pitch_gain_and_turkish_decimal(self):
        panel = self.panel
        panel.input_choice.SetSelection(1)
        panel.output_choice.SetSelection(1)
        panel.pitch.SetValue(5)
        panel.index_rate.SetValue('0,4')
        panel.block.SetSelection(0)
        panel.gain.SetValue(35)
        panel.gate_db.SetValue('-35')
        options = panel.Options()
        self.assertEqual((options.input_device, options.output_device), (2, 3))
        self.assertEqual((options.pitch, options.index_rate, options.gain, options.block_seconds), (5, .4, .35, .25))
        panel.pitch.SetValue(9)
        self.assertEqual(options.pitch, 5)
        self.assertEqual(options.gate_db, -35)
        self.assertEqual((options.input_name, options.output_name), ('Test mikrofonu', 'Test kulaklığı'))
        self.settings.prepare_job.assert_called_once_with(['contentvec', 'rmvpe'])

    def test_model_refresh_preserves_selection_and_does_not_change_running_session(self):
        panel = self.panel
        models = {'other': {'pth': str(self.model)}, 'voice': {'pth': str(self.model)}}
        panel.RefreshModels(models)
        self.assertEqual(panel.model_choice.GetStringSelection(), 'voice')
        panel.EnableUI(False)
        panel.RefreshModels({})
        self.assertEqual(panel.model_choice.GetStringSelection(), 'voice')
        self.assertFalse(panel.model_choice.IsEnabled())

    def test_failed_thread_start_restores_controls_and_releases_job_lock(self):
        with patch('ui_live_cover.threading.Thread', side_effect=RuntimeError('synthetic thread failure')), \
             patch.object(wx, 'MessageBox'):
            self.panel.OnStart(None)
        self.assertFalse(JOB_LOCK.locked())
        self.assertTrue(self.panel.btn_start.IsEnabled())
        self.assertFalse(self.panel.btn_stop.IsEnabled())
        self.assertIn('synthetic thread failure', self.panel.txt_status.GetValue())

    def test_stop_releases_lock_only_after_final_ui_callback_and_closes_session(self):
        session = Mock()
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False)
        def execute(kind, payload, cancelled, progress):
            self.assertEqual(kind, 'live_cover')
            self.assertEqual(payload['options']['model_path'], str(self.model))
            progress('Synthetic converted audio')
            self.panel.OnStop(None)
            self.assertTrue(cancelled())
            raise InterruptedError('stopped')
        session.execute.side_effect = execute
        self.panel.audio_session_factory = Mock(return_value=session)
        with patch('ui_live_cover.threading.Thread') as thread:
            self.panel.OnStart(None)
            self.assertTrue(JOB_LOCK.locked())
            options = thread.call_args.kwargs['args'][0]
        self.panel.Run(options)
        self.assertTrue(JOB_LOCK.locked())
        session.__exit__.assert_called_once()
        self.app.ProcessPendingEvents()
        self.assertFalse(JOB_LOCK.locked())
        self.assertTrue(self.panel.btn_start.IsEnabled())
        self.assertEqual(self.panel.txt_status.GetValue(), 'Canlı dinleme durduruldu.')

    def test_other_job_blocks_live_start_and_model_preparation(self):
        JOB_LOCK.acquire()
        with patch('ui_live_cover.threading.Thread') as thread:
            self.panel.OnStart(None)
            thread.assert_not_called()
        self.assertTrue(JOB_LOCK.locked())
        self.settings.prepare_job.assert_not_called()

    def test_force_stop_before_session_creation_is_remembered(self):
        self.panel.OnForceStop(None)
        self.assertTrue(self.panel.stop_requested.is_set())
        self.assertTrue(self.panel.force_requested.is_set())

    def test_audio_device_identity_follows_the_native_item_not_a_separate_index(self):
        control = self.panel.output_choice
        control.Clear()
        control.Append('Line 2', AudioDevice(12, 'Line 2'))
        control.Append('Varsayılan', AudioDevice(-1, 'Windows varsayılan aygıtı'))
        control.SetSelection(0)
        options = self.panel.Options()
        self.assertEqual((options.output_device, options.output_name), (12, 'Line 2'))

    def test_disconnected_selection_is_not_replaced_with_default(self):
        self.panel.output_choice.SetSelection(1)
        with patch('ui_live_cover.enumerate_devices', return_value={
                'inputs': DEVICES['inputs'], 'outputs': [AudioDevice(-1, 'Varsayılan')]}):
            self.panel.RefreshDevices()
        self.assertEqual(self.panel.output_choice.GetSelection(), wx.NOT_FOUND)
        with self.assertRaisesRegex(ValueError, 'yeniden seçin'):
            self.panel.Options()

    def test_device_refresh_error_keeps_the_explicit_selection(self):
        self.panel.output_choice.SetSelection(1)
        with patch('ui_live_cover.enumerate_devices', side_effect=RuntimeError('device query failed')):
            self.panel.RefreshDevices()
        self.assertEqual(self.panel.SelectedDevice(self.panel.output_choice), AudioDevice(3, 'Test kulaklığı'))

    def test_repeated_status_never_spams_the_log_and_microphone_is_logged_once(self):
        self.panel.Report('Canlı ses modeli hazırlanıyor')
        for _ in range(20):
            self.panel.Report('Canlı dinleme: tahmini gecikme 900 ms')
        self.assertEqual(self.panel.txt_log.GetValue(), '')
        self.panel.Report('Mikrofon açıldı. Giriş: Mikrofon; dönüştürülmüş çıkış: Line 2.')
        self.panel.Report('Mikrofon açıldı. Giriş: Mikrofon; dönüştürülmüş çıkış: Line 2.')
        for _ in range(20): self.panel.Report('Ses eşiğinin altında; dönüştürme bekliyor.')
        self.panel.OnFinished('Canlı dinleme durduruldu.', False)
        self.assertEqual(self.panel.txt_log.GetValue().strip(), 'Mikrofon açıldı.')
        self.assertIn('Line 2', self.panel.txt_route.GetValue())

    def test_gate_is_adjustable_while_live_and_uses_no_worker_ui_getter(self):
        session = Mock()
        self.panel.audio_session = session
        self.panel.EnableUI(False)
        self.assertTrue(self.panel.gate_db.IsEnabled())
        self.panel.gate_db.SetValue('-35')
        self.panel.OnGateChange(None)
        session.set_live_gate.assert_called_with(True, -35)
        self.assertEqual(self.panel._live_gate, (True, -35))

    def test_summary_names_the_detected_gpu(self):
        from hardware import HardwareReport, DeviceSupport
        self.settings.preference = 'gpu'
        self.settings.report = HardwareReport(DeviceSupport('cpu', 'CPU', True),
            [DeviceSupport('cuda:0', 'RTX fixture', True, backend='CUDA')])
        self.assertIn('RTX fixture', self.panel.Summary())

    def start_calibration(self, session, closed=None):
        session.__enter__ = Mock(return_value=session)
        session.__exit__ = Mock(return_value=False, side_effect=closed)
        self.panel.audio_session_factory = Mock(return_value=session)
        with patch('ui_live_cover.threading.Thread') as thread:
            self.panel.OnCalibrate(None)
            self.assertTrue(JOB_LOCK.locked())
            self.assertTrue(self.panel.calibrating)
            self.assertFalse(self.panel.btn_start.IsEnabled())
            self.assertFalse(self.panel.btn_calibrate.IsEnabled())
            self.assertFalse(self.panel.gate_db.IsEnabled())
            self.assertEqual(self.panel.btn_stop.GetLabel(), 'Ölçümü iptal et')
            options = thread.call_args.kwargs['args'][0]
        self.panel.RunCalibration(options)
        self.assertTrue(JOB_LOCK.locked())
        session.__exit__.assert_called_once()
        self.app.ProcessPendingEvents()
        self.assertFalse(JOB_LOCK.locked())
        self.assertTrue(self.panel.btn_start.IsEnabled())

    def test_automatic_setup_needs_no_model_or_output_and_announces_only_after_close(self):
        panel = self.panel
        panel.RefreshModels({})
        panel.output_choice.SetSelection(wx.NOT_FOUND)
        panel.input_choice.SetSelection(1)
        session = Mock()
        session.execute.return_value = {'threshold_db': -42, 'noise_db': -52.,
            'close_db': -48, 'seconds': 10, 'input_device': 2, 'input_name': 'Test mikrofonu'}
        def exited(*args):
            self.assertNotIn('Ayarlandı.', panel.txt_calibration.GetValue())
            self.assertEqual(panel.GateThreshold(), -45)
            self.notice.assert_not_called()
        # Capture closure order while start_calibration installs context methods.
        def execute(kind, payload, cancelled, progress):
            self.assertEqual(kind, 'calibrate_gate')
            self.assertEqual(payload, {'input_device': 2, 'input_name': 'Test mikrofonu'})
            progress('Mikrofon açıldı. Giriş: Test mikrofonu; ses çıkışı kapalı.')
            progress('Konuşmayın. Ortam ölçülüyor: 1 saniye kaldı.')
            self.assertEqual(panel.txt_log.GetValue().strip(), 'Mikrofon açıldı.')
            return session.execute.return_value
        session.execute.side_effect = execute
        self.start_calibration(session, closed=exited)
        self.settings.prepare_job.assert_not_called()
        self.assertEqual(panel.GateThreshold(), -42)
        self.assertIn('Ayarlandı. Mikrofon kapatıldı.', panel.txt_calibration.GetValue())
        self.assertIn('kapanma -48 dB', panel.txt_gate_profile.GetValue())
        self.assertFalse(panel.calibrating)
        self.assertIsNone(panel.audio_session)
        self.assertIn('Mikrofon kapalı', panel.txt_route.GetValue())
        self.notice.assert_called_once()
        args, kwargs = self.notice.call_args
        self.assertEqual(args[1], 'Dinleme tamamlandı')
        self.assertIn('10 saniyelik ortam dinlemesi tamamlandı.', args[0])
        self.assertIn('Ayarlandı. Mikrofon kapatıldı.', args[0])
        self.assertIs(kwargs['parent'], panel)

    def test_cancelled_setup_keeps_threshold_and_silent_log(self):
        self.panel.gate_db.SetValue('-58')
        session = Mock()
        def execute(kind, payload, cancelled, progress):
            progress('Mikrofon açıldı. Ölçüm; ses çıkışı kapalı.')
            for _ in range(20): progress('Konuşmayın. Ortam ölçülüyor: 9 saniye kaldı.')
            self.panel.OnStop(None)
            self.assertTrue(cancelled())
            raise InterruptedError('cancel')
        session.execute.side_effect = execute
        self.start_calibration(session)
        self.assertEqual(self.panel.GateThreshold(), -58)
        self.assertIn('iptal edildi', self.panel.txt_calibration.GetValue())
        self.assertEqual(self.panel.txt_log.GetValue().strip(), 'Mikrofon açıldı.')
        self.notice.assert_not_called()

    def test_failed_setup_preserves_previous_threshold(self):
        self.panel.gate_db.SetValue('-58')
        session = Mock()
        session.execute.side_effect = ValueError('konuşma algılandı')
        with patch.object(wx, 'MessageBox') as notice:
            self.start_calibration(session)
        self.assertEqual(self.panel.GateThreshold(), -58)
        self.assertIn('konuşma', self.panel.txt_calibration.GetValue())
        notice.assert_called_once()

    def test_close_failure_cannot_announce_or_apply_a_successful_profile(self):
        self.panel.gate_db.SetValue('-58')
        session = Mock()
        session.execute.return_value = {'threshold_db': -42, 'noise_db': -52.,
            'input_device': 2, 'input_name': 'Test mikrofonu'}
        with patch.object(wx, 'MessageBox'):
            self.start_calibration(session, closed=RuntimeError('microphone close failed'))
        self.assertEqual(self.panel.GateThreshold(), -58)
        self.assertNotIn('Ayarlandı.', self.panel.txt_calibration.GetValue())

    def test_success_arriving_after_cancel_is_not_applied(self):
        self.panel.gate_db.SetValue('-58')
        session = Mock()
        def execute(*args, **kwargs):
            self.panel.OnStop(None)
            return {'threshold_db': -42, 'noise_db': -52.,
                    'input_device': 2, 'input_name': 'Test mikrofonu'}
        session.execute.side_effect = execute
        self.start_calibration(session)
        self.assertEqual(self.panel.GateThreshold(), -58)
        self.assertIn('iptal edildi', self.panel.txt_calibration.GetValue())

    def test_busy_job_blocks_calibration_and_thread_failure_releases_lock(self):
        JOB_LOCK.acquire()
        with patch('ui_live_cover.threading.Thread') as thread:
            self.panel.OnCalibrate(None)
            thread.assert_not_called()
        JOB_LOCK.release()
        with patch('ui_live_cover.threading.Thread', side_effect=RuntimeError('thread failed')):
            self.panel.OnCalibrate(None)
        self.assertFalse(JOB_LOCK.locked())
        self.assertFalse(self.panel.calibrating)
        self.assertTrue(self.panel.btn_calibrate.IsEnabled())

    def test_new_microphone_discards_the_previous_automatic_profile(self):
        panel = self.panel
        panel._calibrated_input = DEVICES['inputs'][1]
        panel.input_choice.SetSelection(1)
        panel.gate_db.SetValue('-58')
        panel.OnInputChange(None)
        self.assertEqual(panel.GateThreshold(), -58)
        panel.input_choice.SetSelection(0)
        panel.OnInputChange(None)
        self.assertIsNone(panel._calibrated_input)
        self.assertEqual(panel.GateThreshold(), -45)
        self.assertIn('yeniden yapın', panel.txt_calibration.GetValue())

    def test_calibrated_default_is_pinned_to_the_microphone_that_was_measured(self):
        self.panel._calibrated_input = AudioDevice(12, 'Measured microphone')
        options = self.panel.Options()
        self.assertEqual((options.input_device, options.input_name), (12, 'Measured microphone'))

    def test_invalid_response_does_not_change_threshold(self):
        from live_gate import CalibrationOptions
        with patch.object(wx, 'MessageBox'):
            self.panel.OnCalibrationFinished(CalibrationOptions(),
                {'threshold_db': -42, 'noise_db': float('nan'), 'input_device': 0, 'input_name': 'Test'}, '', False)
        self.assertEqual(self.panel.GateThreshold(), -45)

    def test_gate_accepts_values_below_minus_80_and_turkish_decimals(self):
        for text, expected in (('-100', -100), ('-120,5', -120.5), ('-1e300', -1e300)):
            with self.subTest(text=text):
                self.panel.gate_db.SetValue(text)
                self.panel.OnGateChange(None)
                self.assertEqual(self.panel.Options().gate_db, expected)
                self.assertEqual(self.panel._live_gate, (True, expected))
        self.notice.assert_not_called()

    def test_invalid_partial_gate_text_keeps_last_valid_live_threshold(self):
        session = Mock()
        self.panel.audio_session = session
        self.panel.gate_db.SetValue('-100')
        self.panel.OnGateChange(None)
        session.set_live_gate.assert_called_with(True, -100)
        session.set_live_gate.reset_mock()
        for text in ('-', '', 'nan', '-inf', '1'):
            with self.subTest(text=text):
                self.panel.gate_db.SetValue(text)
                self.panel.OnGateChange(None)
                session.set_live_gate.assert_not_called()
                self.assertEqual(self.panel._live_gate, (True, -100))
                with self.assertRaises(ValueError):
                    self.panel.Options()


class FiveTabIntegration(unittest.TestCase):
    def test_live_is_fourth_settings_fifth_and_navigation_uses_pages(self):
        import main
        from app_settings import AppSettings
        from model_manager import ModelManager
        from ui_settings import SettingsPanel
        app = wx.GetApp() or wx.App(False)
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            settings = AppSettings(str(Path(folder)/'settings.json'), ModelManager(folder))
            with patch('app_settings.AppSettings', return_value=settings), \
                 patch('ui_cover.load_models', return_value={}) as models, \
                 patch('ui_live_cover.enumerate_devices', return_value=DEVICES), \
                 patch.object(main.GhostkillerMainFrame, 'BeginStartupSequence'):
                frame = main.GhostkillerMainFrame(startup_checks=False)
                try:
                    self.assertEqual([frame.notebook.GetPageText(i) for i in range(5)], [
                        '1. Müzik ve Ses Temizleme', '2. Ses Değiştirme (AI Cover)',
                        '3. Model Eğitimi', '4. Canlı AI Cover', '5. Ayarlar'])
                    frame.OpenSettings()
                    self.assertIs(frame.notebook.GetCurrentPage(), frame.settings_tab)
                    frame.OpenCover()
                    self.assertIs(frame.notebook.GetCurrentPage(), frame.cover_tab)
                    models.return_value = {'new': {'pth': str(Path(folder)/'new.pth'), 'index': ''}}
                    frame.RefreshCoverModels()
                    self.assertEqual(frame.live_cover_tab.model_names, ['new'])
                    models.return_value = {'external': {'pth': str(Path(folder)/'external.pth'), 'index': ''}}
                    frame.notebook.SetSelection(3)
                    app.ProcessPendingEvents()
                    self.assertIs(frame.notebook.GetCurrentPage(), frame.live_cover_tab)
                    self.assertEqual(frame.live_cover_tab.model_names, ['external'])
                    self.assertEqual(list(frame.cover_tab.models), ['external'])
                finally:
                    frame.Destroy()
                    app.ProcessPendingEvents()


if __name__ == '__main__': unittest.main()
