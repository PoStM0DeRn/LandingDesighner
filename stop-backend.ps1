# Stops backend processes listening on the port. Only kills python/uvicorn.
param([int]$Port = 8000)

$ErrorActionPreference = "Stop"

$conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if (-not $conn) {
    Write-Host "[stop-backend] Nothing is listening on port $Port." -ForegroundColor Yellow
    exit 0
}

$ownerPids = $conn | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $ownerPids) {
    $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { "<gone>" }
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue).CommandLine
    $isOurs = ($name -match "python") -or ($cmd -match "uvicorn")
    if (-not $isOurs) {
        Write-Host "[stop-backend] PID $procId ($name) is NOT a backend process - refusing to kill." -ForegroundColor Red
        continue
    }
    Write-Host "[stop-backend] Killing backend tree PID $procId ($name)..." -ForegroundColor Green
    taskkill /PID $procId /T /F | Out-Null
}

Start-Sleep -Seconds 2
$still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($still) {
    Write-Host "[stop-backend] WARNING: port $Port is still busy." -ForegroundColor Red
    exit 1
}
Write-Host "[stop-backend] Port $Port is free." -ForegroundColor Green
