# Launches the backend as a single instance.
# Refuses to start if the port is already taken (anti-phantom guard).
param([int]$Port = 8000)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $ownerPid = ($conn | Select-Object -First 1).OwningProcess
    $owner = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
    Write-Host "[run-backend] Port $Port is already in use by PID $ownerPid ($($owner.ProcessName))." -ForegroundColor Yellow
    Write-Host "[run-backend] The backend is probably already running: http://127.0.0.1:$Port/api/health" -ForegroundColor Yellow
    Write-Host "[run-backend] NOT starting a duplicate. Use stop-backend.ps1 first if you need a restart." -ForegroundColor Yellow
    exit 1
}

$proc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "$Port" `
    -WindowStyle Hidden -WorkingDirectory (Join-Path $root "backend") -PassThru
Write-Host "[run-backend] Started uvicorn (tree root PID $($proc.Id)) on http://127.0.0.1:$Port" -ForegroundColor Green

Start-Sleep -Seconds 5
try {
    $health = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 10
    Write-Host "[run-backend] Health: $($health | ConvertTo-Json -Compress)" -ForegroundColor Green
} catch {
    Write-Host "[run-backend] Backend did not answer /api/health yet (still booting?)." -ForegroundColor Yellow
}
