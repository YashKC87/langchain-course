# Builds the DWIP agent into a single dwip-agent.exe (dist\dwip-agent.exe), served by the DWIP server at
# /download/dwip-agent.exe. Optionally builds dist\DWIPAgent.msi when the WiX v4+ CLI ("wix") is installed.
#
#   pwsh packaging\build_agent.ps1            # exe only
#   pwsh packaging\build_agent.ps1 -Msi       # exe + MSI (needs: dotnet tool install --global wix)
param([switch]$Msi, [string]$Version = "1.0.0")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    python -m PyInstaller --noconfirm --onefile --console --name dwip-agent `
        --distpath dist --workpath build\pyinstaller --specpath build `
        --hidden-import psutil --hidden-import httpx agent\agent.py
    if ($LASTEXITCODE) { throw "PyInstaller failed" }
    Write-Host "Built dist\dwip-agent.exe"
    if ($Msi) {
        if (-not (Get-Command wix -ErrorAction SilentlyContinue)) { throw "WiX not found: dotnet tool install --global wix" }
        wix build packaging\DWIPAgent.wxs -d Version=$Version -d ExePath=dist\dwip-agent.exe -o dist\DWIPAgent.msi
        if ($LASTEXITCODE) { throw "WiX build failed" }
        Write-Host "Built dist\DWIPAgent.msi (install: msiexec /i DWIPAgent.msi SERVER=http://host:8000 TOKEN=xyz /qn)"
    }
} finally { Pop-Location }
