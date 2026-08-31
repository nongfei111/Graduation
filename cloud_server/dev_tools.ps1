# Developer Tools Script
$SERVER = "http://8.134.196.56:5000"
$DEV_TOKEN = "dev-secret-2026"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Developer Tools" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Select operation:" -ForegroundColor Green
Write-Host "  1. List all users"
Write-Host "  2. Reset admin password"
Write-Host "  3. Reset testuser password"
Write-Host "  4. Custom reset password"
Write-Host "  5. Health check"
Write-Host "  6. Test login"
Write-Host ""

$choice = Read-Host "Enter option (1-6)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "[Listing users]..." -ForegroundColor Cyan
        $headers = @{ "X-Dev-Token" = $DEV_TOKEN }
        $result = Invoke-RestMethod -Uri "$SERVER/api/dev/users" -Headers $headers -Method Get
        $result | ConvertTo-Json -Depth 10
    }
    "2" {
        Write-Host ""
        Write-Host "[Reset admin password to admin123456]..." -ForegroundColor Cyan
        $headers = @{ "X-Dev-Token" = $DEV_TOKEN; "Content-Type" = "application/json" }
        $body = @{ username = "admin"; password = "admin123456" } | ConvertTo-Json
        $result = Invoke-RestMethod -Uri "$SERVER/api/dev/reset-password" -Headers $headers -Method Post -Body $body
        $result | ConvertTo-Json
    }
    "3" {
        Write-Host ""
        Write-Host "[Reset testuser password to test123456]..." -ForegroundColor Cyan
        $headers = @{ "X-Dev-Token" = $DEV_TOKEN; "Content-Type" = "application/json" }
        $body = @{ username = "testuser"; password = "test123456" } | ConvertTo-Json
        $result = Invoke-RestMethod -Uri "$SERVER/api/dev/reset-password" -Headers $headers -Method Post -Body $body
        $result | ConvertTo-Json
    }
    "4" {
        $username = Read-Host "Username"
        $password = Read-Host "New password"

        Write-Host ""
        Write-Host "[Reset $username password]..." -ForegroundColor Cyan
        $headers = @{ "X-Dev-Token" = $DEV_TOKEN; "Content-Type" = "application/json" }
        $body = @{ username = $username; password = $password } | ConvertTo-Json
        $result = Invoke-RestMethod -Uri "$SERVER/api/dev/reset-password" -Headers $headers -Method Post -Body $body
        $result | ConvertTo-Json
    }
    "5" {
        Write-Host ""
        Write-Host "[Health check]..." -ForegroundColor Cyan
        $result = Invoke-RestMethod -Uri "$SERVER/api/health" -Method Get
        $result | ConvertTo-Json
    }
    "6" {
        $username = Read-Host "Username"
        $password = Read-Host "Password"

        Write-Host ""
        Write-Host "[Testing login]..." -ForegroundColor Cyan
        $headers = @{ "Content-Type" = "application/json" }
        $body = @{ username = $username; password = $password } | ConvertTo-Json

        try {
            $result = Invoke-RestMethod -Uri "$SERVER/api/auth/login" -Headers $headers -Method Post -Body $body
            $result | ConvertTo-Json -Depth 10

            if ($result.success -eq $true) {
                Write-Host ""
                Write-Host "Login successful!" -ForegroundColor Green
                Write-Host "Token: $($result.access_token)" -ForegroundColor Gray
            }
        } catch {
            Write-Host "Login failed: $_" -ForegroundColor Red
        }
    }
    default {
        Write-Host "Invalid option" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
