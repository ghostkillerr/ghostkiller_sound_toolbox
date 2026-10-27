const repository = 'ghostkillerr/ghostkiller_sound_toolbox';

export function packageFor(manifest, backend) {
  if (!manifest || manifest.distribution_status === 'unpublished' || !['cpu', 'cuda'].includes(backend)) return null;
  const version = manifest.version;
  const manual = Object.hasOwn(manifest, 'manual_packages');
  const item = (manual ? manifest.manual_packages : manifest.packages)?.[backend];
  if (manual && item?.format !== 'offline-zip') return null;
  if (!/^\d+\.\d+\.\d+$/.test(version) || !item || typeof item.download_url !== 'string') return null;
  if (!/^[a-f0-9]{64}$/i.test(item.sha256) || new Set(item.sha256.toLowerCase()).size < 2) return null;
  if (!Number.isSafeInteger(item.size) || item.size <= 0 || item.size > 8 * 1024 ** 3) return null;
  try {
    const url = new URL(item.download_url);
    const filename = manual ? `Ghostkiller-Sound-Toolbox-${backend.toUpperCase()}-V${version}.zip`
      : `Ghostkiller_V2_Setup_${backend}_${version}.exe`;
    const expected = `https://github.com/${repository}/releases/download/v${version}/${filename}`;
    if (url.href !== expected || item.download_url !== expected) return null;
    return {version, url: url.href, sha256: item.sha256.toLowerCase(), size: item.size,
      format: manual ? 'offline-zip' : 'single-exe'};
  } catch { return null; }
}

export function renderDownloads(manifest, root = document) {
  let available = 0;
  for (const backend of ['cpu', 'cuda']) {
    const link = root.getElementById(`${backend}-download`);
    const checksum = root.getElementById(`${backend}-checksum`);
    const meta = root.getElementById(`${backend}-meta`);
    const item = packageFor(manifest, backend);
    link.removeAttribute('href');
    link.setAttribute('aria-disabled', 'true');
    link.setAttribute('tabindex', '-1');
    link.textContent = 'Henüz yayımlanmadı';
    checksum.hidden = true;
    meta.textContent = `Windows x64 · ${backend === 'cpu' ? 'CPU' : 'NVIDIA CUDA'}`;
    if (!item) continue;
    available++;
    link.href = item.url;
    link.removeAttribute('aria-disabled');
    link.removeAttribute('tabindex');
    link.textContent = `Ghostkiller Sound Toolbox ${backend.toUpperCase()} V${item.version} indir ↓`;
    const size = item.size / (item.size >= 1e9 ? 1e9 : 1e6);
    const unit = item.size >= 1e9 ? 'GB' : 'MB';
    meta.textContent += ` · v${item.version} · ${new Intl.NumberFormat('tr-TR', {maximumFractionDigits: 2}).format(size)} ${unit}${item.format === 'offline-zip' ? ' · ZIP' : ''}`;
    root.getElementById(`${backend}-sha`).textContent = item.sha256;
    checksum.hidden = false;
  }
  root.getElementById('release-version').textContent = available ? `v${manifest.version}` : 'Yayın hazırlanıyor';
  root.getElementById('download-status').textContent = available
    ? (manifest.manual_packages ? 'ZIP dosyasının tamamını ayıkla, açılan klasörde setup dosyasını çalıştır. Yanındaki .bin dosyaları aynı klasörde kalmalı.' : 'Kurulum dosyaları doğrudan projenin GitHub yayınından indirilir.')
    : 'Kurulumlar test ediliyor. Doğrulanmış sürüm yayımlandığında CPU ve CUDA indirme bağlantıları burada açılacak.';
}

if (typeof document !== 'undefined') {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  fetch('./version.json', {cache: 'no-store', signal: controller.signal})
    .then(response => { if (!response.ok) throw new Error('Release information unavailable'); return response.json(); })
    .then(manifest => renderDownloads(manifest))
    .catch(() => {
      document.getElementById('download-status').textContent = 'İndirme listesi yüklenemedi. Bağlantınızı kontrol edin veya aşağıdaki GitHub yayınları bağlantısını kullanın.';
    })
    .finally(() => clearTimeout(timeout));
}
