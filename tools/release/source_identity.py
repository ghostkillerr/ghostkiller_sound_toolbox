"""Identify the application sources without including private data or build outputs."""
import hashlib
from pathlib import Path


def source_digest(root=None):
    root = Path(root or Path(__file__).resolve().parents[2])
    paths = list(root.glob('*.py')) + list(root.glob('*.spec')) + list(root.glob('*.ps1'))
    paths.extend(root/name for name in ('version.json','logo.ico','lisans.txt',
                                       'training/vendor/LICENSE','training/vendor/NOTICE.md'))
    paths.extend(root/'restoration/vendor'/name for name in
                 ('LICENSE','NOTICE.md','MODEL_LICENSE.md','GUIDED_DIFFUSION_LICENSE'))
    paths.extend(root/'instruments/vendor'/name for name in ('LICENSE','NOTICE.md'))
    for directory in ('rvc','training','restoration','instruments','tools/release'):
        paths.extend(path for path in (root/directory).rglob('*')
                     if path.is_file() and path.suffix in ('.py','.json')
                     and not {'models','__pycache__'}.intersection(path.relative_to(root).parts))
    paths.extend(path for path in (root/'third_party/runtime').rglob('*') if path.is_file())
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        relative = path.relative_to(root).as_posix().encode('utf-8')
        digest.update(len(relative).to_bytes(4,'little'))
        digest.update(relative)
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()
