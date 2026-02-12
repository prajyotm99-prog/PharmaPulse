"""
Daily Test Mode — 10 questions, one test per date, shared across users.
"""

import datetime as dt

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException

from app.models import (
    Question, DailyTest, DailyTestQuestion, DailyTestAttempt, DailyTestAnswer,
    CorrectOptionEnum, CategoryEnum,
)
from app.schemas import (
    DailyTestOut, DailyTestAnswerRequest, DailyTestSubmitResponse,
    QuestionBrief,
)

# ── Daily Test Distribution ────────────────────────────

DAILY_DISTRIBUTION = [
    ("Pharmacology", 3, None),
    ("Pharmaceutics", 2, None),
    ("Drug Laws", 2, None),
    ("Microbiology", 1, None),        # Micro/Chem slot 1
    ("Pharmaceutical Chemistry", 0, None),  # handled below
    ("Hospital Pharmacy", 1, None),
    (None, 1, ["current_affairs", "case_law"]),  # Current Affairs / Case Law
]

# Simplified: 3 Pharma + 2 Pharmaceutics + 2 Drug Laws + 1 Micro/Chem + 1 Hospital + 1 CA/CaseLaw = 10


def _get_or_create_daily_test(db: Session, test_date: str) -> DailyTest:
    """Get existing daily test or create a new one for the date."""
    existing = db.query(DailyTest).filter(DailyTest.test_date == test_date).first()
    if existing:
        return existing

    # Generate new daily test
    selected_ids = []

    # Pharmacology: 3
    ids = _random_questions_by_chapter(db, "Pharmacology", 3)
    selected_ids.extend(ids)

    # Pharmaceutics: 2
    ids = _random_questions_by_chapter(db, "Pharmaceutics", 2)
    selected_ids.extend(ids)

    # Drug Laws: 2
    ids = _random_questions_by_chapter(db, "Drug Laws", 2)
    selected_ids.extend(ids)

    # Microbiology or Pharmaceutical Chemistry: 1
    micro_chem_ids = (
        db.query(Question.id)
        .filter(Question.chapter.in_(["Microbiology", "Pharmaceutical Chemistry"]))
        .order_by(func.random())
        .limit(1)
        .all()
    )
    selected_ids.extend([q[0] for q in micro_chem_ids])

    # Hospital Pharmacy: 1
    ids = _random_questions_by_chapter(db, "Hospital Pharmacy", 1)
    selected_ids.extend(ids)

    # Current Affairs / Case Law: 1
    ca_ids = (
        db.query(Question.id)
        .filter(Question.category.in_([CategoryEnum.current_affairs, CategoryEnum.case_law]))
        .order_by(func.random())
        .limit(1)
        .all()
    )
    selected_ids.extend([q[0] for q in ca_ids])

    if len(selected_ids) < 1:
        raise HTTPException(
            status_code=400,
            detail="Not enough questions in the bank for daily test.",
        )

    # Create daily test
    daily_test = DailyTest(test_date=test_date)
    db.add(daily_test)
    db.flush()

    for order, qid in enumerate(selected_ids):
        dtq = DailyTestQuestion(
            daily_test_id=daily_test.id,
            question_id=qid,
            question_order=order,
        )
        db.add(dtq)

    db.commit()
    db.refresh(daily_test)
    return daily_test


def _random_questions_by_chapter(db: Session, chapter: str, count: int):
    rows = (
        db.query(Question.id)
        .filter(Question.chapter == chapter)
        .order_by(func.random())
        .limit(count)
        .all()
    )
    return [r[0] for r in rows]


def start_daily_test(db: Session, user_id: int, date_str: str = None) -> DailyTestOut:
    """Start or resume today's daily test for the user."""
    today = date_str or dt.date.today().isoformat()
    daily_test = _get_or_create_daily_test(db, today)

    # Check if user already has an attempt
    attempt = db.query(DailyTestAttempt).filter(
        DailyTestAttempt.daily_test_id == daily_test.id,
        DailyTestAttempt.user_id == user_id,
    ).first()

    if not attempt:
        attempt = DailyTestAttempt(
            daily_test_id=daily_test.id,
            user_id=user_id,
            completed=False,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

    # Fetch questions
    dtqs = (
        db.query(DailyTestQuestion)
        .filter(DailyTestQuestion.daily_test_id == daily_test.id)
        .order_by(DailyTestQuestion.question_order)
        .all()
    )

    questions = []
    for dtq in dtqs:
        q = dtq.question
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

    return DailyTestOut(
        daily_test_id=daily_test.id,
        attempt_id=attempt.id,
        test_date=today,
        questions=questions,
    )


def answer_daily_question(
    db: Session, user_id: int, req: DailyTestAnswerRequest
):
    """Answer a daily test question."""
    attempt = db.query(DailyTestAttempt).filter(
        DailyTestAttempt.id == req.attempt_id,
        DailyTestAttempt.user_id == user_id,
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.completed:
        raise HTTPException(status_code=400, detail="Daily test already submitted")

    # Verify question belongs to this daily test
    dtq = db.query(DailyTestQuestion).filter(
        DailyTestQuestion.daily_test_id == attempt.daily_test_id,
        DailyTestQuestion.question_id == req.question_id,
    ).first()
    if not dtq:
        raise HTTPException(status_code=404, detail="Question not in this daily test")

    question = db.query(Question).filter(Question.id == req.question_id).first()
    is_correct = req.selected_option == question.correct_option.value

    # Upsert answer
    existing = db.query(DailyTestAnswer).filter(
        DailyTestAnswer.attempt_id == req.attempt_id,
        DailyTestAnswer.question_id == req.question_id,
    ).first()

    if existing:
        existing.selected_option = CorrectOptionEnum(req.selected_option)
        existing.is_correct = is_correct
        existing.answered_at = dt.datetime.utcnow()
    else:
        ans = DailyTestAnswer(
            attempt_id=req.attempt_id,
            question_id=req.question_id,
            selected_option=CorrectOptionEnum(req.selected_option),
            is_correct=is_correct,
        )
        db.add(ans)

    db.commit()

    return {
        "correct": is_correct,
        "correct_option": question.correct_option.value,
        "explanation": question.explanation,
    }


def submit_daily_test(
    db: Session, user_id: int, attempt_id: int
) -> DailyTestSubmitResponse:
    """Submit daily test and calculate score."""
    attempt = db.query(DailyTestAttempt).filter(
        DailyTestAttempt.id == attempt_id,
        DailyTestAttempt.user_id == user_id,
    ).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.completed:
        raise HTTPException(status_code=400, detail="Already submitted")

    # Count questions in this daily test
    total = db.query(DailyTestQuestion).filter(
        DailyTestQuestion.daily_test_id == attempt.daily_test_id
    ).count()

    answers = db.query(DailyTestAnswer).filter(
        DailyTestAnswer.attempt_id == attempt_id
    ).all()

    correct = sum(1 for a in answers if a.is_correct)
    wrong = sum(1 for a in answers if not a.is_correct)
    unanswered = total - len(answers)

    attempt.correct_count = correct
    attempt.wrong_count = wrong
    attempt.score = round(correct / total * 100 if total > 0 else 0, 2)
    attempt.completed = True
    attempt.completed_at = dt.datetime.utcnow()
    db.commit()

    return DailyTestSubmitResponse(
        attempt_id=attempt_id,
        correct_count=correct,
        wrong_count=wrong,
        unanswered=unanswered,
        score=attempt.score,
        total=total,
    )
