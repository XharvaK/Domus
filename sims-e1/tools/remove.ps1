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
# 2.23.0: Domus_<version> is the file the game lists. Older ashley_e1_* scripts and
# zips in this folder are removed too, and so is Domus_*.
$probeName = '(?i)^(ashley_e1_.*|Domus_.*)\.(ts4script|zip)$'
if (Test-Path -LiteralPath $folder -PathType Container) {
    Get-ChildItem -LiteralPath $folder -File |
        Where-Object { $_.Name -match $probeName } |
        Remove-Item -Force
}
if (-not [string]::IsNullOrWhiteSpace($Version)) {
    foreach ($name in @(
            ("Domus_" + $Version + ".ts4script"), ("Domus_" + $Version + ".zip"),
            ("ashley_e1_" + $Version + ".ts4script"), ("ashley_e1_" + $Version + ".zip"))) {
        $artifact = Join-Path $folder $name
        if (Test-Path -LiteralPath $artifact) { throw "Exact artifact remains after removal" }
    }
}
$cache = Join-Path $root "localthumbcache.package"
if (Test-Path -LiteralPath $cache -PathType Leaf) { Remove-Item -LiteralPath $cache -Force }
$mods = Join-Path $root "Mods"
$remaining = @()
if (Test-Path -LiteralPath $mods -PathType Container) {
    $remaining = @(Get-ChildItem -LiteralPath $mods -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '(?i)^(ashley_e1.*|Domus_.*)\.(ts4script|zip)$' })
}
if ($remaining.Count -gt 0) {
    throw ("Ashley E1 package remains under Mods: " + (($remaining | Select-Object -ExpandProperty FullName) -join "; "))
}
Write-Output "REMOVE_PASS exact artifact absent; saves untouched"
