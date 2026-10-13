"""Bounded pitch statistics over extracted frames; not a voice quality score."""
import numpy as np


class PitchSummary:
    def __init__(self):
        self.frames = self.voiced = self.outside = 0
        self.minimum = self.maximum = None
        # Fixed bins bound memory independently of recording duration.
        self.histogram = np.zeros(2400,dtype=np.int64)

    def add(self, f0):
        values = np.asarray(f0,dtype=np.float64)
        if not np.isfinite(values).all() or np.any(values<0):
            raise ValueError("Perde analizi geçersiz değer içeriyor.")
        self.frames += values.size
        voiced = values[values>0]
        self.voiced += voiced.size
        if not voiced.size: return
        self.outside += int(np.count_nonzero((voiced<50)|(voiced>1100)))
        minimum,maximum = float(voiced.min()),float(voiced.max())
        self.minimum = minimum if self.minimum is None else min(minimum,self.minimum)
        self.maximum = maximum if self.maximum is None else max(maximum,self.maximum)
        # 0.1 MIDI-note bins; tails clamp for statistics only, never modify training F0.
        notes = 69+12*np.log2(voiced/440)
        bins = np.clip(np.floor((notes+60)*10).astype(np.int64),0,2399)
        self.histogram += np.bincount(bins,minlength=2400)

    def percentile(self, fraction):
        if not self.voiced: return None
        bin_index = int(np.searchsorted(np.cumsum(self.histogram),max(1,self.voiced*fraction)))
        note = (bin_index+.5)/10-60
        return float(440*2**((note-69)/12))

    def result(self):
        return dict(frames=self.frames,voiced_frames=self.voiced,
                    voiced_fraction=self.voiced/max(1,self.frames),
                    out_of_range_fraction=self.outside/max(1,self.voiced),
                    minimum_hz=self.minimum,maximum_hz=self.maximum,
                    p05_hz=self.percentile(.05),median_hz=self.percentile(.5),p95_hz=self.percentile(.95),
                    histogram=self.histogram.tolist(),histogram_midi_origin=-60,histogram_midi_width=.1,
                    processed_voiced_seconds=self.voiced*.01,
                    note="Örtüşen hazırlama parçalarındaki F0 çerçeveleri; süre benzersiz sesli dakika değildir. Yüzdelikler 0.1 MIDI-notalık histogramdan yaklaşık hesaplanır; sıfır F0 nefes/ünsüz olabileceğinden silinmez.")
