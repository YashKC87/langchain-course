# Local invoke workaround for Windows paths with spaces (same azd/cmd quoting bug).
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$MessageParts
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$message = ($MessageParts -join " ").Trim()
if (-not $message) {
    throw "Usage: .\scripts\invoke-agent-local.ps1 `"Your message here`" (agent must be running via azd ai agent run)"
}

Remove-Item Env:AGENT_TRANSCRIPTS -ErrorAction SilentlyContinue
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"

& azd ai agent invoke --local --debug $message
