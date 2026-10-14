"""Stage only public website assets; never publish the application workspace."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build_site(output=None):
    destination = Path(output or ROOT/'build/site').resolve()
    if not destination.is_relative_to(ROOT/'build'):
        raise ValueError('Public website output must stay inside build/.')
    allowed = {'index.html', 'styles.css', 'app.mjs', 'logo.ico', 'lisans.txt', 'version.json', '.nojekyll'}
    if destination.exists() and any(path.name not in allowed or not path.is_file() or path.is_symlink()
                                    for path in destination.iterdir()):
        raise ValueError('Website output contains unrelated files; use an empty build directory.')
    destination.mkdir(parents=True, exist_ok=True)
    for source in (ROOT/'website/index.html', ROOT/'website/styles.css', ROOT/'website/app.mjs',
                   ROOT/'logo.ico', ROOT/'lisans.txt', ROOT/'version.json'):
        shutil.copyfile(source, destination/source.name)
    (destination/'.nojekyll').write_text('', encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    print(build_site(args.output))
