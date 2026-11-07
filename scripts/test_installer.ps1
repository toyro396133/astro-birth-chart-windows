# Smoke test the actual Inno Setup installer, Start Menu registration and uninstall.
$ErrorActionPreference = 'Stop'
$setup = (Resolve-Path 'dist\installer\AstroBirthChart-Setup.exe').Path
$expectedVersion = (Get-Content 'dist\AstroBirthChart\version.json' -Raw | ConvertFrom-Json).version
$install = Join-Path $env:RUNNER_TEMP 'AstroBirthChart-Install-QA\AstroBirthChart'
$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AstroBirthChart.Windows_is1'
if (Test-Path $key) { throw "Old Inno installer registration already exists on test runner" }

function Run-Setup($arguments) {
    $proc = Start-Process -FilePath $setup -ArgumentList $arguments -Wait -PassThru
    if ($proc.ExitCode -ne 0) { throw "Inno Setup returned $($proc.ExitCode)" }
}
$flags = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', "/DIR=$install")
Run-Setup $flags
if (-not (Test-Path (Join-Path $install 'AstroBirthChart.exe'))) { throw 'EXE missing after setup' }
if (-not (Test-Path (Join-Path $install 'installed-by-setup.marker'))) { throw 'Installed marker missing' }
if (-not (Test-Path $key)) { throw 'Windows Uninstall entry is missing' }
$app = Get-ItemProperty $key
if ($app.DisplayVersion -ne $expectedVersion) { throw "Unexpected uninstall version: $($app.DisplayVersion)" }
if (-not $app.UninstallString) { throw 'Missing uninstall command' }
$manifest = Get-Content (Join-Path $install 'version.json') -Raw | ConvertFrom-Json
if ($manifest.version -ne $expectedVersion) { throw 'Installed version manifest mismatch' }
$process = Start-Process -FilePath (Join-Path $install 'AstroBirthChart.exe') -ArgumentList '--self-test' -Wait -PassThru
if ($process.ExitCode -ne 0) { throw 'Installed program self-test failed' }

# Installing the same AppId over the old version must keep ONE uninstall entry.
Run-Setup $flags
if (-not (Test-Path $key)) { throw 'Upgrade lost the uninstall registration' }
$entries = @(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' |
    Where-Object { $_.PSChildName -like 'AstroBirthChart.Windows*' })
if ($entries.Count -ne 1) { throw "Expected one Windows uninstall entry, got $($entries.Count)" }

$uninstaller = Get-ChildItem -Path $install -Filter 'unins*.exe' | Select-Object -First 1
if (-not $uninstaller) { throw 'Inno uninstaller is missing' }
$uninstall = Start-Process -FilePath $uninstaller.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -Wait -PassThru
if ($uninstall.ExitCode -ne 0) { throw "Uninstaller returned $($uninstall.ExitCode)" }
if (Test-Path $key) { throw 'The Windows uninstall registry entry was not removed' }
if (Test-Path (Join-Path $install 'AstroBirthChart.exe')) { throw 'Uninstaller left the main EXE behind' }
Write-Host 'WINDOWS_INSTALL_UNINSTALL_OK'
