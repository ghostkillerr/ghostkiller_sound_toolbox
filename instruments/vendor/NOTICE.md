# SCNet inference architecture

Unmodified `SCNet.py` and `separation.py` from starrytong/SCNet, revision
`5d95bf96b19c3eede63248d171efeca8e3abb948`, under the accompanying MIT license.
Source: https://github.com/starrytong/SCNet
Released SCNet weights MIT clarification:
https://github.com/starrytong/SCNet/issues/35

Ghostkiller supplies its own offline weights-only loader and bounded-memory
overlap/add controller. No upstream training or automatic download code is run.

The optional six-source HTDemucs architecture is provided by the already pinned
audio-separator distribution, not copied here. Official checkpoint source:
https://github.com/facebookresearch/demucs/blob/main/demucs/remote/files.txt
The download's SHA-256 begins with the publisher's `34c22ccb` checksum.
Demucs code is MIT; the model weights are not covered by that license.
The upstream author states that the weights are provided only for scientific
purposes: https://github.com/facebookresearch/demucs/issues/327 .
Ghostkiller shows this restriction and the publisher's statement before
downloading or using the optional six-source checkpoint. It is not bundled in
installers; no commercial-use or weight-redistribution rights are granted here.
Guitar/piano outputs are experimental, as noted in the official Demucs README.
