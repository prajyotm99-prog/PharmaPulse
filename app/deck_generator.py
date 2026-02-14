from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from typing import List, Dict
import random
from app.models import Question, UserQuestionProgress
from app.schemas import QuestionResponse

# Chapter weightages (must sum to 100%)
CHAPTER_WEIGHTS = {
    "Pharmacology": 0.30,      # 6 questions
    "Pharmaceutics": 0.20,     # 4 questions
    "Pharmaceutical Chemistry": 0.20,  # 4 questions
    "Microbiology": 0.10,      # 2 questions
    "Pharmacognosy": 0.10,     # 2 questions
    "Drug Laws": 0.05,         # 1 question
    "Clinical Pharmacy": 0.05  # 1 question
}

DECK_SIZE = 20

class DeckGenerator:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        
    def generate_deck(self) -> List[QuestionResponse]:
        """
        Generate exactly 20 questions following strict rules:
        1. Respect chapter weightage
        2. Exclude already mastered questions (first_try_correct=True)
        3. No duplicates in same deck
        4. Fill gaps from high-priority chapters if needed
        """
        
        # Calculate target count per chapter
        target_counts = self._calculate_chapter_targets()
        
        # Get mastered question IDs for this user
        mastered_ids = self._get_mastered_question_ids()
        
        # Pull questions per chapter
        selected_questions = []
        remaining_needed = DECK_SIZE
        
        for chapter, target_count in target_counts.items():
            if remaining_needed <= 0:
                break
                
            questions = self._pull_chapter_questions(
                chapter=chapter,
                count=target_count,
                exclude_ids=mastered_ids + [q.id for q in selected_questions]
            )
            
            selected_questions.extend(questions)
            remaining_needed -= len(questions)
        
        # If we're short, fill from highest weight chapters
        if len(selected_questions) < DECK_SIZE:
            selected_questions = self._fill_remaining_slots(
                current_questions=selected_questions,
                mastered_ids=mastered_ids,
                needed=DECK_SIZE - len(selected_questions)
            )
        
        # Ensure exactly 20 (trim if somehow got more)
        if len(selected_questions) > DECK_SIZE:
            selected_questions = selected_questions[:DECK_SIZE]
        
        # Shuffle to randomize order
        random.shuffle(selected_questions)
        
        # Convert to response schema
        return [QuestionResponse.from_orm(q) for q in selected_questions]
    
    def _calculate_chapter_targets(self) -> Dict[str, int]:
        """Calculate how many questions needed per chapter"""
        targets = {}
        total_allocated = 0
        
        # Sort by weight descending
        sorted_chapters = sorted(
            CHAPTER_WEIGHTS.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for chapter, weight in sorted_chapters[:-1]:
            count = int(DECK_SIZE * weight)
            targets[chapter] = count
            total_allocated += count
        
        # Give remainder to last chapter
        last_chapter = sorted_chapters[-1][0]
        targets[last_chapter] = DECK_SIZE - total_allocated
        
        return targets
    
    def _get_mastered_question_ids(self) -> List[int]:
        """Get IDs of questions user got correct on first try"""
        mastered = self.db.query(UserQuestionProgress.question_id).filter(
            and_(
                UserQuestionProgress.user_id == self.user_id,
                UserQuestionProgress.first_try_correct == True
            )
        ).all()
        
        return [q.question_id for q in mastered]
    
    def _pull_chapter_questions(
        self,
        chapter: str,
        count: int,
        exclude_ids: List[int]
    ) -> List[Question]:
        """Pull questions from specific chapter, excluding mastered ones"""
        
        query = self.db.query(Question).filter(
            Question.chapter == chapter
        )
        
        if exclude_ids:
            query = query.filter(Question.id.notin_(exclude_ids))
        
        # Random order
        questions = query.order_by(func.random()).limit(count).all()
        
        return questions
    
    def _fill_remaining_slots(
        self,
        current_questions: List[Question],
        mastered_ids: List[int],
        needed: int
    ) -> List[Question]:
        """
        Fill remaining slots from high-priority chapters
        when some chapters don't have enough questions
        """
        if needed <= 0:
            return current_questions
        
        exclude_ids = mastered_ids + [q.id for q in current_questions]
        
        # Get from highest weight chapters first
        sorted_chapters = sorted(
            CHAPTER_WEIGHTS.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        additional = []
        for chapter, _ in sorted_chapters:
            if len(additional) >= needed:
                break
            
            questions = self._pull_chapter_questions(
                chapter=chapter,
                count=needed - len(additional),
                exclude_ids=exclude_ids + [q.id for q in additional]
            )
            additional.extend(questions)
        
        return current_questions + additional