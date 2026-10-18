param(
    [Parameter(Mandatory=$true)][ValidateSet('chrome','brave','firefox')][string]$Browser,
    [Parameter(Mandatory=$true)][string]$ExtensionId,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
if ($Browser -eq 'firefox') {
    if ($ExtensionId -ne 'browser@localpassword.app') { throw 'Firefox ID must be browser@localpassword.app' }
} elseif ($ExtensionId -cnotmatch '^[a-p]{32}$') { throw 'Use the 32-letter ID shown on the browser extensions page.' }
$name = 'app.localpassword.browser'
$hostFile = Join-Path $PSScriptRoot 'LocalPasswordBrowser\LocalPasswordBrowser.exe'
if (-not (Test-Path -LiteralPath $hostFile -PathType Leaf)) { throw 'Keep this script beside the complete LocalPasswordBrowser folder.' }
$vendor = @{chrome='Google\Chrome'; brave='BraveSoftware\Brave-Browser'; firefox='Mozilla'}[$Browser]
$registry = "HKCU:\Software\$vendor\NativeMessagingHosts\$name"
$folder = Join-Path $env:LOCALAPPDATA "LocalPasswordBrowser\$Browser"
$manifestPath = Join-Path $folder "$name.json"
if ($Remove) {
    if (Test-Path -LiteralPath $registry) { Remove-Item -LiteralPath $registry }
    if (Test-Path -LiteralPath $manifestPath) { Remove-Item -LiteralPath $manifestPath }
    Write-Host 'Browser registration removed. Your vault was not changed.'
    exit
}
$manifest = @{name=$name; description='Local Password local vault bridge'; path=$hostFile; type='stdio'}
if ($Browser -eq 'firefox') { $manifest.allowed_extensions = @($ExtensionId) }
else { $manifest.allowed_origins = @("chrome-extension://$ExtensionId/") }
New-Item -ItemType Directory -Force -Path $folder | Out-Null
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
New-Item -Path $registry -Force | Out-Null
Set-Item -LiteralPath $registry -Value $manifestPath
Write-Host "Registered Local Password for $Browser. Keep the bridge folder in its current location."
