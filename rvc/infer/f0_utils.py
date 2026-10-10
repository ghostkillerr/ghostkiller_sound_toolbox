"""Pitch smoothing that preserves unvoiced boundaries."""
import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter


def smooth_f0(f0):
    result = np.asarray(f0).copy()
    voiced = np.isfinite(result) & (result > 0)
    result[~voiced] = 0
    boundaries = np.flatnonzero(np.diff(np.r_[False, voiced, False]))
    for start, stop in boundaries.reshape(-1, 2):
        if stop - start > 11:
            segment = median_filter(result[start:stop], size=3, mode="nearest")
            result[start:stop] = np.maximum(savgol_filter(segment, 7, 3), 0)
    return result
