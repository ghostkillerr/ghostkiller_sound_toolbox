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
