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

    # Add validator to fix DATABASE_URL automatically
    @property
    def fixed_database_url(self):
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

settings = Settings()

# Use the fixed URL
DATABASE_URL = settings.fixed_database_url

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