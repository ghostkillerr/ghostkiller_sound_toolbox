param(
    [Parameter(Mandatory=$true)][string]$InputDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Publication directory must be new.' }
$plans = @()
foreach ($backend in @('cpu', 'cuda')) {
    $receipts = @(Get-ChildItem -LiteralPath $InputDirectory -Filter "Ghostkiller_V2_Setup_${backend}_*_offline.build.json" -File)
    if ($receipts.Count -ne 1) { throw "Expected one exact $backend receipt." }
    $receipt = Get-Content -LiteralPath $receipts[0].FullName -Raw | ConvertFrom-Json
    $version = $receipt.application_version
    if ($version -notmatch '^\d+\.\d+\.\d+$' -or $receipt.backend -ne $backend -or
        $receipt.format -ne 'offline-zip' -or $receipt.purpose -ne 'release' -or
        $receipt.release_eligible -ne $true -or
        $receipt.installer.filename -cne "Ghostkiller_V2_Setup_${backend}_${version}_offline.zip") {
        throw 'Invalid publication input receipt.'
    }
    $inputArchive = Get-Item -LiteralPath (Join-Path $InputDirectory $receipt.installer.filename)
    if ($inputArchive.Length -ne $receipt.installer.size -or
        (Get-FileHash -LiteralPath $inputArchive.FullName -Algorithm SHA256).Hash -ne $receipt.installer.sha256) {
        throw 'Publication input does not match receipt.'
    }
    $label = "Ghostkiller Sound Toolbox $($backend.ToUpperInvariant()) V$version"
    $filename = $label.Replace(' ', '-') + '.zip'
    $receipt.installer.filename = $filename
    $receipt | Add-Member -NotePropertyName release_asset_label -NotePropertyValue $label
    $plans += @{input=$inputArchive.FullName; filename=$filename; receipt=$receipt}
}
if ($plans[0].receipt.application_version -ne $plans[1].receipt.application_version -or
    $plans[0].receipt.application_source_sha256 -ne $plans[1].receipt.application_source_sha256) {
    throw 'CPU and CUDA must have the same version and application source.'
}
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
foreach ($plan in $plans) {
    $target = Join-Path $OutputDirectory $plan.filename
    Copy-Item -LiteralPath $plan.input -Destination $target
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $plan.receipt.installer.sha256) {
        throw 'Publication copy failed its hash check.'
    }
    $plan.receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath ([IO.Path]::ChangeExtension($target, '.build.json')) -Encoding utf8
    Write-Output $target
}
