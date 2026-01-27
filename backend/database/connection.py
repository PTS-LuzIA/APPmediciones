"""
Conexión a base de datos PostgreSQL
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import sys
from pathlib import Path

# Añadir el directorio backend al path para imports
sys.path.append(str(Path(__file__).parent.parent))

from config import settings
from models.base import Base

# Crear engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verificar conexiones antes de usar
    pool_size=10,
    max_overflow=20,
    echo=settings.ENV == "development"  # Log SQL en desarrollo
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency para FastAPI que proporciona una sesión de base de datos.

    Uso:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Crea todas las tablas en la base de datos.

    NOTA: En producción, usar migrations (Alembic) en lugar de esto.
    """
    Base.metadata.create_all(bind=engine)
    print("✓ Tablas creadas exitosamente")


def drop_tables():
    """
    PELIGRO: Elimina todas las tablas.
    Solo usar en desarrollo.
    """
    if settings.ENV == "production":
        raise Exception("No se puede eliminar tablas en producción")

    Base.metadata.drop_all(bind=engine)
    print("✓ Tablas eliminadas")
