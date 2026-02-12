"""
Core CRUD: CSV parsing, question insertion, deck creation.
"""

import csv
import io
import datetime as dt
from typing import List, Tuple
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import UploadFile, HTTPException

from app.models import (
    Question, Deck, DeckQuestion,
    CategoryEnum, CorrectOptionEnum,
)
from app.schemas import CSVUploadResult

# ── Constants ──────────────────────────────────────────

REQUIRED_HEADERS = [
    "question_text", "option_a", "option_b", "option_c", "option_d",
    "correct_option", "explanation", "chapter", "category", "difficulty",
    "deck_name",
]

VALID_CATEGORIES = {"technical", "current_affairs", "case_law"}
VALID_OPTIONS = {"A", "B", "C", "D"}
VALID_DIFFICULTIES = {1, 2, 3, 4, 5}


# ── CSV Upload ─────────────────────────────────────────

async def process_csv_upload(file: UploadFile, db: Session) -> CSVUploadResult:
    """
    Parse and validate CSV, insert questions into master bank,
    create immutable decks. Full transactional safety.
    """
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    # ── Header validation ──
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="CSV file is empty or unreadable.")

    headers = list(reader.fieldnames)
    if headers != REQUIRED_HEADERS:
        missing = set(REQUIRED_HEADERS) - set(headers)
        extra = set(headers) - set(REQUIRED_HEADERS)
        msg = "CSV header mismatch."
        if missing:
            msg += f" Missing: {missing}."
        if extra:
            msg += f" Extra: {extra}."
        msg += f" Expected exact headers: {REQUIRED_HEADERS}"
        raise HTTPException(status_code=400, detail=msg)

    # ── Parse rows ──
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows.")

    errors: List[str] = []
    valid_rows = []

    for i, row in enumerate(rows, start=2):  # row 1 = header
        row_errors = []

        qt = (row.get("question_text") or "").strip()
        if not qt:
            row_errors.append("question_text is empty")

        co = (row.get("correct_option") or "").strip().upper()
        if co not in VALID_OPTIONS:
            row_errors.append(f"correct_option '{co}' not in A/B/C/D")

        diff_str = (row.get("difficulty") or "").strip()
        try:
            diff = int(diff_str)
            if diff not in VALID_DIFFICULTIES:
                row_errors.append(f"difficulty {diff} not in 1-5")
        except ValueError:
            row_errors.append(f"difficulty '{diff_str}' is not a number")
            diff = None

        chapter = (row.get("chapter") or "").strip()
        if not chapter:
            row_errors.append("chapter is empty")

        cat = (row.get("category") or "").strip().lower()
        if cat not in VALID_CATEGORIES:
            row_errors.append(f"category '{cat}' not in {VALID_CATEGORIES}")

        deck_name = (row.get("deck_name") or "").strip()
        if not deck_name:
            row_errors.append("deck_name is empty")

        if row_errors:
            errors.append(f"Row {i}: {'; '.join(row_errors)}")
            continue

        valid_rows.append({
            "question_text": qt,
            "option_a": (row.get("option_a") or "").strip(),
            "option_b": (row.get("option_b") or "").strip(),
            "option_c": (row.get("option_c") or "").strip(),
            "option_d": (row.get("option_d") or "").strip(),
            "correct_option": co,
            "explanation": (row.get("explanation") or "").strip(),
            "chapter": chapter,
            "category": cat,
            "difficulty": diff,
            "deck_name": deck_name,
        })

    # ── Insert questions + create decks inside a transaction ──
    inserted = 0
    duplicates = 0
    decks_created: List[str] = []

    # Group rows by deck_name
    deck_groups = defaultdict(list)
    for r in valid_rows:
        deck_groups[r["deck_name"]].append(r)

    try:
        # Bulk-check existing question texts
        existing_texts = set(
            t[0] for t in db.query(Question.question_text).all()
        )

        question_map = {}  # question_text -> Question obj (for deck linking)

        for r in valid_rows:
            if r["question_text"] in existing_texts:
                duplicates += 1
                # Still need the question object for deck linking
                if r["question_text"] not in question_map:
                    q = db.query(Question).filter(
                        Question.question_text == r["question_text"]
                    ).first()
                    if q:
                        question_map[r["question_text"]] = q
                continue

            q = Question(
                question_text=r["question_text"],
                option_a=r["option_a"],
                option_b=r["option_b"],
                option_c=r["option_c"],
                option_d=r["option_d"],
                correct_option=CorrectOptionEnum(r["correct_option"]),
                explanation=r["explanation"] or None,
                chapter=r["chapter"],
                category=CategoryEnum(r["category"]),
                difficulty=r["difficulty"],
            )
            db.add(q)
            db.flush()  # get the ID
            existing_texts.add(r["question_text"])
            question_map[r["question_text"]] = q
            inserted += 1

        # ── Create decks (immutable — always new) ──
        for deck_name, group_rows in deck_groups.items():
            actual_name = _get_unique_deck_name(db, deck_name)
            deck = Deck(name=actual_name, is_new=True, active=True)
            db.add(deck)
            db.flush()

            for r in group_rows:
                q_obj = question_map.get(r["question_text"])
                if q_obj is None:
                    # Question was a duplicate; fetch from DB
                    q_obj = db.query(Question).filter(
                        Question.question_text == r["question_text"]
                    ).first()
                if q_obj:
                    dq = DeckQuestion(deck_id=deck.id, question_id=q_obj.id)
                    db.add(dq)

            decks_created.append(actual_name)

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return CSVUploadResult(
        total_rows=len(rows),
        inserted=inserted,
        duplicates_skipped=duplicates,
        errors=errors,
        decks_created=decks_created,
    )


def _get_unique_deck_name(db: Session, base_name: str) -> str:
    """If deck name exists, append version suffix."""
    existing = db.query(Deck).filter(Deck.name == base_name).first()
    if not existing:
        return base_name

    # Find highest version
    like_pattern = f"{base_name}_v%"
    versions = (
        db.query(Deck.name)
        .filter(Deck.name.like(like_pattern))
        .all()
    )
    max_v = 1
    for (name,) in versions:
        try:
            v = int(name.rsplit("_v", 1)[1])
            max_v = max(max_v, v)
        except (ValueError, IndexError):
            pass
    return f"{base_name}_v{max_v + 1}"


# ── Deck Queries ───────────────────────────────────────

def get_all_decks(db: Session):
    decks = db.query(Deck).filter(Deck.active == True).order_by(Deck.created_at.desc()).all()
    result = []
    for d in decks:
        result.append({
            "id": d.id,
            "name": d.name,
            "is_new": d.is_new,
            "active": d.active,
            "question_count": len(d.questions),
            "created_at": d.created_at,
        })
    return result


def get_deck_detail(db: Session, deck_id: int):
    deck = db.query(Deck).filter(Deck.id == deck_id, Deck.active == True).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return {
        "id": deck.id,
        "name": deck.name,
        "is_new": deck.is_new,
        "questions": [dq.question for dq in deck.questions],
    }


def mark_deck_viewed(db: Session, deck_id: int):
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    deck.is_new = False
    db.commit()
    return {"message": "Deck marked as viewed"}


# ── Question Bank Queries ──────────────────────────────

def get_questions_by_chapter(db: Session, chapter: str, limit: int = None):
    q = db.query(Question).filter(Question.chapter == chapter)
    if limit:
        q = q.order_by(func.random()).limit(limit)
    return q.all()


def get_question_bank_stats(db: Session):
    total = db.query(func.count(Question.id)).scalar()
    by_chapter = (
        db.query(Question.chapter, func.count(Question.id))
        .group_by(Question.chapter)
        .all()
    )
    by_category = (
        db.query(Question.category, func.count(Question.id))
        .group_by(Question.category)
        .all()
    )
    return {
        "total_questions": total,
        "by_chapter": {ch: ct for ch, ct in by_chapter},
        "by_category": {str(cat): ct for cat, ct in by_category},
    }
