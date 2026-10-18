"""Noise-only auto setup, lifecycle and speech gate regression tests."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from live_audio import AudioDevice, RATE
from live_gate import (NoiseGate, NoiseMeasurement, CalibrationOptions, calibrate_gate,
                       FRAME, CALIBRATION_SECONDS, HOLD_MS, RELEASE_MS)


def noise(db, seconds=10):
    # Constant per-frame RMS with no DC component and reproducible levels.
    wave = np.sin(np.arange(RATE*seconds)*2*np.pi*1000/RATE)
    return (wave*10**(db/20)*np.sqrt(2)).astype('float32')


class MeasurementTests(unittest.TestCase):
    def measure(self, samples, size=997):
        measurement = NoiseMeasurement()
        for start in range(0, len(samples), size):
            measurement.feed(samples[start:start+size])
        self.assertEqual(measurement.frames, 10*RATE)
        self.assertEqual(len(measurement.levels), 1000)
        self.assertLess(len(measurement.pending), FRAME)
        return measurement.result()

    def test_noise_floor_sets_both_thresholds_and_is_chunk_independent(self):
        for floor in (-200, -100, -85, -70, -55, -40, -30):
            with self.subTest(floor=floor):
                result = self.measure(noise(floor))
                self.assertAlmostEqual(result['noise_db'], floor, places=1)
                self.assertLessEqual(abs(result['threshold_db']-(floor+10)), 1)
                self.assertEqual(result['close_db'], result['threshold_db']-6)
                self.assertEqual(result, self.measure(noise(floor), size=960))

    def test_isolated_loud_click_does_not_raise_the_room_floor(self):
        samples = noise(-60)
        samples[3*RATE:3*RATE+FRAME*2] = .3
        self.assertAlmostEqual(self.measure(samples)['noise_db'], -60, places=1)

    def test_speech_during_measurement_rejects_instead_of_cutting_off_the_voice(self):
        samples = noise(-60)
        samples[3*RATE:5*RATE] = noise(-28, 2)
        with self.assertRaisesRegex(ValueError, 'konuşma|değişken'):
            self.measure(samples)

    def test_muted_clipped_and_excessively_noisy_input_never_make_a_profile(self):
        for samples, expected in ((np.zeros(RATE*10), 'sinyali'),
                                  (noise(-20), 'çok yüksek'),
                                  (np.ones(RATE*10), 'çok yüksek')):
            with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, expected):
                self.measure(samples)

    def test_incomplete_and_invalid_samples_are_rejected(self):
        measurement = NoiseMeasurement()
        with self.assertRaisesRegex(ValueError, 'tamamlanmadı'):
            measurement.result()
        for samples in (np.zeros((2, 2)), np.array([np.nan]), np.array([np.inf]),
                        np.array([1.1]), np.zeros(RATE+1), np.array([])):
            with self.subTest(samples=samples.shape), self.assertRaises(ValueError):
                measurement.feed(samples)

    def test_measurement_is_bounded_even_if_last_driver_chunk_is_long(self):
        samples = noise(-60, 11)
        result = self.measure(samples, size=48000)
        self.assertEqual(result['seconds'], 10)


class CalibrationLifecycleTests(unittest.TestCase):
    def test_packaged_live_smoke_never_opens_physical_audio(self):
        from release_self_test import check_live_gate
        with patch('live_gate.WaveInput', side_effect=AssertionError('physical capture')), \
             patch('live_audio.WaveOutput', side_effect=AssertionError('physical playback')):
            result = check_live_gate()
        self.assertTrue(result['input_closed'])
        self.assertFalse(result['microphone_opened'])
        self.assertFalse(result['output_opened'])

    def exercise(self, *, invalid=False, failure=None):
        state = SimpleNamespace(reads=0, closed=False, notices=[], cancelled=False)
        samples = noise(-55)
        class Input:
            actual_device = AudioDevice(4, 'Test microphone')
            def __enter__(self): return self
            def __exit__(self, *_): state.closed = True
            def read(self, stopped):
                self.assert_open = not state.closed
                if failure == 'read': raise OSError('unplugged')
                if failure == 'cancel': state.cancelled = True
                if stopped(): raise InterruptedError()
                start = state.reads*960
                state.reads += 1
                return np.zeros(960) if invalid else samples[start:start+960]
        def progress(message):
            state.notices.append(message)
            if failure == 'progress': raise RuntimeError('progress failed')
        factory = Mock(return_value=Input())
        result = calibrate_gate(CalibrationOptions(4, 'Test microphone'),
            input_factory=factory, cancelled=lambda: state.cancelled,
            progress=progress, clock=lambda: 0)
        return result, state, factory

    def test_exact_ten_seconds_closes_input_before_return_without_output_or_model(self):
        with patch('live_audio.WaveOutput', side_effect=AssertionError('no output')), \
             patch('live_cover.LiveRVC', side_effect=AssertionError('no model')):
            result, state, factory = self.exercise()
        self.assertTrue(state.closed)
        self.assertEqual(state.reads, 500)
        factory.assert_called_once_with(4)
        self.assertEqual((result['input_device'], result['input_name']), (4, 'Test microphone'))
        self.assertEqual(sum(text.startswith('Mikrofon açıldı.') for text in state.notices), 1)
        self.assertEqual(len(state.notices), 11)
        self.assertIn('10 saniye', state.notices[1])
        self.assertIn('1 saniye', state.notices[-1])
        self.assertFalse(any('Ayarlandı' in text for text in state.notices))

    def test_cancel_before_start_does_not_open_microphone(self):
        factory = Mock()
        with self.assertRaises(InterruptedError):
            calibrate_gate(CalibrationOptions(), cancelled=lambda: True, input_factory=factory)
        factory.assert_not_called()

    def test_native_factory_uses_name_and_id_verification(self):
        with patch('live_gate.WaveInput') as factory:
            factory.return_value.__enter__.side_effect = OSError('stop before recording')
            with self.assertRaises(OSError):
                calibrate_gate(CalibrationOptions(4, 'Selected microphone'))
            factory.assert_called_once_with(4, expected_name='Selected microphone')

    def test_read_progress_cancel_and_invalid_measurement_all_close_microphone(self):
        for failure, invalid in (('read', False), ('progress', False), ('cancel', False), (None, True)):
            with self.subTest(failure=failure, invalid=invalid):
                closed = []
                class Input:
                    def __enter__(self): return self
                    def __exit__(self, *_): closed.append(True)
                    def read(self, stopped):
                        if failure == 'read': raise OSError('unplugged')
                        if failure == 'cancel': raise InterruptedError()
                        return np.zeros(960)
                def progress(message):
                    if failure == 'progress': raise RuntimeError('progress failed')
                with self.assertRaises((OSError, RuntimeError, InterruptedError, ValueError)):
                    calibrate_gate(CalibrationOptions(), input_factory=lambda device: Input(),
                                   progress=progress, clock=lambda: 0)
                self.assertEqual(closed, [True])

    def test_stalled_microphone_has_a_deadline_and_closes(self):
        clock = Mock(side_effect=[0, 14])
        source = Mock()
        source.__enter__ = Mock(return_value=source)
        source.__exit__ = Mock(return_value=False)
        with self.assertRaises(TimeoutError):
            calibrate_gate(CalibrationOptions(), input_factory=lambda device: source, clock=clock)
        source.__exit__.assert_called_once()
        source.read.assert_not_called()

    def test_invalid_options_do_not_open_microphone(self):
        for values in ({'input_device': True}, {'input_device': -2}, {'input_name': None}):
            factory = Mock()
            with self.assertRaises(ValueError):
                calibrate_gate(CalibrationOptions(**values), input_factory=factory)
            factory.assert_not_called()


class GateEnvelopeTests(unittest.TestCase):
    def test_unbounded_low_threshold_opens_for_real_signal_but_never_zero_underflow(self):
        for threshold in (-81, -120, -1000, -1e300):
            with self.subTest(threshold=threshold):
                gate = NoiseGate(True, threshold)
                self.assertFalse(gate.process(np.zeros(FRAME))[1])
                self.assertTrue(gate.process(np.full(FRAME, .001))[1])
                gate.process(np.zeros(RATE))
                self.assertFalse(gate.process(np.zeros(FRAME))[1])

    def test_hysteresis_keeps_soft_syllables_open_and_requires_full_open_threshold_again(self):
        gate = NoiseGate(True, -40)
        gate.process(noise(-35, 1))
        middle = noise(-44, 1)
        self.assertTrue(gate.process(middle)[1])
        self.assertTrue(gate.open)
        gate.process(noise(-65, 1))
        self.assertFalse(gate.open)
        self.assertFalse(gate.process(middle)[1])
        self.assertTrue(gate.process(noise(-38, 1))[1])

    def test_hold_and_release_preserve_word_ends_then_reach_exact_digital_silence(self):
        gate = NoiseGate(True, -40)
        gate.process(np.full(FRAME, .1))
        gate.process(np.full(round(RATE*HOLD_MS/1000), .0001))
        np.testing.assert_array_equal(gate.last_mask, 1)
        gate.process(np.full(round(RATE*RELEASE_MS/1000)+FRAME*2, .0001))
        mask = gate.last_mask
        self.assertTrue(np.all(np.diff(mask) <= 0))
        self.assertLess(np.max(np.abs(np.diff(mask))), .001)
        self.assertEqual(mask[-1], 0)
        self.assertFalse(gate.process(np.full(FRAME, .0001))[1])

    def test_zero_input_is_still_released_instead_of_leaving_a_held_model_tail(self):
        gate = NoiseGate(True, -40)
        gate.process(np.full(FRAME, .1))
        self.assertTrue(gate.process(np.zeros(FRAME))[1])
        self.assertTrue(gate.process(np.zeros(RATE))[1])  # release mask exists in this block
        self.assertFalse(gate.process(np.zeros(FRAME))[1])


if __name__ == '__main__':
    unittest.main()
