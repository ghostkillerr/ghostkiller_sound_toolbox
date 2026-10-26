"""Measure a fresh, hidden GUI construction without opening user data or engines."""
import json
from pathlib import Path
import sys
import tempfile
import time


def run(output, started):
    import app_runtime
    from startup_diagnostics import process_age_seconds
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='startup-probe-', dir=output.parent) as directory:
        (Path(directory) / 'models').mkdir()
        original_data, original_models = app_runtime.data_directory, app_runtime.model_directory
        app_runtime.data_directory = lambda: directory
        app_runtime.model_directory = lambda *args: str(Path(directory) / 'models')
        try:
            import main
            import ui_cover
            original_app = ui_cover.get_app_dir
            ui_cover.get_app_dir = lambda: directory
            try:
                app = main.wx.App(False)
                frame = main.GhostkillerMainFrame(startup_checks=False)
                result = {'ok': True, 'frozen': bool(getattr(sys, 'frozen', False)),
                          'python_to_frame_s': time.perf_counter() - started,
                          'process_to_frame_s': process_age_seconds(),
                          'heavy_modules': [name for name in ('torch', 'onnxruntime', 'librosa', 'transformers')
                                            if name in sys.modules],
                          'scope': 'Hidden frame, isolated empty user data; no network, model or microphone. Not a cold-cache or visible-window benchmark.'}
                frame.Destroy()
            finally:
                ui_cover.get_app_dir = original_app
        finally:
            app_runtime.data_directory, app_runtime.model_directory = original_data, original_models
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0
