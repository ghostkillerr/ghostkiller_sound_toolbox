"""Opt-out, manual updates and detached maintenance without updating this host."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import wx
from app_runtime import JOB_LOCK
from app_settings import AppSettings
from model_manager import ModelManager
import updater
import windows_installer

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = b'MZ' + b'verified synthetic update fixture' * 4


def manifest():
    return {'version': '2.1.0', 'packages': {'cpu': {
        'download_url': 'https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/download/v2.1.0/Ghostkiller_V2_Setup_cpu_2.1.0.exe',
        'sha256': hashlib.sha256(PAYLOAD).hexdigest(), 'size': len(PAYLOAD)}}}


class ImmediateThread:
    def __init__(self, target, **kwargs):
        self.target = target

    def start(self):
        self.target()


class AutomaticUpdateTests(unittest.TestCase):
    def tearDown(self):
        if JOB_LOCK.locked():
            JOB_LOCK.release()
        if updater.CHECK_LOCK.locked():
            updater.CHECK_LOCK.release()

    def parent(self, enabled=True):
        return SimpleNamespace(settings=SimpleNamespace(auto_update=enabled), IsBeingDeleted=lambda: False)

    def check(self, parent, *, automatic=False, switch_off=False):
        response = io.BytesIO(json.dumps(manifest()).encode('utf-8'))
        def deliver(fn, *args):
            if switch_off:
                parent.settings.auto_update = False
            fn(*args)
        with patch.object(updater.threading, 'Thread', ImmediateThread), \
             patch.object(updater.wx, 'CallAfter', side_effect=deliver), \
             patch.object(updater.urllib.request, 'urlopen', return_value=response) as fetch, \
             patch.object(updater, 'last_update_result', return_value={}), \
             patch.object(updater, '_show_update_dialog') as show:
            updater.check_for_updates(parent, silent=automatic, automatic=automatic)
        return fetch, show

    def test_missing_preference_defaults_on_and_opt_out_survives_other_saves(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'settings.json'
            path.write_text('{"theme":"dark","other":"keep"}')
            settings = AppSettings(str(path), Mock())
            self.assertTrue(settings.auto_update)
            settings.select_auto_update(False)
            settings.select_theme('light')
            restored = AppSettings(str(path), Mock())
            self.assertFalse(restored.auto_update)
            self.assertEqual(json.loads(path.read_text())['other'], 'keep')
            with patch('app_settings.os.replace', side_effect=PermissionError('read only')):
                with self.assertRaises(PermissionError):
                    settings.select_auto_update(True)
            self.assertFalse(settings.auto_update)
            self.assertFalse(AppSettings(str(path), Mock()).auto_update)

    def test_disabled_startup_never_accesses_network_and_source_never_auto_updates(self):
        with patch.object(updater.urllib.request, 'urlopen') as fetch, \
             patch.object(updater.sys, 'frozen', True, create=True):
            updater.check_startup_updates(self.parent(False))
        fetch.assert_not_called()
        with patch.object(updater, 'check_for_updates') as check, \
             patch.object(updater.sys, 'frozen', False, create=True):
            updater.check_startup_updates(self.parent())
        check.assert_not_called()

    def test_installed_startup_enables_automatic_apply(self):
        parent = self.parent()
        with patch.object(updater.sys, 'frozen', True, create=True), patch.object(updater, 'check_for_updates') as check:
            updater.check_startup_updates(parent)
        check.assert_called_once_with(parent, silent=True, automatic=True)

    def test_native_welcome_is_closed_before_automatic_update_begins(self):
        import main
        parent = self.parent()
        with patch.object(main, 'check_startup_updates') as check:
            def welcome(*args):
                check.assert_not_called()
            with patch.object(main.wx, 'MessageBox', side_effect=welcome):
                main.GhostkillerMainFrame.ShowStartupMessage(parent)
        check.assert_called_once_with(parent)

    def test_turning_off_during_network_check_prevents_apply(self):
        _, show = self.check(self.parent(), automatic=True, switch_off=True)
        show.assert_not_called()

    def test_manual_check_still_works_when_automatic_updates_are_off(self):
        fetch, show = self.check(self.parent(False))
        fetch.assert_called_once()
        show.assert_called_once()
        self.assertFalse(show.call_args.kwargs['automatic'])

    def test_automatic_download_has_no_yes_no_dialog(self):
        for backend in ('cpu', 'cuda'):
            data = manifest()
            if backend == 'cuda':
                data['packages']['cuda'] = data['packages'].pop('cpu')
                data['packages']['cuda']['download_url'] = data['packages']['cuda']['download_url'].replace('_cpu', '_cuda')
            with self.subTest(backend=backend), patch.object(updater, 'runtime_backend', return_value=backend), \
                 patch.object(updater.wx, 'MessageDialog') as dialog, \
                 patch.object(updater, '_download_and_run_installer') as download:
                updater._show_update_dialog(self.parent(), data, silent=True, automatic=True)
            dialog.assert_not_called()
            download.assert_called_once()
            self.assertEqual(download.call_args.kwargs['backend'], backend)

    def test_invalid_automatic_package_cannot_download(self):
        with patch.object(updater, 'runtime_backend', return_value='cuda'), \
             patch.object(updater.wx, 'MessageBox') as message, \
             patch.object(updater, '_download_and_run_installer') as download:
            updater._show_update_dialog(self.parent(), manifest(), silent=True, automatic=True)
        message.assert_not_called()
        download.assert_not_called()

    def test_busy_startup_defers_without_interrupting_job_and_opt_out_cancels_retry(self):
        parent = self.parent()
        JOB_LOCK.acquire()
        with patch.object(updater.wx, 'CallLater') as later, \
             patch.object(updater, '_download_and_run_installer') as download:
            updater._show_update_dialog(parent, manifest(), silent=True, automatic=True)
            later.assert_called_once()
            self.assertTrue(JOB_LOCK.locked())
            JOB_LOCK.release()
            parent.settings.auto_update = False
            _, callback, *args = later.call_args.args
            callback(*args, **later.call_args.kwargs)
        download.assert_not_called()

    def test_failed_same_version_does_not_create_restart_loop_but_manual_retry_works(self):
        response = lambda *args, **kwargs: io.BytesIO(json.dumps(manifest()).encode('utf-8'))
        with patch.object(updater.threading, 'Thread', ImmediateThread), \
             patch.object(updater.wx, 'CallAfter', side_effect=lambda fn, *args: fn(*args)), \
             patch.object(updater.urllib.request, 'urlopen', side_effect=response), \
             patch.object(updater, 'last_update_result', return_value={'state':'failed', 'version':'2.1.0'}), \
             patch.object(updater, '_show_update_dialog') as show:
            updater.check_for_updates(self.parent(), silent=True, automatic=True)
            show.assert_not_called()
            updater.check_for_updates(self.parent(False))
            show.assert_called_once()

    def test_helper_acceptance_closes_app_only_after_verified_handoff(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'setup.exe'
            path.write_bytes(PAYLOAD)
            with patch.object(updater.threading, 'Thread', ImmediateThread), \
                 patch.object(updater.wx, 'CallAfter', side_effect=lambda fn, *args: fn(*args)), \
                 patch.object(updater, 'run_in_place_update', return_value=True) as handoff, \
                 patch.object(updater.wx, 'GetApp') as app:
                self.assertTrue(updater._launch_setup_and_exit(path, updater.validate_package(manifest(), 'cpu')))
            handoff.assert_called_once()
            app.return_value.ExitMainLoop.assert_called_once()
            self.assertFalse(JOB_LOCK.locked())

    def test_settings_checkbox_persists_and_button_remains_usable_when_off(self):
        from ui_settings import SettingsPanel
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            with tempfile.TemporaryDirectory() as folder:
                settings = AppSettings(str(Path(folder)/'settings.json'), ModelManager(folder))
                frame.settings = settings
                panel = SettingsPanel(frame, settings, auto_detect=False)
                self.assertTrue(panel.chk_auto_update.GetValue())
                panel.chk_auto_update.SetValue(False)
                panel.OnAutoUpdate(None)
                self.assertFalse(AppSettings(settings.path, settings.manager).auto_update)
                self.assertTrue(panel.btn_update.IsEnabled())
                with patch('ui_settings.check_for_updates') as check:
                    panel.OnCheckUpdates(None)
                check.assert_called_once_with(frame, silent=False)
                with patch.object(settings, 'save_option', side_effect=PermissionError('read only')), patch.object(wx, 'MessageBox'):
                    panel.chk_auto_update.SetValue(True)
                    panel.OnAutoUpdate(None)
                self.assertFalse(panel.chk_auto_update.GetValue())
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_helper_launch_states_are_distinct_and_missing_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'status.json'
            for state, exception in (('started', None), ('cancelled', windows_installer.InstallerLaunchCancelled), ('failed', RuntimeError)):
                path.write_text(json.dumps({'state':state, 'message':'fixture failure'}))
                if exception:
                    with self.assertRaises(exception):
                        windows_installer.wait_for_update_launch(Mock(), path)
                else:
                    self.assertTrue(windows_installer.wait_for_update_launch(Mock(), path))
            path.unlink()
            with self.assertRaises(RuntimeError):
                windows_installer.wait_for_update_launch(Mock(poll=lambda: 1), path)

    def test_handoff_targets_existing_directory_and_uses_hidden_silent_process(self):
        with tempfile.TemporaryDirectory(prefix='ghostkiller_update_') as folder:
            root = Path(folder)
            data = root/'data'
            data.mkdir()
            executable = root/'installed with spaces'/'Ghostkiller_Sound_Cleaner_V2.exe'
            setup = root/'Ghostkiller_V2_Setup.exe'
            setup.write_bytes(PAYLOAD)
            with patch.object(windows_installer.sys, 'frozen', True, create=True), \
                 patch.object(windows_installer.sys, 'executable', str(executable)), \
                 patch('app_runtime.data_directory', return_value=str(data)), \
                 patch('app_runtime.resource_directory', return_value=str(ROOT)), \
                 patch.object(windows_installer.subprocess, 'Popen') as start, \
                 patch.object(windows_installer, 'wait_for_update_launch', return_value=True):
                self.assertTrue(windows_installer.run_in_place_update(setup, updater.validate_package(manifest(), 'cpu')))
            job = json.loads((root/'job.json').read_text())
            self.assertIn('/VERYSILENT', job['arguments'])
            self.assertIn('/NORESTART', job['arguments'])
            self.assertIn('/NOCLOSEAPPLICATIONS', job['arguments'])
            # Windows CI TEMP may use an 8.3 alias; the launcher resolves it.
            self.assertIn(f'"/DIR={executable.resolve().parent}"', job['arguments'])
            self.assertIn(f'/GKUPDATEPID={os.getpid()}', job['arguments'])
            self.assertEqual(start.call_args.kwargs['creationflags'], subprocess.CREATE_NO_WINDOW)
            self.assertIn('-NonInteractive', start.call_args.args[0])
            self.assertEqual(Path(start.call_args.args[0][0]).name, 'powershell.exe')
            self.assertEqual(start.call_args.kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')


@unittest.skipUnless(os.name == 'nt', 'Windows PowerShell helper contract')
class PowerShellUpdateHelperTests(unittest.TestCase):
    def run_helper(self, scenario, code=0, *, parent_exited=False):
        with tempfile.TemporaryDirectory(prefix='ghostkiller_update_') as folder:
            root = Path(folder)
            target = root/'installed'
            internal = target/'_internal'
            internal.mkdir(parents=True)
            (internal/'version.json').write_text('{"version":"2.1.0"}')
            (internal/'build-info.json').write_text('{"backend":"cpu"}')
            if scenario == 'wrong_backend':
                (internal/'build-info.json').write_text('{"backend":"cuda"}')
            setup = root/'Ghostkiller_V2_Setup.exe'
            setup.write_bytes(PAYLOAD if scenario != 'tampered' else PAYLOAD + b'tampered')
            result = target/'result.json'
            status = root/'status.json'
            calls = target/'calls.json'
            config = root/'job.json'
            config.write_text(json.dumps({
                'installer':str(setup), 'sha256':hashlib.sha256(PAYLOAD).hexdigest(), 'size':len(PAYLOAD),
                'version':'2.1.0', 'backend':'cpu', 'executable':str(target/'app.exe'),
                'parent_pid':os.getpid(), 'arguments':'/VERYSILENT /NORESTART /GKUPDATEPID=123',
                'status':str(status), 'result':str(result),
            }))
            probe = target/'probe.ps1'
            probe.write_text(r'''
param($Helper, $Config, $Calls, $Scenario, [int]$Code, [int]$Exited)
. $Helper
$global:observed = @{launch = 0; restart = 0; notice = 0}
function Get-UpdateParent($Id) { return [pscustomobject]@{HasExited = [bool]$Exited} }
function Start-UpdateInstaller($Job) {
    $global:observed.launch++
    $global:observed.arguments = $Job.arguments
    if ($Scenario -eq 'cancelled') { throw [ComponentModel.Win32Exception]::new(1223) }
    $process = [pscustomobject]@{ExitCode = $Code}
    $process | Add-Member ScriptMethod WaitForExit {}
    return $process
}
function Restart-UpdatedApplication($Job) { $global:observed.restart++ }
function Show-UpdateNotice($Message) { $global:observed.notice++ }
Invoke-InPlaceUpdate -JobPath $Config
Write-UpdateState $Calls $global:observed
''', encoding='utf-8-sig')
            powershell = Path(os.environ.get('SystemRoot', r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
            run = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                  '-File', str(probe), str(ROOT/'update_helper.ps1'), str(config), str(calls), scenario, str(code), str(int(parent_exited))],
                                 capture_output=True, text=True, errors='replace', timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            return json.loads(result.read_text(encoding='utf-8-sig')), json.loads(calls.read_text(encoding='utf-8-sig'))

    def test_hash_change_and_uac_cancel_do_not_apply(self):
        result, calls = self.run_helper('tampered')
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(calls['launch'], 0)
        result, calls = self.run_helper('cancelled')
        self.assertEqual(result['state'], 'cancelled')
        self.assertEqual(calls['restart'], 0)

    def test_setup_exit_and_installed_backend_are_verified(self):
        for scenario, code, state in (('ok',0,'completed'), ('ok',1,'failed'), ('ok',3010,'restart_required'),
                                      ('wrong_backend',0,'failed')):
            with self.subTest(scenario=scenario, code=code):
                result, calls = self.run_helper(scenario, code)
                self.assertEqual(result['state'], state)
                self.assertEqual(calls['launch'], 1)
                self.assertIn('/VERYSILENT', calls['arguments'])
                self.assertEqual(calls['restart'], 0)  # Never start a second app while parent is alive.

    def test_finished_helper_restarts_and_cleans_only_its_own_download(self):
        for code, restart, notice in ((0,1,0), (1,1,0), (3010,0,1)):
            with self.subTest(code=code):
                result, calls = self.run_helper('ok', code, parent_exited=True)
                self.assertEqual(calls['restart'], restart)
                self.assertEqual(calls['notice'], notice)


if __name__ == '__main__':
    unittest.main()
