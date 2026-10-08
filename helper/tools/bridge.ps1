# The helper bridge (8d): reads new telemetry, runs the peripheral thalamus, sends heartbeats and
# observations to Ashley, and keeps the archive and string indexes fresh. It lives with the game:
# this watcher (started at logon by the "Domus bridge" task, one instance at a time) waits for
# TS4_x64.exe and starts the bridge, which exits a short drain after the game closes.
# Output goes to <data>\bridge.log.
$ErrorActionPreference = 'Continue'
$helper = Split-Path -Parent $PSScriptRoot
$python = Join-Path $helper '.venv\Scripts\python.exe'
Set-Location $helper
$env:PYTHONPATH = '.'
$dataDir = & $python -c "from domus_helper.paths import Paths; print(Paths.from_env().data_dir)"
New-Item -ItemType Directory -Force $dataDir | Out-Null
$log = Join-Path $dataDir 'bridge.log'
# Only shells and Python count: the headless conhost that hosts this watcher names bridge.ps1 too.
$others = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $PID -and $_.Name -match '^(powershell|pwsh|python)\.exe$' -and
    $_.CommandLine -match 'domus_helper\.bridge --interval|tools\\bridge\.ps1' }
if ($others) { exit 0 }
while ($true) {
    if (Get-Process -Name 'TS4_x64' -ErrorAction SilentlyContinue) {
        Add-Content -Path $log -Value ("== game seen, bridge start {0:u}" -f (Get-Date).ToUniversalTime()) -Encoding utf8
        & $python -u -m domus_helper.bridge --interval 2 --with-game *>> $log
        Add-Content -Path $log -Value ("== bridge stop {0:u}" -f (Get-Date).ToUniversalTime()) -Encoding utf8
    }
    Start-Sleep -Seconds 15
}
