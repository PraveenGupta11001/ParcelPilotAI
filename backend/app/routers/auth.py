import os
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshTokenRequest
from app.auth.jwt import create_access_token, create_refresh_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
def register_user(req: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new system user.

    Enforces email uniqueness before hashing the passwords using bcrypt.

    Args:
        req: RegisterRequest schema containing email, password, full name, role, and optional account scope.
        db: Database session.

    Returns:
        dict: A dictionary containing registration success status, user_id, email, role, and full_name.

    Raises:
        HTTPException: 400 Bad Request if the email is already registered.
    """
    existing = db.query(User).filter(User.email == req.email.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )
    
    salt = bcrypt.gensalt()
    pwd_hash = bcrypt.hashpw(req.password.encode('utf-8'), salt).decode('utf-8')
    
    new_user = User(
        user_id="user-" + os.urandom(4).hex(),
        role=req.role,
        account_id=req.account_id,
        full_name=req.full_name,
        email=req.email.strip(),
        password_hash=pwd_hash
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "success": True,
        "user_id": new_user.user_id,
        "email": new_user.email,
        "role": new_user.role,
        "full_name": new_user.full_name
    }

@router.post("/mock-login")
@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Logs in an existing user using bcrypt password validation.

    Generates secure JWT access and refresh tokens upon successful authentication.

    Args:
        req: LoginRequest schema containing credentials (email, password).
        db: Database session.

    Returns:
        dict: A dictionary containing the access token, refresh token, and logged-in user profile details.

    Raises:
        HTTPException: 401 Unauthorized if verification fails or the user does not exist.
    """
    user = db.query(User).filter(User.email == req.email.strip()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
    hashed_pwd = user.password_hash.encode('utf-8')
    if not bcrypt.checkpw(req.password.encode('utf-8'), hashed_pwd):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )
        
    access_token = create_access_token({"sub": user.user_id})
    refresh_token = create_refresh_token({"sub": user.user_id})
    
    user.refresh_key = refresh_token
    db.commit()
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "role": user.role,
            "account_id": user.account_id,
            "full_name": user.full_name
        }
    }

@router.post("/refresh")
def refresh(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refreshes credentials using a valid refresh token.

    Validates refresh token authenticity, ensures matches the stored key for the user in database, and issues fresh rotated credentials.
    """
    payload = decode_access_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token."
        )
    user_id = payload.get("sub")
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user or user.refresh_key != req.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid refresh token."
        )
    
    new_access_token = create_access_token({"sub": user.user_id})
    new_refresh_token = create_refresh_token({"sub": user.user_id})
    
    user.refresh_key = new_refresh_token
    db.commit()
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }
