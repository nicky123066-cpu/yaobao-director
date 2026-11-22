$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$projectPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw 'Create .venv and install requirements-dev.txt first.' }
Push-Location -LiteralPath (Join-Path $projectRoot 'ui')
try {
    & npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
} finally { Pop-Location }
& $projectPython scripts\prepare_ffmpeg.py
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg preparation failed' }
& $projectPython -m PyInstaller --noconfirm YaobaoDirector.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
Write-Host 'Built dist\YaobaoDirector\幺爆导演台.exe; keep the entire directory.'
