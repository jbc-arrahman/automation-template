# Launch the device's installed Google Chrome with a CDP debugging port (Windows PowerShell).
# Usage: .\scripts\launch_chrome.ps1 [-Port 9222] [-UserDataDir ".\profiles\installed"]
param(
    [int]$Port = $(if ($env:CDP_PORT) { [int]$env:CDP_PORT } else { 9222 }),
    [string]$UserDataDir = $(if ($env:CHROME_USER_DATA_DIR) { $env:CHROME_USER_DATA_DIR } else { Join-Path (Resolve-Path "$PSScriptRoot\..") "profiles\installed" }),
    [string]$ProfileDir = $(if ($env:CHROME_PROFILE_DIRECTORY) { $env:CHROME_PROFILE_DIRECTORY } else { "Default" })
)

$candidates = @(
    $env:CHROME_BINARY,
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { $_ -and (Test-Path $_) }

if (-not $candidates) {
    Write-Error "Google Chrome not found. Set CHROME_BINARY in .env or install Chrome."
    exit 1
}

$chrome = $candidates[0]
New-Item -ItemType Directory -Force -Path $UserDataDir | Out-Null

$args = @(
    "--remote-debugging-port=$Port",
    "--remote-debugging-address=127.0.0.1",
    "--user-data-dir=$UserDataDir",
    "--profile-directory=$ProfileDir",
    "--no-first-run",
    "--no-default-browser-check"
)

Start-Process -FilePath $chrome -ArgumentList $args
Write-Host "Launched Chrome on http://127.0.0.1:$Port with profile $UserDataDir ($ProfileDir)"
