"""Copy exact upstream license texts absent from selected wheel metadata."""
import json
from pathlib import Path
import urllib.request
from tools.release.preflight import ROOT, sha256

SOURCES = {
    'cython': ('3.2.5', [('COPYING.txt', 'https://raw.githubusercontent.com/cython/cython/3.2.5/COPYING.txt'),
                          ('LICENSE.txt', 'https://raw.githubusercontent.com/cython/cython/3.2.5/LICENSE.txt')]),
    'samplerate': ('0.1.0', [
        ('LICENSE.rst', 'https://raw.githubusercontent.com/tuxu/python-samplerate/v0.1.0/LICENSE.rst'),
        ('LIBSAMPLERATE_COPYING', 'https://raw.githubusercontent.com/libsndfile/libsamplerate/0.1.9/COPYING'),
    ]),
    'tokenizers': ('0.22.2', [('LICENSE', 'https://raw.githubusercontent.com/huggingface/tokenizers/v0.22.2/LICENSE')]),
    'flatbuffers': ('25.12.19', [('LICENSE', 'https://raw.githubusercontent.com/google/flatbuffers/v25.12.19/LICENSE')]),
}


def main():
    manifest = {}
    for name, (version, items) in SOURCES.items():
        folder = ROOT / 'third_party' / 'python' / name
        folder.mkdir(parents=True, exist_ok=True)
        files = []
        for filename, url in items:
            with urllib.request.urlopen(url, timeout=30) as response:
                text = response.read()
            if len(text) < 100:
                raise ValueError(f'Unexpected license text: {url}')
            path = folder / filename
            path.write_bytes(text)
            files.append({'path': str(path.relative_to(ROOT)).replace('\\', '/'),
                          'sha256': sha256(path), 'source': url})
        manifest[name] = {'version': version, 'files': files}
    (ROOT / 'third_party' / 'python' / 'manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Copied upstream license texts with exact version URLs and SHA-256.')


if __name__ == '__main__':
    main()
