# Admin credentials (update these with your actual values)
$adminEmail = "admin@pharmapulse.com"
$adminPassword = "AdminPass123!"  # Use your actual password

Write-Host "=== Admin Login Test ===" -ForegroundColor Cyan

# 1. Login as admin
Write-Host "`nLogging in as admin..." -ForegroundColor Yellow
$loginResponse = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/auth/login" `
    -Method Post `
    -ContentType "application/json" `
    -Body "{`"email`":`"$adminEmail`",`"password`":`"$adminPassword`"}"

$adminToken = $loginResponse.access_token
Write-Host "✅ Admin login successful!" -ForegroundColor Green
Write-Host "`nAdmin Token:" -ForegroundColor Cyan
Write-Host $adminToken -ForegroundColor White

# Save token to file
$adminToken | Out-File -FilePath "admin-token.txt"
Write-Host "`n✅ Token saved to: admin-token.txt" -ForegroundColor Green

# 2. Verify admin access
Write-Host "`nVerifying admin access..." -ForegroundColor Yellow
$headers = @{
    Authorization = "Bearer $adminToken"
}

$adminInfo = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/auth/me" `
    -Method Get `
    -Headers $headers

Write-Host "✅ Admin verified!" -ForegroundColor Green
Write-Host "`nAdmin Info:" -ForegroundColor Cyan
Write-Host "ID: $($adminInfo.id)"
Write-Host "Email: $($adminInfo.email)"
Write-Host "Role: $($adminInfo.role)" -ForegroundColor Yellow
Write-Host "Created: $($adminInfo.created_at)"

Write-Host "`n=== Admin setup complete! ===" -ForegroundColor Green