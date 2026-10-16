# Copyright (c) 2025, NVIDIA CORPORATION. All rights reserved.
# NVIDIA Source Code License for A2SB: see LICENSE.
# Inference-only extraction; original implementations retained.
import torch
from tqdm import tqdm
from .diffusion import (Diffusion, get_multidiffusion_vf, multidiffusion_pad_inputs, multidiffusion_unpad_outputs)
from .networks import SinusoidalTemporalEmbedding
from .utils import find_middle_of_zero_segments

class BridgeSampler:
    def __init__(self, model, device, cancelled=None):
        self.model, self.cancelled = model, cancelled
        self.ddpm = Diffusion(beta_max=1.)
        self.t_to_emb = SinusoidalTemporalEmbedding(64,min_freq=.5).to(device)
        self.use_ot_ode = False

    def get_vf_model(self, _):
        if self.cancelled and self.cancelled():
            raise InterruptedError('Vokal onarımı iptal edildi.')
        return self.model

    @torch.no_grad()
    def ddpm_sample(self, x_1, t_steps=None, mask=None, mask_pred_x0=True,
                    win_length=256,
                    hop_length=256,
                    batch_size=16
                    ):
        """
        win_length: temporal window length of input spectrogram
        hop_length: step size. If hop_length < win_length, we use multidiffusion
        """
        assert hop_length <= win_length
        n_steps = t_steps.shape[1] - 1
        original_width = x_1.shape[-1]
        x_1 = multidiffusion_pad_inputs(x_1, win_length, hop_length)
        mask = multidiffusion_pad_inputs(mask, win_length, hop_length)

        x_t = x_1.clone()
        pred_x0 = None
        all_pred_x0s = []

        for t_idx in tqdm(range(n_steps)):
            # print(t_idx)
            t_emb = self.t_to_emb(t_steps[:,t_idx]).repeat(x_1.shape[0], 1)
            t = t_steps[:, t_idx]
            t_prev = t_steps[:, t_idx+1]
            #vf_output = self.get_vf_model(t[0].item())(x_t, t_emb)
            vf_model = self.get_vf_model(t[0].item())
            vf_output = get_multidiffusion_vf(vf_model, x_t, t_emb, win_length=win_length,
                                              hop_length=hop_length, batch_size=batch_size
                                              )
            pred_x0 = self.ddpm.get_pred_x0(t_steps[:, t_idx], x_t, vf_output)
            if mask is not None and mask_pred_x0:
                pred_x0 = pred_x0 * mask + (1-mask) * x_1

            all_pred_x0s.append(pred_x0.cpu())
            x_t_prev = self.ddpm.p_posterior(t_prev, t, x_t, pred_x0, ot_ode=self.use_ot_ode)
            x_t = x_t_prev
            if mask is not None:
                xt_true = x_1
                if not self.use_ot_ode:
                    std_sb = self.ddpm.get_std_t(t_prev)
                    xt_true = xt_true + std_sb * torch.randn_like(xt_true)
                x_t = (1. - mask) * xt_true + mask * x_t
        all_pred_x0s = [multidiffusion_unpad_outputs(pred, original_width) for pred in all_pred_x0s]
        return all_pred_x0s

    @torch.no_grad()
    def fast_inpaint_ddpm_sample(self, x_1, t_steps=None, mask=None, mask_pred_x0=True,
                    win_length=256,
                    hop_length=256,
                    batch_size=16):
        """
        assumes any masked segment is shorter win_length and sufficiently suparated
        """
        original_width = x_1.shape[-1]
        x_1 = x_1.clone()
        x_1 = multidiffusion_pad_inputs(x_1, win_length, hop_length)
        mask = multidiffusion_pad_inputs(mask, win_length, hop_length, padding_constant=0)

        middle_indices = find_middle_of_zero_segments(1-mask[0,0,0])
        for center_idx in middle_indices:
            l_idx = int(center_idx-win_length/2)
            r_idx = int(center_idx +win_length/2)
            if l_idx < 0:
                r_idx -= l_idx
                l_idx = 0

            if r_idx > x_1.shape[-1]:
                l_idx -= (r_idx - x_1.shape[-1])
                r_idx = x_1.shape[-1]
            assert(r_idx - l_idx == win_length)
            assert(l_idx >= 0)
            assert(r_idx <= x_1.shape[-1])
            curr_x_1 = x_1[:,:,:,l_idx:r_idx]
            curr_mask = mask[:,:,:,l_idx:r_idx]
            new_x_0 = self.ddpm_sample(curr_x_1, t_steps, mask=curr_mask, mask_pred_x0=mask_pred_x0, win_length=win_length, hop_length=hop_length, batch_size=batch_size)
            x_1[:,:,:,l_idx:r_idx] = new_x_0[-1]
        x_1 = multidiffusion_unpad_outputs(x_1, original_width)
        return [x_1]
