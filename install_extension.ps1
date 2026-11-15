<#
.SYNOPSIS
    FalconDM 1-Click Browser Extension Installer
.DESCRIPTION
    Registers Windows Native Messaging Hosts in HKCU for Chrome, Edge, Brave, Opera, and Firefox.
    Copies the extension directory path to the clipboard and launches the target browser's extension page.
#>

[CmdletBinding()]
param(
    [string]$Browser = "chrome"
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "       FalconDM Turbo Downloader - 1-Click Extension Setup" -ForegroundColor White
Write-Host "       100% Free - Open Source - No Chrome Web Store Fee Needed" -ForegroundColor Yellow
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

$RootDir = $PSScriptRoot
if (-not $RootDir) { $RootDir = (Get-Location).Path }
$ExtDir = Join-Path $RootDir "browser_extension"
$NativeBat = Join-Path $RootDir "core\native_host.bat"
$ChromeManifest = Join-Path $RootDir "core\com.falcondm.downloader.json"
$FirefoxManifest = Join-Path $RootDir "core\com.falcondm.downloader_firefox.json"

# Update manifests with absolute paths
try {
    if (Test-Path $ChromeManifest) {
        $c = Get-Content $ChromeManifest -Raw | ConvertFrom-Json
        $c.path = $NativeBat
        $c | ConvertTo-Json -Depth 5 | Set-Content $ChromeManifest -Encoding UTF8
    }
    if (Test-Path $FirefoxManifest) {
        $f = Get-Content $FirefoxManifest -Raw | ConvertFrom-Json
        $f.path = $NativeBat
        $f | ConvertTo-Json -Depth 5 | Set-Content $FirefoxManifest -Encoding UTF8
    }
} catch {}

# Registry entries (HKCU - No Administrator privileges needed)
$RegPaths = @(
    "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.falcondm.downloader",
    "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.falcondm.downloader",
    "HKCU:\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.falcondm.downloader",
    "HKCU:\Software\Opera Software\Opera Stable\NativeMessagingHosts\com.falcondm.downloader",
    "HKCU:\Software\Opera Software\Opera GX Stable\NativeMessagingHosts\com.falcondm.downloader",
    "HKCU:\Software\Vivaldi\NativeMessagingHosts\com.falcondm.downloader"
)

foreach ($r in $RegPaths) {
    if (-not (Test-Path $r)) { New-Item -Path $r -Force | Out-Null }
    Set-ItemProperty -Path $r -Name "(Default)" -Value $ChromeManifest -Force | Out-Null
}

$FfReg = "HKCU:\Software\Mozilla\NativeMessagingHosts\com.falcondm.downloader"
if (-not (Test-Path $FfReg)) { New-Item -Path $FfReg -Force | Out-Null }
Set-ItemProperty -Path $FfReg -Name "(Default)" -Value $FirefoxManifest -Force | Out-Null

Write-Host "[OK] Native Messaging Hosts registered in Windows Registry." -ForegroundColor Green

# Copy path to clipboard
Set-Clipboard -Value $ExtDir
Write-Host "[OK] Extension path copied to Clipboard: $ExtDir" -ForegroundColor Green
Write-Host ""

# Launch Browser
$urls = @{
    "chrome"  = "chrome://extensions"
    "edge"    = "edge://extensions"
    "brave"   = "brave://extensions"
    "opera"   = "opera://extensions"
    "firefox" = "about:debugging#/runtime/this-firefox"
}

if ($Browser.ToLower() -ne "none") {
    $targetUrl = $urls[$Browser.ToLower()]
    if (-not $targetUrl) { $targetUrl = "chrome://extensions" }
    Start-Process $targetUrl -ErrorAction SilentlyContinue
}

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "             QUICK INSTRUCTIONS (Takes 5 Seconds):" -ForegroundColor Yellow
Write-Host "  1. Turn ON 'Developer mode' toggle switch at the top-right." -ForegroundColor White
Write-Host "  2. Click 'Load unpacked' button." -ForegroundColor White
Write-Host "  3. In the folder dialog, press Ctrl + V (path is in your clipboard!)" -ForegroundColor White
Write-Host "  4. Hit Enter or click 'Select Folder'." -ForegroundColor White
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "FalconDM will now intercept downloads and show video grabbers!" -ForegroundColor Green
