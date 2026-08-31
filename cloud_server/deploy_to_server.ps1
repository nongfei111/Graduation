# Deploy to server script
$serverIp = "8.134.196.56"
$serverUser = "root"
$serverPath = "/home/smart_doorbell/server"
$localPath = "C:\Users\HP\Desktop\graduation\cloud_server\server"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Server Deploy Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server: $serverIp" -ForegroundColor Yellow
Write-Host "Local: $localPath" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Upload app.py to server? (y/n)"
if ($confirm -ne "y" -and $confirm -ne "Y") {
    Write-Host "Cancelled" -ForegroundColor Gray
    exit 0
}

Write-Host ""
Write-Host "[1/2] Uploading app.py..." -ForegroundColor Cyan
scp "$localPath\app.py" "${serverUser}@${serverIp}:${serverPath}/app.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Upload successful!" -ForegroundColor Green
} else {
    Write-Host "Upload failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Upload complete! Restart service now?" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$autoRestart = Read-Host "Auto restart service? (y/n)"
if ($autoRestart -eq "y" -or $autoRestart -eq "Y") {
    Write-Host ""
    Write-Host "[2/2] Restarting service..." -ForegroundColor Cyan
    ssh ${serverUser}@${serverIp} "pkill -f 'python.*app.py' && cd $serverPath && nohup /home/smart_doorbell/venv/bin/python app.py > /tmp/smart_doorbell.log 2>&1 &"

    Write-Host ""
    Write-Host "Waiting 3 seconds..." -ForegroundColor Cyan
    Start-Sleep -Seconds 3

    Write-Host ""
    Write-Host "[Verify] Health check..." -ForegroundColor Cyan
    $healthCheck = curl.exe -s "http://${serverIp}:5000/api/health"
    if ($healthCheck -match "ok") {
        Write-Host "Service is running!" -ForegroundColor Green
        Write-Host "Response: $healthCheck" -ForegroundColor Gray
    } else {
        Write-Host "Service may not be running. Check logs:" -ForegroundColor Red
        Write-Host "ssh root@8.134.196.56 'tail -f /tmp/smart_doorbell.log'" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Deploy Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
