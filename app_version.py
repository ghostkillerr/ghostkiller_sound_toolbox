"""One application version shared by runtime, frozen build and installer."""
import json
from pathlib import Path
import re
from app_runtime import resource_directory


def read_application_version(path=None):
    path = Path(path) if path is not None else Path(resource_directory())/'version.json'
    value = json.loads(path.read_text(encoding='utf-8'))
    version = value.get('version') if isinstance(value, dict) else None
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Uygulama sürüm bilgisi eksik veya geçersiz: '+str(path))
    return version
