"""Prepare pinned DEVELOPMENT codecs for source CI; never a release bundle.

Release installers still require the independently built, source-complete LGPL
bundle. These tools stay in ignored paths and are never uploaded by CI.
"""
import argparse
import os
from pathlib import Path
import shutil
import tempfile
import zipfile

from tools.release.fetch_ffmpeg_material import BINARY_ARCHIVE, BINARY_SHA256, download
from tools.release.preflight import ROOT, sha256


def prepare(archive, destination):
    archive, destination = Path(archive), Path(destination)
    if sha256(archive) != BINARY_SHA256:
        raise ValueError('CI codec archive SHA-256 mismatch.')
    destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        members = {}
        for filename in ('ffmpeg.exe','ffprobe.exe'):
            matches=[info for info in source.infolist() if not info.is_dir() and info.filename.endswith('/bin/'+filename)]
            if len(matches)!=1:
                raise ValueError('CI archive codec member missing or ambiguous: '+filename)
            members[filename]=matches[0]
        with tempfile.TemporaryDirectory(prefix='.ci-codecs_',dir=destination) as temporary:
            stage=Path(temporary)
            for filename,member in members.items():
                with source.open(member) as stream, (stage/filename).open('wb') as output:
                    shutil.copyfileobj(stream,output)
            for filename in members:
                os.replace(stage/filename,destination/filename)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=ROOT/'build/ci-ffmpeg-8.1.1.zip')
    args=parser.parse_args()
    args.archive.parent.mkdir(parents=True,exist_ok=True)
    if not args.archive.is_file() or sha256(args.archive)!=BINARY_SHA256:
        download(BINARY_ARCHIVE,args.archive,BINARY_SHA256)
    prepare(args.archive,ROOT/'tools/ffmpeg')
    print('Pinned development FFmpeg/FFprobe ready for source tests; not release material.')


if __name__=='__main__':
    main()
