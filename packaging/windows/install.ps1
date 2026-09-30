# Install Local Password into the Start menu and onto the desktop.
param(
    [string]$Source = ""
)

$ErrorActionPreference = "Stop"

if (-not $Source) {
    $Source = Join-Path $PSScriptRoot "LocalPassword"
}

$sourceExe = Join-Path $Source "LocalPassword.exe"
if (-not (Test-Path -LiteralPath $sourceExe)) {
    Write-Error "LocalPassword.exe was not found in $Source"
}

Get-Process -Name LocalPassword -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 400

$dest = Join-Path $env:LOCALAPPDATA "Programs\Local Password"
if (Test-Path -LiteralPath $dest) {
    Remove-Item -LiteralPath $dest -Recurse -Force
}
Copy-Item -LiteralPath $Source -Destination $dest -Recurse -Force

$exe = Join-Path $dest "LocalPassword.exe"
$icon = Join-Path $dest "local-password.ico"
$iconSource = Join-Path (Split-Path (Split-Path $Source -Parent) -Parent) "packaging\windows\local-password.ico"
if (Test-Path -LiteralPath $iconSource) {
    Copy-Item -LiteralPath $iconSource -Destination $icon -Force
}
$iconLocation = if (Test-Path -LiteralPath $icon) { $icon } else { "$exe,0" }

$uninstall = @'
param([switch]$Stage2)
$ErrorActionPreference = "SilentlyContinue"
$dest = Join-Path $env:LOCALAPPDATA "Programs\Local Password"
if (-not $Stage2) {
    $copy = Join-Path $env:TEMP "uninstall-local-password.ps1"
    Copy-Item -LiteralPath $PSCommandPath -Destination $copy -Force
    Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $copy, "-Stage2")
    exit 0
}
Start-Sleep -Seconds 1
Remove-Item -LiteralPath (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Local Password.lnk") -Force
$desktop = [Environment]::GetFolderPath("Desktop")
Remove-Item -LiteralPath (Join-Path $desktop "Local Password.lnk") -Force
Remove-Item -LiteralPath "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalPassword" -Recurse -Force
Get-Process -Name LocalPassword -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 400
if (Test-Path -LiteralPath $dest) {
    Remove-Item -LiteralPath $dest -Recurse -Force
}
'@
$uninstallPath = Join-Path $dest "uninstall.ps1"
Set-Content -LiteralPath $uninstallPath -Value $uninstall -Encoding UTF8

$wsh = New-Object -ComObject WScript.Shell
function New-AppShortcut([string]$Path) {
    $shortcut = $wsh.CreateShortcut($Path)
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $dest
    $shortcut.WindowStyle = 1
    $shortcut.Description = "Local Password"
    $shortcut.IconLocation = $iconLocation
    $shortcut.Save()
}

$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Local Password.lnk"
$desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "Local Password.lnk"
New-AppShortcut $startMenu
New-AppShortcut $desktop

$reg = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalPassword"
New-Item -Path $reg -Force | Out-Null
$sizeKb = [int]((Get-ChildItem -LiteralPath $dest -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1KB)
Set-ItemProperty -LiteralPath $reg -Name DisplayName -Value "Local Password"
Set-ItemProperty -LiteralPath $reg -Name DisplayIcon -Value $iconLocation
Set-ItemProperty -LiteralPath $reg -Name Publisher -Value "Local Password"
Set-ItemProperty -LiteralPath $reg -Name DisplayVersion -Value "1.15.0"
Set-ItemProperty -LiteralPath $reg -Name InstallLocation -Value $dest
Set-ItemProperty -LiteralPath $reg -Name UninstallString -Value "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$uninstallPath`""
Set-ItemProperty -LiteralPath $reg -Name EstimatedSize -Value $sizeKb -Type DWord
Set-ItemProperty -LiteralPath $reg -Name NoModify -Value 1 -Type DWord
Set-ItemProperty -LiteralPath $reg -Name NoRepair -Value 1 -Type DWord

Write-Host "Local Password is installed."
Write-Host "Open it from the Start menu, or from the desktop icon."
Start-Process -FilePath $exe
