"""Small job-scoped cache for feature and pitch helper networks."""
from collections import OrderedDict
import os


def file_identity(path):
    canonical = os.path.normcase(os.path.realpath(path))
    try:
        stat = os.stat(canonical)
    except OSError:
        return canonical, None, None
    return canonical, stat.st_size, stat.st_mtime_ns


class InferenceHelperCache:
    """At most two helpers; caller owns lifetime and clears at job completion.

    A new key evicts the oldest helper *before* allocating another network.
    Device, precision and file identities must be included in the key. This
    cache intentionally does not share generator checkpoints between models.
    """
    def __init__(self, max_entries=2):
        if not isinstance(max_entries, int) or not 1 <= max_entries <= 4:
            raise ValueError("Yardımcı ağ cache sınırı 1 ile 4 arasında olmalıdır.")
        self.max_entries = max_entries
        self._entries = OrderedDict()

    def get_or_create(self, key, loader):
        if key in self._entries:
            self._entries.move_to_end(key)
            return self._entries[key]
        while len(self._entries) >= self.max_entries:
            self._entries.popitem(last=False)
        value = loader()
        self._entries[key] = value
        return value

    def clear(self):
        self._entries.clear()

    def __len__(self):
        return len(self._entries)
