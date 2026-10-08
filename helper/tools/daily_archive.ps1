# Daily telemetry upkeep (D48, the User's rule 2026-10-05), run by a scheduled task.
# 1. Outcome records for every session still on disk (live or archived).
# 2. Finished sessions older than a day move to verified gzip in the helper data folder.
# 3. Archived sessions older than 7 days are packed into weekly zips (kept, never deleted).
$ErrorActionPreference = 'Continue'
$helper = Split-Path -Parent $PSScriptRoot
$python = Join-Path $helper '.venv\Scripts\python.exe'
Set-Location $helper
$env:PYTHONPATH = '.'
$dataDir = & $python -c "from domus_helper.paths import Paths; print(Paths.from_env().data_dir)"
New-Item -ItemType Directory -Force $dataDir | Out-Null
$log = Join-Path $dataDir 'daily_archive.log'
Add-Content -Path $log -Value ("== {0:u}" -f (Get-Date).ToUniversalTime()) -Encoding utf8
& $python -m domus_helper.outcomes --all --write 2>&1 | Select-Object -Last 1 |
    Add-Content -Path $log -Encoding utf8
& $python -m domus_helper.telemetry_archive --weekly-after-days 7 2>&1 |
    Add-Content -Path $log -Encoding utf8
