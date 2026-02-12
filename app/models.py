"""
All SQLAlchemy ORM models for the exam engine.
"""

import datetime as dt
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float,
    ForeignKey, Index, UniqueConstraint, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ── Enums ──────────────────────────────────────────────

class RoleEnum(str, enum.Enum):
    admin = "admin"
    user = "user"


class CategoryEnum(str, enum.Enum):
    technical = "technical"
    current_affairs = "current_affairs"
    case_law = "case_law"


class CorrectOptionEnum(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class FlashcardStatus(str, enum.Enum):
    pending = "pending"
    correct = "correct"


# ── Users ──────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SAEnum(RoleEnum), default=RoleEnum.user, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


# ── Master Question Bank ───────────────────────────────

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, unique=True, nullable=False)
    option_a = Column(Text, nullable=False)
    option_b = Column(Text, nullable=False)
    option_c = Column(Text, nullable=False)
    option_d = Column(Text, nullable=False)
    correct_option = Column(SAEnum(CorrectOptionEnum), nullable=False)
    explanation = Column(Text, nullable=True)
    chapter = Column(String(255), nullable=False, index=True)
    category = Column(SAEnum(CategoryEnum), nullable=False, index=True)
    difficulty = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    __table_args__ = (
        Index("ix_questions_chapter_category", "chapter", "category"),
    )


# ── Decks ──────────────────────────────────────────────

class Deck(Base):
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    is_new = Column(Boolean, default=True, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    questions = relationship("DeckQuestion", back_populates="deck", lazy="selectin")


class DeckQuestion(Base):
    __tablename__ = "deck_questions"

    id = Column(Integer, primary_key=True, index=True)
    deck_id = Column(Integer, ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)

    deck = relationship("Deck", back_populates="questions")
    question = relationship("Question", lazy="joined")

    __table_args__ = (
        UniqueConstraint("deck_id", "question_id", name="uq_deck_question"),
    )


# ── Flashcard Sessions ─────────────────────────────────

class FlashcardSession(Base):
    __tablename__ = "flashcard_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    deck_id = Column(Integer, ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    session_questions = relationship("FlashcardSessionQuestion", back_populates="session", lazy="selectin")


class FlashcardSessionQuestion(Base):
    __tablename__ = "flashcard_session_questions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("flashcard_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    status = Column(SAEnum(FlashcardStatus), default=FlashcardStatus.pending, nullable=False)
    shuffle_order = Column(Integer, nullable=False, default=0)
    last_attempted_at = Column(DateTime, nullable=True)

    session = relationship("FlashcardSession", back_populates="session_questions")
    question = relationship("Question", lazy="joined")


# ── Full-Length Tests ──────────────────────────────────

class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_questions = Column(Integer, nullable=False)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    score = Column(Float, default=0.0)
    negative_marks = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    completed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=dt.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class TestQuestion(Base):
    __tablename__ = "test_questions"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    question_order = Column(Integer, nullable=False)

    question = relationship("Question", lazy="joined")


class TestAnswer(Base):
    __tablename__ = "test_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("test_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    selected_option = Column(SAEnum(CorrectOptionEnum), nullable=True)
    is_correct = Column(Boolean, nullable=True)
    answered_at = Column(DateTime, default=dt.datetime.utcnow)

    question = relationship("Question", lazy="joined")

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_test_answer"),
    )


# ── Daily Tests ────────────────────────────────────────

class DailyTest(Base):
    __tablename__ = "daily_tests"

    id = Column(Integer, primary_key=True, index=True)
    test_date = Column(String(10), unique=True, nullable=False, index=True)  # YYYY-MM-DD
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class DailyTestQuestion(Base):
    __tablename__ = "daily_test_questions"

    id = Column(Integer, primary_key=True, index=True)
    daily_test_id = Column(Integer, ForeignKey("daily_tests.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    question_order = Column(Integer, nullable=False)

    question = relationship("Question", lazy="joined")


class DailyTestAttempt(Base):
    __tablename__ = "daily_test_attempts"

    id = Column(Integer, primary_key=True, index=True)
    daily_test_id = Column(Integer, ForeignKey("daily_tests.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    score = Column(Float, default=0.0)
    completed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=dt.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("daily_test_id", "user_id", name="uq_daily_attempt"),
    )


class DailyTestAnswer(Base):
    __tablename__ = "daily_test_answers"

    id = Column(Integer, primary_key=True, index=True)
    attempt_id = Column(Integer, ForeignKey("daily_test_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    selected_option = Column(SAEnum(CorrectOptionEnum), nullable=True)
    is_correct = Column(Boolean, nullable=True)
    answered_at = Column(DateTime, default=dt.datetime.utcnow)

    question = relationship("Question", lazy="joined")

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_daily_test_answer"),
    )
