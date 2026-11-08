# Build a setup-compatible delta from the previously published stable Release.
# Verify both downloaded predecessor assets against GitHub SHA-256 metadata.
$ErrorActionPreference = "Stop"
$version = python -c "import sys; sys.path.insert(0,'src'); import astrochart; print(astrochart.__version__)"
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') { throw "Invalid target version" }
$oldTag = gh api repos/toyro396133/astro-birth-chart-windows/releases/latest --jq '.tag_name'
if ($LASTEXITCODE -ne 0 -or $oldTag -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+$') { throw "Previous stable release missing" }
if ($oldTag -eq "v$version") { throw "Cannot create a delta from the same version" }
$previous = "dist\previous-release"
New-Item -ItemType Directory -Path $previous -Force | Out-Null
$oldRelease = gh api "repos/toyro396133/astro-birth-chart-windows/releases/tags/$oldTag" | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "Cannot read prior release metadata" }
foreach ($filename in @("AstroBirthChart-Windows-x64.zip", "AstroBirthChart-Setup.exe")) {
    gh release download $oldTag --pattern $filename --dir $previous
    if ($LASTEXITCODE -ne 0) { throw "Previous release asset unavailable: $filename" }
    $asset = @($oldRelease.assets | Where-Object { $_.name -ceq $filename })
    if ($asset.Count -ne 1 -or $asset[0].digest -notmatch '^sha256:[0-9a-f]{64}$') {
        throw "Missing prior asset SHA-256"
    }
    $actual = (Get-FileHash -Path (Join-Path $previous $filename) -Algorithm SHA256).Hash.ToLowerInvariant()
    if ("sha256:$actual" -cne $asset[0].digest) { throw "Previous asset digest mismatch: $filename" }
}
$oldZip = Join-Path $previous "AstroBirthChart-Windows-x64.zip"
$generated = "installer\generated-setup-delta.iss"
python scripts/create_setup_delta.py $oldZip "dist\AstroBirthChart" "installer\astrochart.iss" $generated
if ($LASTEXITCODE -ne 0) { throw "Setup delta script generation failed" }
$iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) { throw "Inno Setup missing" }
& $iscc "/DAppVersion=$version" $generated
if ($LASTEXITCODE -ne 0) { throw "Delta Inno installer compilation failed" }
$deltaName = "AstroBirthChart-Setup-Delta-from-$oldTag-to-v$version.exe"
$delta = Join-Path "dist\installer" $deltaName
$full = "dist\installer\AstroBirthChart-Setup.exe"
if (-not (Test-Path $delta)) { throw "Delta Setup executable missing" }
$partialBytes = (Get-Item $delta).Length
$fullBytes = (Get-Item $full).Length
if ($partialBytes -ge $fullBytes) {
    throw "Delta package ($partialBytes bytes) does not save bandwidth vs full ($fullBytes bytes)"
}
Write-Host "SETUP_DELTA_READY: $deltaName $partialBytes/$fullBytes bytes"
