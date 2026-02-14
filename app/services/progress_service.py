from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import UserQuestionProgress, Question
from datetime import datetime

class ProgressService:
    
    @staticmethod
    def record_answer(
        db: Session,
        user_id: int,
        question_id: int,
        is_correct: bool
    ):
        """
        Record user's answer and update mastery tracking
        """
        # Get or create progress record
        progress = db.query(UserQuestionProgress).filter(
            and_(
                UserQuestionProgress.user_id == user_id,
                UserQuestionProgress.question_id == question_id
            )
        ).first()
        
        if not progress:
            progress = UserQuestionProgress(
                user_id=user_id,
                question_id=question_id,
                attempts=0,
                first_try_correct=False
            )
            db.add(progress)
        
        # Update attempts
        progress.attempts += 1
        progress.last_attempted = datetime.utcnow()
        
        # Track first-try correctness
        if progress.attempts == 1 and is_correct:
            progress.first_try_correct = True
        
        db.commit()
        db.refresh(progress)
        
        return progress
    
    @staticmethod
    def get_deck_results(
        db: Session,
        user_id: int,
        question_ids: list
    ) -> dict:
        """
        Calculate deck completion results
        """
        progress_records = db.query(UserQuestionProgress).filter(
            and_(
                UserQuestionProgress.user_id == user_id,
                UserQuestionProgress.question_id.in_(question_ids)
            )
        ).all()
        
        first_try_correct_count = sum(
            1 for p in progress_records if p.first_try_correct
        )
        
        total_attempts = sum(p.attempts for p in progress_records)
        
        accuracy = (first_try_correct_count / 20) * 100 if len(question_ids) == 20 else 0
        
        # Determine mastery level
        if first_try_correct_count >= 18:
            mastery_level = "Mastery"
        elif first_try_correct_count >= 14:
            mastery_level = "Good"
        else:
            mastery_level = "Needs Revision"
        
        return {
            "total_questions": 20,
            "first_try_correct": first_try_correct_count,
            "accuracy_percent": round(accuracy, 1),
            "total_attempts": total_attempts,
            "mastery_level": mastery_level
        }