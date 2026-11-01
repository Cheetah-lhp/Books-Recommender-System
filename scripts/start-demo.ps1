param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('catalog', 'model', 'frontend')]
    [string]$Service,
    [string]$RunId = 'remote-demo',
    [string]$PythonExe,
    [switch]$Install
)

$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $demoRoot
. (Join-Path $PSScriptRoot 'demo-common.ps1')
if (-not $PythonExe) {
    $venvPython = Join-Path $demoRoot '.venv/Scripts/python.exe'
    $PythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
}
$Host.UI.RawUI.WindowTitle = "Readora $Service"
$env:PYTHONUTF8 = '1'
$sourcePath = Join-Path $demoRoot 'src'
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$sourcePath;$env:PYTHONPATH" } else { $sourcePath }
$env:DB_ENGINE = 'sqlite'
$env:BOOKS_SQLITE_PATH = Join-Path $demoRoot 'data/demo_catalog.db'
$env:ML_CATALOG_URL = 'http://127.0.0.1:8000'
$env:API_BASE = 'http://127.0.0.1:8000'
$env:VITE_API_URL = 'http://127.0.0.1:8000'
$env:ML_RECOMMENDER_URL = 'http://127.0.0.1:8001/recommend'
$env:READORA_DEMO_MODE = '1'
$env:READORA_CATALOG_SORT = 'ratings_count'

if ($Install) {
    & $PythonExe scripts/setup_demo.py --install
    if ($LASTEXITCODE -ne 0) { throw 'Model dependency installation failed.' }
    & $PythonExe -m pip install -r web/backend/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Catalog dependency installation failed.' }
}

$demoPort = @{ catalog = 8000; model = 8001; frontend = 3000 }[$Service]
if (Test-DemoPort $demoPort) {
    Write-Host "Port $demoPort is already in use. Check http://127.0.0.1:$demoPort before restarting."
    return
}

switch ($Service) {
    'catalog' {
        New-Item -ItemType Directory -Path (Join-Path $demoRoot 'data') -Force | Out-Null
        & $PythonExe web/backend/init_sample_data.py
        if ($LASTEXITCODE -ne 0) { throw 'Sample catalog initialization failed.' }
        & $PythonExe -m uvicorn main:app --app-dir web/backend --host 127.0.0.1 --port 8000
        if ($LASTEXITCODE -ne 0) { throw 'Catalog service stopped with an error.' }
    }
    'model' {
        if ($RunId -eq 'remote-demo') {
            & $PythonExe scripts/setup_demo.py
            if ($LASTEXITCODE -ne 0) { throw 'Bundled model setup failed.' }
        }
        & $PythonExe -m books_recommender.cli serve --run-id $RunId --port 8001
        if ($LASTEXITCODE -ne 0) { throw 'Model service stopped with an error.' }
    }
    'frontend' {
        Set-Location -LiteralPath (Join-Path $demoRoot 'web/front_end')
        if ($Install -or -not (Test-Path node_modules)) {
            npm.cmd ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        }
        npm.cmd run dev -- --host 127.0.0.1 --strictPort
        if ($LASTEXITCODE -ne 0) { throw 'Frontend service stopped with an error.' }
    }
}
