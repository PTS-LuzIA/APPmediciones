"""
APPmediciones - FastAPI Main Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from pathlib import Path
import sys

# Añadir backend al path
sys.path.append(str(Path(__file__).parent))

from config import settings

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(settings.LOGS_DIR / "backend.log")
    ]
)

logger = logging.getLogger(__name__)

# Crear aplicación FastAPI
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Sistema de gestión de presupuestos de construcción basado en estructura jerárquica",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================
# EVENTOS DE STARTUP/SHUTDOWN
# =====================================================

@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar"""
    logger.info("=" * 60)
    logger.info(f"🚀 {settings.API_TITLE} v{settings.API_VERSION}")
    logger.info(f"   Entorno: {settings.ENV}")
    logger.info(f"   Puerto: {settings.API_PORT}")
    logger.info(f"   Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
    logger.info("=" * 60)

    # Verificar conexión a base de datos
    try:
        from database.connection import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("✓ Conexión a base de datos OK")
    except Exception as e:
        logger.error(f"❌ Error conectando a base de datos: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar"""
    logger.info("👋 Cerrando APPmediciones...")


# =====================================================
# RUTAS BÁSICAS
# =====================================================

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "app": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.API_VERSION,
        "environment": settings.ENV
    }


# =====================================================
# INCLUIR ROUTERS
# =====================================================

from api.routes import (
    auth_router,
    proyectos_router,
    nodos_router,
    conceptos_router,
    procesamiento_router
)

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(proyectos_router, prefix="/api/proyectos", tags=["Proyectos"])
app.include_router(nodos_router, prefix="/api/nodos", tags=["Nodos"])
app.include_router(conceptos_router, prefix="/api/conceptos", tags=["Conceptos"])
app.include_router(procesamiento_router, prefix="/api/procesamiento", tags=["Procesamiento"])


# =====================================================
# MANEJO DE ERRORES
# =====================================================

from fastapi import Request
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Manejador global de excepciones"""
    logger.error(f"Error no manejado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if settings.ENV == "development" else "An error occurred"
        }
    )


# =====================================================
# MAIN (para ejecutar directamente)
# =====================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENV == "development",
        log_level=settings.LOG_LEVEL.lower()
    )
