# The helper bridge (8d): reads new telemetry, runs the peripheral thalamus, sends heartbeats and
# observations to Ashley, and keeps the archive and string indexes fresh. Run at logon by a scheduled
# task; one instance at a time. Output goes to <data>\bridge.log.
$ErrorActionPreference = 'Continue'
$helper = Split-Path -Parent $PSScriptRoot
$python = Join-Path $helper '.venv\Scripts\python.exe'
Set-Location $helper
$env:PYTHONPATH = '.'
$dataDir = & $python -c "from domus_helper.paths import Paths; print(Paths.from_env().data_dir)"
New-Item -ItemType Directory -Force $dataDir | Out-Null
$log = Join-Path $dataDir 'bridge.log'
$running = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.CommandLine -match 'domus_helper\.bridge --interval' }
if ($running) { exit 0 }
Add-Content -Path $log -Value ("== start {0:u}" -f (Get-Date)) -Encoding utf8
& $python -u -m domus_helper.bridge --interval 5 *>> $log
