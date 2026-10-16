# NVIDIA A2SB inference subset

Source: https://github.com/NVIDIA/diffusion-audio-restoration
Commit: `02ddff01c4dbbe20839e13e09da1988db7dd4be9`.
Copyright (c) 2025 NVIDIA CORPORATION. All rights reserved.

The NVIDIA Source Code License for A2SB in LICENSE applies to these files.
Use is limited to non-commercial research or evaluation. The application
license is not a substitute for this component license. Model weights use
the separate NVIDIA OneWay NonCommercial License, linked in MODEL_LICENSE.md.

Changes: networks.py uses a relative utils import and keeps the small attention
level bookkeeping tensor explicitly on CPU for meta-device schema validation.
No learned weight or network shape changes. sampling.py extracts the
two inference methods from A2SB_lightning_module.py, retaining their bodies,
and adds a small cancellation-aware model owner. transforms.py extracts
eight unchanged transform classes with inference-only imports. diffusion.py
and utils.py retain their implementations. No training framework or runtime
source evaluation is needed. The application wrapper is outside this vendor
package.

Upstream networks.py attributes guided-diffusion components to OpenAI under
the MIT license; the upstream MIT notice is included in GUIDED_DIFFUSION_LICENSE.

Reviewed upstream file hashes:

- `networks.py`: `622fc0bc3466d68780b047291881f800de486b1af6a40e204e02e61bc94974e2`
- `diffusion.py`: `50d7733a749c5715e13f05a51ef0f0b3a260459798f3da43fd4b4b233ba04be1`
- `utils.py`: `eb045c41c1cbdb8d4a3fa48f67c2bb2efb117c5bbe5409494affd1e2e9f1d867`
- `LICENSE`: `24be835fee4fb5e8f5eb81371b688bc3c30e70bf191465236bfa5990447028b8`
- `A2SB_lightning_module.py`: `beeb70ec4690d068ee72b41caf7233290c5d6db96f7274c8619f93063426253b`
- `audio_transforms/transforms.py`: `4023af28dd78b4692ecf0a9537a6ae818a9e2d39d855cb14450e4ffc5fb95cbb`
