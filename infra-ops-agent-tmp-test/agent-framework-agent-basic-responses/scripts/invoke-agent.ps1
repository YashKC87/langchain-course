# Workaround for azd on Windows when the user profile path contains a space
# (e.g. C:\Users\Yashaswi KC\...). Unquoted env vars like AGENT_TRANSCRIPTS
# cause: 'C:\Users\Yashaswi' is not recognized as an internal or external command.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$MessageParts
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path "azure.yaml")) {
    throw "Run this script from the azd project (azure.yaml not found in $projectRoot)"
}

$message = ($MessageParts -join " ").Trim()
if (-not $message) {
    throw "Usage: .\scripts\invoke-agent.ps1 `"Your message here`""
}

Remove-Item Env:AGENT_TRANSCRIPTS -ErrorAction SilentlyContinue
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"

$python = Join-Path $projectRoot "src\agent-framework-agent-basic-responses\.venv\Scripts\python.exe"
$invokePy = Join-Path $PSScriptRoot "invoke-responses.py"
if (Test-Path $python) {
    & $python $invokePy $MessageParts
    exit $LASTEXITCODE
}

# Fallback to azd (may fail on spaced profile paths).
& azd ai agent invoke --debug infra-ops-agent $message
