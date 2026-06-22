<#
.SYNOPSIS
    Start FAH Explorer locally (Windows, direct Python).
.DESCRIPTION
    Loads .env, initialises the database, and launches uvicorn.
    For production use the Docker path instead.
.PARAMETER Port
    Port to listen on (default 8000).
.PARAMETER Workers
    Number of uvicorn workers (default 1 for local; set 2+ for production).
.EXAMPLE
    .\scripts\start.ps1
    .\scripts\start.ps1 -Port 8765 -Workers 2
#>
param(
    [int]$Port    = 8000,
    [int]$Workers = 1
)

$Root = Split-Path -Parent $PSScriptRoot

# Load .env if present
$EnvFile = Join-Path $Root ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | Where-Object { $_ -match "^\s*[^#].+=." } | ForEach-Object {
        $parts = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
    Write-Host "[fah] Loaded $EnvFile"
}

# Warn if no password is set
if (-not $env:FAH_PASSWORD) {
    Write-Warning "FAH_PASSWORD is not set — the app is running in open (unauthenticated) mode."
}

# Initialise / migrate the database
Write-Host "[fah] Initialising database..."
python -c "import sys; sys.path.insert(0,'$(Join-Path $Root 'backend')'); from fah.db.session import init_db; init_db()"

# Launch
Write-Host "[fah] Starting FAH Explorer v1.0.0 on http://localhost:$Port"
python -m uvicorn fah.main:app `
    --app-dir "$(Join-Path $Root 'backend')" `
    --host 127.0.0.1 `
    --port $Port `
    --workers $Workers `
    --timeout-keep-alive 75 `
    --log-level info
