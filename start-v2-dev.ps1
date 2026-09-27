[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $RepoRoot '.runtime'
$StatePath = Join-Path $RuntimeDir 'v2-dev-processes.json'
$BackendPort = 8011
$FrontendPort = 6005
$BackendHealthUrl = "http://127.0.0.1:$BackendPort/api/health"
$FrontendUrl = "http://127.0.0.1:$FrontendPort/"
$BackendLauncher = Join-Path $RepoRoot 'bowei_ai_dashboard\start-backend-v2-dev.bat'
$FrontendLauncher = Join-Path $RepoRoot 'frontend-v2\start-frontend-v2-dev.bat'

function Test-ListeningPort([int] $Port) {
  return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1)
}

function Assert-LaunchFile([string] $Path) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "Launch file does not exist: $Path"
  }
}

function Save-State([object[]] $Processes) {
  $state = [ordered]@{
    startedAt = (Get-Date).ToString('o')
    processes = $Processes
    logs = [ordered]@{
      backend = (Join-Path $RuntimeDir 'backend.log')
      backendError = (Join-Path $RuntimeDir 'backend.err.log')
      frontend = (Join-Path $RuntimeDir 'frontend.log')
      frontendError = (Join-Path $RuntimeDir 'frontend.err.log')
    }
  }
  $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $StatePath -Encoding utf8
}

function Wait-BackendReady([int] $ProcessId) {
  $deadline = (Get-Date).AddSeconds(120)
  do {
    if ($null -eq (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
      throw "后端进程已退出：PID=$ProcessId；请查看 .runtime\backend.log 和 .runtime\backend.err.log"
    }
    try {
      $health = Invoke-RestMethod -Uri $BackendHealthUrl -Method Get -TimeoutSec 5
      if ($health.status -eq 'ok') { return }
    } catch {
      # The backend may still be starting or installing its local environment.
    }
    Start-Sleep -Seconds 1
  } while ((Get-Date) -lt $deadline)
  throw "后端未在 120 秒内就绪：$BackendHealthUrl；请查看 .runtime\backend.log 和 .runtime\backend.err.log"
}

function Wait-FrontendReady([int] $ProcessId) {
  $deadline = (Get-Date).AddSeconds(120)
  do {
    if ($null -eq (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
      throw "V2 前端进程已退出：PID=$ProcessId；请查看 .runtime\frontend.log 和 .runtime\frontend.err.log"
    }
    try {
      $response = Invoke-WebRequest -Uri $FrontendUrl -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -eq 200) { return }
    } catch {
      # The Vite process may still be starting or installing dependencies.
    }
    Start-Sleep -Seconds 1
  } while ((Get-Date) -lt $deadline)
  throw "V2 前端未在 120 秒内就绪：$FrontendUrl；请查看 .runtime\frontend.log 和 .runtime\frontend.err.log"
}

if (Test-Path -LiteralPath $StatePath) {
  throw "An existing V2 state file was found: $StatePath. Run stop-frontend-v2.bat first."
}

if (Test-ListeningPort $BackendPort) {
  throw "Port $BackendPort is already in use; V2 backend was not started."
}

if (Test-ListeningPort $FrontendPort) {
  throw "Port $FrontendPort is already in use; V2 frontend was not started."
}

Assert-LaunchFile $BackendLauncher
Assert-LaunchFile $FrontendLauncher
New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null

$backendLog = Join-Path $RuntimeDir 'backend.log'
$backendErrLog = Join-Path $RuntimeDir 'backend.err.log'
$frontendLog = Join-Path $RuntimeDir 'frontend.log'
$frontendErrLog = Join-Path $RuntimeDir 'frontend.err.log'
Remove-Item -LiteralPath $backendLog, $backendErrLog, $frontendLog, $frontendErrLog -Force -ErrorAction SilentlyContinue

$trackedProcesses = @()
try {
  $backendProcess = Start-Process -FilePath 'cmd.exe' `
    -ArgumentList @('/d', '/c', "call `"$BackendLauncher`"") `
    -WorkingDirectory (Split-Path -Parent $BackendLauncher) `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrLog `
    -WindowStyle Hidden `
    -PassThru
  $trackedProcesses += [pscustomobject]@{ role = 'backend'; id = $backendProcess.Id }
  Save-State $trackedProcesses

  Write-Output "Backend process started; waiting for $BackendHealthUrl"
  Wait-BackendReady $backendProcess.Id

  $frontendProcess = Start-Process -FilePath 'cmd.exe' `
    -ArgumentList @('/d', '/c', "call `"$FrontendLauncher`"") `
    -WorkingDirectory (Split-Path -Parent $FrontendLauncher) `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendErrLog `
    -WindowStyle Hidden `
    -PassThru
  $trackedProcesses += [pscustomobject]@{ role = 'frontend'; id = $frontendProcess.Id }
  Save-State $trackedProcesses

  Write-Output "Frontend process started; waiting for $FrontendUrl"
  Wait-FrontendReady $frontendProcess.Id

  Start-Process $FrontendUrl | Out-Null
  Write-Output "V2 is ready: $FrontendUrl"
  Write-Output "Stop services with: $RepoRoot\stop-frontend-v2.bat"
} catch {
  Write-Error $_
  $stopScript = Join-Path $RepoRoot 'stop-v2-dev.ps1'
  if (Test-Path -LiteralPath $stopScript) {
    & $stopScript
  }
  exit 1
}
