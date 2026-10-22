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
from rvc.infer.helper_cache import InferenceHelperCache, file_identity
from rvc.infer.quality_policy import InferenceQualityPolicy
from app_runtime import model_directory
from compute_backend import clear_cache, trim_cache
from rvc.infer.model_validation import (validate_architecture, validate_meta_network,
                                      validate_weights, checkpoint_archive_precheck)
from rvc.infer.safe_index import available_memory

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("faiss").setLevel(logging.WARNING)
logging.getLogger("faiss.loader").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class VoiceConverter:
    """
    A class for performing voice conversion using the Retrieval-Based Voice Conversion (RVC) method.
    """

    def __init__(self, device=None, allow_model_download=True, helper_cache=None, quality_policy=None):
        """
        Initializes the VoiceConverter with default configuration, and sets up models and parameters.
        """
        self.config = Config(device=device)
        self.allow_model_download = allow_model_download
        self.helper_cache = helper_cache if helper_cache is not None else InferenceHelperCache()
        if quality_policy is not None and not isinstance(quality_policy, InferenceQualityPolicy):
            raise ValueError("Geçersiz kalite politikası.")
        self.quality_policy = quality_policy or InferenceQualityPolicy()
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
        self._loaded_model_identity = None

    def load_hubert(self, embedder_model: str, embedder_model_custom: str = None):
        """
        Loads the HuBERT model for speaker embedding extraction.

        Args:
            embedder_model (str): Path to the pre-trained HuBERT model.
            embedder_model_custom (str): Path to the custom HuBERT model.
        """
        folder = embedder_model_custom if embedder_model == "custom" else os.path.join(
            model_directory(), "embedders", embedder_model.replace("-", "_") if "hubert" in embedder_model else embedder_model)
        key = ("embedder", str(self.config.device), "float32", embedder_model,
               file_identity(os.path.join(folder or "", "config.json")),
               file_identity(os.path.join(folder or "", "pytorch_model.bin")),
               file_identity(os.path.join(folder or "", "model.safetensors")))
        def loader():
            model = load_embedding(embedder_model, embedder_model_custom,
                                   allow_download=self.allow_model_download, rvc_version=self.version)
            return model.to(self.config.device).float().eval()
        self.hubert_model = self.helper_cache.get_or_create(key, loader)

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
            logger.warning("Audio noise removal failed: %s", error)
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
            encoding = {"subtype": "PCM_24"} if output_format.upper() == "FLAC" else {}
            sf.write(output_path, audio, sample_rate, format=output_format.upper(), **encoding)
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
        hop_length: int = 160,
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
        quality_policy: InferenceQualityPolicy = None,
        **kwargs,
    ):
        """
        Performs voice conversion on the input audio.

        Args:
            pitch (int): Key for F0 up-sampling.
            index_rate (float): Rate for index matching.
            volume_envelope (int): RMS mix rate.
            protect (float): Protection rate for certain audio segments.
            hop_length (int): Fixed RVC pitch hop, 160 samples at 16 kHz (100 fps).
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
        hop_length = 160 if hop_length is None else hop_length
        clean_strength = float(clean_strength) if clean_strength is not None else 0.5
        for name, value in (("index_rate", index_rate), ("volume_envelope", volume_envelope),
                            ("protect", protect), ("clean_strength", clean_strength)):
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name}, 0 ile 1 arasında olmalıdır.")
        if not 0 <= protect <= .5:
            raise ValueError("protect, 0 ile 0.5 arasında olmalıdır.")
        if isinstance(hop_length, bool) or hop_length != 160:
            raise ValueError("RVC hop_length sabittir: 16 kHz'de 160 örnek (100 fps).")
        if quality_policy is not None:
            if not isinstance(quality_policy, InferenceQualityPolicy):
                raise ValueError("Geçersiz kalite politikası.")
            self.quality_policy = quality_policy

        if not model_path or not os.path.isfile(model_path):
            raise FileNotFoundError(f"Model bulunamadı: {model_path}")

        self.get_vc(model_path, sid)
        self.validate_embedder(embedder_model, embedder_model_custom)
        self.vc.quality_policy = self.quality_policy
        if not isinstance(sid, int) or not 0 <= sid < self.n_spk:
            raise ValueError("Geçersiz konuşmacı numarası.")

        start_time = time.time()
        logger.info("Converting audio %r", audio_input_path)
        source_info = sf.info(str(audio_input_path).strip(' "\n'))

        audio = load_audio_infer(
            audio_input_path,
            16000,
            memory_output_rate=max(self.tgt_sr, int(resample_sr)),
            **kwargs,
        )

        if self.quality_policy.input_highpass_80hz:
            from scipy.signal import butter, filtfilt
            b_hp, a_hp = butter(4, 80 / 8000, btype='highpass')
            if audio.size <= 3 * max(len(b_hp), len(a_hp)):
                raise ValueError("Ses 80 Hz filtresi için çok kısa; daha uzun bir ses seçin.")
            audio = filtfilt(b_hp, a_hp, audio)

        if audio.size == 0 or not np.isfinite(audio).all():
            raise ValueError("Ses dosyası boş veya geçersiz örnekler içeriyor.")
        audio_max = np.abs(audio).max() / 0.95

        if audio_max > 1:
            audio /= audio_max

        embedder_key = (embedder_model, embedder_model_custom)
        if self.hubert_model is None or embedder_key != self.last_embedder_model or len(self.helper_cache):
            self.load_hubert(embedder_model, embedder_model_custom)
            self.last_embedder_model = embedder_key

        file_index = (
            (index_path or "").strip()
            .strip('"')
            .strip("\n")
            .strip('"')
            .strip()
        )
        # The caller selected this index explicitly. Renaming "trained" to
        # "added" can silently select another voice, even in a parent directory.

        output_sr = int(resample_sr) if resample_sr >= 16000 else self.tgt_sr

        if split_audio:
            chunks, intervals = process_audio(audio, 16000)
            logger.info("Audio split into %d chunks", len(chunks))
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
                logger.info("Converted audio chunk %d", len(converted_chunks))

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
        expected_frames = round(source_info.frames * output_sr / source_info.samplerate)
        if len(audio_opt) < expected_frames:
            raise ValueError("Dönüşüm kaynak sesin zaman çizelgesinden kısa çıktı üretti; çıktı kaydedilmedi.")
        audio_opt = audio_opt[:expected_frames]
        # Keep neural output intact until the shared user-export boundary.
        sf.write(audio_output_path, audio_opt, output_sr, format="WAV", subtype="FLOAT")
        output_path_format = os.path.splitext(audio_output_path)[0] + f".{export_format.lower()}"
        audio_output_path = self.convert_audio_format(
            audio_output_path, output_path_format, export_format
        )

        elapsed_time = time.time() - start_time
        logger.info("Conversion completed at %r in %.2f seconds", audio_output_path, elapsed_time)
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

        identity = file_identity(weight_root)
        if not self.loaded_model or self.loaded_model != weight_root or self._loaded_model_identity != identity:
            self.cleanup_model(release_helpers=False)
            try:
                self.load_model(weight_root)
                if self.cpt is None:
                    raise FileNotFoundError(weight_root)
                self.setup_network()
                self.setup_vc_instance()
                self.loaded_model = weight_root
                self._loaded_model_identity = identity
            except Exception:
                self.cleanup_model(release_helpers=False)
                raise

    def cleanup_model(self, release_helpers=True):
        """
        Cleans up the model and releases resources.
        """
        self.net_g = self.n_spk = self.vc = self.tgt_sr = None
        self.cpt = self.loaded_model = None
        self._loaded_model_identity = None
        self.version = self.use_f0 = None
        if release_helpers:
            self.hubert_model = self.last_embedder_model = None
            self.helper_cache.clear()
            clear_cache(self.config.device)
        else:
            trim_cache(self.config.device)

    def validate_embedder(self, embedder_model, custom_embedder=None):
        """Honor checkpoint metadata before computing mismatched features.

        Metadata-free legacy models retain the historical ContentVec contract.
        Explicit metadata never silently falls back to another helper network.
        """
        expected = (self.cpt or {}).get("embedder_model")
        if expected is not None:
            if not isinstance(expected, str) or not expected.strip():
                raise ValueError("Model embedder_model bilgisi geçersiz.")
            if expected.strip().lower() != str(embedder_model).strip().lower():
                raise ValueError(f"Model '{expected}' embedder ile eğitilmiş; seçilen '{embedder_model}' uyumlu değil.")
        if embedder_model == "custom" and (not custom_embedder or not os.path.isdir(custom_embedder)):
            raise ValueError("Model için eşleşen özel embedder klasörü seçilmelidir.")

    def load_model(self, weight_root):
        """
        Loads the model weights from the specified path.

        Args:
            weight_root (str): Path to the model weights.
        """
        if os.path.isfile(weight_root):
            checkpoint_archive_precheck(weight_root)
            self.cpt = torch.load(weight_root, map_location="cpu", weights_only=True, mmap=True)
        else:
            self.cpt = None

    def setup_network(self):
        """
        Sets up the network configuration based on the loaded checkpoint.
        """
        if self.cpt is not None:
            if not isinstance(self.cpt, dict) or not isinstance(self.cpt.get("config"), (list, tuple)) or len(self.cpt["config"]) != 18:
                raise ValueError("Geçersiz RVC model yapılandırması.")
            self.cpt["config"] = validate_architecture(self.cpt["config"], self.cpt.get("weight"))
            self.tgt_sr = self.cpt["config"][-1]
            self.use_f0 = self.cpt.get("f0", 1)
            if type(self.use_f0) not in (bool, int) or self.use_f0 not in (0, 1):
                raise ValueError("RVC model f0 bilgisi 0 veya 1 olmalıdır.")

            self.version = self.cpt.get("version", "v1")
            self.text_enc_hidden_dim = 768 if self.version == "v2" else 256
            self.vocoder = self.cpt.get("vocoder", "HiFi-GAN")
            if self.version not in ("v1", "v2") or self.vocoder not in ("HiFi-GAN", "MRF HiFi-GAN", "RefineGAN"):
                raise ValueError("Desteklenmeyen RVC model sürümü veya vocoder.")
            if not self.use_f0 and self.vocoder != "HiFi-GAN":
                raise ValueError("Bu vocoder F0 bilgisi gerektiriyor.")
            if not isinstance(self.tgt_sr, int) or self.tgt_sr < 16000:
                raise ValueError("Geçersiz model örnekleme hızı.")
            # Meta construction checks combined channel/layer/kernel allocation
            # costs before any real generator parameter allocation is attempted.
            with torch.device("meta"):
                schema = Synthesizer(
                    *self.cpt["config"], use_f0=self.use_f0,
                    text_enc_hidden_dim=self.text_enc_hidden_dim, vocoder=self.vocoder)
                del schema.enc_q
                required = validate_meta_network(schema)
                validate_weights(schema, self.cpt["weight"])
            del schema
            if required * 2 > available_memory() * .6:
                raise ValueError("RVC ağını oluşturmak için kullanılabilir RAM yetersiz. Daha küçük bir model seçin veya diğer uygulamaları kapatın.")
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
            # Parameters already reside in the generator. Retain metadata, not
            # a second CPU copy of every checkpoint weight for the whole job.
            self.cpt.pop("weight", None)

    def setup_vc_instance(self):
        """
        Sets up the voice conversion pipeline instance based on the target sampling rate and configuration.
        """
        if self.cpt is not None:
            self.vc = VC(self.tgt_sr, self.config, self.helper_cache, self.quality_policy)
            self.n_spk = self.cpt["config"][-3]
