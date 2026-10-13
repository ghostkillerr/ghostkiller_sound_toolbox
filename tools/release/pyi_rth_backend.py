"""Set native Intel DLL search paths before PyTorch is imported by the EXE."""
import os
from pathlib import Path
import sys

_backend_dll_handles = []
if os.name == 'nt' and hasattr(os, 'add_dll_directory'):
    _backend_root = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) / 'oneapi'
    if _backend_root.is_dir():
        _backend_dirs = sorted({path.parent for path in _backend_root.rglob('*.dll')})
        for _backend_dir in _backend_dirs:
            _backend_dll_handles.append(os.add_dll_directory(str(_backend_dir)))
        os.environ['PATH'] = os.pathsep.join(map(str, _backend_dirs)) + os.pathsep + os.environ.get('PATH', '')
