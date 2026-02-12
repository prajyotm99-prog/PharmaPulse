from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings
import os

# Settings class
class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "change-this-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ADMIN_EMAIL: str = "admin@pharmapulse.com"
    ADMIN_PASSWORD: str = "AdminPass123!"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()

# Get DATABASE_URL
DATABASE_URL = settings.DATABASE_URL

# Fix for psycopg (version 3)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Create engine
engine = create_engine(DATABASE_URL)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

# Dependency for FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()