$backendPid = $null
$listenerLine = netstat -ano -p tcp | Where-Object {
  $_ -match '^\s*TCP\s+\S+:8000\s+\S+\s+LISTENING\s+(\d+)\s*$'
} | Select-Object -First 1

if ($listenerLine -and $listenerLine -match 'LISTENING\s+(\d+)\s*$') {
  $backendPid = [int]$matches[1]
}

if ($backendPid) {
  Stop-Process -Id $backendPid -Force
  Start-Sleep -Seconds 1
  Write-Host "Killed backend PID $backendPid on port 8000"
} else {
  Write-Host "No backend running on port 8000"
}

$python = "$PSScriptRoot\venv\Scripts\python.exe"
$stdoutLog = "$PSScriptRoot\backend_stdout.log"
$stderrLog = "$PSScriptRoot\backend_stderr.log"

if (-not (Test-Path $python)) {
  Write-Error "Missing virtual environment at $python"
  exit 1
}

if (Test-Path $stdoutLog) {
  Remove-Item $stdoutLog -Force
}

if (Test-Path $stderrLog) {
  Remove-Item $stderrLog -Force
}

$process = Start-Process -FilePath $python `
  -ArgumentList "-m","uvicorn","main:app","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory $PSScriptRoot `
  -RedirectStandardOutput $stdoutLog `
  -RedirectStandardError $stderrLog `
  -PassThru

Start-Sleep -Seconds 3

try {
  $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
  Write-Host "Backend started successfully on http://127.0.0.1:8000 (PID $($process.Id))"
  Write-Host $health.Content
  exit 0
} catch {
  Write-Error "Backend failed to become healthy. Check logs:"
  Write-Host "STDOUT: $stdoutLog"
  Write-Host "STDERR: $stderrLog"
  if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
  }
  exit 1
}
