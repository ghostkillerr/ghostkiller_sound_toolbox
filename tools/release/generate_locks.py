"""Generate hash-locked Windows/Python 3.12 manifests from reviewed versions.

Reads package metadata only. Does not install or upgrade the current environment.
Changing requirements/versions.json is a reviewable dependency update.
"""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import urllib.request
from urllib.parse import urljoin, urlsplit, parse_qs, unquote

ROOT = Path(__file__).resolve().parents[2]
XPU_VERSIONS = {
    'intel-cmplr-lib-rt': '2025.3.2', 'intel-cmplr-lib-ur': '2025.3.2',
    'intel-cmplr-lic-rt': '2025.3.2', 'intel-sycl-rt': '2025.3.2',
    'onemkl-license': '2025.3.1', 'onemkl-sycl-blas': '2025.3.1',
    'onemkl-sycl-dft': '2025.3.1', 'onemkl-sycl-lapack': '2025.3.1',
    'onemkl-sycl-rng': '2025.3.1', 'onemkl-sycl-sparse': '2025.3.1',
    'dpcpp-cpp-rt': '2025.3.2', 'intel-opencl-rt': '2025.3.2',
    'mkl': '2025.3.1', 'intel-openmp': '2025.3.2', 'tbb': '2022.3.1',
    'tcmlib': '1.4.1', 'umf': '1.0.3', 'intel-pti': '0.16.0',
    'triton-xpu': '3.7.0',
}


def read_json(url):
    with urllib.request.urlopen(url, timeout=30) as stream:
        return json.load(stream)


def pypi_line(item):
    name, version = item
    record = read_json(f'https://pypi.org/pypi/{name}/{version}/json')
    hashes = sorted({entry['digests']['sha256'] for entry in record['urls']})
    if not hashes:
        raise ValueError(f'No published files for {name}=={version}')
    return f'{name}=={version} \\\n' + ' \\\n'.join(f'    --hash=sha256:{digest}' for digest in hashes) + '\n'


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.urls.extend(value for key, value in attrs if key == 'href')


def pytorch_line(name, version, index):
    base = f'https://download.pytorch.org/whl/{index}/{name}/'
    with urllib.request.urlopen(base, timeout=30) as stream:
        parser = Links()
        parser.feed(stream.read().decode('utf-8'))
    prefix = f'{name.replace("-", "_")}-{version}-'
    matches = []
    for link in parser.urls:
        url = urljoin(base, link)
        filename = unquote(urlsplit(url).path.rsplit('/', 1)[-1])
        if filename.startswith(prefix) and filename.endswith('.whl') and (
            'cp312-cp312-win_amd64' in filename or filename.endswith('py3-none-win_amd64.whl')
            or filename.endswith('py2.py3-none-win_amd64.whl') or filename.endswith('py3-none-any.whl')
        ):
            matches.append(url)
    if len(matches) != 1:
        raise ValueError(f'Expected one Python 3.12 Windows wheel: {name} {version}, found {len(matches)}')
    # The official index also lists the R2 mirror, which can reject requests in
    # some regions. Its paths and checksums are shared by the primary origin.
    selected = urlsplit(matches[0])
    if selected.netloc == 'download-r2.pytorch.org':
        matches[0] = selected._replace(netloc='download.pytorch.org').geturl()
    digest = parse_qs(urlsplit(matches[0]).fragment).get('sha256', [])
    if len(digest) != 1:
        # Some official XPU indexes omit hashes. Hash the HTTPS bytes; never
        # substitute a placeholder or trust an ETag as a SHA-256 value.
        print(f'Hashing official wheel: {name} {version}', flush=True)
        checksum = hashlib.sha256()
        count = 0
        with urllib.request.urlopen(matches[0], timeout=30) as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                count += len(chunk)
                if count > 4 * 1024 ** 3:
                    raise ValueError(f'Unexpectedly large wheel: {name}')
                checksum.update(chunk)
        digest = [checksum.hexdigest()]
    return f'{name} @ {matches[0].split("#")[0]} \\\n    --hash=sha256:{digest[0]}\n'


def main():
    folder = ROOT / 'requirements'
    versions = json.loads((folder / 'versions.json').read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=6) as workers:
        common = ''.join(workers.map(pypi_line, sorted(versions.items())))
    (folder / 'common.lock').write_text('# Reviewed Windows x64 / CPython 3.12 dependency graph.\n' + common, encoding='utf-8')
    for backend, index, suffix in [('cpu', 'cpu', '+cpu'), ('cuda', 'cu128', '+cu128'), ('xpu', 'xpu', '+xpu')]:
        lines = ['# Install in a separate environment; do not overlay another backend.\n', '-r common.lock\n']
        for name, version in [('torch', '2.11.0'), ('torchvision', '0.26.0'), ('torchaudio', '2.11.0')]:
            lines.append(pytorch_line(name, version + suffix, index))
        lines.append(pypi_line(('onnxruntime-gpu' if backend == 'cuda' else 'onnxruntime',
                                '1.26.0' if backend == 'cuda' else '1.29.0')))
        if backend == 'xpu':
            for name, version in sorted(XPU_VERSIONS.items()):
                if name == 'triton-xpu':
                    lines.append(pytorch_line(name, version, index))
                else:
                    lines.append(pypi_line((name, version)))
        (folder / f'{backend}.lock').write_text(''.join(lines), encoding='utf-8')
    bootstrap = [('pip', '23.2.1'), ('setuptools', '70.2.0'), ('wheel', '0.45.1'), ('cmake', '3.31.6'), ('cython', '3.2.5')]
    (folder / 'bootstrap.lock').write_text(''.join(pypi_line(item) for item in bootstrap), encoding='utf-8')
    print('Generated hash locks for CPU, CUDA 12.8 and XPU. No packages installed.')


if __name__ == '__main__':
    main()
