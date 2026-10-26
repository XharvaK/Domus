# Registers the helper's two scheduled tasks, so a reinstall or a new PC gets them back (OP15):
#   "Domus bridge": tools\bridge.ps1 (the watcher) at logon, and again every 5 minutes. One instance runs.
#   "Domus telemetry archive": tools\daily_archive.ps1 every day at 12:00, and as soon as possible after a missed run.
# Run with -WhatIf to see what would be registered; that registers nothing.
[CmdletBinding(SupportsShouldProcess)]
param()
$ErrorActionPreference = 'Stop'
$tools = $PSScriptRoot

$bridgeAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
    '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $tools 'bridge.ps1'))
$bridgeTriggers = @(
    New-ScheduledTaskTrigger -AtLogOn
    New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
)
# The watcher runs for as long as the User is logged on: no time limit, and no second copy.
$bridgeSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0)

$archiveAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
    '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "{0}"' -f (Join-Path $tools 'daily_archive.ps1'))
$archiveTrigger = New-ScheduledTaskTrigger -Daily -At '12:00'
$archiveSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew

function Register-HelperTask([string]$name, $action, $trigger, $settings, [string]$description) {
    if ($PSCmdlet.ShouldProcess($name, 'Register scheduled task')) {
        Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
            -Description $description -Force | Out-Null
        Write-Output ("registered: {0}" -f $name)
    }
}

Register-HelperTask 'Domus bridge' $bridgeAction $bridgeTriggers $bridgeSettings `
    'Starts the Domus helper watcher at logon and every 5 minutes; the watcher runs one bridge while the game is open.'
Register-HelperTask 'Domus telemetry archive' $archiveAction $archiveTrigger $archiveSettings `
    'Daily Domus telemetry upkeep: outcome records, archive of finished sessions, weekly zips.'
