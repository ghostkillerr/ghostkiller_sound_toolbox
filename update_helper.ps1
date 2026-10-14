# Runs at the original user's privilege level, outside the files being replaced.
# Only the verified Inno process is elevated. Tests dot-source these functions.
param([string]$JobPath)
$ErrorActionPreference = 'Stop'

function Write-UpdateState($Path, $State) {
    $temporary = $Path + '.part'
    [IO.File]::WriteAllText($temporary, ($State | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $Path -Force
}

function Get-UpdateParent($Id) {
    return [Diagnostics.Process]::GetProcessById($Id)
}

function Start-UpdateInstaller($Job) {
    return Start-Process -FilePath $Job.installer -ArgumentList $Job.arguments -Verb RunAs -WindowStyle Hidden -PassThru
}

function Restart-UpdatedApplication($Job) {
    # This helper was started by the application without elevation.
    Start-Process -FilePath $Job.executable -WorkingDirectory ([IO.Path]::GetDirectoryName($Job.executable))
}

function Show-UpdateNotice($Message) {
    Add-Type -AssemblyName System.Windows.Forms
    [void][Windows.Forms.MessageBox]::Show($Message, 'Program güncellemesi')
}

function Invoke-InPlaceUpdate([string]$JobPath) {
    $job = Get-Content -LiteralPath $JobPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $root = [IO.Path]::GetFullPath([IO.Path]::GetDirectoryName($JobPath))
    $installer = [IO.Path]::GetFullPath($job.installer)
    $guard = $null
    $parent = $null
    $started = $false
    $state = @{state = 'failed'; version = $job.version; message = 'Güncelleme tamamlanamadı.'}
    try {
        if (-not ([IO.Path]::GetFileName($root).StartsWith('ghostkiller_update_')) -or
            [IO.Path]::GetDirectoryName($installer) -ne $root -or
            [IO.Path]::GetFullPath($job.status) -ne (Join-Path $root 'status.json')) {
            throw 'Invalid update workspace.'
        }
        $parent = Get-UpdateParent $job.parent_pid
        $guard = [IO.File]::Open($installer, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
        if ($job.size -and $guard.Length -ne $job.size) { throw 'Installer size changed.' }
        if ($guard.ReadByte() -ne 77 -or $guard.ReadByte() -ne 90) { throw 'Invalid installer header.' }
        $guard.Position = 0
        $algorithm = [Security.Cryptography.SHA256]::Create()
        try {
            $hash = [BitConverter]::ToString($algorithm.ComputeHash($guard)).Replace('-', '').ToLowerInvariant()
        } finally { $algorithm.Dispose() }
        if ($hash -ne $job.sha256) { throw 'Installer SHA-256 changed.' }
        $setup = Start-UpdateInstaller $job
        $started = $true
        Write-UpdateState $job.status @{state = 'started'}
        # PrepareToInstall waits for parent_pid before touching application files.
        $setup.WaitForExit()
        $code = $setup.ExitCode
        if ($code -eq 3010) {
            $state = @{state = 'restart_required'; version = $job.version; message = 'Güncellemenin tamamlanması için Windows yeniden başlatılmalı.'}
        } elseif ($code -ne 0) {
            throw "Güncelleme tamamlanamadı (hata $code). Ayarlardan yeniden deneyebilirsiniz."
        } else {
            $internal = Join-Path ([IO.Path]::GetDirectoryName($job.executable)) '_internal'
            $installed = Get-Content -LiteralPath (Join-Path $internal 'version.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            $info = Get-Content -LiteralPath (Join-Path $internal 'build-info.json') -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($installed.version -ne $job.version -or $info.backend -ne $job.backend) {
                throw 'Installed version/backend does not match the verified update.'
            }
            $state = @{state = 'completed'; version = $job.version; message = 'Güncelleme tamamlandı.'}
        }
    } catch {
        $updateException = $_.Exception
        $cancelled = $false
        while ($null -ne $updateException) {
            if ($updateException -is [ComponentModel.Win32Exception] -and $updateException.NativeErrorCode -eq 1223) { $cancelled = $true }
            $updateException = $updateException.InnerException
        }
        $state = @{state = $(if ($cancelled) { 'cancelled' } else { 'failed' }); version = $job.version; message = $_.Exception.Message}
    } finally {
        if ($guard) { $guard.Dispose() }
        Write-UpdateState $job.result $state
        if (-not $started) {
            Write-UpdateState $job.status $state
        } elseif ($parent.HasExited) {
            if ($state.state -ne 'restart_required') {
                try { Restart-UpdatedApplication $job } catch {
                    $state.message += ' Programı kısayolundan yeniden açın.'
                    Write-UpdateState $job.result $state
                }
            } else {
                Show-UpdateNotice $state.message
            }
            # All removable paths were created specifically for this update.
            foreach ($name in @('Ghostkiller_V2_Setup.exe', 'job.json', 'status.json', 'status.json.part', 'update_helper.ps1')) {
                $owned = Join-Path $root $name
                if (Test-Path -LiteralPath $owned) { Remove-Item -LiteralPath $owned -Force -ErrorAction SilentlyContinue }
            }
            if ((Get-ChildItem -LiteralPath $root -Force | Measure-Object).Count -eq 0) {
                Remove-Item -LiteralPath $root -Force -ErrorAction SilentlyContinue
            }
        } else {
            Write-UpdateState $job.status $state
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-InPlaceUpdate -JobPath $JobPath
}
