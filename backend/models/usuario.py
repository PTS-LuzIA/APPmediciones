"""
Modelo Usuario - Gestión de usuarios del sistema
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from .base import Base, SCHEMA_NAME


class Usuario(Base):
    """
    Usuario del sistema.

    Gestiona autenticación y permisos.
    """
    __tablename__ = 'usuarios'
    __table_args__ = {'schema': SCHEMA_NAME}

    # Identificación
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # Información personal
    nombre_completo = Column(String(200))
    empresa = Column(String(200))

    # Estado
    activo = Column(Boolean, default=True)
    es_admin = Column(Boolean, default=False)

    # Fechas
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    ultimo_acceso = Column(DateTime)

    def __repr__(self):
        return f"<Usuario(id={self.id}, username='{self.username}')>"
