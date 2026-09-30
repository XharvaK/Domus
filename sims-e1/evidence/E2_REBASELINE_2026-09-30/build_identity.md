# Installed Sims 4 build identity
CHECK_TIME=2026-09-30T08:44:44.0534046+03:00
MAIN_SHA=2636ac996d915ec63c4ccdbdb1b25db7fed36421
SIMS_RUNNING=False
Command: Get-Process -Name TS4_x64 -ErrorAction SilentlyContinue; output: none.
## GameVersion.txt
Command: Get-Item -LiteralPath 'C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\GameVersion.txt'
Path=C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\GameVersion.txt; Length=17; LastWriteTime=2026-09-29T05:04:09.1638586+03:00
Command: Format-Hex -Path 'C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\GameVersion.txt'
Bytes: 0D 00 00 00 31 2E 31 32 38 2E 39 30 2E 31 30 33 30
Not plain text: leading binary bytes. Content omitted; size and SHA256 recorded instead.
Command: Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\Users\Xharv\OneDrive\Belgeler\Electronic Arts\The Sims 4\GameVersion.txt'
SHA256=BA199DE403997AC8207BC61EA5CAFE5E8826FE3F62A9E3CDAEC75F3EDDE508D4
## Steam manifest
Command: Get-Content 'E:\SteamLibrary\steamapps\appmanifest_1222670.acf' | Select-String '^\s*"(buildid|LastUpdated|StateFlags)"' | ForEach-Object { $_.Line }
	"StateFlags"		"4"
	"LastUpdated"		"1790117142"
	"buildid"		"25223079"
Command: [DateTimeOffset]::FromUnixTimeSeconds(1790117142).ToLocalTime().ToString('o')
LastUpdated local=2026-09-23T01:45:42.0000000+03:00
## Executable
Command: Get-Item 'E:\SteamLibrary\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe'; (Get-Item 'E:\SteamLibrary\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe').VersionInfo
Path=E:\SteamLibrary\steamapps\common\The Sims 4\Game\Bin\TS4_x64.exe; Length=45179248; LastWriteTime=2026-09-23T01:44:35.5613121+03:00; FileVersion=1.128.90.1030; ProductVersion=1.128.90.1030
## Archives
Command: Get-Item -LiteralPath 'E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\core.zip'; Get-FileHash -Algorithm SHA256 -LiteralPath 'E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\core.zip'
Path=E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\core.zip; Length=332162; LastWriteTime=2026-09-23T01:44:35.4387179+03:00; SHA256=641E9233C44763B0103517ED40DA37186FCD10DF76143896D6BF3C497A38690B
Command: Get-Item -LiteralPath 'E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\base.zip'; Get-FileHash -Algorithm SHA256 -LiteralPath 'E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\base.zip'
Path=E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\base.zip; Length=1830057; LastWriteTime=2026-09-23T01:44:35.4367140+03:00; SHA256=5E53E2A5622FA8806F92D8B75A5639AD4B83D49DBAAD4ADD602A411421D02594
Command: Get-Item -LiteralPath 'E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\simulation.zip'; Get-FileHash -Algorithm SHA256 -LiteralPath 'E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\simulation.zip'
Path=E:\SteamLibrary\steamapps\common\The Sims 4\Data\Simulation\Gameplay\simulation.zip; Length=10130550; LastWriteTime=2026-09-23T01:44:35.4387179+03:00; SHA256=B97D71BB8C92116B4320ED640F5D3F06C3E4F1E3FB2F7DFD5FEA5F924D0324EC
| Archive | Expected bytes | Actual bytes | Expected SHA256 | Actual SHA256 | Result |
|---|---:|---:|---|---|---|
| core.zip | 332162 | 332162 | 641E9233C44763B0103517ED40DA37186FCD10DF76143896D6BF3C497A38690B | 641E9233C44763B0103517ED40DA37186FCD10DF76143896D6BF3C497A38690B | MATCH |
| base.zip | 1830057 | 1830057 | 5E53E2A5622FA8806F92D8B75A5639AD4B83D49DBAAD4ADD602A411421D02594 | 5E53E2A5622FA8806F92D8B75A5639AD4B83D49DBAAD4ADD602A411421D02594 | MATCH |
| simulation.zip | 10130550 | 10130550 | B97D71BB8C92116B4320ED640F5D3F06C3E4F1E3FB2F7DFD5FEA5F924D0324EC | B97D71BB8C92116B4320ED640F5D3F06C3E4F1E3FB2F7DFD5FEA5F924D0324EC | MATCH |
ARCHIVES_VS_PLAN = ALL_MATCH
