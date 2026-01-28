"""
Authentication Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.dependencies import get_db, get_current_user
from api.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate
)
from database.manager import DatabaseManager
from models import Usuario
from utils.security import verify_password, create_access_token
from datetime import timedelta
from config import settings

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login endpoint - Authenticate user and return JWT token.

    Args:
        credentials: Username and password
        db: Database session

    Returns:
        Access token and user info

    Raises:
        HTTPException: If credentials are invalid
    """
    manager = DatabaseManager(db)

    # Get user by username
    user = db.query(Usuario).filter(Usuario.username == credentials.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    # Check if user is active
    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        user=UsuarioResponse.model_validate(user)
    )


@router.post("/register", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UsuarioCreate,
    db: Session = Depends(get_db)
):
    """
    Register new user.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException: If username or email already exists
    """
    manager = DatabaseManager(db)

    # Check if username already exists
    existing_user = db.query(Usuario).filter(Usuario.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )

    # Check if email already exists
    existing_email = db.query(Usuario).filter(Usuario.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    new_user = manager.crear_usuario(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        nombre_completo=user_data.nombre_completo
    )

    return UsuarioResponse.model_validate(new_user)


@router.get("/me", response_model=UsuarioResponse)
async def get_current_user_info(
    current_user: Usuario = Depends(get_current_user)
):
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user info
    """
    return UsuarioResponse.model_validate(current_user)


@router.put("/me", response_model=UsuarioResponse)
async def update_current_user(
    user_update: UsuarioUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user information.

    Args:
        user_update: User update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated user info
    """
    manager = DatabaseManager(db)

    # Update user
    updated_user = manager.actualizar_usuario(
        current_user.id,
        email=user_update.email,
        nombre_completo=user_update.nombre_completo,
        password=user_update.password
    )

    return UsuarioResponse.model_validate(updated_user)
