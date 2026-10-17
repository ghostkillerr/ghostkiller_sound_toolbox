"""Create reviewable local update metadata from actual eligible installer bytes."""
import argparse
from datetime import date
import json
from pathlib import Path
import re
from release_security import RELEASE_PAGE, RELEASE_REPOSITORY, validate_package, verify_installer
from tools.release.preflight import sha256
from tools.release.source_identity import source_digest


def create_manifest(version, packages, *, changelog='', release_date=None):
    result = {'version': version, 'app_name': 'Ghostkiller Sound Toolbox',
              'changelog': changelog,
              'release_url': RELEASE_PAGE + '/tag/v' + version, 'packages': {}}
    if release_date is not None:
        result['release_date'] = date.fromisoformat(release_date).isoformat()
    expected_source = source_digest()
    package_source = None
    for backend, installer, build_info in packages:
        installer = Path(installer)
        info = json.loads(Path(build_info).read_text(encoding='utf-8'))
        if info.get('backend') != backend or info.get('release_eligible') is not True or info.get('purpose') != 'release':
            raise ValueError('Diagnostic or mismatched backend builds cannot produce update metadata.')
        if info.get('application_version') != version:
            raise ValueError('Manifest version does not match the frozen application version.')
        source = info.get('application_source_sha256')
        if package_source is not None and source != package_source:
            raise ValueError('All update packages must use the same application sources.')
        if source != expected_source:
            raise ValueError('Frozen application sources are outdated. Rebuild before creating update metadata.')
        package_source = source
        receipt_path = installer.with_suffix('.build.json')
        if not receipt_path.is_file():
            raise ValueError('Installer build receipt missing; compile it with tools.release.build_installer.')
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if (receipt.get('schema_version') != 1 or receipt.get('backend') != backend
                or receipt.get('application_version') != version or receipt.get('purpose') != 'release'
                or receipt.get('release_eligible') is not True
                or receipt.get('build_info_sha256') != sha256(build_info)
                or not re.fullmatch(r'[0-9a-f]{64}',info.get('application_source_sha256',''))
                or receipt.get('application_source_sha256') != info['application_source_sha256']):
            raise ValueError('Installer build receipt does not match this frozen build/backend/version.')
        binary = receipt.get('installer',{})
        actual_digest, actual_size = sha256(installer), installer.stat().st_size
        if (binary.get('filename') != installer.name or binary.get('sha256') != actual_digest
                or binary.get('size') != actual_size):
            raise ValueError('Installer bytes differ from the recorded compilation output.')
        if backend in result['packages']:
            raise ValueError('Duplicate backend in update manifest: '+backend)
        asset = {'download_url': f'https://github.com/{RELEASE_REPOSITORY}/releases/download/v{version}/{installer.name}',
                 'sha256': actual_digest, 'size': actual_size}
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
