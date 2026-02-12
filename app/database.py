from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
import logging

logger = logging.getLogger(__name__)

# Settings class
class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "change-this-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ADMIN_EMAIL: str = "admin@pharmapulse.com"
    ADMIN_PASSWORD: str = "AdminPass123!"

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

# Initialize settings
try:
    settings = Settings()
    logger.info("Settings loaded successfully")
except Exception as e:
    logger.error(f"Failed to load settings: {e}")
    raise

# Get and fix DATABASE_URL
DATABASE_URL = settings.DATABASE_URL
logger.info(f"Original DATABASE_URL starts with: {DATABASE_URL[:20]}...")

# Fix for psycopg (version 3)
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    logger.info("Fixed DATABASE_URL to use postgresql+psycopg://")
elif DATABASE_URL.startswith("postgres://"):
    # Some providers use postgres:// instead of postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    logger.info("Fixed DATABASE_URL from postgres:// to postgresql+psycopg://")

logger.info(f"Final DATABASE_URL starts with: {DATABASE_URL[:30]}...")

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