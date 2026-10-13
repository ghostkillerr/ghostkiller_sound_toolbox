"""Recover upstream notices/source for the existing Gyan FFmpeg 8.1.1 build.

Writes only under build/ffmpeg_material. Original EXEs are not changed, no
installer is run and no claim about unprovided linked-library sources is made.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import tarfile
import urllib.request
import zipfile
from tools.release.preflight import ROOT, sha256

RELEASE_URL = 'https://github.com/GyanD/codexffmpeg/releases/tag/8.1.1'
BINARY_ARCHIVE = 'https://github.com/GyanD/codexffmpeg/releases/download/8.1.1/ffmpeg-8.1.1-full_build.zip'
BINARY_SHA256 = '49b28c5f16addd40239a66949973458769b7056fb7752c30ac0d53389d09a552'
SOURCE_COMMIT = '239f2c733d'


def download(url, target, digest=None):
    checksum = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Ghostkiller-Release-Audit'}), timeout=30) as response, target.open('wb') as stream:
        for block in iter(lambda: response.read(1024 * 1024), b''):
            checksum.update(block)
            stream.write(block)
    if digest and checksum.hexdigest() != digest:
        target.unlink()
        raise ValueError('Upstream archive SHA-256 mismatch.')
    return checksum.hexdigest()


def asset(path, output, **extra):
    return {'path': path.relative_to(output).as_posix(), 'sha256': sha256(path), **extra}


def main():
    binary_root = ROOT / 'tools' / 'ffmpeg'
    output = ROOT / 'build' / 'ffmpeg_material' / '8.1.1'
    output.mkdir(parents=True, exist_ok=True)
    print('Checking exact upstream binary archive.', flush=True)
    archive_path = output / 'upstream-full-build.zip'
    download(BINARY_ARCHIVE, archive_path, BINARY_SHA256)
    licenses = []
    with zipfile.ZipFile(archive_path) as archive:
        for filename in ('ffmpeg.exe', 'ffprobe.exe'):
            members = [name for name in archive.namelist() if name.endswith('/bin/' + filename)]
            if len(members) != 1:
                raise ValueError('Expected native binary absent from upstream archive.')
            digest = hashlib.sha256()
            with archive.open(members[0]) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            if sha256(binary_root / filename) != digest.hexdigest():
                raise ValueError(f'Local {filename} does not match the exact official 8.1.1 build.')
            shutil.copyfile(binary_root / filename, output / filename)
        for item in archive.infolist():
            name = Path(item.filename).name
            if not item.is_dir() and name.lower().startswith(('license', 'licence', 'copying', 'readme', 'notice')):
                target = output / 'licenses' / name
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(archive.read(item))
                licenses.append(asset(target, output, source=BINARY_ARCHIVE))
    archive_path.unlink()
    print('Binary provenance matched. Fetching pinned FFmpeg source.', flush=True)
    request = urllib.request.Request(f'https://api.github.com/repos/FFmpeg/FFmpeg/commits/{SOURCE_COMMIT}', headers={'User-Agent': 'Ghostkiller-Release-Audit'})
    with urllib.request.urlopen(request, timeout=30) as response:
        commit = json.load(response)['sha']
    source_url = f'https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/{commit}'
    source_path = output / 'sources' / f'ffmpeg-{commit}.tar.gz'
    source_path.parent.mkdir(exist_ok=True)
    download(source_url, source_path)
    with tarfile.open(source_path) as archive:
        for member in archive.getmembers():
            name = Path(member.name).name
            if member.isfile() and name.startswith(('COPYING.', 'LICENSE')) and member.name.count('/') == 1:
                target = output / 'licenses' / name
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
                licenses.append(asset(target, output, source=source_url))
    actual = subprocess.run([str(binary_root / 'ffmpeg.exe'), '-version'], capture_output=True,
                            text=True, check=True, timeout=15).stdout
    configure = next(line.removeprefix('configuration: ') for line in actual.splitlines() if line.startswith('configuration: '))
    recipe = output / 'build_recipe.txt'
    recipe.write_text(f'Upstream binary: {BINARY_ARCHIVE}\nUpstream release/source: {RELEASE_URL}\nFFmpeg source commit: {commit}\n\n{actual}\n'
                      'The external libraries are enabled by the configure flags above. Their exact patched sources/build scripts were not provided in the binary archive.\n', encoding='utf-8')
    notice = output / 'NOTICE.md'
    notice.write_text('# FFmpeg 8.1.1 distribution material\n\n'
                      f'Existing EXEs were byte-for-byte matched to {BINARY_ARCHIVE} (SHA-256 {BINARY_SHA256}).\n\n'
                      f'The upstream release identifies FFmpeg commit {commit}. Its source archive and original license texts are included here.\n\n'
                      'The full build uses GPLv3 and many separately licensed linked libraries. This bundle currently includes FFmpeg source only; exact dependency source/build material is still required before redistribution. The release preflight refuses incomplete source material.\n', encoding='utf-8')
    manifest = {'version': '8.1.1', 'license': 'GPL-3.0-or-later',
                'configure': configure, 'source_completeness': 'ffmpeg-only',
                'upstream_release': RELEASE_URL, 'source_commit': commit,
                'binary_provenance': {'url': BINARY_ARCHIVE, 'sha256': BINARY_SHA256},
                'binaries': [{'path': filename, 'sha256': sha256(binary_root / filename)} for filename in ('ffmpeg.exe', 'ffprobe.exe')],
                'licenses': licenses, 'sources': [asset(source_path, output, source=source_url)],
                'build_recipes': [asset(recipe, output), asset(notice, output)]}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Recovered verified binary provenance, license texts and exact FFmpeg source. Linked dependency source material remains incomplete.', flush=True)


if __name__ == '__main__':
    main()
