import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from tools.ci_prepare_ffmpeg import prepare

ROOT=Path(__file__).resolve().parents[1]


class CICodecPreparationTests(unittest.TestCase):
    def test_hash_and_ambiguous_members_preserve_existing_codecs(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root=Path(temporary);target=root/'tools';target.mkdir()
            (target/'ffmpeg.exe').write_bytes(b'original')
            archive=root/'fixture.zip'
            with zipfile.ZipFile(archive,'w') as source:
                source.writestr('one/bin/ffmpeg.exe',b'one')
                source.writestr('two/bin/ffmpeg.exe',b'two')
                source.writestr('one/bin/ffprobe.exe',b'probe')
            with self.assertRaisesRegex(ValueError,'SHA-256'):
                prepare(archive,target)
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            with patch('tools.ci_prepare_ffmpeg.BINARY_SHA256',digest):
                with self.assertRaisesRegex(ValueError,'ambiguous'):
                    prepare(archive,target)
            self.assertEqual((target/'ffmpeg.exe').read_bytes(),b'original')

    def test_only_exact_codec_members_are_extracted_into_owned_filenames(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root=Path(temporary);archive=root/'fixture.zip'
            with zipfile.ZipFile(archive,'w') as source:
                source.writestr('pinned/bin/ffmpeg.exe',b'mpeg')
                source.writestr('pinned/bin/ffprobe.exe',b'probe')
                source.writestr('../../untrusted.txt',b'excluded')
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            with patch('tools.ci_prepare_ffmpeg.BINARY_SHA256',digest):
                prepare(archive,root/'tools')
            self.assertEqual({p.name for p in (root/'tools').iterdir()},{'ffmpeg.exe','ffprobe.exe'})
