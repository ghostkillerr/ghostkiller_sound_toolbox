import numpy as np
import librosa


def process_audio(audio, sr=16000, silence_thresh=-60, min_silence_len=250):
    """
    Splits an audio signal into segments using a fixed frame size and hop size.

    Parameters:
    - audio (np.ndarray): The audio signal to split.
    - sr (int): The sample rate of the input audio (default is 16000).
    - silence_thresh (int): Silence threshold (default =-60dB)
    - min_silence_len (int): Minimum silence duration (default 250ms).

    Returns:
    - list of np.ndarray: A list of audio segments.
    - np.ndarray: The intervals where the audio was split.
    """
    frame_length = int(min_silence_len / 1000 * sr)
    hop_length = frame_length // 2
    intervals = librosa.effects.split(
        audio, top_db=-silence_thresh, ref=1.0, frame_length=frame_length, hop_length=hop_length
    )
    audio_segments = [audio[start:end] for start, end in intervals]

    return audio_segments, intervals


def merge_audio(audio_segments_org, audio_segments_new, intervals, sr_orig, sr_new, original_length=None):
    """
    Merges audio segments back into a single audio signal, filling gaps with silence.
    Assumes audio segments are already at sr_new.

    Parameters:
    - audio_segments_org (list of np.ndarray): The non-silent audio segments (at sr_orig).
    - audio_segments_new (list of np.ndarray): The non-silent audio segments (at sr_new).
    - intervals (np.ndarray): The intervals used for splitting the original audio.
    - sr_orig (int): The sample rate of the original audio
    - sr_new (int): The sample rate of the model
    Returns:
    - np.ndarray: The merged audio signal with silent gaps restored.
    """
    if len(audio_segments_org) != len(intervals) or len(audio_segments_new) != len(intervals):
        raise ValueError("Ses parçaları ve zaman aralıkları eşleşmiyor.")
    sr_ratio = sr_new / sr_orig
    original_length = original_length if original_length is not None else (int(intervals[-1][1]) if len(intervals) else 0)
    dtype = audio_segments_new[0].dtype if audio_segments_new else np.float32
    merged_audio = np.zeros(round(original_length * sr_ratio), dtype=dtype)
    previous_end = 0
    for segment, (start, end) in zip(audio_segments_new, intervals):
        if start < previous_end or end <= start or end > original_length:
            raise ValueError("Geçersiz veya çakışan ses zaman aralığı.")
        start_new, end_new = round(start * sr_ratio), round(end * sr_ratio)
        length = min(len(segment), end_new - start_new)
        merged_audio[start_new:start_new + length] = segment[:length]
        previous_end = end
    return merged_audio
