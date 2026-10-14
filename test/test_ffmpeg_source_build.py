"""Corresponding sources must cover every explicitly enabled external library."""
import unittest
from tools.release.preflight import validate_ffmpeg_sources


class FFmpegSourceTests(unittest.TestCase):
    def fixture(self):
        return {'configure':'--disable-autodetect --enable-libsoxr',
                'sources':[{'path':'ffmpeg.tar.gz'},{'path':'soxr.tar.gz'}],
                'source_components':{'ffmpeg':['ffmpeg.tar.gz'],'libsoxr':['soxr.tar.gz']}}

    def test_label_does_not_replace_library_source_inventory(self):
        manifest=self.fixture()
        validate_ffmpeg_sources(manifest)
        del manifest['source_components']['libsoxr']
        with self.assertRaisesRegex(ValueError,'libsoxr'):
            validate_ffmpeg_sources(manifest)

    def test_enabling_another_external_library_requires_its_sources(self):
        manifest=self.fixture()
        manifest['configure']+=' --enable-libmp3lame --enable-zlib'
        with self.assertRaisesRegex(ValueError,'libmp3lame'):
            validate_ffmpeg_sources(manifest)
        manifest['source_components']['libmp3lame']=['missing-source.tar.gz']
        with self.assertRaisesRegex(ValueError,'libmp3lame'):
            validate_ffmpeg_sources(manifest)
        manifest['sources'].append({'path':'lame.tar.gz'})
        manifest['source_components']['libmp3lame']=['lame.tar.gz']
        with self.assertRaisesRegex(ValueError,'zlib'):
            validate_ffmpeg_sources(manifest)


if __name__=='__main__':
    unittest.main()
