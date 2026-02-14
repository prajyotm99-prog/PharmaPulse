# Test PharmaPulse Production API

Write-Host "=== Testing PharmaPulse API ===" -ForegroundColor Green

# 1. Register a new user
Write-Host "`n1. Registering new user..." -ForegroundColor Yellow
try {
    $registerResponse = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/auth/register" `
        -Method Post `
        -ContentType "application/json" `
        -Body '{"email":"poweruser@test.com","password":"test123"}'
    
    Write-Host "✅ User registered successfully!" -ForegroundColor Green
    Write-Host "User ID: $($registerResponse.id)"
    Write-Host "Email: $($registerResponse.email)"
    Write-Host "Role: $($registerResponse.role)"
} catch {
    Write-Host "⚠️ Registration failed (user might already exist)" -ForegroundColor Yellow
}

# 2. Login and get token
Write-Host "`n2. Logging in..." -ForegroundColor Yellow
$loginResponse = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/auth/login" `
    -Method Post `
    -ContentType "application/json" `
    -Body '{"email":"poweruser@test.com","password":"test123"}'

$token = $loginResponse.access_token
Write-Host "✅ Login successful!" -ForegroundColor Green
Write-Host "Token: $token"

# 3. Get current user info
Write-Host "`n3. Getting user info..." -ForegroundColor Yellow
$userInfo = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/auth/me" `
    -Method Get `
    -Headers @{Authorization="Bearer $token"}

Write-Host "✅ User info retrieved!" -ForegroundColor Green
Write-Host "ID: $($userInfo.id)"
Write-Host "Email: $($userInfo.email)"
Write-Host "Role: $($userInfo.role)"
Write-Host "Created: $($userInfo.created_at)"

# 4. Test health endpoint
Write-Host "`n4. Checking API health..." -ForegroundColor Yellow
$health = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/"
Write-Host "✅ API Status: $($health.status)" -ForegroundColor Green
Write-Host "Service: $($health.service)"

Write-Host "`n=== All tests completed! ===" -ForegroundColor Green