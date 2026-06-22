<#
.SYNOPSIS
    Back up the FAH Explorer SQLite database with a timestamp.
.DESCRIPTION
    Copies fah_explorer.db to data/backups/fah_explorer_YYYYMMDD_HHMMSS.db.
    Retains the last 30 backups; older files are removed automatically.
    Schedule via Windows Task Scheduler for nightly execution.
.EXAMPLE
    .\scripts\backup_db.ps1
#>

$Root    = Split-Path -Parent $PSScriptRoot
$DbPath  = Join-Path $Root "data\fah_explorer.db"
$BakDir  = Join-Path $Root "data\backups"
$Stamp   = Get-Date -Format "yyyyMMdd_HHmmss"
$BakPath = Join-Path $BakDir "fah_explorer_$Stamp.db"

if (-not (Test-Path $DbPath)) {
    Write-Error "Database not found at $DbPath"; exit 1
}

New-Item -ItemType Directory -Force -Path $BakDir | Out-Null
Copy-Item -Path $DbPath -Destination $BakPath
Write-Host "[backup] Saved $BakPath"

# Rotate: keep only the 30 most recent backups
Get-ChildItem -Path $BakDir -Filter "fah_explorer_*.db" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip 30 |
    ForEach-Object { Remove-Item $_.FullName; Write-Host "[backup] Removed old backup: $($_.Name)" }

Write-Host "[backup] Done."
