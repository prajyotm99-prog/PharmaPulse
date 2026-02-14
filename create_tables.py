"""
Create all database tables including new UserQuestionProgress table
Run this once after adding new models
"""

from app.database import engine, Base
import app.models  # This imports all models

print("Creating database tables...")
Base.metadata.create_all(bind=engine)
print("✅ All tables created successfully!")