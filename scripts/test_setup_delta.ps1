# Actual Windows upgrade: previous published Setup -> partial Inno patch.
# Verify upgrade, Windows uninstall log, and untouched large data.
$ErrorActionPreference = "Stop"
$previous = "dist\previous-release\AstroBirthChart-Setup.exe"
if (-not (Test-Path $previous)) { throw "Previous installer missing for delta E2E" }
$version = python -c "import sys; sys.path.insert(0,'src'); import astrochart; print(astrochart.__version__)"
$oldTag = gh api repos/toyro396133/astro-birth-chart-windows/releases/latest --jq '.tag_name'
if ($LASTEXITCODE -ne 0) { throw "Previous version missing" }
$delta = "dist\installer\AstroBirthChart-Setup-Delta-from-$oldTag-to-v$version.exe"
if (-not (Test-Path $delta)) { throw "Delta installer not built" }
$install = Join-Path $env:RUNNER_TEMP "AstroBirthChart-Delta-QA\AstroBirthChart"
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AstroBirthChart.Windows_is1'
if (Test-Path $key) { throw "Windows uninstall registration from earlier test was not cleaned" }
$flags = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/DIR=$install")

function Run-Installer($path, $expectedSuccess) {
    $proc = Start-Process -FilePath (Resolve-Path $path).Path -ArgumentList $flags -Wait -PassThru
    if ($expectedSuccess -and $proc.ExitCode -ne 0) { throw "Setup failed: $path ($($proc.ExitCode))" }
    if (-not $expectedSuccess -and $proc.ExitCode -eq 0) { throw "Unsafe patch incorrectly succeeded" }
}
Run-Installer $previous $true
$initial = (Get-Content (Join-Path $install "version.json") -Raw | ConvertFrom-Json).version
if ("v$initial" -cne $oldTag) { throw "Wrong previous version installed" }
$oldLarge = Join-Path $install "_internal\data\ephemeris\de440s.bsp"
$previousDigest = (Get-FileHash $oldLarge -Algorithm SHA256).Hash
# A modified reused file must stop the partial upgrade BEFORE any writes.
$stream = [System.IO.File]::Open($oldLarge, [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write)
try { $stream.WriteByte(77) } finally { $stream.Dispose() }
Run-Installer $delta $false
if ((Get-Content (Join-Path $install "version.json") -Raw | ConvertFrom-Json).version -ne $initial) {
    throw "Failed patch modified version.json before preflight"
}
# Restore exact source bytes for the positive case.
$stream = [System.IO.File]::Open($oldLarge, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write)
try { $stream.SetLength($stream.Length - 1) } finally { $stream.Dispose() }
if ((Get-FileHash $oldLarge -Algorithm SHA256).Hash -cne $previousDigest) {
    throw "Failed to restore test fixture"
}
Run-Installer $delta $true
$updated = (Get-Content (Join-Path $install "version.json") -Raw | ConvertFrom-Json).version
if ($updated -ne $version) { throw "Wrong version after delta installer" }
if ((Get-FileHash $oldLarge -Algorithm SHA256).Hash -cne $previousDigest) {
    throw "Delta changed a reused ephemeris file"
}
if (-not (Test-Path $key)) { throw "Delta upgrade removed uninstall entry" }
$app = Get-ItemProperty $key
if ($app.DisplayVersion -ne $version) { throw "Uninstall DisplayVersion not updated" }
$entries = @(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' |
    Where-Object { $_.PSChildName -like 'AstroBirthChart.Windows*' })
if ($entries.Count -ne 1) { throw "Delta created an extra uninstall registration" }
$p = Start-Process -FilePath (Join-Path $install 'AstroBirthChart.exe') -ArgumentList '--self-test' -Wait -PassThru
if ($p.ExitCode -ne 0) { throw "Patched EXE failed self-test" }
$uninstaller = Get-ChildItem $install -Filter "unins*.exe" | Select-Object -First 1
if (-not $uninstaller) { throw "Uninstaller missing" }
$removed = Start-Process -FilePath $uninstaller.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
if ($removed.ExitCode -ne 0) { throw "Uninstaller failed" }
if (Test-Path $key) { throw "Orphan uninstall key after delta removal" }
if (Test-Path (Join-Path $install 'AstroBirthChart.exe')) { throw "Patched EXE left behind after uninstall" }
Write-Host "SETUP_DELTA_INSTALL_UPGRADE_UNINSTALL_OK"
