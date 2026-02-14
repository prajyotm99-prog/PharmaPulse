from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import csv
import io
from app.database import get_db
from app.auth import get_current_user
from app.models import User, Question

router = APIRouter(prefix="/admin", tags=["Admin"])

# Required CSV headers - EXACT match required
REQUIRED_HEADERS = [
    "chapter",
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option",
    "difficulty",
    "explanation"
]

def verify_admin(current_user: User = Depends(get_current_user)):
    """Verify user has admin role"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

@router.post("/upload-csv")
async def upload_questions_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(verify_admin)
):
    """
    Upload questions via CSV with strict validation
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Read CSV content
        contents = await file.read()
        csv_data = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        # Validate headers
        actual_headers = csv_reader.fieldnames
        if actual_headers != REQUIRED_HEADERS:
            missing = set(REQUIRED_HEADERS) - set(actual_headers)
            extra = set(actual_headers) - set(REQUIRED_HEADERS)
            
            error_msg = "CSV header mismatch.\n"
            error_msg += f"Expected exact headers: {REQUIRED_HEADERS}\n"
            if missing:
                error_msg += f"Missing: {list(missing)}\n"
            if extra:
                error_msg += f"Extra: {list(extra)}"
            
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Process rows
        total_rows = 0
        inserted = 0
        duplicates = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):
            total_rows += 1
            
            try:
                # Check for duplicate
                existing = db.query(Question).filter(
                    Question.question_text == row['question_text']
                ).first()
                
                if existing:
                    duplicates += 1
                    continue
                
                # Create question
                question = Question(
                    chapter=row['chapter'],
                    question_text=row['question_text'],
                    option_a=row['option_a'],
                    option_b=row['option_b'],
                    option_c=row['option_c'],
                    option_d=row['option_d'],
                    correct_option=row['correct_option'],
                    difficulty=row['difficulty'],
                    explanation=row['explanation']
                )
                
                db.add(question)
                inserted += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        db.commit()
        
        return {
            "total_rows": total_rows,
            "inserted": inserted,
            "duplicates_skipped": duplicates,
            "errors": errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")