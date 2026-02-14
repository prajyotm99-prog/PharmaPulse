# Test Questions Script - FIXED
$token = Get-Content "admin-token.txt"
$headers = @{ Authorization = "Bearer $token" }

Write-Host "=== Testing Your Question Bank ===" -ForegroundColor Green

# 1. List all decks
Write-Host "`n1. Available Decks:" -ForegroundColor Yellow
$decks = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/decks" -Headers $headers
$decks | ForEach-Object {
    Write-Host "  - Deck $($_.id): $($_.name) ($($_.question_count) questions)" -ForegroundColor Cyan
}

# 2. Start flashcard session with first deck
Write-Host "`n2. Starting Flashcard Session with Deck 1..." -ForegroundColor Yellow
$session = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/flashcard/start/1" `
    -Method Post -Headers $headers
Write-Host "  Session ID: $($session.session_id)" -ForegroundColor Green
Write-Host "  Total Questions: $($session.total_questions)" -ForegroundColor Green

# 3. Get first question
Write-Host "`n3. First Question:" -ForegroundColor Yellow
$questionResponse = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/flashcard/next/$($session.session_id)" `
    -Headers $headers

$q = $questionResponse.question
Write-Host "`n$($q.question_text)" -ForegroundColor White
Write-Host "  A) $($q.option_a)" -ForegroundColor Cyan
Write-Host "  B) $($q.option_b)" -ForegroundColor Cyan
Write-Host "  C) $($q.option_c)" -ForegroundColor Cyan
Write-Host "  D) $($q.option_d)" -ForegroundColor Cyan

# 4. Answer the question (example: answer C)
Write-Host "`n4. Submitting Answer..." -ForegroundColor Yellow
$answerBody = @{
    session_id = $session.session_id
    question_id = $q.id
    selected_option = "C"
    time_taken_seconds = 15
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "https://pharmapulse-m7gx.onrender.com/flashcard/answer" `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $answerBody

Write-Host "  Correct Answer: $($result.correct_option)" -ForegroundColor $(if($result.is_correct){'Green'}else{'Red'})
Write-Host "  Your Answer: $($result.selected_option)" -ForegroundColor $(if($result.is_correct){'Green'}else{'Red'})
Write-Host "  Result: $(if($result.is_correct){'✅ CORRECT'}else{'❌ WRONG'})" -ForegroundColor $(if($result.is_correct){'Green'}else{'Red'})
Write-Host "  Explanation: $($result.explanation)" -ForegroundColor Yellow

Write-Host "`n=== Test Complete! ===" -ForegroundColor Green