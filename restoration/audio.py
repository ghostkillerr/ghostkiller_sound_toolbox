"""Candidate detection and bounded mono patches, without model imports."""
import numpy as np
from scipy.ndimage import binary_closing, label, uniform_filter1d

RATE = 44100


def candidate_intervals(reference, cleaned, rate=RATE):
    """Energy loss proposes short gaps; it does not identify a lead singer."""
    if len(reference) != len(cleaned) or not len(cleaned):
        raise ValueError('Onarım için giriş süreleri eşleşmiyor.')
    hop = max(1, round(rate * .01))
    window = max(1, round(rate * .05))
    ref = np.sqrt(np.maximum(uniform_filter1d(reference.astype('float64')**2, window)[::hop], 1e-12))
    proc = np.sqrt(np.maximum(uniform_filter1d(cleaned.astype('float64')**2, window)[::hop], 1e-12))
    active = ref > max(.025, float(np.percentile(ref, 90)) * .15)
    loss = 20 * np.log10(proc / ref) < -8
    groups, count = label(binary_closing(active & loss, structure=np.ones(3)))
    intervals, skipped = [], 0
    duration = len(cleaned) / rate
    for index in range(1, count + 1):
        ids = np.flatnonzero(groups == index)
        a, b = ids[0] * hop / rate, (ids[-1] + 1) * hop / rate
        if b - a >= .8:
            skipped += 1
        elif .04 - 1e-8 <= b-a and .04 < a < b < duration-.04:
            if intervals and a-intervals[-1][1] < .08 and b-intervals[-1][0] < .95:
                intervals[-1][1] = float(b)
            else:
                intervals.append([float(a), float(b)])
    return intervals, skipped


def splice_patch(base, generated, start, end, rate=RATE):
    """Preserve all samples outside a 35 ms collar; fade the outer 15 ms."""
    if generated.shape != base.shape or not np.isfinite(generated).all():
        raise ValueError('Modelin ürettiği onarım sesi geçersiz.')
    left = max(0, round((start-.035)*rate))
    right = min(len(base), round((end+.035)*rate))
    if not 0 <= left < right <= len(base):
        raise ValueError('Vokal onarım aralığı geçersiz.')
    weight = np.ones(right-left, dtype='float64')
    size = min(round(.015*rate), len(weight)//2)
    if size:
        ramp = .5-.5*np.cos(np.linspace(0, np.pi, size))
        weight[:size], weight[-size:] = ramp, ramp[::-1]
    result = base.copy()
    result[left:right] += weight*(generated[left:right]-base[left:right])
    return result, (left, right)


def attenuation_limit(reference, generated):
    """Cap excessive synthesis levels without amplifying a noise floor."""
    def rms(x):
        return float(np.sqrt(np.mean(x.astype('float64')**2)))
    return min(1., max(.01, rms(reference))/max(1e-9, rms(generated)),
               max(.05, 1.1*float(np.abs(reference).max()))/max(1e-9, float(np.abs(generated).max())))
