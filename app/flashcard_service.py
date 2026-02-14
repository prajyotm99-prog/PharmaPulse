"""
Flashcard Mastery Mode — Magoosh-style.

- Start session from a deck → shuffled copy of all deck questions.
- Wrong answers stay in queue; correct answers removed.
- Session ends when all answered correctly.
- Reopening deck starts a fresh session.
"""

import datetime as dt
import random

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import (
    Deck, DeckQuestion, FlashcardSession, FlashcardSessionQuestion,
    Question, FlashcardStatus, CorrectOptionEnum,
)
from app.schemas import (
    FlashcardSessionOut, FlashcardNextQuestion,
    FlashcardAnswerRequest, FlashcardAnswerResult, QuestionBrief,
)
from app.services.progress_service import ProgressService  # ✅ Added import


def start_flashcard_session(db: Session, user_id: int, deck_id: int) -> FlashcardSessionOut:
    """Create a new flashcard session with shuffled deck questions."""
    deck = db.query(Deck).filter(Deck.id == deck_id, Deck.active == True).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")

    deck_questions = db.query(DeckQuestion).filter(DeckQuestion.deck_id == deck_id).all()
    if not deck_questions:
        raise HTTPException(status_code=400, detail="Deck has no questions")

    # Create session
    session = FlashcardSession(user_id=user_id, deck_id=deck_id, completed=False)
    db.add(session)
    db.flush()

    # Shuffle and create session questions
    q_ids = [dq.question_id for dq in deck_questions]
    random.shuffle(q_ids)

    for order, qid in enumerate(q_ids):
        sq = FlashcardSessionQuestion(
            session_id=session.id,
            question_id=qid,
            status=FlashcardStatus.pending,
            shuffle_order=order,
        )
        db.add(sq)

    db.commit()
    db.refresh(session)

    return FlashcardSessionOut(
        session_id=session.id,
        deck_id=deck_id,
        total_questions=len(q_ids),
        pending_count=len(q_ids),
        completed=False,
    )


def get_next_flashcard(db: Session, user_id: int, session_id: int) -> FlashcardNextQuestion:
    """Get next pending question in the session."""
    session = db.query(FlashcardSession).filter(
        FlashcardSession.id == session_id,
        FlashcardSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.completed:
        return FlashcardNextQuestion(
            session_id=session_id,
            question=None,
            pending_count=0,
            completed=True,
        )

    # Get next pending question (ordered by shuffle_order)
    pending = (
        db.query(FlashcardSessionQuestion)
        .filter(
            FlashcardSessionQuestion.session_id == session_id,
            FlashcardSessionQuestion.status == FlashcardStatus.pending,
        )
        .order_by(FlashcardSessionQuestion.shuffle_order)
        .all()
    )

    if not pending:
        session.completed = True
        db.commit()
        return FlashcardNextQuestion(
            session_id=session_id,
            question=None,
            pending_count=0,
            completed=True,
        )

    sq = pending[0]
    q = sq.question

    return FlashcardNextQuestion(
        session_id=session_id,
        question=QuestionBrief(
            id=q.id,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            chapter=q.chapter,
            category=q.category.value if hasattr(q.category, 'value') else q.category,
            difficulty=q.difficulty,
        ),
        pending_count=len(pending),
        completed=False,
    )


def answer_flashcard(
    db: Session, user_id: int, req: FlashcardAnswerRequest
) -> FlashcardAnswerResult:
    """Answer a flashcard question. Correct → removed; Wrong → stays in queue."""
    session = db.query(FlashcardSession).filter(
        FlashcardSession.id == req.session_id,
        FlashcardSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.completed:
        raise HTTPException(status_code=400, detail="Session already completed")

    sq = (
        db.query(FlashcardSessionQuestion)
        .filter(
            FlashcardSessionQuestion.session_id == req.session_id,
            FlashcardSessionQuestion.question_id == req.question_id,
        )
        .first()
    )
    if not sq:
        raise HTTPException(status_code=404, detail="Question not in this session")

    question = db.query(Question).filter(Question.id == req.question_id).first()
    is_correct = req.selected_option == question.correct_option.value

    sq.last_attempted_at = dt.datetime.utcnow()

    # ✅ ADDED: Track progress for mastery system
    ProgressService.record_answer(
        db=db,
        user_id=user_id,
        question_id=req.question_id,
        is_correct=is_correct
    )

    if is_correct:
        sq.status = FlashcardStatus.correct
    else:
        # Move to end of queue by giving it a higher shuffle_order
        max_order = (
            db.query(FlashcardSessionQuestion.shuffle_order)
            .filter(FlashcardSessionQuestion.session_id == req.session_id)
            .order_by(FlashcardSessionQuestion.shuffle_order.desc())
            .first()
        )
        sq.shuffle_order = (max_order[0] + 1) if max_order else 0

    db.flush()

    # Count remaining pending
    pending_count = (
        db.query(FlashcardSessionQuestion)
        .filter(
            FlashcardSessionQuestion.session_id == req.session_id,
            FlashcardSessionQuestion.status == FlashcardStatus.pending,
        )
        .count()
    )

    completed = pending_count == 0
    if completed:
        session.completed = True

    db.commit()

    return FlashcardAnswerResult(
        correct=is_correct,
        correct_option=question.correct_option.value,
        explanation=question.explanation,
        pending_count=pending_count,
        completed=completed,
    )