param(
    [Parameter(Mandatory=$true)][string]$Installer,
    [string]$UpgradeInstaller,
    [string]$OutputDirectory = 'C:\AcceptanceResults'
)
$ErrorActionPreference = 'Stop'
# Run only inside a disposable VM. This deliberately installs the production
# AppId and tests the real admin installer/uninstaller; never use it on the
# developer's normal Windows installation.
$machine = Get-CimInstance Win32_ComputerSystem
if ($machine.Model -notmatch 'Virtual|VMware|KVM|HVM' -and $machine.Manufacturer -notmatch 'QEMU|innotek|VMware') {
    throw 'Run production installation acceptance only in a disposable Windows VM/Sandbox.'
}
$installRoot = 'C:\GhostkillerAcceptance\Application'
if (Test-Path -LiteralPath $installRoot) { throw 'Expected a fresh acceptance VM.' }
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$stages = @($Installer)
if ($UpgradeInstaller) { $stages += $UpgradeInstaller }
$saved = @{}
$results = @()
for ($index=0; $index -lt $stages.Count; $index++) {
    $stageInstaller = (Resolve-Path -LiteralPath $stages[$index]).Path
    $arguments = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/NOICONS',
        ('/DIR='+$installRoot),('/LOG='+ (Join-Path $OutputDirectory "install-$index.log")))
    $process = Start-Process -FilePath $stageInstaller -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Installer exited $($process.ExitCode)" }
    foreach ($relative in $saved.Keys) {
        if ((Get-FileHash -LiteralPath (Join-Path $installRoot $relative) -Algorithm SHA256).Hash -ne $saved[$relative]) {
            throw "Upgrade changed synthetic user data: $relative"
        }
    }
    $smoke = Join-Path $OutputDirectory "smoke-$index.json"
    $app = Join-Path $installRoot 'Ghostkiller_Sound_Cleaner_V2.exe'
    $process = Start-Process -FilePath $app -ArgumentList @('--self-test', $smoke) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0 -or -not (Get-Content -LiteralPath $smoke -Raw | ConvertFrom-Json).ok) {
        throw "Installed frozen smoke failed: $index"
    }
    $results += @{ stage=$index; installer=(Split-Path -Leaf $stageInstaller); smoke='passed' }
    if ($index -eq 0) {
        foreach ($relative in @('models\voice.pth','models\voice.index','models.json','settings.json','training_runs\keep.json')) {
            $path = Join-Path $installRoot $relative
            New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
            [System.IO.File]::WriteAllText($path, 'Synthetic acceptance data; preserve this file.')
            $saved[$relative] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        }
        foreach ($name in @('ffmpeg.exe','ffprobe.exe')) {
            [System.IO.File]::WriteAllText((Join-Path $installRoot $name), 'Legacy codec fixture')
        }
    } else {
        foreach ($name in @('ffmpeg.exe','ffprobe.exe')) {
            if (Test-Path -LiteralPath (Join-Path $installRoot $name)) { throw "Legacy codec was retained: $name" }
        }
    }
}
$uninstaller = Get-ChildItem -LiteralPath $installRoot -Filter 'unins*.exe' | Select-Object -First 1
if (-not $uninstaller) { throw 'Production uninstaller missing.' }
$process = Start-Process -FilePath $uninstaller.FullName -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',
    ('/LOG='+ (Join-Path $OutputDirectory 'uninstall.log'))) -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Uninstaller exited $($process.ExitCode)" }
foreach ($relative in $saved.Keys) {
    if ((Get-FileHash -LiteralPath (Join-Path $installRoot $relative) -Algorithm SHA256).Hash -ne $saved[$relative]) {
        throw "Uninstall changed synthetic user data: $relative"
    }
}
@{ ok=$true; stages=$results; user_data_preserved=$true; uninstall='passed';
   uac_interaction='Manual acceptance still required: accept and cancel the production UAC prompt.';
   scope='Disposable VM install/upgrade/uninstall; does not certify other physical GPU models.' } |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'result.json') -Encoding utf8
