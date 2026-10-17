"""Restricted model consent is accessible, optional and shared by the window."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wx
from restoration import MODEL_ID, MODEL_USAGE_NOTICE
from ui_model_terms import confirm_restoration_terms, confirm_demucs_terms, RestorationTermsDialog


class ModelTermsTests(unittest.TestCase):
    def test_decline_is_not_cached_and_acceptance_is_shared_by_the_window(self):
        root = SimpleNamespace()
        with patch('ui_model_terms.wx.GetTopLevelParent',return_value=root), \
                patch('ui_model_terms.RestorationTermsDialog') as dialog:
            response = dialog.return_value.__enter__.return_value.ShowModal
            response.side_effect = [wx.ID_CANCEL,wx.ID_OK]
            self.assertFalse(confirm_restoration_terms(Mock()))
            self.assertTrue(confirm_restoration_terms(Mock()))
            self.assertTrue(confirm_restoration_terms(Mock()))
            self.assertEqual(response.call_count,2)

    def test_only_download_and_repair_require_model_consent(self):
        from ui_settings import SettingsPanel
        panel = SimpleNamespace(model_list=Mock(),settings=SimpleNamespace(device_for=Mock()),StartJob=Mock())
        panel.model_list.GetCheckedModels.return_value = [MODEL_ID]
        with patch('ui_settings.confirm_restoration_terms',return_value=False) as confirm:
            for action in ('install','repair'):
                SettingsPanel.OnModels(panel,action)
            panel.StartJob.assert_not_called()
            self.assertEqual(confirm.call_count,2)
            SettingsPanel.OnModels(panel,'verify')
            panel.StartJob.assert_called_once_with('verify',[MODEL_ID])

    def test_six_source_consent_is_independent_and_required_before_download(self):
        from ui_settings import SettingsPanel
        root = SimpleNamespace(_a2sb_terms_accepted=True)
        with patch('ui_model_terms.wx.GetTopLevelParent',return_value=root), \
                patch('ui_model_terms.DemucsTermsDialog') as dialog:
            response = dialog.return_value.__enter__.return_value.ShowModal
            response.return_value = wx.ID_CANCEL
            self.assertFalse(confirm_demucs_terms(Mock()))
            response.assert_called_once()
        panel = SimpleNamespace(model_list=Mock(),settings=SimpleNamespace(device_for=Mock()),StartJob=Mock())
        panel.model_list.GetCheckedModels.return_value = ['demucs6']
        with patch('ui_settings.confirm_demucs_terms',return_value=False) as confirm:
            SettingsPanel.OnModels(panel,'install')
            panel.StartJob.assert_not_called()
            confirm.assert_called_once_with(panel)

    def test_terms_dialog_has_readable_notice_and_safe_default(self):
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with RestorationTermsDialog(frame) as dialog:
                labels = [' '.join(child.GetLabel().split()) for child in dialog.GetChildren()]
                self.assertIn(' '.join(MODEL_USAGE_NOTICE.split()),labels)
                self.assertIn('ticari olmayan',MODEL_USAGE_NOTICE)
                self.assertEqual(dialog.GetDefaultItem().GetId(),wx.ID_CANCEL)
                self.assertTrue(any('tarayıcıda aç' in label for label in labels))
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()
