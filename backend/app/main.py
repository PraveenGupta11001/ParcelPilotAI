import warnings
# Silence cryptography library deprecation warning
warnings.filterwarnings("ignore", message=".*ARC4.*", category=DeprecationWarning)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, chat, documents, insights

app = FastAPI(title="ParcelPilot Customer Support AI System API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(insights.router)
