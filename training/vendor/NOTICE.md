# Third-party training primitives

Source: [IAHispano/Applio 3.6.5](https://github.com/IAHispano/Applio/tree/55fe0b976a6990bb75261c32ccecf6bfca3198f1).
Commit: `55fe0b976a6990bb75261c32ccecf6bfca3198f1`. License: MIT, included in `LICENSE`.

Copied: `rvc/train/data_utils.py`, `losses.py`, `mel_processing.py`, the
`load_wav_to_torch`, `load_filepaths_and_text`, `HParams` subset of `utils.py`,
`rvc/lib/algorithm/discriminators.py`, and the 32/40/48 kHz configuration JSONs.
Local changes: dataset imports point to `training.vendor`; unused utilities and
plotting dependencies omitted. Mel filter cache keys include the sample rate,
FFT size and mel band count to prevent reuse across incompatible settings.
The application implements its own single-device
FP32 training loop, subprocess controller, source split, evaluation, atomic
checkpoints and registration. It does not embed Applio's GUI or distributed launcher.

Pretrained weights are separately downloaded from the
[RVC project's model repository](https://huggingface.co/lj1995/VoiceConversionWebUI).
ContentVec and RMVPE retain their own provenance; repository MIT licensing does
not substitute for the licenses of separately distributed assets.
