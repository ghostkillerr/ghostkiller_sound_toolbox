"""Live monitoring contracts without opening any physical microphone/speaker."""
import ctypes as C
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from live_audio import (AudioDevice, InputCaps, WaveFormat, WaveHeader, WaveInput,
                        WaveOutput, WHDR_DONE, WHDR_PREPARED)
from live_cover import LiveOptions, LiveWindow, LatestBlocks, RATE, run_live, LiveRVC, NoiseGate

ROOT = Path(__file__).resolve().parents[1]


class FakeWinMM:
    def __init__(self):
        self.calls = []
        self.headers = {'In': [], 'Out': []}
        self.identities = {'In': 0, 'Out': 0}

    def __getattr__(self, name):
        def call(*args):
            self.calls.append(name)
            direction = 'In' if name.startswith('waveIn') else 'Out'
            if name.endswith('Open'):
                args[0]._obj.value = 100 if direction == 'In' else 200
                self.identities[direction] = args[1] if args[1] != 0xffffffff else 0
            elif name.endswith('GetID'):
                args[1]._obj.value = self.identities[direction]
            elif name.endswith('GetDevCapsW'):
                args[1]._obj.name = f'Test {direction} {args[0]}'
                args[1]._obj.channels = 2
            elif name.endswith('PrepareHeader') and not name.endswith('UnprepareHeader'):
                header = args[1]._obj
                header.flags |= WHDR_PREPARED
                self.headers[direction].append(header)
            elif name.endswith('AddBuffer'):
                header = args[1]._obj
                C.memset(header.data, 1, header.length)
                header.recorded = header.length
                header.flags |= WHDR_DONE
            elif name.endswith('Reset'):
                for header in self.headers[direction]:
                    header.flags |= WHDR_DONE
            elif name.endswith('UnprepareHeader'):
                args[1]._obj.flags &= ~WHDR_PREPARED
            return 0
        return call


class NativeLiveAudioTests(unittest.TestCase):
    def test_windows_abi_and_owned_capture_buffer_lifetime(self):
        self.assertEqual(C.sizeof(WaveFormat), 18)
        self.assertEqual(C.sizeof(WaveHeader), 48)
        api = FakeWinMM()
        source = WaveInput(2, api=api)
        self.assertEqual(len(source.buffers), 8)
        data = source.read(lambda: False)
        self.assertEqual(data.shape, (960,))
        self.assertEqual(data.dtype, np.dtype('float32'))
        np.testing.assert_allclose(data, 257/32768)
        source.close()
        self.assertFalse(source.handle)
        self.assertLess(api.calls.index('waveInReset'), api.calls.index('waveInUnprepareHeader'))
        self.assertEqual(api.calls[-1], 'waveInClose')
        before = list(api.calls)
        source.close()
        self.assertEqual(api.calls, before)

    def test_capture_wait_obeys_stop_without_reusing_a_driver_buffer(self):
        api = FakeWinMM()
        with WaveInput(api=api) as source:
            source.buffers[0].header.flags &= ~WHDR_DONE
            with self.assertRaises(InterruptedError):
                source.read(lambda: True)

    def test_playback_has_stereo_frames_bounded_queue_and_reset_before_free(self):
        api = FakeWinMM()
        with WaveOutput(3, api=api) as output:
            output.write(np.full(RATE, .25, dtype='float32'))
            self.assertEqual(output.queued_frames(), RATE)
            raw = np.frombuffer(output.buffers[0].memory, dtype='<i2', count=RATE*2).reshape(-1, 2)
            np.testing.assert_array_equal(raw, np.full((RATE, 2), 8192, dtype='int16'))
            output.write(np.zeros(RATE, dtype='float32'))
            with self.assertRaisesRegex(RuntimeError, 'kuyruğu'):
                output.write(np.ones(1, dtype='float32'))
            output.clear()
            self.assertEqual(output.queued_frames(), 0)
            for invalid in (np.array([np.nan]), np.zeros((10, 2)), np.zeros(RATE+1)):
                with self.assertRaises(ValueError):
                    output.write(invalid)
        self.assertEqual(api.calls[-1], 'waveOutClose')

    def test_device_enumeration_never_opens_streams(self):
        import live_audio
        api = FakeWinMM()
        def caps(identity, output, size):
            output._obj.name = 'Test aygıtı'
            output._obj.channels = 2
            return 0
        api.waveInGetNumDevs = lambda: 1
        api.waveOutGetNumDevs = lambda: 1
        api.waveInGetDevCapsW = api.waveOutGetDevCapsW = caps
        with patch.object(live_audio, 'winmm', return_value=api):
            result = live_audio.enumerate_devices()
        self.assertEqual(result['inputs'], [AudioDevice(-1, 'Windows varsayılan aygıtı'), AudioDevice(0, 'Test aygıtı')])
        self.assertNotIn('waveInOpen', api.calls)
        self.assertNotIn('waveOutOpen', api.calls)

    def test_input_prepare_failure_releases_already_prepared_buffers(self):
        api = FakeWinMM()
        prepare = api.waveInPrepareHeader
        def fail(handle, header, size):
            if len(api.headers['In']) == 2:
                raise RuntimeError('synthetic prepare error')
            return prepare(handle, header, size)
        api.waveInPrepareHeader = fail
        with self.assertRaisesRegex(RuntimeError, 'prepare error'):
            WaveInput(api=api)
        self.assertEqual(api.calls.count('waveInUnprepareHeader'), 2)
        self.assertEqual(api.calls[-1], 'waveInClose')

    def test_explicit_output_is_verified_and_cannot_fall_back_to_default(self):
        api = FakeWinMM()
        with WaveOutput(2, api=api, expected_name='Test Out 2') as output:
            self.assertEqual(output.actual_device, AudioDevice(2, 'Test Out 2'))
        api = FakeWinMM()
        api.waveOutGetID = lambda handle, identity: setattr(identity._obj, 'value', 0) or 0
        with self.assertRaisesRegex(RuntimeError, 'başka bir aygıt'):
            WaveOutput(2, api=api)
        self.assertNotIn('waveOutWrite', api.calls)
        self.assertEqual(api.calls[-1], 'waveOutClose')

    def test_changed_device_name_is_rejected_before_microphone_start(self):
        api = FakeWinMM()
        with self.assertRaisesRegex(RuntimeError, 'listesi değişti'):
            WaveInput(2, api=api, expected_name='Disconnected microphone')
        self.assertNotIn('waveInOpen', api.calls)
        self.assertNotIn('waveInStart', api.calls)


class LiveCoreTests(unittest.TestCase):
    def test_options_validate_devices_numbers_and_missing_index(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'model.pth'
            path.touch()
            options = LiveOptions(str(path))
            options.validate()
            for values in ({'pitch': True}, {'pitch': 25}, {'input_device': -2},
                           {'output_device': True}, {'index_rate': float('nan')},
                           {'gain': float('inf')}, {'gain': 0}, {'f0_method': 'unknown'},
                           {'block_seconds': .01}, {'block_seconds': True},
                           {'gate_enabled': 1}, {'gate_db': float('nan')}, {'gate_db': 1}):
                with self.subTest(values=values), self.assertRaises(ValueError):
                    replace(options, **values).validate()
            with self.assertRaises(FileNotFoundError):
                replace(options, index_path=str(Path(folder)/'missing.index')).validate()

    def test_window_crossfades_same_samples_without_duration_growth(self):
        frames = RATE//4
        window = LiveWindow(frames)
        values = np.sin(np.arange(frames*4, dtype='float32')*.01)*.2
        actual = np.concatenate([window.process(values[i:i+frames], lambda audio: audio.copy())
                                 for i in range(0, len(values), frames)])
        self.assertEqual(len(actual), len(values)-window.overlap)
        np.testing.assert_allclose(actual[window.overlap:], values[window.overlap:len(actual)], atol=2e-8)
        for invalid in (np.full(frames, np.nan), np.zeros(frames+1)):
            with self.assertRaises(ValueError):
                window.process(invalid, lambda audio: audio)
        with self.assertRaises(ValueError):
            window.process(np.zeros(frames), lambda audio: np.full(len(audio), np.inf))

    def test_backlog_only_retains_latest_two_blocks(self):
        blocks = LatestBlocks()
        for number in range(100):
            blocks.put(number)
        self.assertEqual(blocks.dropped, 98)
        self.assertEqual([blocks.queue.get_nowait(), blocks.queue.get_nowait()], [98, 99])

    def test_gate_silences_background_and_opens_for_quiet_speech_frames(self):
        gate = NoiseGate(True, -40)
        noise = np.full(RATE//2, .0005, dtype='float32')
        gated, active, db = gate.process(noise)
        self.assertFalse(active)
        self.assertLess(db, -60)
        np.testing.assert_array_equal(gated, 0)
        np.testing.assert_array_equal(gate.last_mask, 0)
        voice = noise.copy()
        voice[RATE//4:RATE//4+RATE//50] = .1
        gated, active, _ = gate.process(voice)
        self.assertTrue(active)
        self.assertGreater(np.max(gated), .09)
        self.assertLessEqual(np.max(np.abs(np.diff(gated))), .1)
        gate.process(noise)
        gated, active, _ = gate.process(noise)
        self.assertFalse(active)
        np.testing.assert_array_equal(gated, 0)

    def test_gate_can_be_disabled_or_reconfigured_without_model_reload(self):
        samples = np.full(4800, .0005, dtype='float32')
        gate = NoiseGate(True, -40)
        self.assertFalse(gate.process(samples)[1])
        self.assertTrue(gate.configure(True, -70))
        self.assertTrue(gate.process(samples)[1])
        gate.configure(False, -40)
        np.testing.assert_array_equal(gate.process(samples)[0], samples)

    def exercise_session(self, folder, failure=None, slow=False, progress_error=False, silent=False, gate_updates=False):
        stopped = threading.Event()
        state = SimpleNamespace(opened=[], closed=[], writes=[], converters=0, conversions=0, warmup=False)
        model = Path(folder)/'model.pth'
        model.touch()
        options = LiveOptions(str(model), block_seconds=.25)
        live_controls = {'enabled': True, 'threshold_db': 0}
        class Converter:
            def __init__(self, options): state.converters += 1
            def warmup(self):
                state.warmup = True
                if failure == 'warmup': raise RuntimeError('synthetic warmup error')
            def convert(self, audio):
                state.conversions += 1
                if failure == 'convert': raise RuntimeError('synthetic conversion error')
                if slow: time.sleep(.025)
                return audio*.25
            def close(self): state.closed.append('converter')
        class Input:
            def __init__(self, device):
                self.device = device
                self.owner = None
            def __enter__(self):
                assert state.warmup
                state.opened.append('input')
                return self
            def read(self, cancel):
                self.owner = threading.current_thread()
                if stopped.wait(.0003): raise InterruptedError()
                return np.full(RATE//4 if slow else 960, .0001 if silent else .4, dtype='float32')
            def __exit__(self, *_):
                assert self.owner is None or not self.owner.is_alive()
                state.closed.append('input')
        class Output:
            def __init__(self, device): pass
            def __enter__(self):
                state.opened.append('output')
                return self
            def queued_frames(self): return 0
            def clear(self): pass
            def write(self, audio):
                state.writes.append(audio)
                if gate_updates and len(state.writes) == 1:
                    live_controls['threshold_db'] = -45
                if len(state.writes) == 3: stopped.set()
            def __exit__(self, *_): state.closed.append('output')
        def progress(message):
            if progress_error and 'Mikrofon açıldı.' in message:
                raise RuntimeError('synthetic progress error')
        result = run_live(options, cancelled=stopped.is_set, progress=progress,
                          converter_factory=Converter, input_factory=Input, output_factory=Output,
                          controls=(lambda: live_controls) if gate_updates else None)
        return result, state

    def test_capture_conversion_playback_and_stop_release_every_resource(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            result, state = self.exercise_session(folder)
        self.assertEqual(state.converters, 1)
        self.assertEqual(state.opened, ['output', 'input'])
        self.assertEqual(state.closed, ['input', 'output', 'converter'])
        self.assertEqual(result['blocks'], 3)
        self.assertTrue(all(len(block) == RATE//4 for block in state.writes))
        np.testing.assert_array_equal(state.writes[0][:RATE//50], 0)
        np.testing.assert_allclose(state.writes[1], .05, atol=1e-7)

    def test_slow_inference_drops_old_audio_instead_of_growing_the_queue(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            result, state = self.exercise_session(folder, slow=True)
        self.assertGreater(result['dropped'], 0)
        self.assertEqual(state.closed, ['input', 'output', 'converter'])

    def test_below_threshold_never_calls_conversion_and_never_passes_dry_audio(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            result, state = self.exercise_session(folder, silent=True)
        self.assertEqual(state.conversions, 0)
        self.assertEqual(result['gated_blocks'], 3)
        for audio in state.writes:
            np.testing.assert_array_equal(audio, 0)
        self.assertEqual(state.closed, ['input', 'output', 'converter'])

    def test_running_gate_threshold_can_reopen_without_reloading_the_model(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            result, state = self.exercise_session(folder, gate_updates=True)
        self.assertEqual(state.converters, 1)
        self.assertEqual(state.conversions, 2)
        self.assertEqual(result['gated_blocks'], 1)
        np.testing.assert_array_equal(state.writes[0], 0)
        np.testing.assert_allclose(state.writes[2], .05, atol=1e-7)

    def test_conversion_or_progress_failure_joins_capture_before_closing(self):
        for kwargs, message in (({'failure': 'convert'}, 'conversion'), ({'progress_error': True}, 'progress')):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory(dir=ROOT) as folder:
                with self.assertRaisesRegex(RuntimeError, message):
                    self.exercise_session(folder, **kwargs)
        self.assertFalse(any(thread.name == 'live-microphone' for thread in threading.enumerate()))

    def test_cancel_before_preparation_never_opens_a_microphone(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'model.pth'
            path.touch()
            factory = Mock()
            with self.assertRaises(InterruptedError):
                run_live(LiveOptions(str(path)), cancelled=lambda: True, converter_factory=factory)
            factory.assert_not_called()

    def test_warmup_failure_closes_model_without_opening_audio_devices(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            path = Path(folder)/'model.pth'
            path.touch()
            converter = Mock()
            converter.warmup.side_effect = RuntimeError('synthetic warmup error')
            capture, playback = Mock(), Mock()
            with self.assertRaisesRegex(RuntimeError, 'warmup error'):
                run_live(LiveOptions(str(path)), converter_factory=lambda options: converter,
                         input_factory=capture, output_factory=playback)
            converter.close.assert_called_once()
            capture.assert_not_called()
            playback.assert_not_called()

    def test_model_helpers_and_index_are_loaded_once_for_multiple_blocks(self):
        converter = Mock()
        converter.version, converter.tgt_sr, converter.use_f0 = 'v2', RATE, 1
        converter.quality_policy.input_highpass_80hz = True
        converter.vc.pipeline.side_effect = lambda **kwargs: np.repeat(kwargs['audio'], 3)
        with patch('rvc.infer.infer.VoiceConverter', return_value=converter), \
             patch('rvc.infer.safe_index.load_index', return_value='validated-index') as load:
            live = LiveRVC(LiveOptions('placeholder.pth', index_path='placeholder.index'))
            for _ in range(2):
                self.assertEqual(len(live.convert(np.ones(RATE, dtype='float32')*.1)), RATE)
            live.close()
        converter.get_vc.assert_called_once_with('placeholder.pth', 0)
        converter.load_hubert.assert_called_once_with('contentvec')
        load.assert_called_once_with('placeholder.index', 768)
        self.assertEqual(converter.vc.pipeline.call_count, 2)
        self.assertEqual(converter.vc.pipeline.call_args.kwargs['retrieval_index'], 'validated-index')
        converter.cleanup_model.assert_called_once()

    def test_partial_speech_block_does_not_play_synthesized_noise_in_its_quiet_tail(self):
        stopped = threading.Event()
        written = []
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            model = Path(folder)/'model.pth'
            model.touch()
            class Converter:
                def __init__(self, options): pass
                def warmup(self): pass
                def convert(self, audio): return np.full_like(audio, .3)
                def close(self): pass
            class Input:
                def __init__(self, device): self.cursor = 0
                def __enter__(self): return self
                def read(self, cancelled):
                    if stopped.wait(.0005): raise InterruptedError()
                    # 100 ms of speech, then low-level microphone noise.
                    chunk = np.full(960, .1 if self.cursor < RATE//10 else .0001, dtype='float32')
                    self.cursor += len(chunk)
                    return chunk
                def __exit__(self, *_): pass
            class Output:
                def __init__(self, device): pass
                def __enter__(self): return self
                def queued_frames(self): return 0
                def clear(self): pass
                def write(self, audio):
                    written.append(audio)
                    stopped.set()
                def __exit__(self, *_): pass
            run_live(LiveOptions(str(model)), cancelled=stopped.is_set, converter_factory=Converter,
                     input_factory=Input, output_factory=Output)
        self.assertGreater(np.max(written[0][:RATE//5]), .1)
        np.testing.assert_array_equal(written[0][-RATE//10:], 0)


if __name__ == '__main__':
    unittest.main()
