"""Check the actual Git index for private runtime files and local user paths."""
from pathlib import Path, PurePosixPath
import re
import subprocess

PRIVATE_NAMES = {'models.json','settings.json','training_presets.json','.integrity.json'}
PRIVATE_ROOTS = {'models','modeller','deneme','training_runs','trained_models',
                 'cache','build','dist','Setup'}
PRIVATE_SUFFIXES = {'.pth','.pt','.th','.ckpt','.index','.bin','.safetensors',
                    '.wav','.mp3','.flac','.ogg','.m4a','.aac','.wma','.log'}
USER_PATH = re.compile(r'(?i)(?:[a-z]:/Users/|/home/|/Users/)[\w][\w .@-]*(?:/|$)')


def inspect_entry(name, data):
    path = PurePosixPath(name)
    reasons = []
    if path.name in PRIVATE_NAMES or path.name.removesuffix('.lock') in PRIVATE_NAMES:
        reasons.append('personal runtime configuration')
    if path.parts[0] in PRIVATE_ROOTS or path.parts[:2] == ('rvc','models'):
        reasons.append('local data/output directory')
    if path.suffix.lower() in PRIVATE_SUFFIXES:
        reasons.append('model, audio or log data')
    if path.name == '.env' or path.name.startswith('.env.') and path.name != '.env.example':
        reasons.append('local environment configuration')
    if path.parts[0] == 'docs' and path.suffix == '.json' and path.name != 'REVIEWED_UVR_SOURCE_HASHES.json':
        reasons.append('local diagnostic report')
    # Exact upstream build metadata is covered by its license/provenance hash.
    # Its build-machine paths are not this application's user configuration.
    if name == 'third_party/runtime/PYTHON.json':
        return reasons
    try:
        text = data.decode('utf-8')
    except UnicodeError:
        return reasons
    normalized = text.replace('\\\\','\\').replace('\\','/')
    if USER_PATH.search(normalized):
        reasons.append('absolute user-directory path')
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',text):
        reasons.append('private key')
    if re.search(r'\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{35,})\b',text):
        reasons.append('GitHub access token')
    return reasons


def check_index(root):
    listing = subprocess.check_output(['git','ls-files','--stage','-z'],cwd=root)
    findings = []
    with subprocess.Popen(['git','cat-file','--batch'],cwd=root,
                          stdin=subprocess.PIPE,stdout=subprocess.PIPE) as process:
        for record in listing.split(b'\0'):
            if not record:
                continue
            metadata, filename = record.split(b'\t',1)
            mode, oid, stage = metadata.split()
            name = filename.decode('utf-8')
            if stage != b'0':
                findings.append((name,['unresolved merge']))
                continue
            if mode == b'160000':
                continue
            process.stdin.write(oid+b'\n'); process.stdin.flush()
            header = process.stdout.readline().split()
            if len(header) != 3 or header[1] != b'blob':
                raise ValueError(f'Cannot read indexed file: {name}')
            data = process.stdout.read(int(header[2]))
            process.stdout.read(1)
            reasons = inspect_entry(name,data)
            if reasons:
                findings.append((name,reasons))
        process.stdin.close()
    return findings


def main():
    findings = check_index(Path(__file__).resolve().parents[1])
    for name,reasons in findings:
        print(f'{name}: {", ".join(reasons)}')
    if findings:
        print('Private data found in Git. Remove it from the index before publishing.')
        return 1
    print('Public Git tree checked: no private runtime data or local user paths.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
