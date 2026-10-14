"""Create real native controls without displaying a window or loading models."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import wx
import ui_cover
import ui_separator
from types import SimpleNamespace
from app_runtime import JOB_LOCK, post_ui


class AccessibilityControls(unittest.TestCase):
    def test_tab_focus_visits_training_explanation_before_next_setting(self):
        from ui_training import TrainingPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None,size=(800,850))
        try:
            panel = TrainingPanel(frame,SimpleNamespace(theme='light'))
            layout = wx.BoxSizer(wx.VERTICAL)
            layout.Add(panel,1,wx.EXPAND)
            frame.SetSizer(layout)
            frame.Show()
            frame.Layout()
            app.Yield()
            panel.epochs.SetFocus()
            panel.epochs.Navigate(wx.NavigationKeyEvent.IsForward)
            app.Yield()
            explanation = panel.field_explanations[panel.epochs]
            self.assertIs(wx.Window.FindFocus(),explanation)
            self.assertIsInstance(explanation,wx.StaticText)
            self.assertNotIsInstance(explanation,wx.TextCtrl)
            self.assertIn('200 epoch',explanation.GetLabel())
            self.assertEqual(explanation.GetAccessible().GetRole(wx.ACC_SELF),(wx.ACC_OK,wx.ROLE_SYSTEM_STATICTEXT))
            self.assertTrue(explanation.GetAccessible().GetState(wx.ACC_SELF)[1] & wx.ACC_STATE_SYSTEM_FOCUSED)
            explanation.Navigate(wx.NavigationKeyEvent.IsForward)
            app.Yield()
            self.assertIs(wx.Window.FindFocus(),panel.advanced_toggle)
            panel.advanced_toggle.SetValue(True)
            panel.OnAdvanced(None)
            for control in (panel.batch,panel.segment,panel.overlap,panel.threads):
                control.SetFocus()
                control.Navigate(wx.NavigationKeyEvent.IsForward)
                app.Yield()
                help_field = panel.field_explanations[control]
                self.assertIs(wx.Window.FindFocus(),help_field)
                help_field.Navigate(wx.NavigationKeyEvent.IsBackward)
                app.Yield()
                self.assertIs(wx.Window.FindFocus(),control)
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_decimal_training_fields_parse_and_restore_without_composite_spin_controls(self):
        from ui_training import TrainingPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
                source = Path(folder)/'voice.wav'
                source.touch()
                panel = TrainingPanel(frame,SimpleNamespace(theme='light'))
                panel.sources = [str(source)]
                panel.model_name.SetValue('voice')
                panel.segment.SetValue('3,5')
                panel.overlap.SetValue('0,4')
                options = panel.Options()
                self.assertEqual(options.segment_seconds,3.5)
                self.assertEqual(options.overlap_seconds,0.4)
                panel.ShowOptions(options)
                self.assertEqual(panel.segment.GetValue(),'3.5')
                self.assertEqual(panel.overlap.GetValue(),'0.4')
                panel.segment.SetValue('invalid')
                with self.assertRaises(ValueError):panel.Options()
                panel.segment.SetValue('0')
                with self.assertRaises(ValueError):panel.Options()
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_training_labels_precede_their_controls_and_empty_sections_are_hidden(self):
        from ui_training import TrainingPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            panel = TrainingPanel(frame,SimpleNamespace(theme='light'))
            self.assertFalse(panel.source_list.IsShown())
            self.assertFalse(panel.progress_panel.IsShown())
            self.assertFalse(panel.result_panel.IsShown())
            self.assertFalse(hasattr(panel,'btn_settings'))
            self.assertFalse(hasattr(panel,'btn_analyze'))
            fields = (panel.model_name,panel.sample_rate,panel.epochs,panel.batch,panel.interval,
                      panel.learning_rate,panel.segment,panel.overlap,panel.holdout,panel.threads,panel.f0)
            for control in fields:
                with self.subTest(name=control.GetName()):
                    self.assertEqual(control.GetPrevSibling().GetLabel(),control.GetName())
                    explanation = control.GetAccessible().GetHelpText(wx.ACC_SELF)[1]
                    self.assertEqual(control.GetAccessible().GetName(wx.ACC_SELF),(wx.ACC_OK,control.GetName()))
                    if control in panel.field_explanations:
                        self.assertFalse(control.GetAccessible().GetDescription(wx.ACC_SELF)[1])
                        self.assertTrue(panel.field_explanations[control].GetLabel())
                    else:
                        self.assertTrue(control.GetAccessible().GetDescription(wx.ACC_SELF)[1])
            for control in (panel.model_name,panel.sample_rate,panel.f0):
                self.assertNotIn(control,panel.field_explanations)
            self.assertFalse(panel.btn_group.IsShown())
            self.assertIsInstance(panel.segment,wx.TextCtrl)
            self.assertIsInstance(panel.overlap,wx.TextCtrl)
            panel.sources = ['example.wav']
            panel.RefreshSources()
            self.assertTrue(panel.source_list.IsShown())
            panel.OnProgress({'stage':'train','message':'Eğitim başladı','percent':10})
            self.assertTrue(panel.progress_panel.IsShown())
            self.assertFalse(panel.txt_resources.IsShown())
            self.assertTrue(panel.txt_log.IsShown())
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_theme_save_preserves_device_and_failed_save_keeps_previous_theme(self):
        from app_settings import AppSettings
        from hardware import HardwareReport,DeviceSupport
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            path = Path(folder)/'settings.json'
            path.write_text('{"device":"cpu","other":"keep"}',encoding='utf-8')
            settings = AppSettings(str(path))
            settings.report = HardwareReport(DeviceSupport('cpu','CPU',True))
            settings.select_theme('dark')
            settings.select('cpu')
            restored = AppSettings(str(path))
            self.assertEqual(restored.theme,'dark')
            self.assertEqual(restored.preference,'cpu')
            self.assertIn('keep',path.read_text())
            with patch('app_settings.os.replace',side_effect=PermissionError('read only')):
                with self.assertRaises(PermissionError):settings.select_theme('light')
            self.assertEqual(settings.theme,'dark')
            self.assertEqual(AppSettings(str(path)).theme,'dark')

    def test_theme_radio_updates_all_panels_and_is_exclusive(self):
        from app_settings import AppSettings
        from model_manager import ModelManager
        from ui_settings import SettingsPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
                settings = AppSettings(str(Path(folder)/'settings.json'),ModelManager(folder))
                frame.settings = settings
                panel = SettingsPanel(frame,settings,auto_detect=False)
                with patch.object(ui_cover,'load_models',return_value={}):
                    cover = ui_cover.CoverPanel(frame,settings)
                self.assertFalse(hasattr(cover,'btn_settings'))
                with patch('ui_common.high_contrast_enabled',return_value=False):
                    panel.theme_choice.SetSelection(1)
                    panel.OnTheme(None)
                    self.assertEqual(cover.GetBackgroundColour(),wx.Colour('#202733'))
                    self.assertEqual(settings.theme,'dark')
                    panel.theme_choice.SetSelection(0)
                    panel.OnTheme(None)
                    self.assertEqual(cover.GetBackgroundColour(),wx.Colour('#F3F5F9'))
                    self.assertEqual(AppSettings(settings.path,settings.manager).theme,'light')
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_failed_model_result_names_model_and_reason_in_readable_dialog(self):
        from app_settings import AppSettings
        from model_manager import ModelManager
        from ui_settings import SettingsPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory() as folder:
                manager = ModelManager(folder)
                settings = AppSettings(str(Path(folder)/'settings.json'),manager)
                panel = SettingsPanel(frame,settings,auto_detect=False)
                with patch.object(manager,'process',return_value={'UVR-DeNoise.pth':'Test doğrulama hatası'}), patch('ui_settings.DetailsDialog') as dialog:
                    JOB_LOCK.acquire()
                    panel.EnableUI(False)
                    panel.RunJob('install',('UVR-DeNoise.pth',))
                    app.ProcessPendingEvents()
                    summary = panel.txt_status.GetValue()
                    self.assertIn('Gürültü Temizliği',summary)
                    self.assertIn('Test doğrulama hatası',summary)
                    dialog.return_value.__enter__.return_value.ShowModal.assert_called_once()
                    self.assertFalse(JOB_LOCK.locked())
                    self.assertTrue(panel.btn_repair.IsEnabled())
        finally:
            if JOB_LOCK.locked(): JOB_LOCK.release()
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_simple_hardware_summary_keeps_diagnostics_separate(self):
        from hardware import HardwareReport, DeviceSupport
        report = HardwareReport(DeviceSupport('cpu', 'Example CPU', True),
                                [DeviceSupport('cuda:0', 'Example GPU', True, backend='CUDA')],
                                runtime='PyTorch test')
        summary = report.summary('gpu')
        self.assertIn('Example GPU', summary)
        self.assertIn('Seçiminiz: Ekran kartı', summary)
        self.assertNotIn('PyTorch', summary)
        self.assertNotIn('CUDA', summary)
        self.assertIn('PyTorch test', report.describe())
        report.gpus = []
        self.assertIn('İşlemciyi seçin', report.summary('gpu'))
        self.assertNotIn('Ekran kartı kontrolü başarılı', report.summary('gpu'))

    def test_advanced_cover_controls_stay_native_and_keep_defaults(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with patch.object(ui_cover, 'load_models', return_value={}):
                panel = ui_cover.CoverPanel(frame)
            self.assertFalse(panel.advanced_options.IsShown())
            panel.advanced_toggle.SetValue(True)
            panel.OnAdvanced(None)
            self.assertTrue(panel.advanced_options.IsShown())
            self.assertIn('[AÇIK]', panel.advanced_toggle.GetLabel())
            self.assertEqual(panel.index_rate_ctrl.GetValue(), '0.75')
            self.assertEqual(panel.f0_choice.GetStringSelection(), 'rmvpe')
            self.assertTrue(all(control.GetValue() for control in panel.quality_controls.values()))
            panel.EnableUI(False)
            self.assertFalse(panel.advanced_toggle.IsEnabled())
            panel.EnableUI(True)
            panel.advanced_toggle.SetValue(False)
            panel.OnAdvanced(None)
            self.assertFalse(panel.advanced_options.IsShown())
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_system_contrast_colours_survive_dynamic_model_refresh(self):
        from ui_common import apply_native_style, DetailsDialog
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with patch.object(ui_cover, 'load_models', return_value={}):
                panel = ui_cover.CoverPanel(frame)
            with patch('ui_common.high_contrast_enabled', return_value=True):
                apply_native_style(panel)
                panel.model_list.SetModels(['voice'])
                button = panel.model_list.buttons[0]
                self.assertEqual(button.GetForegroundColour(), wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))
                self.assertEqual(button.GetBackgroundColour(), wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE))
            with DetailsDialog(panel, 'Teknik ayrıntılar', 'Readable diagnostic text') as dialog:
                self.assertEqual(dialog.details.GetName(), 'Teknik ayrıntılar')
                self.assertFalse(dialog.details.IsEditable())
                self.assertIsNotNone(dialog.FindWindowById(wx.ID_CANCEL))
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_start_thread_constructor_failure_releases_lock_and_restores_ui(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder, patch.object(ui_cover, 'load_models', return_value={}), patch.object(wx, 'MessageBox'), patch('app_settings.AppSettings.prepare_job', return_value='cpu'):
                root = Path(folder)
                source = root / 'input.wav'
                source.touch()
                cover = ui_cover.CoverPanel(frame)
                separator = ui_separator.SeparatorPanel(frame)
                cover.models = {'voice': {'pth': 'dummy.pth', 'index': ''}}
                cover.UpdateModelCheckList()
                cover.model_list.buttons[0].SetValue(True)
                cover.input_audio_path = separator.current_input_file = str(source)
                cover.output_folder_path = separator.output_directory = folder
                for panel in (cover, separator):
                    with patch.object(ui_cover.threading, 'Thread', side_effect=RuntimeError('thread unavailable')):
                        with self.assertRaisesRegex(RuntimeError, 'thread unavailable'):
                            panel.OnStart(None)
                    self.assertFalse(JOB_LOCK.locked())
                    self.assertTrue(panel.btn_start.IsEnabled())
                    self.assertFalse(panel.btn_cancel.IsEnabled())
        finally:
            if JOB_LOCK.locked(): JOB_LOCK.release()
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_model_selection_survives_refresh_and_controls_disable_immediately(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with patch.object(ui_cover, 'load_models', return_value={}):
                panel = ui_cover.CoverPanel(frame)
            panel.model_list.SetModels(['first'])
            panel.model_list.buttons[0].SetValue(True)
            panel.model_list.SetModels(['first', 'second'])
            self.assertEqual(panel.model_list.GetCheckedModels(), ['first'])
            self.assertIn('[AÇIK]', panel.model_list.buttons[0].GetLabel())
            panel.model_list.OnKeyDown(SimpleNamespace(GetKeyCode=lambda: wx.WXK_DOWN), 0)
            panel.model_list.OnKeyDown(SimpleNamespace(GetKeyCode=lambda: wx.WXK_UP), 1)
            panel.EnableUI(False)
            self.assertFalse(panel.btn_start.IsEnabled())
            self.assertFalse(panel.model_list.IsEnabled())
            self.assertTrue(panel.btn_cancel.IsEnabled())
            panel.UpdateStatus('outside range', 200)
            self.assertEqual(panel.gauge.GetValue(), 100)
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_queued_callback_skips_destroyed_window(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        with patch.object(wx, 'IsMainThread', return_value=False), patch.object(wx, 'CallAfter') as dispatch:
            with patch.object(wx, 'MessageBox') as message:
                post_ui(frame, message, 'should not be shown')
                callback = dispatch.call_args.args[0]
                frame.Destroy()
                app.Yield()
                callback()
                message.assert_not_called()

    def test_native_panels_have_accessible_names_and_supported_methods(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with patch.object(ui_cover, 'load_models', return_value={}):
                cover = ui_cover.CoverPanel(frame)
            separator = ui_separator.SeparatorPanel(frame)
            self.assertEqual(cover.f0_choice.GetStrings(), ['rmvpe', 'crepe'])
            self.assertEqual(cover.index_rate_ctrl.GetName(), 'Ses benzerlik oranı, 0 ile 1 arası')
            self.assertEqual(cover.txt_log.GetName(), 'İşlem günlüğü')
            self.assertEqual(separator.txt_status.GetName(), 'İşlem durumu ve yüzde')
            self.assertTrue(separator.chk_step1.GetValue())
            self.assertIn('[AÇIK]', separator.chk_step1.GetLabel())
            app.ProcessPendingEvents()
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()


if __name__ == '__main__':
    unittest.main()
