import os
import gc
import torch
import torch.nn.functional as F
import torchcrepe
import faiss
import librosa
import numpy as np
from scipy import signal
from torch import Tensor

from rvc.lib.predictors.f0 import CREPE, FCPE, RMVPE
from rvc.infer.f0_utils import smooth_f0
from rvc.infer.safe_index import load_index
from rvc.infer.helper_cache import InferenceHelperCache, file_identity
from rvc.infer.quality_policy import InferenceQualityPolicy
from app_runtime import model_directory
from compute_backend import trim_cache

import logging

logging.getLogger("faiss").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

FILTER_ORDER = 5
CUTOFF_FREQUENCY = 48  # Hz
SAMPLE_RATE = 16000  # Hz
bh, ah = signal.butter(
    N=FILTER_ORDER, Wn=CUTOFF_FREQUENCY, btype="high", fs=SAMPLE_RATE
)


class AudioProcessor:
    """
    A class for processing audio signals, specifically for adjusting RMS levels.
    """

    def change_rms(
        source_audio: np.ndarray,
        source_rate: int,
        target_audio: np.ndarray,
        target_rate: int,
        rate: float,
    ):
        """
        Adjust the RMS level of target_audio to match the RMS of source_audio, with a given blending rate.

        Args:
            source_audio: The source audio signal as a NumPy array.
            source_rate: The sampling rate of the source audio.
            target_audio: The target audio signal to adjust.
            target_rate: The sampling rate of the target audio.
            rate: The blending rate between the source and target RMS levels.
        """
        # Calculate RMS of both audio data
        rms1 = librosa.feature.rms(
            y=source_audio,
            frame_length=source_rate // 2 * 2,
            hop_length=source_rate // 2,
        )
        rms2 = librosa.feature.rms(
            y=target_audio,
            frame_length=target_rate // 2 * 2,
            hop_length=target_rate // 2,
        )

        # Interpolate RMS to match target audio length
        rms1 = F.interpolate(
            torch.from_numpy(rms1).float().unsqueeze(0),
            size=target_audio.shape[0],
            mode="linear",
        ).squeeze()
        rms2 = F.interpolate(
            torch.from_numpy(rms2).float().unsqueeze(0),
            size=target_audio.shape[0],
            mode="linear",
        ).squeeze()
        rms2 = torch.maximum(rms2, torch.zeros_like(rms2) + 1e-6)

        # Adjust target audio RMS based on the source audio RMS
        adjusted_audio = (
            target_audio
            * (torch.pow(rms1, 1 - rate) * torch.pow(rms2, rate - 1)).numpy()
        )
        return adjusted_audio


class Autotune:
    """
    A class for applying autotune to a given fundamental frequency (F0) contour.
    """

    def __init__(self):
        """
        Initializes the Autotune class with a set of reference frequencies.
        """
        self.note_dict = [
            49.00,  # G1
            51.91,  # G#1 / Ab1
            55.00,  # A1
            58.27,  # A#1 / Bb1
            61.74,  # B1
            65.41,  # C2
            69.30,  # C#2 / Db2
            73.42,  # D2
            77.78,  # D#2 / Eb2
            82.41,  # E2
            87.31,  # F2
            92.50,  # F#2 / Gb2
            98.00,  # G2
            103.83,  # G#2 / Ab2
            110.00,  # A2
            116.54,  # A#2 / Bb2
            123.47,  # B2
            130.81,  # C3
            138.59,  # C#3 / Db3
            146.83,  # D3
            155.56,  # D#3 / Eb3
            164.81,  # E3
            174.61,  # F3
            185.00,  # F#3 / Gb3
            196.00,  # G3
            207.65,  # G#3 / Ab3
            220.00,  # A3
            233.08,  # A#3 / Bb3
            246.94,  # B3
            261.63,  # C4
            277.18,  # C#4 / Db4
            293.66,  # D4
            311.13,  # D#4 / Eb4
            329.63,  # E4
            349.23,  # F4
            369.99,  # F#4 / Gb4
            392.00,  # G4
            415.30,  # G#4 / Ab4
            440.00,  # A4
            466.16,  # A#4 / Bb4
            493.88,  # B4
            523.25,  # C5
            554.37,  # C#5 / Db5
            587.33,  # D5
            622.25,  # D#5 / Eb5
            659.25,  # E5
            698.46,  # F5
            739.99,  # F#5 / Gb5
            783.99,  # G5
            830.61,  # G#5 / Ab5
            880.00,  # A5
            932.33,  # A#5 / Bb5
            987.77,  # B5
            1046.50,  # C6
        ]

    def autotune_f0(self, f0, f0_autotune_strength):
        """
        Autotunes a given F0 contour by snapping each frequency to the closest reference frequency.

        Args:
            f0: The input F0 contour as a NumPy array.
        """
        autotuned_f0 = np.zeros_like(f0)
        for i, freq in enumerate(f0):
            if not np.isfinite(freq) or freq <= 0:
                continue
            closest_note = min(self.note_dict, key=lambda x: abs(x - freq))
            autotuned_f0[i] = freq + (closest_note - freq) * f0_autotune_strength
        return autotuned_f0


class Pipeline:
    """
    The main pipeline class for performing voice conversion, including preprocessing, F0 estimation,
    voice conversion using a model, and post-processing.
    """

    def __init__(self, tgt_sr, config, helper_cache=None, quality_policy=None):
        """
        Initializes the Pipeline class with target sampling rate and configuration parameters.

        Args:
            tgt_sr: The target sampling rate for the output audio.
            config: A configuration object containing various parameters for the pipeline.
        """
        self.x_pad = config.x_pad
        self.x_query = config.x_query
        self.x_center = config.x_center
        self.x_max = config.x_max
        self.sample_rate = 16000
        self.tgt_sr = tgt_sr
        self.window = 160
        self.t_pad = self.sample_rate * self.x_pad
        self.t_pad_tgt = tgt_sr * self.x_pad
        self.t_pad2 = self.t_pad * 2
        self.t_query = self.sample_rate * self.x_query
        self.t_center = self.sample_rate * self.x_center
        self.t_max = self.sample_rate * self.x_max
        self.time_step = self.window / self.sample_rate * 1000
        self.f0_min = 50
        self.f0_max = 1100
        self.f0_mel_min = 1127 * np.log(1 + self.f0_min / 700)
        self.f0_mel_max = 1127 * np.log(1 + self.f0_max / 700)
        self.device = config.device
        self.autotune = Autotune()
        self.helper_cache = helper_cache if helper_cache is not None else InferenceHelperCache()
        if quality_policy is not None and not isinstance(quality_policy, InferenceQualityPolicy):
            raise ValueError("Geçersiz kalite politikası.")
        self.quality_policy = quality_policy or InferenceQualityPolicy()

    def get_f0(
        self,
        x,
        p_len,
        f0_method: str = "rmvpe",
        pitch: int = 0,
        f0_autotune: bool = False,
        f0_autotune_strength: float = 1.0,
        proposed_pitch: bool = False,
        proposed_pitch_threshold: float = 155.0,
    ):
        """
        Estimates the fundamental frequency (F0) of a given audio signal using various methods.

        Args:
            x: The input audio signal as a NumPy array.
            p_len: Desired length of the F0 output.
            pitch: Key to adjust the pitch of the F0 contour.
            f0_method: Method to use for F0 estimation (e.g., "crepe").
            f0_autotune: Whether to apply autotune to the F0 contour.
            proposed_pitch: whether to apply proposed pitch adjustment
            proposed_pitch_threshold: target frequency, 155.0 for male, 255.0 for female
        """
        if f0_method == "crepe":
            model = CREPE(
                device=self.device, sample_rate=self.sample_rate, hop_size=self.window
            )
            f0 = model.get_f0(x, self.f0_min, self.f0_max, p_len, "full")
            del model
        elif f0_method == "crepe-tiny":
            model = CREPE(
                device=self.device, sample_rate=self.sample_rate, hop_size=self.window
            )
            f0 = model.get_f0(x, self.f0_min, self.f0_max, p_len, "tiny")
            del model
        elif f0_method == "rmvpe":
            key = ("rmvpe", str(self.device), "float32",
                   file_identity(os.path.join(model_directory(), "predictors", "rmvpe.pt")))
            model = self.helper_cache.get_or_create(
                key, lambda: RMVPE(device=self.device, sample_rate=self.sample_rate, hop_size=self.window)
            )
            f0 = model.get_f0(x, filter_radius=0.03)
            del model
        elif f0_method == "fcpe":
            model = FCPE(
                device=self.device, sample_rate=self.sample_rate, hop_size=self.window
            )
            f0 = model.get_f0(x, p_len, filter_radius=0.006)
            del model

        else:
            raise ValueError(f"Desteklenmeyen F0 yöntemi: {f0_method}")

        f0 = np.asarray(f0, dtype=np.float32).reshape(-1)
        f0[~np.isfinite(f0) | (f0 < 0)] = 0
        f0 = np.pad(f0[:p_len], (0, max(0, p_len - len(f0))))
        # f0 adjustments
        if f0_autotune is True:
            f0 = self.autotune.autotune_f0(f0, f0_autotune_strength)
            f0 *= pow(2, pitch / 12)
        elif proposed_pitch is True:
            limit = 12
            # calculate median f0 of the audio
            valid_f0 = np.where(f0 > 0)[0]
            if len(valid_f0) < 2:
                # no valid f0 detected
                up_key = 0
            else:
                median_f0 = float(
                    np.median(np.interp(np.arange(len(f0)), valid_f0, f0[valid_f0]))
                )
                if median_f0 <= 0 or np.isnan(median_f0):
                    up_key = 0
                else:
                    # calculate proposed shift
                    up_key = max(
                        -limit,
                        min(
                            limit,
                            int(
                                np.round(
                                    12 * np.log2(proposed_pitch_threshold / median_f0)
                                )
                            ),
                        ),
                    )
            print("calculated pitch offset:", up_key)
            f0 *= pow(2, (pitch + up_key) / 12)
        else:
            f0 *= pow(2, pitch / 12)

        # Compatibility default; users may disable smoothing for explicit A/B.
        if self.quality_policy.smooth_pitch:
            f0 = smooth_f0(f0)

        # quantizing f0 to 255 buckets to make coarse f0
        f0bak = f0.copy()
        f0_mel = 1127 * np.log(1 + f0 / 700)
        f0_mel[f0_mel > 0] = (f0_mel[f0_mel > 0] - self.f0_mel_min) * 254 / (
            self.f0_mel_max - self.f0_mel_min
        ) + 1
        f0_mel[f0_mel <= 1] = 1
        f0_mel[f0_mel > 255] = 255
        f0_coarse = np.rint(f0_mel).astype(int)

        return f0_coarse, f0bak

    def voice_conversion(
        self,
        model,
        net_g,
        sid,
        audio0,
        pitch,
        pitchf,
        index,
        big_npy,
        index_rate,
        version,
        protect,
        target_frames=None,
    ):
        """
        Performs voice conversion on a given audio segment.

        Args:
            model: The feature extractor model.
            net_g: The generative model for synthesizing speech.
            sid: Speaker ID for the target voice.
            audio0: The input audio segment.
            pitch: Quantized F0 contour for pitch guidance.
            pitchf: Original F0 contour for pitch guidance.
            index: FAISS index for speaker embedding retrieval.
            big_npy: Speaker embeddings stored in a NumPy array.
            index_rate: Blending rate for speaker embedding retrieval.
            version: Model version (Keep to support old models).
            protect: Protection level for preserving the original pitch.
        """
        with torch.no_grad():
            pitch_guidance = pitch is not None and pitchf is not None
            # prepare source audio
            feats = torch.from_numpy(audio0).float()
            feats = feats.mean(-1) if feats.dim() == 2 else feats
            assert feats.dim() == 1, feats.dim()
            feats = feats.view(1, -1).to(self.device)
            # HuBERT/ContentVec uses valid convolutions (400-sample receptive
            # field, 320-sample hop). Supply reflected tail context so its last
            # feature also covers the requested 100-fps synthesis frames.
            maximum_frames = (len(audio0) + self.window - 1) // self.window
            target_frames = maximum_frames if target_frames is None else target_frames
            if isinstance(target_frames, (bool, np.bool_)) or not isinstance(target_frames, (int, np.integer)) or not 1 <= target_frames <= maximum_frames:
                raise ValueError("RVC hedef çerçeve sayısı ses parçasıyla uyumsuz.")
            target_frames = int(target_frames)
            encoder_config = getattr(model, "config", None)
            kernels = getattr(encoder_config, "conv_kernel", (10, 3, 3, 3, 3, 2, 2))
            strides = getattr(encoder_config, "conv_stride", (5, 2, 2, 2, 2, 2, 2))
            receptive, encoder_hop = 1, 1
            for kernel, stride in zip(kernels, strides):
                receptive += (kernel - 1) * encoder_hop
                encoder_hop *= stride
            if encoder_hop != self.window * 2:
                raise ValueError("Embedder 50 fps özellik üretmelidir; RVC 100 fps sözleşmesiyle uyumlu değil.")
            required_features = (target_frames + 1) // 2
            padding = max(0, receptive + (required_features - 1) * encoder_hop - feats.shape[-1])
            if padding:
                feats = F.pad(feats, (0, padding), mode="reflect" if padding < feats.shape[-1] else "replicate")
            # extract features
            feats = model(feats)["last_hidden_state"]
            feats = (
                model.final_proj(feats[0]).unsqueeze(0) if version == "v1" else feats
            )
            # make a copy for pitch guidance and protection
            feats0 = feats.clone() if pitch_guidance else None
            if (
                index
            ):  # set by parent function, only true if index is available, loaded, and index rate > 0
                feats = self._retrieve_speaker_embeddings(
                    feats, index, big_npy, index_rate
                )
            # feature upsampling
            feats = F.interpolate(feats.permute(0, 2, 1), scale_factor=2).permute(
                0, 2, 1
            )
            # adjust the length if the audio is short
            if feats.shape[1] < target_frames:
                raise ValueError("Embedder istenen ses süresi için yeterli özellik çerçevesi üretmedi.")
            p_len = target_frames
            if pitch_guidance:
                p_len = min(p_len, pitch.shape[1], pitchf.shape[1])
                feats0 = F.interpolate(feats0.permute(0, 2, 1), scale_factor=2).permute(
                    0, 2, 1
                )[:, :p_len]
                feats = feats[:, :p_len]
                pitch, pitchf = pitch[:, :p_len], pitchf[:, :p_len].float()
                # Pitch protection blending
                if protect < 0.5:
                    pitchff = pitchf.clone()
                    pitchff[pitchf > 0] = 1
                    pitchff[pitchf < 1] = protect
                    feats = feats * pitchff.unsqueeze(-1) + feats0 * (
                        1 - pitchff.unsqueeze(-1)
                    )
                    feats = feats.to(feats0.dtype)
            else:
                pitch, pitchf = None, None
                feats = feats[:, :p_len]
            if p_len <= 0:
                raise ValueError("Ses parçası dönüşüm için çok kısa.")
            p_len = torch.tensor([p_len], device=self.device).long()
            audio1 = (
                (net_g.infer(feats.float(), p_len, pitch, pitchf, sid)[0][0, 0])
                .data.cpu()
                .float()
                .numpy()
            )
            # clean up
            del feats, feats0, p_len
            trim_cache(self.device)
        return audio1

    def _retrieve_speaker_embeddings(self, feats, index, big_npy, index_rate):
        npy = np.ascontiguousarray(feats[0].float().cpu().numpy())
        if index.ntotal == 0:
            return feats
        if getattr(index, "metric_type", faiss.METRIC_L2) != faiss.METRIC_L2:
            raise ValueError("FAISS indeksi L2 uzaklık metriği kullanmalıdır.")
        if getattr(index, "d", npy.shape[1]) != npy.shape[1]:
            raise ValueError("FAISS indeksi seçilen ses modeliyle uyumlu değil.")
        # Legacy array argument remains supported for existing API callers.
        # Production uses search_and_reconstruct: no full reconstruct_n copy.
        if big_npy is not None and (big_npy.ndim != 2 or big_npy.shape[1] != npy.shape[1] or len(big_npy) != index.ntotal):
            raise ValueError("FAISS indeksi seçilen ses modeliyle uyumlu değil.")
        result = np.empty_like(npy)
        for start in range(0, len(npy), 256):
            block = npy[start:start + 256]
            if big_npy is None:
                score, ix, neighbors = index.search_and_reconstruct(block, min(8, index.ntotal))
            else:
                score, ix = index.search(block, k=min(8, index.ntotal))
                neighbors = big_npy[np.clip(ix, 0, index.ntotal - 1)]
            valid = (ix >= 0) & (ix < index.ntotal) & np.isfinite(score)
            valid &= np.isfinite(neighbors).all(axis=2)
            # Existing squared inverse-L2-distance weighting, bounded per block.
            weight = np.where(valid, np.square(1 / np.maximum(score, 1e-5)), 0)
            totals = weight.sum(axis=1, keepdims=True)
            weight /= np.maximum(totals, 1e-20)
            retrieved = np.sum(np.where(valid[:, :, None], neighbors, 0) * weight[:, :, None], axis=1)
            result[start:start + len(block)] = np.where(totals > 0, retrieved, block)
        feats = (
            torch.from_numpy(result).unsqueeze(0).to(self.device) * index_rate
            + (1 - index_rate) * feats
        )
        return feats

    def pipeline(
        self,
        model,
        net_g,
        sid,
        audio,
        pitch,
        f0_method,
        file_index,
        index_rate,
        pitch_guidance,
        volume_envelope,
        version,
        protect,
        f0_autotune,
        f0_autotune_strength,
        proposed_pitch,
        proposed_pitch_threshold,
    ):
        """
        The main pipeline function for performing voice conversion.

        Args:
            model: The feature extractor model.
            net_g: The generative model for synthesizing speech.
            sid: Speaker ID for the target voice.
            audio: The input audio signal.
            input_audio_path: Path to the input audio file.
            pitch: Key to adjust the pitch of the F0 contour.
            f0_method: Method to use for F0 estimation.
            file_index: Path to the FAISS index file for speaker embedding retrieval.
            index_rate: Blending rate for speaker embedding retrieval.
            pitch_guidance: Whether to use pitch guidance during voice conversion.
            tgt_sr: Target sampling rate for the output audio.
            resample_sr: Resampling rate for the output audio.
            version: Model version.
            protect: Protection level for preserving the original pitch.
            hop_length: Hop length for F0 estimation methods.
            f0_autotune: Whether to apply autotune to the F0 contour.
        """
        if file_index != "" and os.path.exists(file_index) and index_rate > 0:
            try:
                index = load_index(file_index, 768 if version == "v2" else 256)
                big_npy = None
                logger.info("FAISS index loaded: %r; vectors=%d, rate=%s", os.path.basename(file_index), index.ntotal, index_rate)
            except Exception as error:
                raise ValueError(
                    "FAISS indeksi okunamadı. Geçerli bir index seçin veya model kaydını "
                    f"index olmadan yeniden ekleyin. Ayrıntı: {error}"
                ) from error
        else:
            if file_index != "" and not os.path.exists(file_index):
                logger.warning("FAISS index not found: %r", file_index)
            index = big_npy = None
        if len(audio) < self.window or not np.isfinite(audio).all():
            raise ValueError("Ses boş, geçersiz veya 10 milisaniyeden kısa.")
        if self.quality_policy.pipeline_highpass_48hz:
            audio = signal.filtfilt(bh, ah, audio)
        audio_pad = np.pad(audio, (self.window // 2, self.window // 2), mode="reflect")
        opt_ts = []
        if audio_pad.shape[0] > self.t_max:
            audio_sum = np.zeros_like(audio)
            for i in range(self.window):
                audio_sum += audio_pad[i : i - self.window]
            for t in range(self.t_center, audio.shape[0], self.t_center):
                opt_ts.append(
                    t
                    - self.t_query
                    + np.where(
                        np.abs(audio_sum[t - self.t_query : t + self.t_query])
                        == np.abs(audio_sum[t - self.t_query : t + self.t_query]).min()
                    )[0][0]
                )
        s = 0
        audio_opt = []
        t = None
        audio_pad = np.pad(audio, (self.t_pad, self.t_pad), mode="reflect")
        p_len = (audio_pad.shape[0] + self.window - 1) // self.window
        sid = torch.tensor(sid, device=self.device).unsqueeze(0).long()
        if pitch_guidance:
            pitch, pitchf = self.get_f0(
                audio_pad,
                p_len,
                f0_method,
                pitch,
                f0_autotune,
                f0_autotune_strength,
                proposed_pitch,
                proposed_pitch_threshold,
            )
            pitch = pitch[:p_len]
            pitchf = pitchf[:p_len]
            if self.device == "mps":
                pitchf = pitchf.astype(np.float32)
            pitch = torch.tensor(pitch, device=self.device).unsqueeze(0).long()
            pitchf = torch.tensor(pitchf, device=self.device).unsqueeze(0).float()
        for t in opt_ts:
            t = t // self.window * self.window
            if pitch_guidance:
                audio_opt.append(
                    self.voice_conversion(
                        model,
                        net_g,
                        sid,
                        audio_pad[s : t + self.t_pad2 + self.window],
                        pitch[:, s // self.window : (t + self.t_pad2) // self.window],
                        pitchf[:, s // self.window : (t + self.t_pad2) // self.window],
                        index,
                        big_npy,
                        index_rate,
                        version,
                        protect,
                        target_frames=(t + self.t_pad2 - s) // self.window,
                    )[self.t_pad_tgt : -self.t_pad_tgt]
                )
            else:
                audio_opt.append(
                    self.voice_conversion(
                        model,
                        net_g,
                        sid,
                        audio_pad[s : t + self.t_pad2 + self.window],
                        None,
                        None,
                        index,
                        big_npy,
                        index_rate,
                        version,
                        protect,
                        target_frames=(t + self.t_pad2 - s) // self.window,
                    )[self.t_pad_tgt : -self.t_pad_tgt]
                )
            s = t
        if pitch_guidance:
            audio_opt.append(
                self.voice_conversion(
                    model,
                    net_g,
                    sid,
                    audio_pad[t:],
                    pitch[:, t // self.window :] if t is not None else pitch,
                    pitchf[:, t // self.window :] if t is not None else pitchf,
                    index,
                    big_npy,
                    index_rate,
                    version,
                    protect,
                )[self.t_pad_tgt : -self.t_pad_tgt]
            )
        else:
            audio_opt.append(
                self.voice_conversion(
                    model,
                    net_g,
                    sid,
                    audio_pad[t:],
                    None,
                    None,
                    index,
                    big_npy,
                    index_rate,
                    version,
                    protect,
                )[self.t_pad_tgt : -self.t_pad_tgt]
            )
        audio_opt = np.concatenate(audio_opt)
        expected_length = round(len(audio) * self.tgt_sr / self.sample_rate)
        if len(audio_opt) < expected_length:
            raise ValueError("RVC modeli beklenen ses süresinden kısa çıktı üretti; çıktı kaydedilmedi.")
        # The last partial 10-ms frame has been synthesized with tail context;
        # discard only the extra generated samples beyond the source timeline.
        audio_opt = audio_opt[:expected_length]
        if not len(audio_opt) or not np.isfinite(audio_opt).all():
            raise ValueError("RVC motoru boş veya geçersiz ses üretti.")
        if volume_envelope != 1:
            audio_opt = AudioProcessor.change_rms(
                audio, self.sample_rate, audio_opt, self.tgt_sr, volume_envelope
            )
        audio_max = np.abs(audio_opt).max() / 0.99
        if audio_max > 1:
            audio_opt /= audio_max
        if pitch_guidance:
            del pitch, pitchf
        del sid
        trim_cache(self.device)
        return audio_opt
