"""
Admin-only routes: CSV upload, question bank stats.
"""

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import require_admin
from app.models import User
from app.crud import process_csv_upload, get_question_bank_stats
from app.schemas import CSVUploadResult

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/upload-csv", response_model=CSVUploadResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Upload master CSV to insert questions and create immutable decks.
    Admin-only endpoint.
    """
    if not file.filename.endswith(".csv"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")
    return await process_csv_upload(file, db)


@router.get("/question-bank-stats")
def question_bank_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get overview stats of the master question bank."""
    return get_question_bank_stats(db)
