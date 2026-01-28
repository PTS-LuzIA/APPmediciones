"""
Pydantic schemas for authentication
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UsuarioBase(BaseModel):
    """Base schema for Usuario"""
    username: str
    email: EmailStr
    nombre_completo: Optional[str] = None


class UsuarioCreate(UsuarioBase):
    """Schema for creating a user"""
    password: str


class UsuarioUpdate(BaseModel):
    """Schema for updating a user"""
    email: Optional[EmailStr] = None
    nombre_completo: Optional[str] = None
    password: Optional[str] = None
    es_admin: Optional[bool] = None
    activo: Optional[bool] = None


class UsuarioResponse(UsuarioBase):
    """Schema for user response"""
    id: int
    es_admin: bool
    activo: bool
    fecha_creacion: datetime
    ultimo_acceso: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Schema for login request"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Schema for token response"""
    access_token: str
    token_type: str = "bearer"
    user: UsuarioResponse
