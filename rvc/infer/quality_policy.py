"""Explicit compatibility policy for existing audio and pitch preprocessing."""
from dataclasses import dataclass


@dataclass(frozen=True)
class InferenceQualityPolicy:
    # Preserve the shipped defaults. Disabling them is an explicit A/B option,
    # not a claim of better quality for any voice.
    input_highpass_80hz: bool = True
    pipeline_highpass_48hz: bool = True
    smooth_pitch: bool = True

    def __post_init__(self):
        if any(type(value) is not bool for value in
               (self.input_highpass_80hz, self.pipeline_highpass_48hz, self.smooth_pitch)):
            raise ValueError("Kalite politikası seçenekleri bool olmalıdır.")
