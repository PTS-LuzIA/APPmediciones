"""
API Dependencies - Authentication, database sessions, etc.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Generator
from jose import JWTError, jwt
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from database.connection import SessionLocal
from database.manager import DatabaseManager
from models import Usuario
from config import settings

# Security
security = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get database session.

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Usuario:
    """
    Dependency to get current authenticated user from JWT token.

    Args:
        credentials: HTTP Bearer token
        db: Database session

    Returns:
        Current user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        token = credentials.credentials
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")

        if user_id_str is None:
            raise credentials_exception

        user_id = int(user_id_str)

    except (JWTError, ValueError):
        raise credentials_exception

    # Get user from database
    manager = DatabaseManager(db)
    user = manager.obtener_usuario(user_id)

    if user is None:
        raise credentials_exception

    if not user.activo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not active"
        )

    return user


async def get_current_admin_user(
    current_user: Usuario = Depends(get_current_user)
) -> Usuario:
    """
    Dependency to ensure current user is admin.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user if admin

    Raises:
        HTTPException: If user is not admin
    """
    if not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user


def get_database_manager(db: Session = Depends(get_db)) -> DatabaseManager:
    """
    Dependency to get DatabaseManager instance.

    Args:
        db: Database session

    Returns:
        DatabaseManager instance
    """
    return DatabaseManager(db)
