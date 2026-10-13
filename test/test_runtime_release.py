"""Release regressions for device routing, registry races and worker failures."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import nullcontext
import tempfile
import unittest
from unittest.mock import patch
import json
import os

from app_runtime import configure_runtime_cache
configure_runtime_cache()
import torch
import hardware
import ui_cover
import ui_separator
from registry_store import apply_model_changes

ROOT = Path(__file__).resolve().parents[1]


class ReleaseRuntimeTests(unittest.TestCase):
    def test_stale_addition_does_not_delete_concurrent_model(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/"models.json"
            base = {"base":{"pth":"base.pth","index":""}}
            apply_model_changes(path, base, validator=ui_cover.validate_models)
            apply_model_changes(path, {**base,"second":{"pth":"second.pth","index":""}}, validator=ui_cover.validate_models)
            apply_model_changes(path, {**base,"first":{"pth":"first.pth","index":""}}, validator=ui_cover.validate_models)
            self.assertEqual(set(json.loads(path.read_text(encoding="utf-8"))), {"base","first","second"})

    def test_explicit_removal_keeps_other_instance_addition(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/"models.json"
            base = {"base":{"pth":"base.pth","index":""}}
            apply_model_changes(path, base, validator=ui_cover.validate_models)
            apply_model_changes(path, {"new":{"pth":"new.pth","index":""}}, validator=ui_cover.validate_models)
            apply_model_changes(path, {}, previous=base, validator=ui_cover.validate_models)
            self.assertEqual(set(json.loads(path.read_text(encoding="utf-8"))), {"new"})

    def test_conflicting_same_name_edit_preserves_registry(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/"models.json"
            base = {"base":{"pth":"base.pth","index":""}}
            apply_model_changes(path, base)
            apply_model_changes(path, {"base":{"pth":"concurrent.pth","index":""}})
            with self.assertRaisesRegex(ValueError, "başka"):
                apply_model_changes(path, {}, previous=base)
            self.assertEqual(json.loads(path.read_text())["base"]["pth"],"concurrent.pth")

    def test_xpu_is_detected_without_cuda(self):
        fake = SimpleNamespace(is_available=lambda:True, device_count=lambda:1,
                               get_device_name=lambda i:"Intel Arc",get_device_properties=lambda i:SimpleNamespace(total_memory=12*1024**3),
                               device=lambda i:nullcontext(),empty_cache=lambda:None)
        with patch.object(torch,"xpu",fake), patch.object(torch.cuda,"is_available",return_value=False), \
             patch.object(hardware,"windows_cards",return_value=["Intel Arc"]),patch.object(hardware,"probe_operations"):
            report = hardware.detect_hardware()
        self.assertEqual(report.selected("gpu").device,"xpu:0")

    def test_modern_windows_hip_uses_backward_probe(self):
        with patch.object(torch.version,"hip","10.1.0"),patch.object(torch,"__version__","2.14.0"), \
             patch.object(hardware.os,"name","nt"),patch.object(hardware,"probe_training_operations") as probe:
            hardware.ensure_training_backend("cuda:0")
        probe.assert_called_once_with("cuda:0")

    def test_separator_system_exit_is_an_operation_error(self):
        class Separator:
            def __init__(self,**kwargs): pass
            def load_model(self,**kwargs): raise SystemExit(1)
        job = SimpleNamespace(is_cancelled=False,model_dir=str(ROOT),job_device="cpu",
                              UpdateStatus=lambda *a:None,LogMessage=lambda *a:None)
        with patch.object(ui_separator,"Separator",Separator):
            self.assertFalse(ui_separator.SeparatorPanel.RunSeparatorCommand(job,"unused","model","stage",str(ROOT)))

    def test_separator_name_is_utf16_bounded_and_collision_resistant(self):
        from app_runtime import output_filename
        suffix = "_Ghostkiller_1_Ayrilmis_Vokal.flac"
        first = output_filename("😀"*240+"a",suffix)
        second = output_filename("😀"*240+"b",suffix)
        self.assertLessEqual(len(first.encode("utf-16-le"))//2,255)
        self.assertTrue(first.endswith(suffix))
        self.assertNotEqual(first,second)


if __name__=="__main__": unittest.main()
