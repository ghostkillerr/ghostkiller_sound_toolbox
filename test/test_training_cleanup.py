"""Session lifecycle regressions using disposable files, never user training data."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app_settings import write_json_atomic
from registry_store import registry_lock
from training.config import TrainingOptions, BACKEND_COMMIT, FORMAT_VERSION, TRAINER_REVISION
from training.service import delete_training_job, training_job_size, validate_resume, TrainingProcess
from training.storage import read_manifest


class TrainingCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.runs = self.root / 'training_runs'
        self.job = self.runs / 'parent'
        self.job.mkdir(parents=True)
        self.manifest = {
            'status': 'completed', 'options': TrainingOptions('parent', ('unused.wav',)).to_dict(),
            'format_version': FORMAT_VERSION, 'backend_commit': BACKEND_COMMIT,
            'trainer_revision': TRAINER_REVISION, 'device': 'cpu', 'asset_records': {},
        }
        write_json_atomic(str(self.job / 'manifest.json'), self.manifest)
        (self.job / 'resume.pth').write_bytes(b'last valid checkpoint')

    def test_failed_child_still_needs_parent_for_resume(self):
        child = self.runs / 'child'
        child.mkdir()
        write_json_atomic(str(child / 'manifest.json'), {
            'status': 'failed', 'options': {'name': 'child'},
            'initial_from': {'checkpoint': str(self.job / 'resume.pth')},
        })
        with self.assertRaisesRegex(ValueError, 'başlangıç'):
            delete_training_job(self.job, self.runs)
        self.assertEqual((self.job / 'resume.pth').read_bytes(), b'last valid checkpoint')

    def test_partial_cleanup_keeps_tombstone_and_can_be_retried(self):
        def interrupted_remove(path):
            (Path(path) / 'resume.pth').unlink()
            raise PermissionError('synthetic locked file')

        with patch('shutil.rmtree', side_effect=interrupted_remove):
            with self.assertRaises(PermissionError):
                delete_training_job(self.job, self.runs)
        self.assertEqual(read_manifest(self.job)['status'], 'deleting')
        delete_training_job(self.job, self.runs)
        self.assertFalse(self.job.exists())

    def test_corrupt_optional_cache_does_not_report_completed_deletion_as_failed(self):
        catalog = self.runs / 'preparation-cache.json'
        for value in ([], {'broken': []}):
            with self.subTest(value=value):
                job = self.runs / ('fixture_' + str(len(value)))
                job.mkdir()
                write_json_atomic(str(job / 'manifest.json'), self.manifest)
                catalog.write_text(json.dumps(value), encoding='utf-8')
                original = catalog.read_bytes()
                self.assertGreater(delete_training_job(job, self.runs), 0)
                self.assertFalse(job.exists())
                self.assertEqual(catalog.read_bytes(), original)

    def test_registered_model_inside_session_blocks_cleanup(self):
        write_json_atomic(str(self.root / 'models.json'), {
            'manual voice': {'pth': str(self.job / 'resume.pth'), 'index': ''},
        })
        with self.assertRaisesRegex(ValueError, 'AI Cover'):
            delete_training_job(self.job, self.runs)
        self.assertTrue((self.job / 'resume.pth').is_file())

    def test_other_sessions_source_recordings_are_not_deleted(self):
        source = self.job / 'comparison.wav'
        source.write_bytes(b'original input for another session')
        child = self.runs / 'other'
        child.mkdir()
        write_json_atomic(str(child / 'manifest.json'), {
            'status': 'created', 'options': {'name': 'other', 'sources': [str(source)]},
        })
        with self.assertRaisesRegex(ValueError, 'kaydı'):
            delete_training_job(self.job, self.runs)
        self.assertEqual(source.read_bytes(), b'original input for another session')

    def test_legacy_relative_model_in_frozen_app_blocks_cleanup(self):
        application = self.root / 'application'
        application.mkdir()
        write_json_atomic(str(self.root / 'models.json'), {
            'legacy voice': {'pth': '../training_runs/parent/resume.pth', 'index': ''},
        })
        with patch('training.cleanup.app_directory', return_value=str(application)):
            with self.assertRaisesRegex(ValueError, 'AI Cover'):
                delete_training_job(self.job, self.runs)
        self.assertTrue((self.job / 'resume.pth').is_file())

    def test_session_root_junction_is_rejected_before_resolution(self):
        # Emulate a Windows junction even on hosts without junction privileges.
        with patch.object(Path, 'is_junction', new=lambda value: value == self.job, create=True):
            with self.assertRaises(ValueError):
                training_job_size(self.job, self.runs)

    def test_resume_validation_does_not_modify_an_active_session(self):
        settings = SimpleNamespace(prepare_job=Mock(return_value='cpu'),
                                   manager=SimpleNamespace(root='changed-model-root', records={}, require_ready=Mock()))
        before = (self.job / 'manifest.json').read_bytes()
        for guard in ('controller.guard', 'worker.guard'):
            with self.subTest(guard=guard), registry_lock(self.job / guard):
                with self.assertRaises(TimeoutError):
                    validate_resume(self.job, settings)
            self.assertEqual((self.job / 'manifest.json').read_bytes(), before)

    def test_controller_rejects_cleanup_before_clearing_markers(self):
        self.manifest['status'] = 'deleting'
        write_json_atomic(str(self.job / 'manifest.json'), self.manifest)
        (self.job / 'cancel.request').write_bytes(b'keep cancellation')
        (self.job / 'heartbeat.json').write_bytes(b'keep heartbeat')
        with patch('native_process.NativeProcessGroup.spawn') as spawn:
            with self.assertRaisesRegex(ValueError, 'temizlen'):
                TrainingProcess().run(self.job, lambda value: None, resume=True)
        spawn.assert_not_called()
        self.assertEqual((self.job / 'cancel.request').read_bytes(), b'keep cancellation')
        self.assertEqual((self.job / 'heartbeat.json').read_bytes(), b'keep heartbeat')

    def test_raw_worker_rejects_cleanup_without_mutating_session(self):
        from training.worker import main
        self.manifest['status'] = 'deleting'
        write_json_atomic(str(self.job / 'manifest.json'), self.manifest)
        before = (self.job / 'manifest.json').read_bytes()
        with patch('training.worker._run_worker', return_value=0) as run:
            self.assertEqual(main([str(self.job), '--resume']), 1)
        run.assert_not_called()
        self.assertEqual((self.job / 'manifest.json').read_bytes(), before)

    def test_ui_leaves_cancel_marker_for_the_locked_controller(self):
        import wx
        import ui_training
        from app_runtime import JOB_LOCK
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            panel = ui_training.TrainingPanel(frame, SimpleNamespace(open_settings=Mock()))
            marker = self.job / 'cancel.request'
            marker.write_bytes(b'active cancellation')
            with patch('ui_training.validate_resume', return_value=TrainingOptions.from_dict(self.manifest['options'])), \
                 patch('ui_training.threading.Thread') as thread:
                panel.Start(True, str(self.job))
            thread.return_value.start.assert_called_once()
            self.assertEqual(marker.read_bytes(), b'active cancellation')
            panel.runner.cancel()
            self.assertTrue(panel.runner.cancel_requested)
        finally:
            if JOB_LOCK.locked():
                JOB_LOCK.release()
            frame.Destroy()
            app.ProcessPendingEvents()


if __name__ == '__main__':
    unittest.main()
