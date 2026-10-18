"""Validated model downloads that can resume an unchanged HTTP representation."""
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.error import HTTPError
from urllib.request import Request


def download(url, target, *, opener, cancelled=None, progress=None, validate=None):
    from app_settings import write_json_atomic
    from registry_store import registry_lock

    target = Path(target)
    model_root = next((parent for parent in target.resolve().parents if parent.name.casefold() == 'models'), target.parent)
    cache = model_root / '.downloads'
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((str(target.resolve()) + '\n' + url).encode()).hexdigest()
    partial, state = cache / (key + '.part'), cache / (key + '.state')

    def check():
        if cancelled and cancelled():
            raise InterruptedError('Model indirmesi iptal edildi. Desteklenen sunucularda sonraki deneme kaldığı yerden sürer.')

    def discard():
        partial.unlink(missing_ok=True)
        state.unlink(missing_ok=True)

    def publish():
        check()
        try:
            if validate:
                validate(str(partial))
        except InterruptedError:
            raise
        except BaseException:
            discard()  # Never reuse a corrupt or untrusted model payload.
            raise
        check()
        os.replace(partial, target)
        state.unlink(missing_ok=True)

    with registry_lock(partial):
        check()
        try:
            saved = json.loads(state.read_text(encoding='utf-8'))
            size = partial.stat().st_size
            resumable = (saved.get('url') == url and isinstance(saved.get('validator'), str)
                         and bool(saved['validator']) and isinstance(saved.get('total'), int)
                         and 0 < size <= saved['total'])
        except (OSError, ValueError, AttributeError, TypeError):
            resumable = False
        if not resumable:
            discard()
            saved, size = {}, 0
        if size and size == saved['total']:
            publish()
            return

        headers = {'User-Agent': 'Ghostkiller-Sound-Toolbox', 'Accept-Encoding': 'identity'}
        if size:
            headers.update(Range=f'bytes={size}-', **{'If-Range': saved['validator']})
        try:
            response = opener(Request(url, headers=headers), timeout=30)
        except HTTPError as error:
            if error.code != 416 or not size:
                raise
            error.close()
            discard()
            size = 0
            response = opener(Request(url, headers={'Accept-Encoding': 'identity'}), timeout=30)

        keep_partial = bool(size)
        try:
            with response:
                code = getattr(response, 'status', None) or 200
                length = int(response.headers.get('Content-Length', 0))
                if length < 0:
                    raise ValueError('İndirilecek modelin boyutu geçersiz.')
                etag = response.headers.get('ETag', '')
                validator = etag if etag and not etag.startswith('W/') else response.headers.get('Last-Modified', '')
                if code == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if not size or not match or validator != saved['validator']:
                        keep_partial = False
                        raise ValueError('Kısmi indirme sunucudaki dosyayla eşleşmiyor. İndirmeyi yeniden başlatın.')
                    start, end, total = map(int, match.groups())
                    if start != size or end < start or end + 1 != total or total != saved['total'] or (length and length != end - start + 1):
                        keep_partial = False
                        raise ValueError('Sunucunun kısmi indirme boyutu geçersiz. İndirmeyi yeniden başlatın.')
                elif code == 200:
                    if size:
                        discard()
                    size, total = 0, length  # If-Range failed or the server ignores ranges: start fresh.
                else:
                    raise ValueError(f'Model sunucusu beklenmeyen yanıt verdi: {code}')
                keep_partial = bool(validator and total)
                write_json_atomic(str(state), {'url': url, 'validator': validator, 'total': total})
                if total and shutil.disk_usage(cache).free < total - size + 64 * 1024**2:
                    raise OSError(errno.ENOSPC, 'Model indirmesi için diskte yeterli boş alan yok.')
                if progress:
                    progress(size, total)
                with partial.open('ab' if size else 'wb') as output:
                    while True:
                        check()
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        if total and size + len(chunk) > total:
                            keep_partial = False
                            raise ValueError('İndirilen model bildirilen boyutu aşıyor.')
                        output.write(chunk)
                        size += len(chunk)
                        if progress:
                            progress(size, total)
                check()
                if not size or total and size != total:
                    raise RuntimeError('Model indirmesi boş veya eksik. Eksikleri indir ile yeniden deneyin.')
            publish()
        finally:
            if not keep_partial:
                discard()
