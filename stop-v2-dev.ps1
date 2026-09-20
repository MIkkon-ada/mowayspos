[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$StatePath = Join-Path $RepoRoot '.runtime\v2-dev-processes.json'

if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
  Write-Output 'No V2 state file found; no processes were stopped.'
  exit 0
}

$state = Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json
foreach ($processInfo in @($state.processes)) {
  $processId = 0
  if (-not [int]::TryParse([string]$processInfo.id, [ref]$processId)) { continue }
  $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
  if ($null -eq $process) { continue }

  & taskkill.exe /PID $processId /T /F *> $null
  Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
  Write-Output "Stopped $($processInfo.role) process PID=$processId"
}

Remove-Item -LiteralPath $StatePath -Force -ErrorAction SilentlyContinue
Write-Output 'V2 state file removed.'
