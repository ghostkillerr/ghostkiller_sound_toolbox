"""Pin audio-separator to the app's model folder and selected compute device."""
import os
from app_runtime import configure_runtime_cache

configure_runtime_cache()

import torch
from audio_separator.separator import Separator


class LocalSeparator(Separator):
    def check_ffmpeg_installed(self):
        import subprocess
        from app_runtime import ffmpeg_executable, configure_pydub
        configure_pydub()
        output = subprocess.check_output([ffmpeg_executable(), '-version'], text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=15)
        self.logger.info(output.splitlines()[0])

    def load_model(self, *args, **kwargs):
        result = super().load_model(*args,**kwargs)
        if self.output_format.upper()=='FLAC':
            from types import MethodType
            from separation_audio import write_flac24, finite_values
            self.model_instance.write_audio = MethodType(write_flac24,self.model_instance)
            if hasattr(self.model_instance,'inference_vr'):
                original = self.model_instance.inference_vr
                def checked_inference(*args,**kwargs):
                    outputs = original(*args,**kwargs)
                    for output in outputs:
                        finite_values(output)
                    return outputs
                self.model_instance.inference_vr = checked_inference
        return result

    @property
    def model_file_dir(self):
        return self._app_model_dir

    @model_file_dir.setter
    def model_file_dir(self, value):
        # The library's AUDIO_SEPARATOR_MODEL_DIR override must not relocate app models.
        pass

    def __init__(self, model_file_dir, device="cpu", asset_handler=None, **kwargs):
        self._app_model_dir = os.path.realpath(model_file_dir)
        self._app_device = device
        self.asset_handler = asset_handler
        os.makedirs(self._app_model_dir, exist_ok=True)
        super().__init__(model_file_dir=self._app_model_dir, **kwargs)

    def setup_torch_device(self, system_info):
        import onnxruntime
        self.torch_device_cpu = torch.device("cpu")
        self.torch_device = torch.device(self._app_device)
        self.torch_device_mps = None
        self.onnx_execution_provider = ["CPUExecutionProvider"]
        if self.torch_device.type == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("Ekran kartı kullanılamıyor. Ayarlar'dan donanımı yeniden kontrol edin.")
            if "CUDAExecutionProvider" in onnxruntime.get_available_providers():
                index = self.torch_device.index
                if index is None:
                    index = torch.cuda.current_device()
                self.onnx_execution_provider.insert(0, ("CUDAExecutionProvider", {"device_id": index}))
        self.logger.info(f"Uygulamanın seçtiği cihaz: {self.torch_device}")

    def download_file_if_not_exists(self, url, output_path):
        path = os.path.realpath(output_path)
        if os.path.normcase(os.path.commonpath([self._app_model_dir, path])) != os.path.normcase(self._app_model_dir):
            raise ValueError("Model dosyası models klasörü dışında olamaz.")
        if self.asset_handler:
            return self.asset_handler(url, path)
        if not os.path.isfile(path) or not os.path.getsize(path):
            raise FileNotFoundError(f"Eksik model dosyası: {os.path.basename(path)}. Ayarlar sekmesinden indirin.")


from separation_steps import SEPARATION_STEPS
