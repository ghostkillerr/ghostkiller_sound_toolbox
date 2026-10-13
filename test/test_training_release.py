"""Release regressions with synthetic audio, clocks and isolated worker fixtures."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from app_runtime import configure_runtime_cache
configure_runtime_cache()
from training.config import TrainingOptions
from training.dataset import estimate_storage, segment_extent, prepare, checkpoint_reserve
from training.service import TrainingProcess

ROOT = Path(__file__).resolve().parents[1]


class TrainingReleaseTests(unittest.TestCase):
    def test_checkpoint_single_batch_terminal_cursor_and_exact_resume(self):
        self.exercise_checkpoint_exact_resume("cpu")

    def exercise_checkpoint_exact_resume(self,device):
        import torch
        import training.engine as engine
        clock = [0.]
        dataset = [torch.ones(1) for _ in range(3)]
        options = TrainingOptions("release",("unused.wav",),epochs=10,save_every=10,batch_size=3)

        def step(info,net_g,net_d,opt_g,opt_d,config):
            value = torch.rand((),device=device).item()+random.random()+np.random.random()
            for model,opt in ((net_g,opt_g),(net_d,opt_d)):
                opt.zero_grad()
                model(torch.tensor([[value]],dtype=torch.float32,device=device)).square().sum().backward()
                opt.step()
            clock[0] += 61
            return {"loss_g":1.,"loss_d":1.,"loss_mel":1.,"loss_kl":1.}

        with tempfile.TemporaryDirectory(dir=ROOT) as folder,ExitStack() as stack:
            patches = {"TextAudioLoaderMultiNSFsid":Mock(return_value=dataset),
                       "TextAudioCollateMultiNSFsid":Mock(return_value=lambda batch:[torch.ones(1)]),
                       "model_pair":Mock(side_effect=lambda *a:(torch.nn.Linear(1,1),torch.nn.Linear(1,1))),
                       "load_pretrained":Mock(),"train_step":Mock(side_effect=step),
                       "evaluate":Mock(return_value=1.),"export_model":Mock(),
                       "update_manifest":Mock(),"ResourceMonitor":Mock()}
            for key,value in patches.items(): stack.enter_context(patch.object(engine,key,value))
            stack.enter_context(patch.object(engine.time,"monotonic",side_effect=lambda:clock[0]))
            full = Path(folder)/"full"
            resume = Path(folder)/"resume"
            full.mkdir(); resume.mkdir()
            engine.run_training(full,options,device,folder,lambda *a,**k:None)
            baseline = torch.load(full/"resume.pth",map_location="cpu",weights_only=True)
            clock[0] = 0
            def crash(stage,**values):
                if stage == "checkpoint":
                    raise RuntimeError("synthetic crash after committed periodic checkpoint")
            with self.assertRaisesRegex(RuntimeError,"synthetic crash"):
                engine.run_training(resume,options,device,folder,crash)
            paused = torch.load(resume/"resume.pth",map_location="cpu",weights_only=True)
            self.assertEqual((paused["epoch"],paused["step"],paused["next_batch"]),(5,5,1))
            self.assertEqual(clock[0],305)
            self.assertEqual(paused["scheduler_g"]["last_epoch"],4)
            original_load = torch.load
            with patch.object(torch,"load",wraps=original_load) as loader:
                result = engine.run_training(resume,options,device,folder,lambda *a,**k:None,resume=True)
            self.assertEqual(result["steps"],10)
            self.assertEqual(loader.call_args.kwargs,{"map_location":"cpu","weights_only":True,"mmap":True})
            continued = original_load(resume/"resume.pth",map_location="cpu",weights_only=True)
            self.assertEqual(continued["scheduler_g"],baseline["scheduler_g"])
            self.assertEqual(continued["scheduler_d"],baseline["scheduler_d"])
            self.assertEqual(continued["python_rng"],baseline["python_rng"])
            self.assertEqual(continued["numpy_rng"],baseline["numpy_rng"])
            torch.testing.assert_close(continued["torch_rng"],baseline["torch_rng"],rtol=0,atol=0)
            self.assertEqual(continued["rng_layout"],baseline["rng_layout"])
            for actual,expected in zip(continued["device_rng"],baseline["device_rng"]):
                torch.testing.assert_close(actual,expected,rtol=0,atol=0)
            for key in ("generator","discriminator"):
                for name,value in baseline[key].items():
                    torch.testing.assert_close(continued[key][name],value,rtol=0,atol=0)

    def test_sample_rounding_cannot_create_zero_step(self):
        with self.assertRaisesRegex(ValueError,"ses örneği"):
            TrainingOptions("voice",("unused",),segment_seconds=1.000001,overlap_seconds=1.).validate(False)

    def test_resume_requires_same_backend_and_rng_layout_and_allows_legacy_cpu(self):
        from training.storage import validate_checkpoint_backend
        cpu = {"kind":"cpu","runtime":"cpu","device_count":0,"device_index":None}
        cuda = {"kind":"cuda","runtime":"cuda","device_count":1,"device_index":0}
        hip = {**cuda,"runtime":"hip"}
        xpu = {**cuda,"kind":"xpu","runtime":"xpu"}
        cases = (({"rng_layout":cpu,"device_rng":[]},cuda,False),
                 ({"rng_layout":cuda,"device_rng":[1]},cpu,False),
                 ({"rng_layout":cuda,"device_rng":[1]},hip,False),
                 ({"rng_layout":cuda,"device_rng":[1]},xpu,False),
                 ({"rng_layout":cuda,"device_rng":[1]},{**cuda,"device_count":2},False),
                 ({"rng_layout":cuda,"device_rng":[1]},{**cuda,"device_index":1},False),
                 ({"rng_layout":cuda,"device_rng":[]},cuda,False),
                 ({"rng_layout":cuda,"device_rng":[1]},cuda,True),
                 ({"cuda_rng":[]},cpu,True),
                 ({"cuda_rng":[]},cuda,False),
                 ({"cuda_rng":[1]},cuda,True),
                 ({"cuda_rng":[1]},hip,False))
        for checkpoint,current,allowed in cases:
            with self.subTest(current=current,checkpoint=checkpoint),patch("training.storage.rng_layout",return_value=current):
                if allowed: self.assertEqual(validate_checkpoint_backend(checkpoint,"fixture"),current)
                else:
                    with self.assertRaises(ValueError): validate_checkpoint_backend(checkpoint,"fixture")

    def test_extent_matches_actual_segment_loop_including_holdout_tails(self):
        for frames in (0,40000,40100,80000,119000,1600000):
            for segment,step in ((120000,108000),(40000,4000),(40000,1)):
                reference = [min(segment,frames-pos) for pos in range(0,frames,step)
                             if min(segment,frames-pos) >= 40000]
                self.assertEqual(segment_extent(frames,segment,step,40000),(len(reference),sum(reference)))

    def test_high_overlap_storage_counts_real_segments(self):
        options = TrainingOptions("voice",("unused",),segment_seconds=1.,overlap_seconds=.9)
        normal = TrainingOptions("voice",("unused",),segment_seconds=1.,overlap_seconds=0.)
        high = estimate_storage(40000*600,options,checkpoint_bytes=0)
        low = estimate_storage(40000*600,normal,checkpoint_bytes=0)
        self.assertEqual(high["pieces"],5991)
        self.assertGreater(high["bytes"],9*low["bytes"])
        timeline = estimate_storage(40000*600,options,single_source=True,checkpoint_bytes=0)
        self.assertEqual(timeline["pieces"],5982)

    def test_high_overlap_disk_failure_prevents_decode_and_source_changes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            source = root/"source.wav"
            source.write_bytes(b"untouched synthetic source")
            job = root/"job"; job.mkdir()
            options = TrainingOptions("voice",(str(source),),segment_seconds=1.,overlap_seconds=.9)
            normal = TrainingOptions("voice",(str(source),),segment_seconds=1.,overlap_seconds=0.)
            available = estimate_storage(40000*600,normal,True)["bytes"]+40000*600*4+4096
            with patch("training.dataset.shutil.disk_usage",return_value=SimpleNamespace(free=available)), \
                 patch("training.dataset.subprocess.run",return_value=SimpleNamespace(stdout=b"600\n",returncode=0)), \
                 patch("training.dataset.decode") as decoder:
                with self.assertRaisesRegex(RuntimeError,"boş disk"):
                    prepare(job,options,lambda *a,**k:None)
            decoder.assert_not_called()
            self.assertEqual(source.read_bytes(),b"untouched synthetic source")

    def test_existing_checkpoint_requires_atomic_second_generation(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/"resume.pth"
            path.write_bytes(b"synthetic checkpoint")
            original_stat = Path.stat
            def stat(value,*args,**kwargs):
                if value == path:
                    return SimpleNamespace(st_size=2*1024**3,st_mode=0o100000)
                return original_stat(value,*args,**kwargs)
            with patch.object(Path,"stat",new=stat):
                self.assertEqual(checkpoint_reserve(folder,TrainingOptions("voice",("unused",))),4*1024**3)

    def test_fp16_pretrained_reserve_includes_fp32_adam_and_atomic_generations(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            pretrained = root/"models"/"pretrained"/"v2"
            pretrained.mkdir(parents=True)
            generator,discriminator = pretrained/"f0G40k.pth",pretrained/"f0D40k.pth"
            generator.write_bytes(b"synthetic FP16 G metadata")
            discriminator.write_bytes(b"synthetic FP16 D metadata")
            (root/"manifest.json").write_text(json.dumps({"model_root":str(root/"models")}),encoding="utf-8")
            sizes = {generator:200*1024**2,discriminator:500*1024**2}
            original_stat = Path.stat
            def stat(path,*args,**kwargs):
                if path in sizes: return SimpleNamespace(st_size=sizes[path],st_mode=0o100000)
                return original_stat(path,*args,**kwargs)
            with patch.object(Path,"stat",new=stat):
                self.assertEqual(checkpoint_reserve(root,TrainingOptions("voice",("unused",))),
                                 12*(sizes[generator]+sizes[discriminator])+6*sizes[generator]+16*1024**2)

    def fixture(self, folder):
        root = Path(folder)
        (root/"manifest.json").write_text(json.dumps({"options":TrainingOptions("voice",("unused",)).to_dict(),"status":"running","error":""}),encoding="utf-8")
        return root

    def test_native_worker_empty_error_contains_exit_phase_and_log(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.fixture(folder)
            (root/"heartbeat.json").write_text(json.dumps({"stage":"train"}))
            (root/"worker.log").write_text("native DLL load failed\n",encoding="utf-8")
            process = SimpleNamespace(poll=lambda:-1073741819,returncode=-1073741819)
            def spawn(*args,**kwargs):
                (root/"heartbeat.json").write_text(json.dumps({"stage":"train"}))
                return process
            with patch("training.service.subprocess.Popen",side_effect=spawn):
                with self.assertRaises(RuntimeError) as caught:
                    TrainingProcess().run(folder,lambda *a:None)
            self.assertIn("0xC0000005",str(caught.exception))
            self.assertIn("DLL load failed",str(caught.exception))
            self.assertIn("worker.log",str(caught.exception))
            self.assertIn("son aşama: train",str(caught.exception))

    def test_windowed_worker_error_reads_newest_two_owned_runtime_logs(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.fixture(folder)
            (root/"worker.log").touch()
            for index in range(3):
                path = root/f"worker_runtime_{index}.log"
                path.write_text(f"diagnostic{index}: missing native DLL",encoding="utf-8")
                os.utime(path,ns=(100+index,100+index))
            runner = TrainingProcess()
            runner.job = folder
            message = runner._error_detail(1)
            self.assertIn("diagnostic2",message)
            self.assertIn("diagnostic1",message)
            self.assertNotIn("diagnostic0",message)
            self.assertIn("missing native DLL",message)

    def test_duplicate_worker_rejects_before_training_without_manifest_changes(self):
        from training.worker import main
        from registry_store import registry_lock
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.fixture(folder)
            before = (root/"manifest.json").read_bytes()
            with registry_lock(root/"worker.guard"),patch("training.worker._run_worker") as run,patch("training.worker.sys.stderr"):
                self.assertEqual(main([folder]),1)
            run.assert_not_called()
            self.assertEqual((root/"manifest.json").read_bytes(),before)

    def test_training_worker_probe_is_atomic_native_cpu_without_model_dispatch(self):
        from training.worker import main
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            target = Path(folder)/"probe.json"
            with patch("training.worker._run_worker") as train:
                self.assertEqual(main(["--probe",str(target)]),0)
            train.assert_not_called()
            result = json.loads(target.read_text(encoding="utf-8"))
            self.assertTrue(result["ok"] and result["forward_backward"])
            self.assertEqual(result["device"],"cpu")
            self.assertEqual(result["pid"],os.getpid())
            self.assertTrue(result["torch_version"])
            self.assertFalse((Path(folder)/"worker.guard.lock").exists())
            self.assertEqual(list(Path(folder).glob("*.part")),[])

    def test_training_worker_probe_reports_path_and_file_errors_with_native_codes(self):
        from training.worker import main
        with tempfile.TemporaryDirectory(dir=ROOT) as folder,patch("training.worker.sys.stderr"):
            target = Path(folder)/"probe.json"
            target.write_bytes(b"previous successful report")
            self.assertEqual(main(["--probe",folder]),1)
            with patch("app_settings.write_json_atomic",side_effect=OSError("read-only destination")):
                self.assertEqual(main(["--probe",str(target)]),1)
            self.assertEqual(target.read_bytes(),b"previous successful report")
            for arguments in ([],["--probe"],[folder,"--probe",str(target)],["--probe",str(target),"--resume"]):
                with self.assertRaises(SystemExit) as caught: main(arguments)
                self.assertEqual(caught.exception.code,2)

    def test_duplicate_controller_and_active_worker_preserve_session_markers(self):
        from registry_store import registry_lock
        for guard in ("controller.guard","worker.guard"):
            with self.subTest(guard=guard),tempfile.TemporaryDirectory(dir=ROOT) as folder:
                root = self.fixture(folder)
                protected = {"cancel.request":b"cancel requested","heartbeat.json":b"active heartbeat",
                             "resume.pth":b"last complete checkpoint","manifest.json":(root/"manifest.json").read_bytes()}
                for name,value in protected.items(): (root/name).write_bytes(value)
                with registry_lock(root/guard),patch("training.service.subprocess.Popen") as spawn:
                    with self.assertRaises(TimeoutError): TrainingProcess().run(folder,lambda *a:None)
                spawn.assert_not_called()
                for name,value in protected.items(): self.assertEqual((root/name).read_bytes(),value)

    def test_partial_recovery_only_removes_named_owned_checkpoint_fragments(self):
        from training.storage import cleanup_incomplete_artifacts
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            files = {"resume.pth":b"complete checkpoint","latest.pth":b"complete model",
                     "resume.pth.fake.part":b"incomplete","best_validation.pth.fake.part":b"incomplete",
                     "personal.part":b"user file","random.part":b"legacy unknown"}
            for name,value in files.items(): (root/name).write_bytes(value)
            removed = cleanup_incomplete_artifacts(root)
            self.assertEqual(set(removed),{"resume.pth.fake.part","best_validation.pth.fake.part"})
            for name in set(files)-set(removed): self.assertEqual((root/name).read_bytes(),files[name])

    def test_callback_error_uses_bounded_wait_then_tree_cleanup(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.fixture(folder)
            process = Mock()
            process.poll.return_value = None
            process.wait.side_effect = subprocess.TimeoutExpired("worker",5)
            def spawn(*args,**kwargs):
                (root/"events.jsonl").write_text(json.dumps({"stage":"train","time":1})+"\n")
                return process
            group = Mock()
            group.spawn.side_effect = spawn
            group.__enter__ = Mock(return_value=group)
            group.__exit__ = Mock(return_value=False)
            with patch("training.service.subprocess.Popen",side_effect=spawn),patch("native_process.NativeProcessGroup",return_value=group):
                with self.assertRaisesRegex(ValueError,"callback failed"):
                    TrainingProcess().run(folder,Mock(side_effect=ValueError("callback failed")))
            process.wait.assert_called_once_with(timeout=5)
            group.terminate.assert_called_once_with(timeout=3)

    def test_explicit_force_stop_preserves_previous_checkpoint_bytes(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = self.fixture(folder)
            checkpoint = root/"resume.pth"
            checkpoint.write_bytes(b"last committed checkpoint")
            process = Mock()
            process.poll.return_value = None
            group = Mock()
            group.spawn.return_value = process
            group.__enter__ = Mock(return_value=group)
            group.__exit__ = Mock(return_value=False)
            runner = TrainingProcess(); runner.force_stop()
            with patch("training.service.subprocess.Popen",return_value=process),patch("native_process.NativeProcessGroup",return_value=group):
                with self.assertRaisesRegex(InterruptedError,"Henüz kaydedilmeyen"):
                    runner.run(folder,lambda *a:None)
            self.assertEqual(checkpoint.read_bytes(),b"last committed checkpoint")
            self.assertEqual(json.loads((root/"manifest.json").read_text())["status"],"interrupted")
            group.terminate.assert_called_once_with(timeout=3)

    def test_heartbeat_distinguishes_dead_worker_and_live_long_operation(self):
        for heartbeat_time,reason in ((0.,"worker_unresponsive"),(1000.,"long_operation")):
            with self.subTest(reason=reason),tempfile.TemporaryDirectory(dir=ROOT) as folder:
                root = self.fixture(folder)
                clock = [0.]
                process = Mock()
                process.poll.return_value = None
                process.wait.side_effect = subprocess.TimeoutExpired("worker",.2)
                group = Mock()
                group.__enter__ = Mock(return_value=group)
                group.__exit__ = Mock(return_value=False)
                def spawn(*args,**kwargs):
                    (root/"heartbeat.json").write_text(json.dumps({"time":heartbeat_time,"stage":"train"}))
                    clock[0] = 601.
                    return process
                group.spawn.side_effect = spawn
                runner = TrainingProcess()
                received = []
                def receive(value):
                    received.append(value)
                    runner.force_stop()
                with patch("training.service.subprocess.Popen",side_effect=spawn), \
                     patch("native_process.NativeProcessGroup",return_value=group), \
                     patch("training.service.time.monotonic",side_effect=lambda:clock[0]), \
                     patch("training.service.time.time",return_value=1000.):
                    with self.assertRaises(InterruptedError): runner.run(folder,receive)
                self.assertEqual(received[0]["reason"],reason)
                self.assertEqual(received[0]["stage"],"unresponsive")

    def test_training_results_are_native_announcements_and_force_stop_is_explicit(self):
        import wx
        import ui_training
        app = wx.GetApp() or wx.App(False)
        frame = wx.Frame(None)
        try:
            panel = ui_training.TrainingPanel(frame,SimpleNamespace(open_settings=Mock()))
            panel.runner = Mock(cancel_requested=False)
            panel.EnableUI(False)
            self.assertFalse(panel.btn_force_stop.IsEnabled())
            panel.OnProgress({"stage":"unresponsive","message":"synthetic stalled worker"})
            self.assertTrue(panel.btn_force_stop.IsEnabled())
            with patch.object(wx,"MessageBox",return_value=wx.NO):
                panel.OnForceStop(None)
            panel.runner.force_stop.assert_not_called()
            with patch.object(wx,"MessageBox",return_value=wx.YES):
                panel.OnForceStop(None)
            panel.runner.force_stop.assert_called_once()
            with patch.object(wx,"MessageBox",return_value=wx.OK) as announce:
                panel.OnFinished({"synthetic":True},"completed synthetic training")
            announce.assert_called_once()
            self.assertEqual(announce.call_args.args[0],"completed synthetic training")
            self.assertFalse(panel.btn_force_stop.IsEnabled())
            self.assertEqual(panel.txt_status.GetValue(),"completed synthetic training")
        finally:
            frame.Destroy()
            app.ProcessPendingEvents()

    def test_native_process_group_cleans_real_worker_and_grandchild(self):
        from native_process import NativeProcessGroup
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            child_pid = root/"child.pid"
            script = root/"owned_worker.py"
            script.write_text("import os,subprocess,sys,time\nfrom pathlib import Path\ntime.sleep(.5)\np = subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)\nPath(sys.argv[1]).write_text(str(p.pid))\ntime.sleep(60)\n",encoding="utf-8")
            kwargs = {"creationflags":subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session":True}
            with NativeProcessGroup() as group:
                process = subprocess.Popen([sys.executable,str(script),str(child_pid)],**kwargs)
                group.attach(process)
                deadline = time.monotonic()+10
                while not child_pid.exists() and time.monotonic()<deadline: time.sleep(.02)
                self.assertTrue(child_pid.exists())
                pid = int(child_pid.read_text())
                group.terminate(timeout=3)
                self.assertIsNotNone(process.poll())
            if os.name == "nt":
                import ctypes
                from ctypes import wintypes
                kernel = ctypes.WinDLL("kernel32",use_last_error=True)
                kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
                kernel.OpenProcess.restype = wintypes.HANDLE
                kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
                kernel.CloseHandle.argtypes = [wintypes.HANDLE]
                handle = kernel.OpenProcess(0x1000,False,pid)
                if handle:
                    try:
                        code = wintypes.DWORD()
                        self.assertTrue(kernel.GetExitCodeProcess(handle,ctypes.byref(code)))
                        self.assertNotEqual(code.value,259)
                    finally: kernel.CloseHandle(handle)


if __name__ == "__main__":
    unittest.main()
