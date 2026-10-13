"""Version-bound update packages. No installation is allowed without a digest."""
from dataclasses import dataclass
import hashlib
import hmac
from pathlib import Path
import re
from urllib.parse import urlsplit

RELEASE_REPOSITORY = "ghostkillerr/ghostkiller_sound_toolbox"
RELEASE_PAGE = f"https://github.com/{RELEASE_REPOSITORY}/releases"
BACKENDS = frozenset({"cpu", "cuda", "rocm", "xpu"})
MAX_INSTALLER_BYTES = 8 * 1024 ** 3


@dataclass(frozen=True)
class InstallerPackage:
    version: str
    backend: str
    url: str
    sha256: str
    size: int | None = None


def validate_package(manifest, backend):
    """Reject old, mutable or incomplete update metadata before any download."""
    if backend not in BACKENDS:
        raise ValueError("Güncelleme için çalışma ortamı belirlenemedi.")
    if not isinstance(manifest, dict):
        raise ValueError("Güncelleme kaydı geçersiz.")
    version = manifest.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"v?\d+\.\d+\.\d+", version):
        raise ValueError("Güncelleme sürümü geçersiz.")
    version = version.removeprefix("v")
    packages = manifest.get("packages")
    if packages is not None:
        if not isinstance(packages, dict):
            raise ValueError("Güncelleme paketleri geçersiz.")
        asset = packages.get(backend)
    else:
        # A single-package manifest must identify its backend as well.
        asset = manifest if manifest.get("backend") == backend else None
    if not isinstance(asset, dict):
        raise ValueError(f"{backend} çalışma ortamı için doğrulanmış güncelleme paketi yok.")
    url = asset.get("download_url", "")
    if not isinstance(url, str):
        raise ValueError("Güncelleme bağlantısı geçersiz.")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "github.com"
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Güncelleme yalnız güvenilen GitHub yayınından indirilebilir.")
    prefix = f"/{RELEASE_REPOSITORY}/releases/download/"
    suffix = parsed.path.removeprefix(prefix)
    parts = suffix.split("/")
    if (not parsed.path.startswith(prefix) or len(parts) != 2
            or parts[0] not in {version, f"v{version}"}
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.exe", parts[1])):
        raise ValueError("Kurulum bağlantısı bildirilen sürümün sabit yayın dosyası olmalı.")
    digest = asset.get("sha256", "")
    if not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
        raise ValueError("Yayın paketi için SHA-256 doğrulama bilgisi eksik veya geçersiz.")
    if len(set(digest.lower())) == 1:
        raise ValueError("Yayın paketi için yer tutucu SHA-256 kabul edilmez.")
    size = asset.get("size")
    if size is not None and (type(size) is not int or size <= 0 or size > MAX_INSTALLER_BYTES):
        raise ValueError("Güncelleme paketinin boyut bilgisi geçersiz.")
    return InstallerPackage(version, backend, url, digest.lower(), size)


def validate_response_url(url, package):
    """GitHub uses a signed release-assets redirect; arbitrary hosts are refused."""
    if url == package.url:
        return
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "release-assets.githubusercontent.com"
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("Güncelleme indirmesi güvenilmeyen bir adrese yönlendirildi.")


def verify_installer(path, package):
    """Hash again immediately before launch, including after download callbacks."""
    path = Path(path)
    size = path.stat().st_size
    if size <= 2 or size > MAX_INSTALLER_BYTES or (package.size is not None and size != package.size):
        raise ValueError("İndirilen kurulumun boyutu yayın kaydıyla uyuşmuyor.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("İndirilen dosya Windows kurulum dosyası değil.")
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if not hmac.compare_digest(digest.hexdigest(), package.sha256):
        raise ValueError("SHA-256 doğrulaması başarısız; kurulum başlatılmadı.")
