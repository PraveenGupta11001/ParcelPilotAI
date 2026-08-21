import os
from datetime import datetime, timezone, timedelta

# Database Configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgrespassword@localhost:5432/parcelpilot"
)

# Authentication Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "parcelpilot-secret-jwt-signing-key-for-auth-2026-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# LLM & Embedding Settings
# Can use voyage-3 (Voyage AI) or text-embedding-3-small (OpenAI)
# Default keys to None, logic will fallback or throw errors gracefully
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Snapshot reference datetime: 2026-08-16 11:00 Asia/Kolkata (IST = UTC+5:30)
# Express in tz-aware format for calculations
IST_TZ = timezone(timedelta(hours=5, minutes=30))
SNAPSHOT_DATETIME = datetime(2026, 8, 16, 11, 0, 0, tzinfo=IST_TZ)
