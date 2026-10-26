param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$Receipt,
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
$archiveFile = Get-Item -LiteralPath $Archive
$metadata = Get-Content -LiteralPath $Receipt -Raw | ConvertFrom-Json
if ($metadata.format -ne 'offline-zip' -or
    $metadata.installer.filename -cne $archiveFile.Name -or
    $metadata.installer.size -ne $archiveFile.Length -or
    $metadata.installer.sha256 -ne (Get-FileHash -LiteralPath $archiveFile.FullName -Algorithm SHA256).Hash) {
    throw 'Offline archive does not match its receipt.'
}
if ($metadata.setup_filename -notmatch '^Ghostkiller_V2_Setup_(cpu|cuda)_\d+\.\d+\.\d+\.exe$') {
    throw 'Invalid offline setup filename.'
}
$stem = [IO.Path]::GetFileNameWithoutExtension($metadata.setup_filename)
$allowed = '^(?:' + [regex]::Escape($metadata.setup_filename) + '|' + [regex]::Escape($stem) + '-\d+(?:[a-z])?\.bin|ONCE_OKU\.txt)$'
$expected = @{}
foreach ($item in $metadata.files) {
    if ($item.filename -cnotmatch $allowed -or $expected.ContainsKey($item.filename) -or $item.size -le 0 -or $item.sha256 -notmatch '^[a-f0-9]{64}$') {
        throw 'Invalid or duplicate offline receipt entry.'
    }
    $expected[$item.filename] = $item
}
if (-not $expected.ContainsKey($metadata.setup_filename) -or -not $expected.ContainsKey('ONCE_OKU.txt') -or $expected.Count -lt 3) {
    throw 'Offline receipt is incomplete.'
}
if (Test-Path -LiteralPath $Destination) { throw 'Extraction destination must be new.' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [IO.Compression.ZipFile]::OpenRead($archiveFile.FullName)
try {
    $seen = @{}
    foreach ($entry in $zip.Entries) {
        if ($entry.FullName -cnotmatch $allowed -or $seen.ContainsKey($entry.FullName) -or
            -not $expected.ContainsKey($entry.FullName) -or $entry.Length -ne $expected[$entry.FullName].size) {
            throw 'Unexpected, unsafe or duplicate archive entry.'
        }
        $seen[$entry.FullName] = $true
        $stream = $entry.Open()
        $hash = [Security.Cryptography.SHA256]::Create()
        try { $actual = [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
        finally { $hash.Dispose(); $stream.Dispose() }
        if ($actual -ne $expected[$entry.FullName].sha256) { throw 'Offline entry hash mismatch.' }
    }
    if ($seen.Count -ne $expected.Count) { throw 'Offline archive is incomplete.' }
} finally { $zip.Dispose() }
[IO.Compression.ZipFile]::ExtractToDirectory($archiveFile.FullName, [IO.Path]::GetFullPath($Destination))
(Get-Item -LiteralPath (Join-Path $Destination $metadata.setup_filename)).FullName
