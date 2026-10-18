"""Persisted preferences shared by audio processing and training."""
import json
import os
import tempfile
from app_runtime import data_directory
from audio_export import (DEFAULT_OUTPUT_FORMAT, OUTPUT_FORMATS, normalize_output_format,
                          DEFAULT_OUTPUT_CHANNELS, OUTPUT_CHANNELS, normalize_output_channels)


def write_json_atomic(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


class AppSettings:
    def __init__(self, path=None, manager=None):
        from model_manager import ModelManager
        self.path = path or os.path.join(data_directory(), "settings.json")
        self.manager = manager or ModelManager()
        self.report = None
        self.preference = "cpu"
        self.theme = "light"
        self.auto_update = True
        self.output_format = DEFAULT_OUTPUT_FORMAT
        self.output_channels = DEFAULT_OUTPUT_CHANNELS
        self.error = ""
        self.open_settings = lambda: None
        self.prepare_models = None
        self.refresh_operations = lambda: None
        try:
            with open(self.path, encoding="utf-8") as stream:
                value = json.load(stream)
            if value.get("device") in ("cpu", "gpu"):
                self.preference = value["device"]
            if value.get('theme') in ('light','dark'):
                self.theme = value['theme']
            if isinstance(value.get('auto_update'), bool):
                self.auto_update = value['auto_update']
            if value.get('output_format') in OUTPUT_FORMATS:
                self.output_format = value['output_format']
            if value.get('output_channels') in OUTPUT_CHANNELS:
                self.output_channels = value['output_channels']
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError) as error:
            self.error = f"Kaydedilmiş ayarlar okunamadı; İşlemci seçildi. {error}"

    def select(self, preference):
        self.device_for(preference)
        self.save_option('device',preference)
        self.preference = preference

    def save_option(self, key, value):
        from registry_store import registry_lock
        with registry_lock(self.path):
            try:
                with open(self.path,encoding='utf-8') as stream:
                    current = json.load(stream)
            except FileNotFoundError:
                current = {}
            if not isinstance(current,dict):
                raise ValueError('Ayar dosyası okunamıyor; önce mevcut ayar dosyasını kontrol edin.')
            current[key] = value
            write_json_atomic(self.path,current)

    def select_theme(self, theme):
        if theme not in ('light','dark'):
            raise ValueError('Görünüm açık veya koyu olmalı.')
        self.save_option('theme',theme)
        self.theme = theme

    def select_auto_update(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError('Otomatik güncelleme tercihi açık veya kapalı olmalı.')
        self.save_option('auto_update', enabled)
        self.auto_update = enabled

    def select_output_format(self, output_format):
        output_format = normalize_output_format(output_format)
        self.save_option('output_format', output_format)
        self.output_format = output_format

    def select_output_channels(self, output_channels):
        output_channels = normalize_output_channels(output_channels)
        self.save_option('output_channels', output_channels)
        self.output_channels = output_channels

    def device_for(self, preference=None):
        if self.report is None:
            raise RuntimeError("Donanım kontrolü tamamlanmadı. Ayarlar sekmesinde Donanımı kontrol et düğmesine basın.")
        return self.report.selected(preference or self.preference).device

    def prepare_job(self, model_ids):
        device = self.device_for()
        self.manager.require_ready(model_ids)
        return device
