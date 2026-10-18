"""Use the project's prepared runtime when main.py is opened with global Python."""
import json
from pathlib import Path
import subprocess
import sys


def source_interpreter(root, executable):
    root = Path(root).resolve()
    current = Path(executable).resolve()
    runtimes = {backend: root/'build'/('release_'+backend)/'Scripts' for backend in ('cpu', 'cuda')}
    try:
        settings = json.loads((root/'settings.json').read_text(encoding='utf-8'))
        preference = settings.get('device', 'cpu')
    except (OSError, ValueError, AttributeError):
        preference = 'cpu'
    # CUDA can also run CPU jobs. A CPU-only GUI cannot honor a saved GPU choice.
    if current.parent == runtimes['cuda'].resolve():
        return None
    if preference != 'gpu' and current.parent == runtimes['cpu'].resolve():
        return None
    directory = runtimes['cuda' if preference == 'gpu' else 'cpu']
    python = directory/'python.exe'
    if not python.is_file():
        return None  # Never install, guess another backend, or replace global Python.
    windowed = directory/'pythonw.exe'
    return str(windowed if windowed.is_file() else python)


def relaunch_source(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if getattr(sys, 'frozen', False) or any(flag in argv for flag in ('--self-test', '--audio-worker', '--training-worker')):
        return False
    root = Path(__file__).resolve().parent
    target = source_interpreter(root, sys.executable)
    if target is None:
        return False
    subprocess.Popen([target, str(root/'main.py'), *argv[1:]], cwd=root,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return True
