import test from 'node:test';
import assert from 'node:assert/strict';
import {packageFor, renderDownloads} from '../website/app.mjs';

function release() {
  const packages = Object.fromEntries(['cpu', 'cuda'].map(backend => [backend, {
    download_url: `https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/download/v2.1.0/Ghostkiller_V2_Setup_${backend}_2.1.0.exe`,
    sha256: '1234567890abcdef'.repeat(4), size: 100_000_000,
  }]));
  return {version: '2.1.0', packages};
}

function dom() {
  const elements = new Map();
  return {getElementById(id) {
    if (!elements.has(id)) elements.set(id, {textContent: '', hidden: false, attributes: {},
      removeAttribute(key) {delete this.attributes[key]; if (key === 'href') delete this.href;},
      setAttribute(key, value) {this.attributes[key] = value;}});
    return elements.get(id);
  }};
}

test('both published profiles render version-bound downloads and checksums', () => {
  const root = dom();
  renderDownloads(release(), root);
  for (const backend of ['cpu', 'cuda']) {
    assert.ok(root.getElementById(`${backend}-download`).href.includes(`_${backend}_2.1.0.exe`));
    assert.equal(root.getElementById(`${backend}-download`).attributes['aria-disabled'], undefined);
    assert.equal(root.getElementById(`${backend}-checksum`).hidden, false);
  }
  assert.equal(root.getElementById('release-version').textContent, 'v2.1.0');
});

test('unpublished metadata and absent files never produce fake download links', () => {
  const root = dom();
  renderDownloads(release(), root);
  renderDownloads({...release(), distribution_status: 'unpublished'}, root);
  assert.equal(root.getElementById('cpu-download').href, undefined);
  assert.equal(root.getElementById('cuda-download').href, undefined);
  assert.equal(packageFor({version: '2.0.0', packages: {}}, 'cpu'), null);
});

test('untrusted, mutable, wrong-version and wrong-backend assets are refused', () => {
  const valid = release().packages.cpu.download_url;
  for (const url of [valid.replace('github.com', 'example.com'), valid.replace('v2.1.0/', 'v2.2.0/'),
    valid.replace('_cpu_', '_cuda_'), valid.replace('/download/v2.1.0/', '/latest/download/'),
    `${valid}?token=bad`, `javascript:alert(1)`, `${valid}#fake`, valid.replace('github.com', 'user@github.com')]) {
    const metadata = release();
    metadata.packages.cpu.download_url = url;
    assert.equal(packageFor(metadata, 'cpu'), null, url);
  }
});

test('missing integrity data, placeholder hashes and invalid sizes are refused', () => {
  for (const change of [{sha256: ''}, {sha256:'0'.repeat(64)}, {size:0}, {size:true}, {size:1.5}, {size:9*1024**3}]) {
    const metadata = release();
    Object.assign(metadata.packages.cpu, change);
    assert.equal(packageFor(metadata, 'cpu'), null);
  }
});

test('named manual ZIPs use separate metadata and cannot fall back to old EXEs', () => {
  const metadata = release();
  const oldCPU = {...metadata.packages.cpu};
  metadata.manual_packages = Object.fromEntries(['cpu', 'cuda'].map(backend => [backend, {
    ...metadata.packages[backend], format: 'offline-zip',
    download_url: `https://github.com/ghostkillerr/ghostkiller_sound_toolbox/releases/download/v2.1.0/Ghostkiller-Sound-Toolbox-${backend.toUpperCase()}-V2.1.0.zip`,
  }]));
  const root = dom();
  renderDownloads(metadata, root);
  assert.ok(root.getElementById('cuda-download').textContent.includes('Ghostkiller Sound Toolbox CUDA V2.1.0'));
  assert.ok(root.getElementById('download-status').textContent.includes('.bin'));
  assert.deepEqual(metadata.packages.cpu, oldCPU);
  for (const change of [{format: 'exe'}, {sha256: 'bad'}, {download_url: oldCPU.download_url},
    {download_url: metadata.manual_packages.cpu.download_url.replace('CPU', 'CUDA')},
    {download_url: metadata.manual_packages.cpu.download_url.replace('/v2.1.0/', '/latest/')},
    {download_url: metadata.manual_packages.cpu.download_url.replace('github.com', 'example.com')}]) {
    const changed = structuredClone(metadata);
    Object.assign(changed.manual_packages.cpu, change);
    assert.equal(packageFor(changed, 'cpu'), null);
  }
  metadata.manual_packages = {};
  assert.equal(packageFor(metadata, 'cpu'), null);
});
