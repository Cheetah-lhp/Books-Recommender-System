param(
    [string]$PythonExe,
    [ValidateRange(10, 1800)]
    [int]$StartupTimeoutSeconds = 180,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$demoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $demoRoot
. (Join-Path $PSScriptRoot 'demo-common.ps1')

function Wait-DemoService {
    param([string]$Name, [string]$Url, [scriptblock]$Validate)
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    Write-Host "Waiting for $Name at $Url ..."
    do {
        try {
            $response = Invoke-RestMethod -Uri $Url -TimeoutSec 3
            if (& $Validate $response) { return }
        }
        catch {
            # Connection refused is expected while the service is starting.
        }
        Start-Sleep -Milliseconds 1000
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "$Name did not become ready. Check its service window; close the started service windows before retrying."
}

function Start-DemoService {
    param([string]$Name)
    $serviceScript = Join-Path $PSScriptRoot 'start-demo.ps1'
    $arguments = @(
        '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $serviceScript), '-Service', $Name,
        '-PythonExe', ('"{0}"' -f $PythonExe)
    )
    # Separate visible consoles are intentional: users read logs and stop each service there.
    $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments `
        -WorkingDirectory $demoRoot -WindowStyle Normal -PassThru
    Write-Host "Started Readora $Name (window PID $($process.Id))."
}

try {
    if (-not $PythonExe) {
        $venvPython = Join-Path $demoRoot '.venv/Scripts/python.exe'
        $PythonExe = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
    }
    $PythonExe = (Get-Command $PythonExe -ErrorAction Stop).Source
    $env:PYTHONUTF8 = '1'
    @'
import sys
assert (3, 11) <= sys.version_info[:2] <= (3, 13), "Use Python 3.11-3.13 for the demo (PyArrow dependency)."
import books_recommender, fastapi, uvicorn, httpx, numpy, pandas, pyarrow, scipy, yaml, dotenv, pymysql
'@ | & $PythonExe -
    if ($LASTEXITCODE -ne 0) {
        throw 'Python runtime is not ready. Follow the one-time setup in README.md: create .venv with Python 3.11-3.13, then run .venv\Scripts\python.exe scripts\setup_demo.py --install.'
    }
    $null = Get-Command node -ErrorAction Stop
    $null = Get-Command npm.cmd -ErrorAction Stop
    @'
const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 22 || (major === 22 && minor < 12)) {
    console.error('Use Node.js 22.12+ or 24.');
    process.exit(1);
}
'@ | node
    if ($LASTEXITCODE -ne 0) { throw 'Node.js version is not supported. Install Node.js 22.12+ or 24.' }

    foreach ($port in @(8000, 8001, 3000)) {
        if (Test-DemoPort $port) {
            throw "Port $port is already in use. Stop the existing service before starting the demo; no additional services were launched."
        }
    }
    # Verify/extract the portable bundle before opening any service windows.
    & $PythonExe scripts/setup_demo.py
    if ($LASTEXITCODE -ne 0) { throw 'Bundled model setup failed. See the error above.' }

    Write-Host 'Starting Readora demo: catalog + model + frontend.'
    Start-DemoService 'catalog'
    Wait-DemoService 'catalog' 'http://127.0.0.1:8000/health' {
        param($response)
        $response.status -eq 'ok' -and $response.service -eq 'Book Recommender System API'
    }
    Wait-DemoService 'catalog data' 'http://127.0.0.1:8000/api/stats' {
        param($response)
        $response.total_books -gt 0
    }
    Start-DemoService 'model'
    Wait-DemoService 'model' 'http://127.0.0.1:8001/health' {
        param($response)
        $response.status -eq 'ok' -and $response.run_id -eq 'remote-demo'
    }
    Start-DemoService 'frontend'
    $demoUrl = 'http://127.0.0.1:3000/demo'
    Wait-DemoService 'frontend' $demoUrl {
        param($response)
        [string]$response -match 'value="history"'
    }
    Write-Host "Demo ready: $demoUrl"
    Write-Host 'Keep the three service windows open. To stop, press Ctrl+C in EACH window, then close it.'
    if (-not $NoBrowser) { Start-Process $demoUrl }
}
catch {
    Write-Host "Demo startup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
