"""The frozen smoke must use real output codecs and clean its own test audio."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from release_self_test import check_audio_exports


class ReleaseAudioSmokeTests(unittest.TestCase):
    def test_all_formats_and_channel_modes_roundtrip_without_leaving_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            report = check_audio_exports(folder)
            combinations = {(item['format'], item['source_channels'], item['mode'])
                            for item in report['roundtrips']}
            self.assertEqual(combinations, {(format, channels, mode)
                for format in ('mp3', 'wav', 'flac', 'ogg')
                for channels in (1, 2) for mode in ('original', 'mono', 'stereo')})
            self.assertTrue(report['numbered_output_preserved'])
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_missing_codec_fails_smoke_and_removes_temporary_audio(self):
        from audio_export import export_audio

        def without_ogg(source, target, output_format, **kwargs):
            if output_format == 'ogg':
                raise RuntimeError('OGG codec unavailable')
            return export_audio(source, target, output_format, **kwargs)

        with tempfile.TemporaryDirectory() as folder, \
                patch('audio_export.export_audio', side_effect=without_ogg):
            with self.assertRaisesRegex(RuntimeError, 'OGG codec unavailable'):
                check_audio_exports(folder)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
