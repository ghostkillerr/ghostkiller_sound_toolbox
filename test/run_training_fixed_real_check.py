"""Explicit CUDA integration evidence; all writes are synthetic test sessions."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app_runtime import configure_runtime_cache
configure_runtime_cache()
from app_settings import AppSettings
from model_manager import ModelManager,file_digest


def main():
    import torch
    torch.set_num_threads(2)
    verification = ROOT/"training_runs"/("release_verification_"+uuid.uuid4().hex[:12])
    verification.mkdir(parents=True)
    print("VERIFICATION "+str(verification),flush=True)
    manager = ModelManager()
    protected = [ROOT/"models.json",ROOT/"settings.json",Path(manager.manifest_path)]
    for key in ("contentvec","rmvpe","training_v2_40k"):
        for relative in manager.primary_files(key):
            path = Path(manager.path(relative))
            if not path.is_file(): raise FileNotFoundError(path)
            protected.append(path)
    before = {str(path):file_digest(path) for path in protected if path.is_file()}
    (verification/"protected_before.json").write_text(json.dumps(before,indent=2),encoding="utf-8")
    # Real schema/CRC/published-hash verification writes only a temporary cache.
    # The installed personal model registry/integrity files stay untouched.
    manager.manifest_path = str(verification/"validated_assets.json")
    failures = manager.process(("contentvec","rmvpe","training_v2_40k"),"verify",log=lambda value:print(value,flush=True))
    if failures: raise RuntimeError(failures)
    spec = importlib.util.spec_from_file_location("smoke_training_fixture",ROOT/"test"/"smoke_training.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    with patch.object(smoke,"AppSettings",side_effect=lambda:AppSettings(manager=manager)):
        smoke.main()
    after = {str(path):file_digest(path) for path in protected if path.is_file()}
    (verification/"protected_after.json").write_text(json.dumps(after,indent=2),encoding="utf-8")
    print("PROTECTED_FILES_UNCHANGED "+str(before == after),flush=True)
    if before != after: raise RuntimeError("Protected source/registry files changed during the test")


if __name__ == "__main__":
    main()
