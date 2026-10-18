"""Global-Python source entrypoint picks prepared runtimes without changing settings."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import source_runtime

ROOT = Path(__file__).resolve().parents[1]


class SourceRuntimeTests(unittest.TestCase):
    def layout(self, folder, preference='gpu'):
        root = Path(folder)
        (root/'settings.json').write_text('{"device":"'+preference+'","other":"preserve"}', encoding='utf-8')
        for backend in ('cpu', 'cuda'):
            directory = root/'build'/('release_'+backend)/'Scripts'
            directory.mkdir(parents=True)
            (directory/'python.exe').touch()
            (directory/'pythonw.exe').touch()
        return root

    def test_global_python_honors_gpu_preference_and_never_mutates_settings(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.layout(folder)
            before = (root/'settings.json').read_bytes()
            result = source_runtime.source_interpreter(root, root/'global'/'python.exe')
            self.assertEqual(result, str(root/'build/release_cuda/Scripts/pythonw.exe'))
            self.assertEqual((root/'settings.json').read_bytes(), before)

    def test_cuda_is_retained_and_cpu_only_gui_honors_saved_gpu_choice(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.layout(folder)
            self.assertIsNone(source_runtime.source_interpreter(root, root/'build/release_cuda/Scripts/python.exe'))
            self.assertEqual(source_runtime.source_interpreter(root, root/'build/release_cpu/Scripts/python.exe'),
                             str(root/'build/release_cuda/Scripts/pythonw.exe'))

    def test_cpu_preference_and_missing_cuda_do_not_fall_back_to_another_backend(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.layout(folder, 'cpu')
            self.assertIn('release_cpu', source_runtime.source_interpreter(root, root/'global/python.exe'))
            (root/'settings.json').write_text('{"device":"gpu"}', encoding='utf-8')
            (root/'build/release_cuda/Scripts/python.exe').unlink()
            self.assertIsNone(source_runtime.source_interpreter(root, root/'global/python.exe'))

    def test_entrypoint_relaunches_only_gui_and_preserves_arguments(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.layout(folder)
            with patch.object(source_runtime, '__file__', str(root/'source_runtime.py')), \
                 patch.object(source_runtime.sys, 'executable', str(root/'global/python.exe')), \
                 patch.object(source_runtime.sys, 'frozen', False, create=True), \
                 patch.object(source_runtime.subprocess, 'Popen') as launch:
                self.assertTrue(source_runtime.relaunch_source(['main.py', '--example']))
                self.assertEqual(launch.call_args.args[0], [str(root/'build/release_cuda/Scripts/pythonw.exe'), str(root/'main.py'), '--example'])
                launch.reset_mock()
                for flag in ('--audio-worker', '--training-worker', '--self-test'):
                    self.assertFalse(source_runtime.relaunch_source(['main.py', flag]))
                launch.assert_not_called()


if __name__ == '__main__': unittest.main()
