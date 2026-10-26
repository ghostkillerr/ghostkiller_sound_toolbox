"""Task flow regressions with isolated settings, synthetic models and native controls."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wx
from app_runtime import JOB_LOCK
from app_settings import AppSettings, write_json_atomic
from model_manager import ModelManager, file_digest


class PreferredExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = self.root/'training_runs'/'voice'
        self.job.mkdir(parents=True)
        self.registry = self.root/'models.json'
        self.index = self.job/'voice.index'
        self.index.write_bytes(b'shared index')
        self.records = []
        for name, data, epoch in (('epoch.pth', b'epoch', 20),
                                   ('latest.pth', b'epoch', None),
                                   ('best_validation.pth', b'favorite', None)):
            path = self.job/name
            path.write_bytes(data)
            self.records.append(dict(file=name, pth=str(path), sha256=file_digest(path),
                                     epoch=epoch, smoke_passed=True))
        self.write('manifest.json', {'status': 'completed', 'options': {'name': 'Voice', 'epochs': 20}})
        self.write('result.json', {'models': self.records, 'index': str(self.index),
                                  'index_sha256': file_digest(self.index)})
        self.write('notes.json', {'preferred_model': 'best_validation.pth'})

    def write(self, name, data):
        write_json_atomic(str(self.job/name), data)

    def test_bulk_export_preserves_preference_and_deduplicates_latest(self):
        from training.service import register_models, delete_training_job
        names, destination = register_models(self.job, self.registry, candidates=('latest.pth',))
        self.assertEqual(len(names), 2)
        saved = json.loads(self.registry.read_text(encoding='utf-8'))
        self.assertEqual({Path(r['pth']).read_bytes() for r in saved.values()}, {b'epoch', b'favorite'})
        self.assertEqual(len({r['index'] for r in saved.values()}), 1)
        self.assertTrue(self.job.is_dir())
        delete_training_job(self.job, self.job.parent)
        self.assertFalse(self.job.exists())
        self.assertTrue(all(Path(r['pth']).is_file() and Path(r['index']).is_file() for r in saved.values()))

    def test_single_export_only_saves_selected_and_cleanup_keeps_unsaved_preference(self):
        from training.service import register_models, delete_training_job
        names, _ = register_models(self.job, self.registry, candidates=('latest.pth',), include_epochs=False)
        self.assertEqual(len(names), 1)
        with self.assertRaisesRegex(ValueError, 'Tercih ettiğiniz model'):
            delete_training_job(self.job, self.job.parent)
        self.assertEqual((self.job/'best_validation.pth').read_bytes(), b'favorite')

    def test_changed_permanent_preference_blocks_cleanup(self):
        from training.service import register_models, delete_training_job
        register_models(self.job, self.registry)
        saved = json.loads(self.registry.read_text(encoding='utf-8'))
        for r in saved.values():
            if Path(r['pth']).read_bytes() == b'favorite':
                Path(r['pth']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Tercih ettiğiniz model'):
            delete_training_job(self.job, self.job.parent)
        self.assertTrue(self.job.is_dir())

    def test_changed_candidate_does_not_create_partial_export(self):
        from training.service import register_models
        (self.job/'best_validation.pth').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'sonradan değişmiş'):
            register_models(self.job, self.registry)
        self.assertFalse(self.registry.exists())
        self.assertFalse((self.root/'trained_models').exists())


class TaskFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp() or wx.App(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings = AppSettings(str(self.root/'settings.json'), ModelManager(self.root))
        self.frame = wx.Frame(None, size=(800, 850))

    def tearDown(self):
        self.frame.Destroy()
        self.app.ProcessPendingEvents()
        if JOB_LOCK.locked():
            JOB_LOCK.release()
        self.temp.cleanup()

    def test_action_bar_status_is_inside_frame_at_startup_and_after_tab_change(self):
        from main import GhostkillerMainFrame
        with patch('app_settings.AppSettings', return_value=self.settings), \
             patch('ui_cover.load_models', return_value={}), \
             patch('ui_settings.SettingsPanel.OnHardware'), \
             patch('ui_live_cover.LiveCoverPanel.RefreshDevices'), \
             patch.object(GhostkillerMainFrame, 'BeginStartupSequence'):
            frame = GhostkillerMainFrame()
            try:
                for size in ((800, 850), (680, 600), (1000, 700)):
                    frame.SetSize(size)
                    frame.Layout()
                    for index in range(5):
                        frame.notebook.SetSelection(index)
                        bar = frame.action_bars[index]
                        page = frame.notebook.GetPage(index)
                        self.assertIs(page.txt_status.GetParent(), bar)
                        self.assertGreaterEqual(page.txt_status.GetSize().height, frame.FromDIP(42), (size, index, bar.GetRect()))
                        self.assertLessEqual(page.txt_status.GetRect().bottom, bar.GetClientSize().height)
                        self.assertLessEqual(bar.GetRect().bottom, bar.GetParent().GetClientSize().height)
                        self.assertEqual(sum(b.IsShown() for b in frame.action_bars), 1)
                frame.cover_tab.SetInput(str(self.root/'vocal.wav'))
                frame.notebook.SetSelection(1)
                with patch.object(frame.settings_tab, 'PrepareRequiredModels'):
                    frame.PrepareModels(('contentvec',))
                frame.settings_tab.return_action()
                self.assertEqual(frame.notebook.GetSelection(), 1)
                self.assertEqual(frame.cover_tab.input_audio_path, str(self.root/'vocal.wav'))
                for shift, expected in ((False, 2), (True, 1)):
                    event = Mock()
                    event.GetKeyCode.return_value = wx.WXK_TAB
                    event.ControlDown.return_value = True
                    event.ShiftDown.return_value = shift
                    frame.OnNavigationKey(event)
                    self.assertEqual(frame.notebook.GetSelection(), expected)
                    event.Skip.assert_not_called()
            finally:
                frame.Destroy()
                self.app.ProcessPendingEvents()

    def test_search_preserves_checked_models_outside_visible_results(self):
        from ui_cover import ModelToggleList
        models = ModelToggleList(self.frame)
        models.SetModels(['Alice', 'Bob', 'Charlie'], checked_models=['Bob'])
        models.search.SetValue('Alice')
        models.FilterModels()
        self.assertFalse(models.buttons[1].IsShown())
        self.assertEqual(models.GetCheckedModels(), ['Bob'])
        self.assertIn('1 model işaretli', models.selection_summary.GetLabel())
        models.search.SetValue('')
        models.FilterModels()
        self.assertTrue(all(b.IsShown() for b in models.buttons))

    def test_model_import_accepts_empty_optional_index_and_rejects_bad_paths(self):
        from ui_models import AddModelDialog
        model = self.root/'voice.pth'
        model.write_bytes(b'fixture')
        with AddModelDialog(self.frame, ['Existing']) as dialog, patch.object(dialog, 'EndModal') as end:
            dialog.model_name.SetValue('Voice')
            dialog.paths['pth'].SetValue(str(model))
            dialog.OnSave(None)
            end.assert_called_once_with(wx.ID_OK)
            self.assertEqual(dialog.Value(), ('Voice', {'pth': str(model), 'index': ''}))
            end.reset_mock()
            dialog.paths['index'].SetValue(str(self.root/'absent.index'))
            dialog.OnSave(None)
            end.assert_not_called()
            self.assertIn('.index', dialog.error.GetLabel())
            self.assertLessEqual(dialog.FindWindow(wx.ID_OK).GetRect().bottom, dialog.GetClientSize().height)

    def test_results_mark_latest_vocal_and_transfer_only_vocal(self):
        from ui_operation import ResultList
        owner = wx.ScrolledWindow(self.frame)
        self.settings.use_vocal = Mock()
        results = ResultList(owner, self.settings)
        results.Add(self.root/'vocal.flac', 'Ayrılmış vokal', True)
        results.Add(self.root/'clean.flac', 'Temiz vokal', True)
        results.Add(self.root/'music.flac', 'Enstrümantal')
        self.assertNotIn('Son vokal', results.list.GetString(0))
        self.assertIn('Son vokal', results.list.GetString(1))
        self.assertFalse(results.cover.IsEnabled())
        results.OnCover(None)
        self.settings.use_vocal.assert_not_called()
        results.list.SetSelection(1)
        results.OnCover(None)
        self.settings.use_vocal.assert_called_once_with(str(self.root/'clean.flac'))
        results.Clear()
        self.assertFalse(results.IsShown())
        self.assertEqual(results.records, [])

    def test_download_estimate_never_downloads_and_requires_explicit_yes(self):
        from ui_settings import SettingsPanel
        panel = SettingsPanel(self.frame, self.settings, auto_detect=False)
        with patch.object(self.settings.manager, 'download_estimate', return_value=(1000, 2)), \
             patch.object(self.settings.manager, 'process') as download, \
             patch.object(panel, 'QueueDownloadConfirmation') as queue, \
             patch('ui_settings.finish_job'), \
             patch('ui_settings.post_ui', side_effect=lambda owner, fn, *args: fn(*args)):
            panel.RunJob('estimate:install', ('contentvec',))
            queue.assert_called_once_with('install', ('contentvec',), 1000, 2)
            download.assert_not_called()
        with patch('ui_settings.wx.MessageDialog') as dialog, patch.object(panel, 'StartJob') as start:
            modal = dialog.return_value.__enter__.return_value
            modal.ShowModal.return_value = wx.ID_NO
            panel.ConfirmDownload('install', ('contentvec',), 1000, 2)
            start.assert_not_called()
            self.assertIn('2 dosyanın boyutu bilinmiyor', dialog.call_args.args[1])
            modal.ShowModal.return_value = wx.ID_YES
            panel.ConfirmDownload('install', ('contentvec',), 1000, 2)
            start.assert_called_once_with('install', ('contentvec',))

    def test_empty_cover_uses_inline_guidance_and_training_actions_are_disabled(self):
        from ui_cover import CoverPanel
        from ui_training import TrainingPanel
        with patch('ui_cover.load_models', return_value={}), patch('wx.MessageBox') as message:
            cover = CoverPanel(self.frame, self.settings)
            cover.OnStart(None)
            self.assertIn('model', cover.txt_status.GetValue())
            message.assert_not_called()
            training = TrainingPanel(self.frame, self.settings)
            training.OnStart(None)
            self.assertIn('kayıt', training.txt_status.GetValue())
            message.assert_not_called()
            self.assertFalse(training.btn_save_selected.IsEnabled())

    def test_download_confirmation_waits_until_finish_has_released_job_lock(self):
        from app_runtime import finish_job
        from ui_settings import SettingsPanel
        panel = SettingsPanel(self.frame, self.settings, auto_detect=False)
        JOB_LOCK.acquire()
        panel.EnableUI(False)
        with patch.object(panel, 'ConfirmDownload', side_effect=lambda *args: self.assertFalse(JOB_LOCK.locked())) as confirm:
            panel.QueueDownloadConfirmation('repair', ('contentvec',), 1, 0)
            self.app.ProcessPendingEvents()
            confirm.assert_not_called()
            finish_job(panel)
            self.app.ProcessPendingEvents()
            self.app.ProcessPendingEvents()
            confirm.assert_called_once_with('repair', ('contentvec',), 1, 0)

    def test_live_advanced_fields_are_folded_and_model_form_does_not_switch_tab(self):
        from ui_live_cover import LiveCoverPanel
        self.settings.add_model = Mock()
        with patch.object(LiveCoverPanel, 'RefreshDevices'):
            panel = LiveCoverPanel(self.frame, self.settings, models={})
        self.assertFalse(panel.advanced.IsShown())
        self.assertIs(panel.f0_choice.GetParent(), panel.advanced)
        self.assertIs(panel.btn_calibrate.GetParent(), panel)
        event = wx.CommandEvent(wx.EVT_BUTTON.typeId, panel.btn_add_model.GetId())
        panel.btn_add_model.GetEventHandler().ProcessEvent(event)
        self.settings.add_model.assert_called_once()

    def test_dark_radio_labels_follow_theme_and_raise_native_choice_event(self):
        from ui_common import RadioChoice, apply_native_style
        self.frame.settings = SimpleNamespace(theme='dark')
        choices = RadioChoice(self.frame, 'Donanım', ['İşlemci', 'Ekran kartı'])
        apply_native_style(choices)
        self.assertGreater(choices.buttons[0].GetForegroundColour().Red(), 200)
        choices.SetSelection(1)
        handler = Mock()
        choices.Bind(wx.EVT_RADIOBOX, handler)
        choices.OnChoice(None)
        self.assertEqual(handler.call_args.args[0].GetInt(), 1)

    def test_about_identifies_source_and_frozen_backend_and_build(self):
        from ui_help import application_identity
        self.assertIn('Yerel kaynak', application_identity())
        (self.root/'build-info.json').write_text(json.dumps({
            'backend': 'cuda', 'built_at_utc': '2026-10-25T00:00:00+00:00',
            'application_source_sha256': 'fixture-source'}), encoding='utf-8')
        with patch('sys.frozen', True, create=True), patch('ui_help.resource_directory', return_value=str(self.root)), \
             patch('ui_help.read_application_version', return_value='2.1.0'):
            identity = application_identity()
        self.assertIn('CUDA', identity)
        self.assertIn('2026-10-25T00:00:00+00:00', identity)
        self.assertIn('fixture-source', identity)


if __name__ == '__main__':
    unittest.main()
