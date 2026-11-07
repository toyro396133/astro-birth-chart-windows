$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
if (-not (Test-Path ".venv")) { py -3.12 -m venv .venv }
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $py -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "dependencies failed" }
& $py scripts/download_ephemeris.py
if ($LASTEXITCODE -ne 0) { throw "ephemeris download failed" }
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests failed" }
& $py -m PyInstaller --noconfirm --clean astro_app.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
& $py -m PyInstaller --onefile --noconfirm --clean --name AstroBirthChartUpdater scripts/update_worker.py --distpath dist/update-helper --workpath build/update-helper
if ($LASTEXITCODE -ne 0) { throw "Updater worker build failed" }
& $py scripts/write_version.py
if ($LASTEXITCODE -ne 0) { throw "Version manifest failed" }
Copy-Item dist/update-helper/AstroBirthChartUpdater.exe dist/AstroBirthChart/AstroBirthChartUpdater.exe
& dist/AstroBirthChart/AstroBirthChartUpdater.exe --self-test
if ($LASTEXITCODE -ne 0) { throw "Updater worker self-test failed" }
$exe = (Resolve-Path "dist\AstroBirthChart\AstroBirthChart.exe").Path
$process = Start-Process -FilePath $exe -ArgumentList "--self-test" -PassThru -Wait
if ($process.ExitCode -ne 0) { throw "EXE engine smoke test failed: $($process.ExitCode)" }
Write-Host "Ready: dist\AstroBirthChart\AstroBirthChart.exe"

Compress-Archive -Path dist/AstroBirthChart -DestinationPath AstroBirthChart-Windows-x64.zip -CompressionLevel Optimal -Force
& $py scripts/verify_release_zip.py AstroBirthChart-Windows-x64.zip
if ($LASTEXITCODE -ne 0) { throw "Release ZIP verification failed" }
Write-Host "Validated release ZIP: AstroBirthChart-Windows-x64.zip"
