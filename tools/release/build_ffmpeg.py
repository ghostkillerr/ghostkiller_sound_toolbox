"""Build the distributable, source-complete Windows x64 FFmpeg/soxr bundle.

Uses a portable w64devkit, never installs a global compiler. Downloads are
separate from the offline build; every input archive is pinned by SHA-256.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from tools.release.fetch_ffmpeg_material import download, asset
from tools.release.preflight import ROOT, sha256, validate_ffmpeg_bundle

KIT_VERSION = '2.10.1'
KIT_COMMIT = 'd38e1f384efebd0bf0a5c7b843028044288a619b'
KIT_SHA256 = 'add1edf984ce4d473cfeb7c52e0ab38db73a855bba6c7f564d5e16648eb2896a'
INPUTS = {
    'ffmpeg': ('ffmpeg-8.1.1.tar.gz',
               'https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/239f2c733de417201d7ad3b3b8b0d9b63285b2b1',
               'ec0aa20fb9f6fd3692ffc04dc12ffa43cfffc4a479e388ccd7910ec6cfe188a2'),
    'libsoxr': ('soxr-0.1.3.tar.gz',
                'https://codeload.github.com/chirlu/soxr/tar.gz/945b592b70470e29f917f4de89b4281fbbd540c0',
                'ae970b44833c7dd2b088d5928b27c7f1796198ff5bc5386b90393aaf33e53d51'),
}
BUNDLE = ROOT / 'build/ffmpeg_material/8.1.1-release'


def inputs(output, *, fetch=False):
    sources = output / 'sources'
    sources.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, (filename, url, digest) in INPUTS.items():
        target = sources / filename
        if not target.exists() and fetch:
            print('Downloading pinned ' + name + ' source.', flush=True)
            download(url, target, digest)
        if not target.is_file() or sha256(target) != digest:
            raise ValueError('Pinned source missing or SHA-256 mismatch: ' + str(target))
        paths[name] = target
    return paths


def extract_source(archive, target):
    # The filtered archive must have exactly one source root. Do not overwrite
    # an existing build (including any local patches) on a rerun.
    if target.exists():
        raise ValueError('Build work directory already exists: ' + str(target))
    target.mkdir(parents=True)
    with tarfile.open(archive) as stream:
        members = stream.getmembers()
        roots = {member.name.split('/')[0] for member in members}
        if len(roots) != 1:
            raise ValueError('Expected one upstream source root.')
        stream.extractall(target, filter='data')
    return target / roots.pop()


def build(kit, output, jobs):
    kit = Path(kit).resolve()
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('FFmpeg build output must stay inside the project build directory.')
    kit_archive = kit.parent / f'w64devkit-x64-{KIT_VERSION}.7z.exe'
    if sha256(kit_archive) != KIT_SHA256:
        raise ValueError('Portable toolchain archive SHA-256 mismatch.')
    archives = inputs(output)
    work = output / 'work'
    if work.exists():
        raise ValueError('Use a fresh output directory; previous build work is preserved.')
    work.mkdir()
    soxr = extract_source(archives['libsoxr'], work/'soxr')
    ffmpeg = extract_source(archives['ffmpeg'], work/'ffmpeg')
    prefix = work/'prefix'
    env = os.environ.copy()
    env['PATH'] = str(kit/'bin') + os.pathsep + env.get('PATH', '')
    env['PKG_CONFIG_PATH'] = (prefix/'lib/pkgconfig').as_posix()
    (work/'tmp').mkdir()
    env['TMPDIR'] = (work/'tmp').as_posix()
    # A source tarball nested in this application's checkout must never inherit
    # the application's Git revision as the FFmpeg version.
    env['revision'] = (ffmpeg/'RELEASE').read_text().strip()
    env['GIT_CEILING_DIRECTORIES'] = (work/'ffmpeg').as_posix()
    env['CMAKE_BUILD_PARALLEL_LEVEL'] = str(jobs)
    recipe = output/'build_recipes'
    recipe.mkdir(exist_ok=True)
    commands = [
        [str(kit/'bin/cmake.exe'), '-S', str(soxr), '-B', str(work/'soxr-build'), '-G', 'Ninja',
         '-DCMAKE_C_COMPILER='+str(kit/'bin/gcc.exe'), '-DCMAKE_CXX_COMPILER='+str(kit/'bin/g++.exe'),
         '-DCMAKE_MAKE_PROGRAM='+str(kit/'bin/ninja.exe'), '-DCMAKE_BUILD_TYPE=Release',
         '-DCMAKE_INSTALL_PREFIX='+str(prefix), '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
         '-DBUILD_SHARED_LIBS=OFF', '-DWITH_OPENMP=OFF', '-DBUILD_TESTS=OFF',
         '-DBUILD_EXAMPLES=OFF', '-DWITH_LSR_BINDINGS=OFF'],
        [str(kit/'bin/cmake.exe'), '--build', str(work/'soxr-build'), '--parallel', str(jobs)],
        [str(kit/'bin/cmake.exe'), '--install', str(work/'soxr-build')],
    ]
    flags = ['--prefix='+prefix.as_posix(), '--target-os=mingw32', '--arch=x86_64', '--cpu=x86-64',
             '--disable-autodetect', '--disable-gpl', '--disable-nonfree', '--disable-version3',
             '--disable-debug', '--disable-doc', '--disable-ffplay', '--disable-network',
             '--disable-x86asm', '--enable-libsoxr', '--enable-static', '--disable-shared',
             '--extra-cflags=-I'+(prefix/'include').as_posix(),
             '--extra-ldflags=-L'+(prefix/'lib').as_posix(), '--extra-version=Ghostkiller-source1']
    commands.extend([[str(kit/'bin/sh.exe'), './configure', *flags],
                     [str(kit/'bin/make.exe'), '-j'+str(jobs), 'V=1',
                      'REVISION='+env['revision'], 'ffmpeg.exe', 'ffprobe.exe']])
    (recipe/'commands.json').write_text(json.dumps(commands, indent=2)+'\n', encoding='utf-8')
    for index, command in enumerate(commands):
        print(f'Building stage {index+1}/{len(commands)}', flush=True)
        with (recipe/f'stage-{index+1}.log').open('wb') as log:
            subprocess.run(command, cwd=ffmpeg if index>=3 else ROOT, env=env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    for name in ('ffmpeg.exe','ffprobe.exe'):
        shutil.copyfile(ffmpeg/name, output/name)
    finish(kit, output, ffmpeg, soxr)


def finish(kit, output, ffmpeg, soxr):
    """Finish an already linked build; still verify every original source byte."""
    kit = Path(kit).resolve()
    output = Path(output).resolve()
    kit_archive = kit.parent / f'w64devkit-x64-{KIT_VERSION}.7z.exe'
    if sha256(kit_archive) != KIT_SHA256:
        raise ValueError('Portable toolchain archive SHA-256 mismatch.')
    archives = inputs(output)
    for component, directory in (('ffmpeg',ffmpeg), ('libsoxr',soxr)):
        with tarfile.open(archives[component]) as archive:
            for member in archive.getmembers():
                if member.isfile():
                    relative=Path(*Path(member.name).parts[1:])
                    if archive.extractfile(member).read() != (directory/relative).read_bytes():
                        raise ValueError('Compiled source differs from archive: '+str(relative))
    recipe = output/'build_recipes'
    work=output/'work'
    (recipe/'environment.json').write_text(json.dumps({
        'PATH_PREPEND':(kit/'bin').as_posix(), 'PKG_CONFIG_PATH':(work/'prefix/lib/pkgconfig').as_posix(),
        'TMPDIR':(work/'tmp').as_posix(), 'revision':(ffmpeg/'RELEASE').read_text().strip(),
        'make_REVISION':(ffmpeg/'RELEASE').read_text().strip(),
        'GIT_CEILING_DIRECTORIES':(work/'ffmpeg').as_posix()}, indent=2)+'\n',encoding='utf-8')
    licenses = output/'licenses'
    licenses.mkdir(exist_ok=True)
    for source, name in ((ffmpeg/'COPYING.LGPLv2.1', 'FFmpeg-COPYING.LGPLv2.1'),
                         (ffmpeg/'LICENSE.md', 'FFmpeg-LICENSE.md'),
                         (soxr/'COPYING.LGPL', 'soxr-COPYING.LGPL'),
                         (soxr/'LICENCE', 'soxr-LICENCE'),
                         (kit/'COPYING.MinGW-w64-runtime.txt', 'COPYING.MinGW-w64-runtime.txt')):
        shutil.copyfile(source, licenses/name)
    for name in ('config.h','config_components.h','ffbuild/config.mak','ffbuild/config.log'):
        target = recipe/Path(name).name
        shutil.copyfile(ffmpeg/name, target)
    shutil.copyfile(Path(__file__), recipe/'build_ffmpeg.py')
    compiler = subprocess.run([str(kit/'bin/gcc.exe'), '--version'], capture_output=True,
                              text=True, check=True).stdout
    actual = subprocess.run([str(output/'ffmpeg.exe'), '-version'], capture_output=True,
                            text=True, check=True).stdout
    configure = next(line.removeprefix('configuration: ') for line in actual.splitlines()
                     if line.startswith('configuration: '))
    dlls=set()
    for name in ('ffmpeg.exe','ffprobe.exe'):
        imports = subprocess.run([str(kit/'bin/objdump.exe'), '-p', str(output/name)],
                                 capture_output=True, text=True, check=True).stdout
        dlls.update(line.split('DLL Name: ',1)[1].strip() for line in imports.splitlines() if 'DLL Name: ' in line)
    dlls=sorted(dlls)
    # There must be no redistributable DLL silently omitted from the source bundle.
    system_dlls = {'advapi32.dll','bcrypt.dll','kernel32.dll','msvcrt.dll','ole32.dll',
                   'shell32.dll','user32.dll','ws2_32.dll','secur32.dll','psapi.dll','gdi32.dll',
                   'winmm.dll','avicap32.dll','ntdll.dll','shlwapi.dll','oleaut32.dll'}
    if set(name.lower() for name in dlls)-system_dlls:
        raise ValueError('Unexpected non-system FFmpeg DLL imports: '+', '.join(dlls))
    (recipe/'provenance.txt').write_text(
        f'Toolchain w64devkit {KIT_VERSION}, commit {KIT_COMMIT}\n'
        f'https://github.com/skeeto/w64devkit/releases/tag/v{KIT_VERSION}\n'
        f'Toolchain archive SHA-256: {KIT_SHA256}\n\n'+compiler+'\n'+actual+
        '\nWindows system DLL imports: '+', '.join(dlls)+
        '\nNo source modifications. libsoxr 0.1.3 is the only external optional library.\n'
        'GCC runtime uses GCC Runtime Library Exception 3.1. MinGW runtime notices are included.\n',
        encoding='utf-8')
    (recipe/'REBUILD.md').write_text(
        '# Rebuilding these CLI tools\n\n'
        'Unmodified corresponding FFmpeg and libsoxr sources are under ../sources. '
        'Archive URLs and hashes are in ../manifest.json. Extract w64devkit 2.10.1 '
        '(URL and hash: provenance.txt), then reproduce commands.json in order. '
        'Replace the recorded absolute source/prefix/toolchain paths with your extracted paths; '
        'stages 4 and 5 run in the FFmpeg source root. Set PATH to the toolchain bin, '
        'Use environment.json for the controlled environment: PKG_CONFIG_PATH, TMPDIR, '
        'revision (upstream RELEASE, not a parent Git checkout) and GIT_CEILING_DIRECTORIES. '
        'Alternatively run this build_ffmpeg.py '
        'from the project: python -m tools.release.build_ffmpeg --toolchain <kit>. '
        'The build does not use -march=native, GPL/nonfree libraries or global codec tools. '
        'x86 assembly is disabled; audio decoding/FLAC and libsoxr resampling remain enabled.\n\n'
        'The complete source allows rebuilding/replacing the independent FFmpeg executables. '
        'No proprietary application object is linked into them. Component licenses retain all '
        'their permissions; the application EULA does not restrict them.\n', encoding='utf-8')
    manifest = {'version':'8.1.1', 'license':'LGPL-2.1-or-later', 'configure':configure,
                'source_completeness':'complete', 'source_components':{
                    name:[path.relative_to(output).as_posix()] for name,path in archives.items()},
                'binaries':[asset(output/name,output) for name in ('ffmpeg.exe','ffprobe.exe')],
                'licenses':[asset(path,output) for path in sorted(licenses.iterdir())],
                'sources':[asset(path,output,source=INPUTS[name][1]) for name,path in archives.items()],
                'build_recipes':[asset(path,output) for path in sorted(recipe.iterdir())]}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    validate_ffmpeg_bundle(output)
    print('Source-complete FFmpeg bundle validated: '+str(output), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='Fetch pinned sources; does not build.')
    parser.add_argument('--finish', action='store_true', help='Verify/finalize an already linked build; does not recompile.')
    parser.add_argument('--toolchain', type=Path, default=ROOT/'build/ffmpeg_toolchain/w64devkit')
    parser.add_argument('--output', type=Path, default=BUNDLE)
    parser.add_argument('--jobs', type=int, default=6)
    args = parser.parse_args()
    if not 1<=args.jobs<=64:
        parser.error('--jobs must be between 1 and 64.')
    if args.download and args.finish:
        parser.error('--download and --finish cannot be combined.')
    if args.download:
        inputs(args.output, fetch=True)
    elif args.finish:
        ffmpeg=args.output/'work/ffmpeg/FFmpeg-239f2c733de417201d7ad3b3b8b0d9b63285b2b1'
        soxr=args.output/'work/soxr/soxr-945b592b70470e29f917f4de89b4281fbbd540c0'
        finish(args.toolchain,args.output,ffmpeg,soxr)
    else:
        build(args.toolchain, args.output, args.jobs)


if __name__=='__main__':
    main()
