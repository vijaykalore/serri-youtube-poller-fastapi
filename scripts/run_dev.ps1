# Run FastAPI app using the venv python to avoid Anaconda interference
param(
    [string]$BindHost = "127.0.0.1",
    [int]$BindPort = 8000
)

$ErrorActionPreference = "Stop"

# Ensure venv exists (prefer the Windows Python launcher 'py' to avoid Anaconda)
$venvRoot = Join-Path $PSScriptRoot "..\\.venv"
$venvPython = Join-Path $venvRoot "Scripts\\python.exe"
if (!(Test-Path $venvPython)) {
    Write-Host "Creating virtual environment at $venvRoot ..."
    $created = $false
    $candidates = @("py -3.12", "py -3.11", "py -3.10", "py")
    foreach ($cmd in $candidates) {
        try {
            & $env:ComSpec /c "$cmd -m venv `"$venvRoot`"" | Out-Null
            if (Test-Path $venvPython) { $created = $true; break }
        } catch { }
    }
    if (-not $created) {
        try {
            python -m venv $venvRoot
        } catch { }
    }
    if (!(Test-Path $venvPython)) {
        Write-Error "Failed to create venv. Please install Python 3.11+ from python.org and ensure 'py' is available."
    }
}

# Ensure required packages for SQLite dev are installed (idempotent)
Write-Host "Ensuring dependencies from requirements-sqlite.txt ..."
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "..\\requirements-sqlite.txt")

# Ensure env for SQLite local dev unless already set
if (-not $env:DATABASE_URL) {
    $absDb = (Resolve-Path (Join-Path $PSScriptRoot "..\\dev.db")).Path
    $absDb = $absDb -replace '\\','/'
    $env:DATABASE_URL = "sqlite+aiosqlite:///$absDb"
}
if (-not $env:DISABLE_POLLER) { $env:DISABLE_POLLER = "1" }

# Use uvicorn via module to ensure venv interpreter
& $venvPython -m uvicorn app.main:app --host $BindHost --port $BindPort --reload
