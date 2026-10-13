"""Small, durable liveness signal independent of a native training operation."""
import json
import os
from pathlib import Path
import threading
import time


class WorkerHeartbeat:
    def __init__(self, job, interval=2):
        self.path = Path(job)/"heartbeat.json"
        self.interval = interval
        self.stage = "startup"
        self.progress_time = time.time()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = None

    def progress(self, stage):
        if stage in ("resources", "heartbeat"):
            return
        with self._lock:
            self.stage, self.progress_time = stage, time.time()

    def _write(self):
        with self._lock:
            value = {"pid":os.getpid(),"time":time.time(),"stage":self.stage,
                     "progress_time":self.progress_time}
        temporary = self.path.with_suffix(".json.part")
        try:
            temporary.write_text(json.dumps(value),encoding="utf-8")
            os.replace(temporary,self.path)
        except OSError:
            # A failed disk signal is detected as stale by the parent. This
            # heartbeat never writes a manifest or training checkpoint.
            pass

    def start(self):
        self._write()
        def beat():
            while not self._stop.wait(self.interval):
                self._write()
        self._thread = threading.Thread(target=beat,name="training-heartbeat",daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
