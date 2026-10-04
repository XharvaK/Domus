param(
    [Parameter(Mandatory = $true)][string]$SimsRoot,
    # D18 (live 2026-10-04): a fixed default removed nothing. Empty removes every
    # installed probe package under Mods\AshleyE1.
    [string]$Version = ""
)

$ErrorActionPreference = "Stop"
if (Get-Process -Name "TS4_x64" -ErrorAction SilentlyContinue) { throw "The Sims 4 must be closed" }
if (-not (Test-Path -LiteralPath $SimsRoot -PathType Container)) { throw "SimsRoot does not exist" }
$root = [IO.Path]::GetFullPath($SimsRoot).TrimEnd('\')
$folder = Join-Path $root "Mods\AshleyE1"
if ([string]::IsNullOrWhiteSpace($Version)) {
    $artifact = Join-Path $folder "ashley_e1_*.ts4script"
    if (Test-Path -LiteralPath $folder -PathType Container) {
        Get-ChildItem -LiteralPath $folder -File |
            Where-Object { $_.Name -match '(?i)^ashley_e1_.*\.ts4script$' } |
            Remove-Item -Force
    }
} else {
    $artifact = Join-Path $folder ("ashley_e1_" + $Version + ".ts4script")
    if (Test-Path -LiteralPath $artifact -PathType Leaf) { Remove-Item -LiteralPath $artifact -Force }
}
$cache = Join-Path $root "localthumbcache.package"
if (Test-Path -LiteralPath $cache -PathType Leaf) { Remove-Item -LiteralPath $cache -Force }
if (-not [string]::IsNullOrWhiteSpace($Version) -and (Test-Path -LiteralPath $artifact)) {
    throw "Exact artifact remains after removal"
}
$mods = Join-Path $root "Mods"
$remaining = @()
if (Test-Path -LiteralPath $mods -PathType Container) {
    $remaining = @(Get-ChildItem -LiteralPath $mods -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '(?i)^ashley_e1.*\.(ts4script|zip)$' })
}
if ($remaining.Count -gt 0) {
    throw ("Ashley E1 package remains under Mods: " + (($remaining | Select-Object -ExpandProperty FullName) -join "; "))
}
Write-Output "REMOVE_PASS exact artifact absent; saves untouched"
