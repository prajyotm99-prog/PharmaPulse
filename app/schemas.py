"""
Pydantic schemas for all request/response models.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ── Auth ───────────────────────────────────────────────

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Questions ──────────────────────────────────────────

class QuestionOut(BaseModel):
    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str
    explanation: Optional[str] = None
    chapter: str
    category: str
    difficulty: int

    class Config:
        from_attributes = True


class QuestionBrief(BaseModel):
    """Question without answer — for test-taking."""
    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    chapter: str
    category: str
    difficulty: int

    class Config:
        from_attributes = True


# ── CSV Upload ─────────────────────────────────────────

class CSVUploadResult(BaseModel):
    total_rows: int
    inserted: int
    duplicates_skipped: int
    errors: List[str]
    decks_created: List[str]


# ── Decks ──────────────────────────────────────────────

class DeckOut(BaseModel):
    id: int
    name: str
    is_new: bool
    active: bool
    question_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class DeckDetail(BaseModel):
    id: int
    name: str
    is_new: bool
    questions: List[QuestionOut]

    class Config:
        from_attributes = True


# ── Flashcards ─────────────────────────────────────────

class FlashcardSessionOut(BaseModel):
    session_id: int
    deck_id: int
    total_questions: int
    pending_count: int
    completed: bool


class FlashcardNextQuestion(BaseModel):
    session_id: int
    question: Optional[QuestionBrief] = None
    pending_count: int
    completed: bool


class FlashcardAnswerRequest(BaseModel):
    session_id: int
    question_id: int
    selected_option: str = Field(..., pattern="^[ABCD]$")


class FlashcardAnswerResult(BaseModel):
    correct: bool
    correct_option: str
    explanation: Optional[str] = None
    pending_count: int
    completed: bool


# ── Full-Length Test ───────────────────────────────────

class TestStartResponse(BaseModel):
    attempt_id: int
    total_questions: int
    questions: List[QuestionBrief]


class TestAnswerRequest(BaseModel):
    attempt_id: int
    question_id: int
    selected_option: str = Field(..., pattern="^[ABCD]$")


class TestAnswerResult(BaseModel):
    correct: bool
    correct_option: str
    explanation: Optional[str] = None


class ChapterScore(BaseModel):
    chapter: str
    total: int
    correct: int
    wrong: int
    unanswered: int
    score: float


class TestSubmitResponse(BaseModel):
    attempt_id: int
    total_questions: int
    correct_count: int
    wrong_count: int
    unanswered_count: int
    score: float
    negative_marks: float
    final_score: float
    chapter_breakdown: List[ChapterScore]


# ── Daily Test ─────────────────────────────────────────

class DailyTestOut(BaseModel):
    daily_test_id: int
    attempt_id: int
    test_date: str
    questions: List[QuestionBrief]


class DailyTestAnswerRequest(BaseModel):
    attempt_id: int
    question_id: int
    selected_option: str = Field(..., pattern="^[ABCD]$")


class DailyTestSubmitResponse(BaseModel):
    attempt_id: int
    correct_count: int
    wrong_count: int
    unanswered: int
    score: float
    total: int


# ── Stats ──────────────────────────────────────────────

class UserStats(BaseModel):
    total_flashcard_sessions: int
    completed_flashcard_sessions: int
    total_test_attempts: int
    completed_test_attempts: int
    average_test_score: Optional[float] = None
    daily_tests_taken: int
