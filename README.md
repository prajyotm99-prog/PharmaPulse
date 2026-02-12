# PharmaPulse

Production-ready competitive exam preparation API with flashcards, full-length tests, daily tests, and a Magoosh-style mastery system.

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- PostgreSQL running locally

### 1. Clone and install

```bash
cd exam-engine
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create PostgreSQL database

```bash
psql -U postgres
CREATE DATABASE exam_engine;
\q
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your actual values:
#   DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/exam_engine
#   SECRET_KEY=some-random-secret-key
#   ADMIN_EMAIL=admin@example.com
#   ADMIN_PASSWORD=your-admin-password
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

Server starts at **http://127.0.0.1:8000**
Swagger docs at **http://127.0.0.1:8000/docs**

On first startup, the admin user is auto-created from your `.env` values.

---

## Deploy to Render

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/exam-engine.git
git push -u origin main
```

### Step 2: Create PostgreSQL on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New → PostgreSQL**
3. Name: `exam-engine-db`
4. Plan: Free (or Starter for production)
5. Click **Create Database**
6. Copy the **Internal Database URL**

### Step 3: Create Web Service on Render

1. Click **New → Web Service**
2. Connect your GitHub repo
3. Settings:
   - **Name**: `exam-engine`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add **Environment Variables**:

| Key | Value |
|-----|-------|
| `DATABASE_URL` | *(paste Internal Database URL from step 2)* |
| `SECRET_KEY` | *(generate a random 32+ char string)* |
| `ADMIN_EMAIL` | `admin@example.com` |
| `ADMIN_PASSWORD` | *(your admin password)* |

5. Click **Create Web Service**

Your API will be live at `https://exam-engine.onrender.com`

---

## Sample CSV Format

The CSV must have **exactly** these columns in this order:

```
question_text,option_a,option_b,option_c,option_d,correct_option,explanation,chapter,category,difficulty,deck_name
```

### Example rows:

```csv
question_text,option_a,option_b,option_c,option_d,correct_option,explanation,chapter,category,difficulty,deck_name
Which drug is a beta-blocker?,Atenolol,Amlodipine,Furosemide,Metformin,A,Atenolol is a selective beta-1 blocker,Pharmacology,technical,2,Pharmacology Basics
What is the pH of blood?,6.8,7.0,7.4,8.0,C,Normal blood pH is 7.35-7.45,Pharmaceutics,technical,1,Pharmaceutics Deck 1
The Drugs and Cosmetics Act was enacted in?,1935,1940,1945,1950,B,The Act was enacted in 1940,Drug Laws,technical,2,Drug Laws Deck 1
```

### Upload via API:

```bash
# 1. Login as admin
curl -X POST https://your-app.onrender.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "your-password"}'

# Response: {"access_token": "eyJ...", "token_type": "bearer"}

# 2. Upload CSV
curl -X POST https://your-app.onrender.com/admin/upload-csv \
  -H "Authorization: Bearer eyJ..." \
  -F "file=@questions.csv"
```

---

## API Endpoints Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login → JWT token |
| GET | `/auth/me` | Get current user info |

### Admin (requires admin JWT)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/upload-csv` | Upload master CSV |
| GET | `/admin/question-bank-stats` | Question bank overview |

### Decks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/decks` | List all active decks |
| GET | `/decks/{id}` | Deck detail with questions |
| PATCH | `/decks/{id}/mark-viewed` | Remove "NEW" badge |

### Flashcards (Mastery Mode)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/flashcard/start/{deck_id}` | Start new session |
| GET | `/flashcard/next/{session_id}` | Get next pending question |
| POST | `/flashcard/answer` | Answer (correct=removed, wrong=re-queued) |

### Full-Length Test
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/test/start?total_questions=100` | Generate weighted test |
| POST | `/test/answer` | Answer a question |
| POST | `/test/submit/{attempt_id}` | Submit → scores + breakdown |
| GET | `/test/history` | Past test attempts |

### Daily Test (10 Questions)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/daily-test/start` | Get today's test |
| POST | `/daily-test/answer` | Answer a question |
| POST | `/daily-test/submit/{attempt_id}` | Submit daily test |

### Stats
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats/me` | User performance stats |

---

## Architecture Notes

- **One master question bank** — all questions in a single `questions` table
- **Immutable decks** — once created, never modified; new uploads create new decks
- **Concurrent safe** — SQLAlchemy sessions are scoped per-request
- **Stateless API** — JWT auth, no server-side sessions
- **Negative marking** — full tests use +1 correct, −0.25 wrong
- **Chapter weightage** — full tests distribute questions by chapter percentages
- **Daily test shared** — same 10 questions for all users on a given date
