"""Explicit deterministic CUDA checkpoint fixture, separate from GAN quality."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"test"))
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
os.environ["PYTHONIOENCODING"] = "utf-8"
from test_training_release import TrainingReleaseTests
import torch

torch.set_num_threads(2)
torch.use_deterministic_algorithms(True)
check = TrainingReleaseTests()
check.exercise_checkpoint_exact_resume("cuda:0")
result = {"passed":True,"backend":"cuda:0","gpu":torch.cuda.get_device_name(0),
          "torch":str(torch.__version__),"steps":10,"periodic_checkpoint_step":5,
          "generator_discriminator_bitwise_equal":True,"scheduler_equal":True,
          "torch_cpu_and_gpu_rng_bitwise_equal":True,"python_numpy_rng_equal":True,
          "fixture":"substituted small networks with actual CUDA AdamW and device RNG",
          "limitation":"This validates checkpoint control flow; it is not real GAN numerical reproducibility or a voice-quality score."}
(ROOT/"docs"/"TRAINING_FIXED_CUDA_CHECKPOINT_EXACT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,ensure_ascii=False),flush=True)
