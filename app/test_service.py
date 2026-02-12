"""
Full-Length Test Mode — chapter-weighted generation, negative marking, breakdown.
"""

import datetime as dt
from typing import Dict, List

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from app.models import (
    Question, TestAttempt, TestQuestion, TestAnswer,
    CorrectOptionEnum,
)
from app.schemas import (
    TestStartResponse, TestAnswerRequest, TestAnswerResult,
    TestSubmitResponse, ChapterScore, QuestionBrief,
)

# ── Chapter Weightage ──────────────────────────────────

CHAPTER_WEIGHTAGE = {
    "Pharmacology": 0.32,
    "Pharmaceutics": 0.20,
    "Drug Laws": 0.15,
    "Microbiology": 0.10,
    "Pharmaceutical Chemistry": 0.10,
    "Hospital Pharmacy": 0.07,
    "Reasoning": 0.06,
}

DEFAULT_TOTAL_QUESTIONS = 100
MARKS_PER_CORRECT = 1.0
NEGATIVE_MARK_PER_WRONG = 0.25


def generate_full_test(db: Session, user_id: int, total: int = None) -> TestStartResponse:
    """Generate a full-length test from master question bank using chapter weightage."""
    total = total or DEFAULT_TOTAL_QUESTIONS

    selected_ids: List[int] = []

    for chapter, weight in CHAPTER_WEIGHTAGE.items():
        count = max(1, round(total * weight))

        q_ids = (
            db.query(Question.id)
            .filter(Question.chapter == chapter)
            .order_by(func.random())
            .limit(count)
            .all()
        )
        selected_ids.extend([qid[0] for qid in q_ids])

    if not selected_ids:
        raise HTTPException(
            status_code=400,
            detail="Not enough questions in the bank to generate a test.",
        )

    # Trim to exact total if we overshot due to rounding
    if len(selected_ids) > total:
        selected_ids = selected_ids[:total]

    # Create attempt
    attempt = TestAttempt(
        user_id=user_id,
        total_questions=len(selected_ids),
        completed=False,
    )
    db.add(attempt)
    db.flush()

    # Lock question order
    for order, qid in enumerate(selected_ids):
        tq = TestQuestion(
            attempt_id=attempt.id,
            question_id=qid,
            question_order=order,
        )
        db.add(tq)

    db.commit()
    db.refresh(attempt)

    # Fetch questions in order
    test_questions = (
        db.query(TestQuestion)
        .filter(TestQuestion.attempt_id == attempt.id)
        .order_by(TestQuestion.question_order)
        .all()
    )

    questions = []
    for tq in test_questions:
        q = tq.question
        questions.append(QuestionBrief(
            id=q.id,
            question_text=q.question_text,
            option_a=q.option_a,
            option_b=q.option_b,
            option_c=q.option_c,
            option_d=q.option_d,
            chapter=q.chapter,
            category=q.category.value if hasattr(q.category, 'value') else q.category,
            difficulty=q.difficulty,
        ))

    return TestStartResponse(
        attempt_id=attempt.id,
        total_questions=len(selected_ids),
        questions=questions,
    )


def answer_test_question(
    db: Session, user_id: int, req: TestAnswerRequest
) -> TestAnswerResult:
    """Record answer for a single test question."""
    attempt = db.query(TestAttempt).filter(
        TestAttempt.id == req.attempt_id,
        TestAttempt.user_id == user_id,
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    if attempt.completed:
        raise HTTPException(status_code=400, detail="Test already submitted")

    # Verify question belongs to this attempt
    tq = db.query(TestQuestion).filter(
        TestQuestion.attempt_id == req.attempt_id,
        TestQuestion.question_id == req.question_id,
    ).first()
    if not tq:
        raise HTTPException(status_code=404, detail="Question not in this test")

    # Check for existing answer (allow update)
    existing = db.query(TestAnswer).filter(
        TestAnswer.attempt_id == req.attempt_id,
        TestAnswer.question_id == req.question_id,
    ).first()

    question = db.query(Question).filter(Question.id == req.question_id).first()
    is_correct = req.selected_option == question.correct_option.value

    if existing:
        existing.selected_option = CorrectOptionEnum(req.selected_option)
        existing.is_correct = is_correct
        existing.answered_at = dt.datetime.utcnow()
    else:
        ans = TestAnswer(
            attempt_id=req.attempt_id,
            question_id=req.question_id,
            selected_option=CorrectOptionEnum(req.selected_option),
            is_correct=is_correct,
        )
        db.add(ans)

    db.commit()

    return TestAnswerResult(
        correct=is_correct,
        correct_option=question.correct_option.value,
        explanation=question.explanation,
    )


def submit_test(db: Session, user_id: int, attempt_id: int) -> TestSubmitResponse:
    """Submit test, calculate scores with negative marking and chapter breakdown."""
    attempt = db.query(TestAttempt).filter(
        TestAttempt.id == attempt_id,
        TestAttempt.user_id == user_id,
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Test attempt not found")
    if attempt.completed:
        raise HTTPException(status_code=400, detail="Test already submitted")

    # Get all test questions
    test_questions = (
        db.query(TestQuestion)
        .filter(TestQuestion.attempt_id == attempt_id)
        .all()
    )
    all_q_ids = {tq.question_id for tq in test_questions}

    # Get all answers
    answers = (
        db.query(TestAnswer)
        .filter(TestAnswer.attempt_id == attempt_id)
        .all()
    )
    answer_map: Dict[int, TestAnswer] = {a.question_id: a for a in answers}

    # Calculate scores
    correct = sum(1 for a in answers if a.is_correct)
    wrong = sum(1 for a in answers if not a.is_correct)
    unanswered = len(all_q_ids) - len(answers)

    score = correct * MARKS_PER_CORRECT
    neg = wrong * NEGATIVE_MARK_PER_WRONG
    final = score - neg

    # Chapter breakdown
    chapter_stats: Dict[str, dict] = {}
    for tq in test_questions:
        q = tq.question
        ch = q.chapter
        if ch not in chapter_stats:
            chapter_stats[ch] = {"total": 0, "correct": 0, "wrong": 0, "unanswered": 0}
        chapter_stats[ch]["total"] += 1

        ans = answer_map.get(q.id)
        if ans is None:
            chapter_stats[ch]["unanswered"] += 1
        elif ans.is_correct:
            chapter_stats[ch]["correct"] += 1
        else:
            chapter_stats[ch]["wrong"] += 1

    chapter_breakdown = []
    for ch, stats in chapter_stats.items():
        ch_score = stats["correct"] * MARKS_PER_CORRECT - stats["wrong"] * NEGATIVE_MARK_PER_WRONG
        chapter_breakdown.append(ChapterScore(
            chapter=ch,
            total=stats["total"],
            correct=stats["correct"],
            wrong=stats["wrong"],
            unanswered=stats["unanswered"],
            score=round(ch_score, 2),
        ))

    # Update attempt
    attempt.correct_count = correct
    attempt.wrong_count = wrong
    attempt.unanswered_count = unanswered
    attempt.score = round(score, 2)
    attempt.negative_marks = round(neg, 2)
    attempt.final_score = round(final, 2)
    attempt.completed = True
    attempt.completed_at = dt.datetime.utcnow()

    db.commit()

    return TestSubmitResponse(
        attempt_id=attempt_id,
        total_questions=attempt.total_questions,
        correct_count=correct,
        wrong_count=wrong,
        unanswered_count=unanswered,
        score=round(score, 2),
        negative_marks=round(neg, 2),
        final_score=round(final, 2),
        chapter_breakdown=chapter_breakdown,
    )


def get_user_test_history(db: Session, user_id: int):
    """Return all test attempts for a user."""
    return (
        db.query(TestAttempt)
        .filter(TestAttempt.user_id == user_id)
        .order_by(TestAttempt.started_at.desc())
        .all()
    )
