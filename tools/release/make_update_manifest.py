"""Create reviewable local update metadata from actual eligible installer bytes."""
import argparse
from datetime import date
import json
from pathlib import Path
from release_security import RELEASE_PAGE, RELEASE_REPOSITORY, validate_package, verify_installer
from tools.release.preflight import sha256


def create_manifest(version, packages, *, changelog='', release_date=None):
    result = {'version': version, 'app_name': 'Ghostkiller Sound Toolbox',
              'changelog': changelog,
              'release_url': RELEASE_PAGE + '/tag/v' + version, 'packages': {}}
    if release_date is not None:
        result['release_date'] = date.fromisoformat(release_date).isoformat()
    for backend, installer, build_info in packages:
        installer = Path(installer)
        info = json.loads(Path(build_info).read_text(encoding='utf-8'))
        if info.get('backend') != backend or info.get('release_eligible') is not True or info.get('purpose') != 'release':
            raise ValueError('Diagnostic or mismatched backend builds cannot produce update metadata.')
        asset = {'download_url': f'https://github.com/{RELEASE_REPOSITORY}/releases/download/v{version}/{installer.name}',
                 'sha256': sha256(installer), 'size': installer.stat().st_size}
        result['packages'][backend] = asset
        package = validate_package(result, backend)
        verify_installer(installer, package)
    if not result['packages']:
        raise ValueError('At least one real installer/build-info pair is required.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--package', action='append', nargs=3, metavar=('BACKEND', 'INSTALLER', 'BUILD_INFO'), required=True)
    parser.add_argument('--changelog', default='')
    parser.add_argument('--release-date', help='Explicit publisher date in YYYY-MM-DD form.')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = create_manifest(args.version, args.package, changelog=args.changelog, release_date=args.release_date)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Created local manifest only; no upload, release or installation performed.')


if __name__ == '__main__':
    main()
