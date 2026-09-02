import warnings
# Silence cryptography and datetime deprecation warnings
warnings.filterwarnings("ignore", message=".*ARC4.*")
warnings.filterwarnings("ignore", message=".*utcnow.*")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.session import SessionLocal
from app.db.models import User

from app.routers import auth, chat, documents, insights, db

from app.config import ALLOWED_ORIGINS

app = FastAPI(title="ParcelPilot Customer Support AI System API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def check_supabase_connection():
    """Check if the Supabase connection is established."""
    try:
        db = SessionLocal()
        db.query(User).first()  # Simple query to check connection
        db.close()
        return True
    except Exception as e:
        print(f"Supabase connection error: {e}")
        return False

# Include Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(insights.router)
app.include_router(db.router)

@app.get("/")
def health_check():
    return {
        "status": "healthy", 
        "service": "ParcelPilot Customer Support AI API",
        "supabase_connection": check_supabase_connection()
        }
