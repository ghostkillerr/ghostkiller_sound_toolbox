"""Locked read/modify/write for JSON registries shared by app instances."""
from contextlib import contextmanager
from pathlib import Path
import json
import os
import threading
import time

_locks = {}
_locks_guard = threading.Lock()


@contextmanager
def registry_lock(path, timeout=5.):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = os.path.normcase(str(path))
    with _locks_guard:
        lock = _locks.setdefault(key, threading.RLock())
    if not lock.acquire(timeout=timeout):
        raise TimeoutError("Model kayıt dosyası başka bir işlem tarafından kullanılıyor; yeniden deneyin.")
    stream = None
    acquired = False
    try:
        stream = (path.parent/(path.name+".lock")).open("a+b")
        stream.seek(0, os.SEEK_END)
        if not stream.tell():
            stream.write(b"\0")
            stream.flush()
        deadline = time.monotonic()+timeout
        while not acquired:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError as error:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Model kayıt dosyası kilitli; başka uygulama işlemi bittikten sonra yeniden deneyin.") from error
                time.sleep(.05)
        yield
    finally:
        try:
            if stream is not None:
                try:
                    if acquired:
                        stream.seek(0)
                        if os.name == "nt":
                            import msvcrt
                            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                finally:
                    stream.close()
        finally:
            lock.release()


def update_registry(path, mutate, validator=None):
    from app_settings import write_json_atomic
    path = Path(path).resolve()
    with registry_lock(path):
        current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if validator:
            validator(current)
        updated = mutate(current)
        updated = current if updated is None else updated
        if validator:
            validator(updated)
        write_json_atomic(str(path), updated)
        return updated


def apply_model_changes(path, proposed, previous=None, validator=None):
    """Merge explicit edits; never remove records absent from a stale snapshot."""
    def mutate(current):
        if previous is None:
            current.update(proposed)
            return current
        changes = {name:value for name,value in proposed.items() if previous.get(name) != value}
        removed = set(previous)-set(proposed)
        for name in set(changes) | removed:
            if current.get(name) != previous.get(name):
                raise ValueError(f"'{name}' kaydı başka bir işlemde değişmiş; listeyi yenileyip yeniden deneyin.")
        for name in removed:
            current.pop(name, None)
        current.update(changes)
        return current
    return update_registry(path, mutate, validator)
