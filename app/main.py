"""
Main FastAPI application — all routes registered here.
"""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, engine, Base, settings
from app.models import (
    User, RoleEnum, Question, TestAttempt,
    FlashcardSession, DailyTestAttempt,
)
from app.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_admin,
)
from app.schemas import (
    UserCreate, UserLogin, UserOut, Token,
    DeckOut, DeckDetail,
    FlashcardSessionOut, FlashcardNextQuestion,
    FlashcardAnswerRequest, FlashcardAnswerResult,
    TestStartResponse, TestAnswerRequest, TestAnswerResult, TestSubmitResponse,
    DailyTestOut, DailyTestAnswerRequest, DailyTestSubmitResponse,
    UserStats,
)
from app.crud import get_all_decks, get_deck_detail, mark_deck_viewed
from app.flashcard_service import (
    start_flashcard_session, get_next_flashcard, answer_flashcard,
)
from app.test_service import (
    generate_full_test, answer_test_question, submit_test, get_user_test_history,
)
from app.daily_test_service import (
    start_daily_test, answer_daily_question, submit_daily_test,
)
from app.admin_routes import router as admin_router

# ── App Setup ──────────────────────────────────────────

app = FastAPI(
    title="MPSC Exam Engine",
    description="Production-ready competitive exam preparation API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)


# ── Startup ────────────────────────────────────────────

@app.on_event("startup")
def on_startup():
    """Create tables and seed admin user."""
    Base.metadata.create_all(bind=engine)

    db = next(get_db())
    try:
        admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not admin:
            admin = User(
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role=RoleEnum.admin,
            )
            db.add(admin)
            db.commit()
            print(f"[STARTUP] Admin user created: {settings.ADMIN_EMAIL}")
        else:
            print(f"[STARTUP] Admin user exists: {settings.ADMIN_EMAIL}")
    finally:
        db.close()


# ── Health ─────────────────────────────────────────────

@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "service": "MPSC Exam Engine"}


# ══════════════════════════════════════════════════════
# AUTH ROUTES
# ══════════════════════════════════════════════════════

@app.post("/auth/register", response_model=UserOut, tags=["Auth"])
def register(data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role=RoleEnum.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=Token, tags=["Auth"])
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return Token(access_token=token)


@app.get("/auth/me", response_model=UserOut, tags=["Auth"])
def me(user: User = Depends(get_current_user)):
    return user


# ══════════════════════════════════════════════════════
# DECK ROUTES
# ══════════════════════════════════════════════════════

@app.get("/decks", response_model=list[DeckOut], tags=["Decks"])
def list_decks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_all_decks(db)


@app.get("/decks/{deck_id}", response_model=DeckDetail, tags=["Decks"])
def deck_detail(deck_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_deck_detail(db, deck_id)


@app.patch("/decks/{deck_id}/mark-viewed", tags=["Decks"])
def mark_viewed(deck_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return mark_deck_viewed(db, deck_id)


# ══════════════════════════════════════════════════════
# FLASHCARD ROUTES
# ══════════════════════════════════════════════════════

@app.post("/flashcard/start/{deck_id}", response_model=FlashcardSessionOut, tags=["Flashcards"])
def flashcard_start(
    deck_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return start_flashcard_session(db, user.id, deck_id)


@app.get("/flashcard/next/{session_id}", response_model=FlashcardNextQuestion, tags=["Flashcards"])
def flashcard_next(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_next_flashcard(db, user.id, session_id)


@app.post("/flashcard/answer", response_model=FlashcardAnswerResult, tags=["Flashcards"])
def flashcard_answer_route(
    req: FlashcardAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return answer_flashcard(db, user.id, req)


# ══════════════════════════════════════════════════════
# FULL-LENGTH TEST ROUTES
# ══════════════════════════════════════════════════════

@app.post("/test/start", response_model=TestStartResponse, tags=["Full Test"])
def test_start(
    total_questions: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return generate_full_test(db, user.id, total_questions)


@app.post("/test/answer", response_model=TestAnswerResult, tags=["Full Test"])
def test_answer(
    req: TestAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return answer_test_question(db, user.id, req)


@app.post("/test/submit/{attempt_id}", response_model=TestSubmitResponse, tags=["Full Test"])
def test_submit(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return submit_test(db, user.id, attempt_id)


@app.get("/test/history", tags=["Full Test"])
def test_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempts = get_user_test_history(db, user.id)
    return [
        {
            "id": a.id,
            "total_questions": a.total_questions,
            "correct_count": a.correct_count,
            "wrong_count": a.wrong_count,
            "final_score": a.final_score,
            "completed": a.completed,
            "started_at": a.started_at,
            "completed_at": a.completed_at,
        }
        for a in attempts
    ]


# ══════════════════════════════════════════════════════
# DAILY TEST ROUTES
# ══════════════════════════════════════════════════════

@app.post("/daily-test/start", response_model=DailyTestOut, tags=["Daily Test"])
def daily_test_start(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return start_daily_test(db, user.id)


@app.post("/daily-test/answer", tags=["Daily Test"])
def daily_test_answer(
    req: DailyTestAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return answer_daily_question(db, user.id, req)


@app.post("/daily-test/submit/{attempt_id}", response_model=DailyTestSubmitResponse, tags=["Daily Test"])
def daily_test_submit(
    attempt_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return submit_daily_test(db, user.id, attempt_id)


# ══════════════════════════════════════════════════════
# USER STATS
# ══════════════════════════════════════════════════════

@app.get("/stats/me", response_model=UserStats, tags=["Stats"])
def user_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total_fc = db.query(FlashcardSession).filter(FlashcardSession.user_id == user.id).count()
    completed_fc = db.query(FlashcardSession).filter(
        FlashcardSession.user_id == user.id, FlashcardSession.completed == True
    ).count()

    total_tests = db.query(TestAttempt).filter(TestAttempt.user_id == user.id).count()
    completed_tests = db.query(TestAttempt).filter(
        TestAttempt.user_id == user.id, TestAttempt.completed == True
    ).count()

    avg_score = db.query(func.avg(TestAttempt.final_score)).filter(
        TestAttempt.user_id == user.id, TestAttempt.completed == True
    ).scalar()

    daily_count = db.query(DailyTestAttempt).filter(
        DailyTestAttempt.user_id == user.id
    ).count()

    return UserStats(
        total_flashcard_sessions=total_fc,
        completed_flashcard_sessions=completed_fc,
        total_test_attempts=total_tests,
        completed_test_attempts=completed_tests,
        average_test_score=round(avg_score, 2) if avg_score else None,
        daily_tests_taken=daily_count,
    )
