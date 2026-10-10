import os
from app_runtime import configure_runtime_cache

configure_runtime_cache()

import time
import torch
import librosa
import logging
import numpy as np
import soundfile as sf
import noisereduce as nr
from pedalboard import (
    Pedalboard,
    Chorus,
    Distortion,
    Reverb,
    PitchShift,
    Limiter,
    Gain,
    Bitcrush,
    Clipping,
    Compressor,
    Delay,
)

from rvc.infer.pipeline import Pipeline as VC
from rvc.lib.utils import load_audio_infer, load_embedding
from rvc.lib.tools.split_audio import process_audio, merge_audio
from rvc.lib.algorithm.synthesizers import Synthesizer
from rvc.configs.config import Config

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("faiss").setLevel(logging.WARNING)
logging.getLogger("faiss.loader").setLevel(logging.WARNING)


class VoiceConverter:
    """
    A class for performing voice conversion using the Retrieval-Based Voice Conversion (RVC) method.
    """

    def __init__(self, device=None, allow_model_download=True):
        """
        Initializes the VoiceConverter with default configuration, and sets up models and parameters.
        """
        self.config = Config(device=device)
        self.allow_model_download = allow_model_download
        self.hubert_model = (
            None  # Initialize the Hubert model (for embedding extraction)
        )
        self.last_embedder_model = None  # Last used embedder model
        self.tgt_sr = None  # Target sampling rate for the output audio
        self.net_g = None  # Generator network for voice conversion
        self.vc = None  # Voice conversion pipeline instance
        self.cpt = None  # Checkpoint for loading model weights
        self.version = None  # Model version
        self.n_spk = None  # Number of speakers in the model
        self.use_f0 = None  # Whether the model uses F0
        self.loaded_model = None

    def load_hubert(self, embedder_model: str, embedder_model_custom: str = None):
        """
        Loads the HuBERT model for speaker embedding extraction.

        Args:
            embedder_model (str): Path to the pre-trained HuBERT model.
            embedder_model_custom (str): Path to the custom HuBERT model.
        """
        self.hubert_model = load_embedding(embedder_model, embedder_model_custom, allow_download=self.allow_model_download)
        self.hubert_model = self.hubert_model.to(self.config.device).float()
        self.hubert_model.eval()

    @staticmethod
    def remove_audio_noise(data, sr, reduction_strength=0.7):
        """
        Removes noise from an audio file using the NoiseReduce library.

        Args:
            data (numpy.ndarray): The audio data as a NumPy array.
            sr (int): The sample rate of the audio data.
            reduction_strength (float): Strength of the noise reduction. Default is 0.7.
        """
        try:
            reduced_noise = nr.reduce_noise(
                y=data, sr=sr, prop_decrease=reduction_strength
            )
            return reduced_noise
        except Exception as error:
            print(f"An error occurred removing audio noise: {error}")
            return None

    @staticmethod
    def convert_audio_format(input_path, output_path, output_format):
        """
        Converts an audio file to a specified output format.

        Args:
            input_path (str): Path to the input audio file.
            output_path (str): Path to the output audio file.
            output_format (str): Desired audio format (e.g., "WAV", "MP3").
        """
        if output_format.upper() != "WAV":
            audio, sample_rate = sf.read(input_path)
            sf.write(output_path, audio, sample_rate, format=output_format.upper())
            return output_path
        return input_path

    @staticmethod
    def post_process_audio(
        audio_input,
        sample_rate,
        **kwargs,
    ):
        board = Pedalboard()
        if kwargs.get("reverb", False):
            reverb = Reverb(
                room_size=kwargs.get("reverb_room_size", 0.5),
                damping=kwargs.get("reverb_damping", 0.5),
                wet_level=kwargs.get("reverb_wet_level", 0.33),
                dry_level=kwargs.get("reverb_dry_level", 0.4),
                width=kwargs.get("reverb_width", 1.0),
                freeze_mode=kwargs.get("reverb_freeze_mode", 0),
            )
            board.append(reverb)
        if kwargs.get("pitch_shift", False):
            pitch_shift = PitchShift(semitones=kwargs.get("pitch_shift_semitones", 0))
            board.append(pitch_shift)
        if kwargs.get("limiter", False):
            limiter = Limiter(
                threshold_db=kwargs.get("limiter_threshold", -6),
                release_ms=kwargs.get("limiter_release", 0.05),
            )
            board.append(limiter)
        if kwargs.get("gain", False):
            gain = Gain(gain_db=kwargs.get("gain_db", 0))
            board.append(gain)
        if kwargs.get("distortion", False):
            distortion = Distortion(drive_db=kwargs.get("distortion_gain", 25))
            board.append(distortion)
        if kwargs.get("chorus", False):
            chorus = Chorus(
                rate_hz=kwargs.get("chorus_rate", 1.0),
                depth=kwargs.get("chorus_depth", 0.25),
                centre_delay_ms=kwargs.get("chorus_delay", 7),
                feedback=kwargs.get("chorus_feedback", 0.0),
                mix=kwargs.get("chorus_mix", 0.5),
            )
            board.append(chorus)
        if kwargs.get("bitcrush", False):
            bitcrush = Bitcrush(bit_depth=kwargs.get("bitcrush_bit_depth", 8))
            board.append(bitcrush)
        if kwargs.get("clipping", False):
            clipping = Clipping(threshold_db=kwargs.get("clipping_threshold", 0))
            board.append(clipping)
        if kwargs.get("compressor", False):
            compressor = Compressor(
                threshold_db=kwargs.get("compressor_threshold", 0),
                ratio=kwargs.get("compressor_ratio", 1),
                attack_ms=kwargs.get("compressor_attack", 1.0),
                release_ms=kwargs.get("compressor_release", 100),
            )
            board.append(compressor)
        if kwargs.get("delay", False):
            delay = Delay(
                delay_seconds=kwargs.get("delay_seconds", 0.5),
                feedback=kwargs.get("delay_feedback", 0.0),
                mix=kwargs.get("delay_mix", 0.5),
            )
            board.append(delay)
        return board(audio_input, sample_rate)

    def convert_audio(
        self,
        audio_input_path: str,
        audio_output_path: str,
        model_path: str,
        index_path: str,
        pitch: int = 0,
        f0_method: str = "rmvpe",
        index_rate: float = 0.75,
        volume_envelope: float = 1.0,
        protect: float = 0.5,
        hop_length: int = 128,
        split_audio: bool = False,
        f0_autotune: bool = False,
        f0_autotune_strength: float = 1,
        embedder_model: str = "contentvec",
        embedder_model_custom: str = None,
        clean_audio: bool = False,
        clean_strength: float = 0.5,
        export_format: str = "WAV",
        post_process: bool = False,
        resample_sr: int = 0,
        sid: int = 0,
        proposed_pitch: bool = False,
        proposed_pitch_threshold: float = 155.0,
        **kwargs,
    ):
        """
        Performs voice conversion on the input audio.

        Args:
            pitch (int): Key for F0 up-sampling.
            index_rate (float): Rate for index matching.
            volume_envelope (int): RMS mix rate.
            protect (float): Protection rate for certain audio segments.
            hop_length (int): Hop length for audio processing.
            f0_method (str): Method for F0 extraction.
            audio_input_path (str): Path to the input audio file.
            audio_output_path (str): Path to the output audio file.
            model_path (str): Path to the voice conversion model.
            index_path (str): Path to the index file.
            split_audio (bool): Whether to split the audio for processing.
            f0_autotune (bool): Whether to use F0 autotune.
            clean_audio (bool): Whether to clean the audio.
            clean_strength (float): Strength of the audio cleaning.
            export_format (str): Format for exporting the audio.
            f0_file (str): Path to the F0 file.
            embedder_model (str): Path to the embedder model.
            embedder_model_custom (str): Path to the custom embedder model.
            resample_sr (int, optional): Resample sampling rate. Default is 0.
            sid (int, optional): Speaker ID. Default is 0.
            **kwargs: Additional keyword arguments.
        """
        pitch = int(float(pitch)) if pitch is not None else 0
        index_rate = float(index_rate) if index_rate is not None else 0.75
        volume_envelope = float(volume_envelope) if volume_envelope is not None else 1.0
        protect = float(protect) if protect is not None else 0.5
        hop_length = int(hop_length) if hop_length is not None else 128
        clean_strength = float(clean_strength) if clean_strength is not None else 0.5
        for name, value in (("index_rate", index_rate), ("volume_envelope", volume_envelope),
                            ("protect", protect), ("clean_strength", clean_strength)):
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name}, 0 ile 1 arasında olmalıdır.")
        if not 0 <= protect <= .5:
            raise ValueError("protect, 0 ile 0.5 arasında olmalıdır.")
        if hop_length <= 0:
            raise ValueError("hop_length pozitif olmalıdır.")

        if not model_path or not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model bulunamadı: {model_path}")

        self.get_vc(model_path, sid)
        if not isinstance(sid, int) or not 0 <= sid < self.n_spk:
            raise ValueError("Geçersiz konuşmacı numarası.")

        start_time = time.time()
        print(f"Converting audio '{audio_input_path}'...")

        audio = load_audio_infer(
            audio_input_path,
            16000,
            **kwargs,
        )

        # SOTA: RVC Öncesi 80 Hz Low-Cut (High-Pass) ve Gürültü/Rumble Temizliği
        try:
            from scipy.signal import butter, filtfilt
            b_hp, a_hp = butter(4, 80 / 8000, btype='highpass')
            audio = filtfilt(b_hp, a_hp, audio)
        except Exception as e:
            print(f"[PRE-PROCESS UYARI] 80Hz Low-Cut filtresi uygulanamadı: {e}")

        if audio.size == 0 or not np.isfinite(audio).all():
            raise ValueError("Ses dosyası boş veya geçersiz örnekler içeriyor.")
        audio_max = np.abs(audio).max() / 0.95

        if audio_max > 1:
            audio /= audio_max

        embedder_key = (embedder_model, embedder_model_custom)
        if self.hubert_model is None or embedder_key != self.last_embedder_model:
            self.load_hubert(embedder_model, embedder_model_custom)
            self.last_embedder_model = embedder_key

        file_index = (
            (index_path or "").strip()
            .strip('"')
            .strip("\n")
            .strip('"')
            .strip()
        )
        if "trained" in file_index:
            alt_index = file_index.replace("trained", "added")
            if os.path.exists(alt_index):
                file_index = alt_index

        output_sr = int(resample_sr) if resample_sr >= 16000 else self.tgt_sr

        if split_audio:
            chunks, intervals = process_audio(audio, 16000)
            print(f"Audio split into {len(chunks)} chunks for processing.")
        else:
            chunks = []
            chunks.append(audio)

        converted_chunks = []
        for c in chunks:
            audio_opt = self.vc.pipeline(
                model=self.hubert_model,
                net_g=self.net_g,
                sid=sid,
                audio=c,
                pitch=pitch,
                f0_method=f0_method,
                file_index=file_index,
                index_rate=index_rate,
                pitch_guidance=self.use_f0,
                volume_envelope=volume_envelope,
                version=self.version,
                protect=protect,
                f0_autotune=f0_autotune,
                f0_autotune_strength=f0_autotune_strength,
                proposed_pitch=proposed_pitch,
                proposed_pitch_threshold=proposed_pitch_threshold,
            )
            converted_chunks.append(audio_opt)
            if split_audio:
                print(f"Converted audio chunk {len(converted_chunks)}")

        if split_audio:
            audio_opt = merge_audio(
                chunks, converted_chunks, intervals, 16000, self.tgt_sr, len(audio)
            )
        else:
            audio_opt = converted_chunks[0]

        if output_sr != self.tgt_sr:
            audio_opt = librosa.resample(audio_opt, orig_sr=self.tgt_sr, target_sr=output_sr, res_type="soxr_vhq")

        if clean_audio:
            cleaned_audio = self.remove_audio_noise(
                audio_opt, output_sr, clean_strength
            )
            if cleaned_audio is not None:
                audio_opt = cleaned_audio

        if post_process:
            audio_opt = self.post_process_audio(
                audio_input=audio_opt,
                sample_rate=output_sr,
                **kwargs,
            )

        if not len(audio_opt) or not np.isfinite(audio_opt).all():
            raise ValueError("Dönüşüm boş veya geçersiz bir ses üretti.")
        sf.write(audio_output_path, audio_opt, output_sr, format="WAV")
        output_path_format = os.path.splitext(audio_output_path)[0] + f".{export_format.lower()}"
        audio_output_path = self.convert_audio_format(
            audio_output_path, output_path_format, export_format
        )

        elapsed_time = time.time() - start_time
        print(
            f"Conversion completed at '{audio_output_path}' in {elapsed_time:.2f} seconds."
        )
        return audio_output_path

    def get_vc(self, weight_root, sid):
        """
        Loads the voice conversion model and sets up the pipeline.

        Args:
            weight_root (str): Path to the model weights.
            sid (int): Speaker ID.
        """
        if sid == "" or sid == []:
            self.cleanup_model()

        if not self.loaded_model or self.loaded_model != weight_root:
            self.cleanup_model()
            try:
                self.load_model(weight_root)
                if self.cpt is None:
                    raise FileNotFoundError(weight_root)
                self.setup_network()
                self.setup_vc_instance()
                self.loaded_model = weight_root
            except Exception:
                self.cleanup_model()
                raise

    def cleanup_model(self):
        """
        Cleans up the model and releases resources.
        """
        self.hubert_model = self.net_g = self.n_spk = self.vc = self.tgt_sr = None
        self.cpt = self.loaded_model = None
        self.last_embedder_model = self.version = self.use_f0 = None
        if self.config.device.startswith("cuda") and torch.cuda.is_available():
            with torch.cuda.device(self.config.device):
                torch.cuda.empty_cache()

    def load_model(self, weight_root):
        """
        Loads the model weights from the specified path.

        Args:
            weight_root (str): Path to the model weights.
        """
        self.cpt = (
            torch.load(weight_root, map_location="cpu", weights_only=True)
            if os.path.isfile(weight_root)
            else None
        )

    def setup_network(self):
        """
        Sets up the network configuration based on the loaded checkpoint.
        """
        if self.cpt is not None:
            if not isinstance(self.cpt, dict) or not isinstance(self.cpt.get("config"), (list, tuple)) or len(self.cpt["config"]) != 18:
                raise ValueError("Geçersiz RVC model yapılandırması.")
            self.cpt["config"] = list(self.cpt["config"])
            if not isinstance(self.cpt.get("weight"), dict) or "emb_g.weight" not in self.cpt["weight"]:
                raise ValueError("RVC model ağırlıkları eksik.")
            self.tgt_sr = self.cpt["config"][-1]
            self.cpt["config"][-3] = self.cpt["weight"]["emb_g.weight"].shape[0]
            self.use_f0 = self.cpt.get("f0", 1)

            self.version = self.cpt.get("version", "v1")
            self.text_enc_hidden_dim = 768 if self.version == "v2" else 256
            self.vocoder = self.cpt.get("vocoder", "HiFi-GAN")
            if self.version not in ("v1", "v2") or self.vocoder not in ("HiFi-GAN", "MRF HiFi-GAN", "RefineGAN"):
                raise ValueError("Desteklenmeyen RVC model sürümü veya vocoder.")
            if not self.use_f0 and self.vocoder != "HiFi-GAN":
                raise ValueError("Bu vocoder F0 bilgisi gerektiriyor.")
            if not isinstance(self.tgt_sr, int) or self.tgt_sr < 16000:
                raise ValueError("Geçersiz model örnekleme hızı.")
            self.net_g = Synthesizer(
                *self.cpt["config"],
                use_f0=self.use_f0,
                text_enc_hidden_dim=self.text_enc_hidden_dim,
                vocoder=self.vocoder,
            )
            del self.net_g.enc_q
            incompatible = self.net_g.load_state_dict(self.cpt["weight"], strict=False)
            if incompatible.missing_keys:
                raise ValueError(f"RVC model ağırlıkları eksik: {', '.join(incompatible.missing_keys[:5])}")
            self.net_g = self.net_g.to(self.config.device).float()
            self.net_g.eval()

    def setup_vc_instance(self):
        """
        Sets up the voice conversion pipeline instance based on the target sampling rate and configuration.
        """
        if self.cpt is not None:
            self.vc = VC(self.tgt_sr, self.config)
            self.n_spk = self.cpt["config"][-3]
