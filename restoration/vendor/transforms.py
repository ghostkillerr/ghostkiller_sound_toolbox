# Copyright (c) 2025, NVIDIA CORPORATION. All rights reserved.
# NVIDIA Source Code License for A2SB: see LICENSE.
# Inference-only extraction; original implementations retained.
import torch
from torch import Tensor
from torch.linalg import svd
from torchaudio.transforms import Spectrogram, InverseSpectrogram
from einops import rearrange

class ComplexSpectrogram:
    def __init__(self, n_fft=1024,
                 win_length=1024,
                 hop_length=256,
                 eps=0.000000001
                 ):
        super().__init__()
        self.eps = eps
        self.spectrogram = Spectrogram(n_fft=n_fft,
                                       win_length=win_length,
                                       hop_length=hop_length,
                                       window_fn=torch.hann_window,
                                       power=None # required for complex
                                       )

    def __call__(self, waveform: Tensor) -> Tensor:
        """
        waveform: length T tensor of waveform audio
        """
        assert len(waveform.shape) == 1, waveform.shape
        spec = self.spectrogram(waveform)
        spec = torch.view_as_real(spec).permute(2, 0, 1)
        return spec

class ComplexToMagInstPhase:
    def __call__(self, complex_spec: Tensor) -> Tensor:
        """
        inputs:
            complex_spec: 2 x H x W complex spectrogram viewed as 2-channel real values
        outputs:
            output: 3 x H x W spectrogram where channels are magnitude, cos(theta), sin(theta)
        """
        mag = torch.sqrt(complex_spec[0:1] ** 2 + complex_spec[1:2] ** 2)
        phase = torch.atan2(complex_spec[1:2],complex_spec[0:1])
        return torch.cat([mag, torch.cos(phase), torch.sin(phase)], 0)

class MagInstPhaseToComplex:
    def __call__(self, msp_spec: Tensor) -> Tensor:
        """
        inputs:
            msp_spec: magnitude + instantaneous phase representation 3 x H x W
        outputs:
            complex_spec: 2 x H x W complex spectrogram viewed as real
        """
        mag = msp_spec[:1]
        cos_theta = msp_spec[1:2]
        sin_theta = msp_spec[2:3]
        return torch.cat([mag*cos_theta, mag*sin_theta], 0)

class SVDFixMagInstPhase:
    def __call__(self, msp_spec: Tensor) -> Tensor:
        """
        cleans up the inconsistent phase predictions by using SVD to map to proper SO(2) parameters
        inputs:
            msp_spec: magnitude + instantaneous phase representation 3 x H x W
        outputs:
            msp_spec: magnitude + instantaneous phase representation 3 x H x W
        """
        mag = msp_spec[:1]
        cos_theta = msp_spec[1:2] # 1 x n_bands x t
        sin_theta = msp_spec[2:3] # 1 x n_bands x t
        top = torch.cat([cos_theta, -sin_theta], 0)
        bottom = torch.cat([sin_theta, cos_theta], 0)
        rot = torch.stack([top, bottom], 0) # 2 x 2 x n_bands x t
        rot = rearrange(rot, "r c n t -> n t r c") # move matrix to end
        U, S, Vh = svd(rot)
        new_S = S.clone()
        new_S[...,0] = 1
        new_S[...,1] = torch.det(U@Vh)
        new_rot = U @ torch.diag_embed(new_S) @ Vh
        new_cos_sin_theta = new_rot[...,:,0]
        new_cos_sin_theta = rearrange(new_cos_sin_theta, "n t r -> r n t")
        new_msp_spec = torch.cat([mag, new_cos_sin_theta], 0)

        return new_msp_spec

class InverseComplexSpectrogram:
    def __init__(self, n_fft=1024,
                 win_length=1024,
                 hop_length=256,
                 eps=0.000000001
                 ):
        super().__init__()
        self.eps = eps
        self.inv_spectrogram = InverseSpectrogram(n_fft=n_fft,
                                              win_length=win_length,
                                              hop_length=hop_length,
                                              window_fn=torch.hann_window
                                              )

    def __call__(self, spec: Tensor) -> Tensor:
        """
        spec: 2 x H X W real spectrogram tensor
        """
        assert(len(spec.shape) == 3), '{} shape not correct'.format(spec.shape)
        # move channels to end, then convert back to complex
        spec = torch.view_as_complex(spec.permute(1, 2, 0).contiguous())
        return self.inv_spectrogram(spec)

class PowerScaleSpectrogram:
    def __init__(self, power=0.5, channels=None, eps=0.000000001):
        super().__init__()
        self.eps = eps
        self.power = power
        self.channels = channels

    def __call__(self, spec: Tensor) -> Tensor:
        """
        spec: C x H x W tensor
        """

        spec_abs = spec.abs()
        scale = spec_abs ** self.power / (spec_abs + self.eps)
        if self.channels is None:
            spec = spec * scale
        else:
            inds_to_scale = torch.tensor(self.channels)
            spec = spec.clone()
            spec[inds_to_scale] = spec[inds_to_scale] * scale[inds_to_scale]
        return spec

class SpectrogramDropDCTerm:
    def __init__(self):
        super().__init__()

    def __call__(self, spec: Tensor) -> Tensor:
        return spec[...,1:,:]

class SpectrogramAddDCTerm:
    def __init__(self):
        super().__init__()

    def __call__(self, spec: Tensor) -> Tensor:
        dc_channel = spec[...,:1,:] * 0 # get a random slice and zero it out
        return torch.cat((dc_channel, spec), -2)
