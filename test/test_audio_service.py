"""Real owned-process crash/cancellation regressions, plus worker dispatch."""
from pathlib import Path
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock
from audio_service import NativeAudioSession
from audio_worker import AudioEngine, short_input, check_audio_memory

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = '''import json, os, sys, time
from pathlib import Path
root=Path(sys.argv[1])
seq=1
while not (root/'stop').exists():
    path=root/f'request_{seq}.json'
    if not path.exists():
        time.sleep(.02)
        continue
    request=json.loads(path.read_text(encoding='utf-8'))
    if request['kind']=='unicode':
        print('日本語 Şarkı 😀',flush=True)
    if request['kind']=='crash':
        print('native failure evidence',flush=True)
        os._exit(7)
    if request['kind']=='hang':
        while True:time.sleep(.02)
    result={'pid':os.getpid()}
    if request['kind']=='tree':
        import subprocess
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        result['child_pid']=child.pid
    response=root/f'response_{seq}.json'
    temporary=response.with_suffix('.part')
    temporary.write_text(json.dumps({'ok':True,'result':result}),encoding='utf-8')
    os.replace(temporary,response)
    seq+=1
'''


class AudioServiceTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows owned process tree contract')
    def test_force_stop_kills_real_worker_and_descendant_even_with_venv_shim(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,self.session(folder) as session:
            result = session.execute('tree',{})
            handles = []
            timer = None
            try:
                for pid in (result['pid'],result['child_pid']):
                    handle = kernel.OpenProcess(0x00100000,False,pid)
                    self.assertTrue(handle,f'Open owned PID {pid}')
                    handles.append(handle)
                timer = threading.Timer(.4,session.request_force_stop)
                timer.start()
                with self.assertRaises(InterruptedError):
                    session.execute('hang',{})
                for handle in handles:
                    self.assertEqual(kernel.WaitForSingleObject(handle,3000),0,'Owned worker/descendant survived force stop')
            finally:
                if timer is not None:
                    timer.cancel()
                    timer.join()
                for handle in handles:
                    kernel.CloseHandle(handle)

    def session(self, directory):
        script = Path(directory)/'fixture.py'
        script.write_text(FIXTURE,encoding='utf-8')
        return NativeAudioSession(command=[sys.executable,'-u',str(script)],directory=directory)

    def test_persistent_worker_has_distinct_pid_and_owned_cleanup(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            preserved = Path(folder)/'personal.wav'
            preserved.write_bytes(b'personal')
            with self.session(folder) as session:
                first = session.execute('ping',{})
                second = session.execute('ping',{})
                directory = session.directory
                self.assertEqual(first,second)
                self.assertNotEqual(first['pid'],os.getpid())
            self.assertFalse(directory.exists())
            self.assertEqual(preserved.read_bytes(),b'personal')

    def test_native_crash_reports_exit_code_and_log_without_parent_exit(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, self.session(folder) as session:
            with self.assertRaisesRegex(RuntimeError,'çıkış kodu 7') as raised:
                session.execute('crash',{})
            self.assertIn('native failure evidence',str(raised.exception))

    def test_worker_stdio_is_utf8_for_unicode_paths(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, self.session(folder) as session:
            session.execute('unicode',{})
            self.assertIn('日本語 Şarkı 😀',(session.directory/'worker.log').read_text(encoding='utf-8'))

    def test_callback_error_closes_live_worker_with_bounded_cleanup(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, self.session(folder) as session:
            start = time.monotonic()
            with self.assertRaisesRegex(RuntimeError,'callback failed'):
                session.execute('hang',{},progress=lambda message:(_ for _ in ()).throw(RuntimeError('callback failed')))
            self.assertIsNotNone(session.process.poll())
            self.assertTrue(session._closed)
            self.assertLess(time.monotonic()-start,12.)

    def test_force_stop_interrupts_hung_native_worker_within_bound(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, self.session(folder) as session:
            timer = threading.Timer(.4,session.request_force_stop)
            start = time.monotonic()
            timer.start()
            try:
                with self.assertRaisesRegex(InterruptedError,'zorla'):
                    session.execute('hang',{})
            finally:
                timer.cancel()
                timer.join()
            self.assertLess(time.monotonic()-start,5.)
            self.assertIsNotNone(session.process.poll())

    def test_normal_cancel_discards_result_without_killing_worker(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder, self.session(folder) as session:
            initial_pid = session.execute('ping',{})['pid']
            with self.assertRaisesRegex(InterruptedError,'iptal'):
                session.execute('ping',{},cancelled=lambda:True)
            self.assertIsNone(session.process.poll())
            self.assertEqual(session.execute('ping',{})['pid'],initial_pid)

    def test_worker_reuses_helpers_and_cleans_voice_network_after_each_model(self):
        fake = Mock()
        import types
        module = types.ModuleType('rvc.infer.infer')
        module.VoiceConverter = Mock(return_value=fake)
        engine = AudioEngine()
        payload = {'device':'cpu','options':{'audio_output_path':'owned.wav'}}
        with patch.dict(sys.modules,{'rvc.infer.infer':module}),patch('hardware.configure_runtime'):
            engine.execute('cover',payload)
            engine.execute('cover',payload)
            self.assertEqual(module.VoiceConverter.call_count,1)
            self.assertEqual(fake.cleanup_model.call_count,2)
            fake.cleanup_model.assert_called_with(release_helpers=False)
            engine.close()
            fake.cleanup_model.assert_called_with()

    def test_long_unicode_source_alias_is_short_and_preserves_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            source = Path(folder)/('😀'*80+'.wav')
            source.write_bytes(b'original')
            output = Path(folder)/'stage'
            output.mkdir()
            alias = Path(short_input(source,output))
            self.assertEqual(alias.name,'input.wav')
            self.assertEqual(alias.read_bytes(),b'original')
            self.assertEqual(source.read_bytes(),b'original')

    def test_separator_memory_precheck_rejects_huge_header_before_decode(self):
        from types import SimpleNamespace
        with patch('soundfile.info',return_value=SimpleNamespace(frames=10**12,channels=2)), \
             patch('training.resources.memory_status',return_value={'available_ram_mb':1024}):
            with self.assertRaisesRegex(MemoryError,'RAM'):
                check_audio_memory('header-only.wav')


if __name__ == '__main__': unittest.main()
