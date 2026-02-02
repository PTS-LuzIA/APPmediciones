"""
Procesamiento Routes - PDF upload and phase execution
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
import sys
from pathlib import Path
import shutil

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.dependencies import get_db, get_current_user, get_database_manager
from api.schemas.procesamiento import (
    PDFUploadResponse,
    Fase1Resultado,
    Fase2Resultado,
    Fase3Resultado
)
from database.manager import DatabaseManager
from models import Usuario
from services.procesamiento_service import ProcesamientoService
from config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def verificar_acceso_proyecto(proyecto_id: int, user_id: int, manager: DatabaseManager, es_admin: bool = False):
    """
    Helper to verify user has access to project.

    Args:
        proyecto_id: Project ID
        user_id: User ID
        manager: Database manager
        es_admin: Whether user is admin

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if proyecto.usuario_id != user_id and not es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )


@router.post("/{proyecto_id}/upload-pdf", response_model=PDFUploadResponse)
async def upload_pdf(
    proyecto_id: int,
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Upload a PDF file to a project.

    Args:
        proyecto_id: Project ID
        file: PDF file to upload
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Upload result with file path

    Raises:
        HTTPException: If project not found, user doesn't have access, or file is invalid
    """
    # Verify access
    verificar_acceso_proyecto(proyecto_id, current_user.id, manager, current_user.es_admin)

    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )

    # Create uploads directory if not exists
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate file path
    filename = f"u{current_user.id}_p{proyecto_id}_{file.filename}"
    file_path = settings.UPLOADS_DIR / filename

    # Save file
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error saving file"
        )

    # Update project with PDF path
    manager.actualizar_proyecto(proyecto_id, pdf_path=str(file_path))

    return PDFUploadResponse(
        proyecto_id=proyecto_id,
        pdf_path=str(file_path),
        mensaje=f"PDF uploaded successfully: {filename}"
    )


@router.post("/{proyecto_id}/fase1", response_model=Fase1Resultado)
async def ejecutar_fase1(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute Fase 1: Extract structure (capítulos, subcapítulos).

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Fase 1 execution result

    Raises:
        HTTPException: If project not found, user doesn't have access, or PDF not uploaded
    """
    manager = DatabaseManager(db)

    # Verify access
    verificar_acceso_proyecto(proyecto_id, current_user.id, manager, current_user.es_admin)

    # Get project
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PDF file uploaded for this project"
        )

    # Execute Fase 1
    service = ProcesamientoService(db)

    try:
        resultado = service.ejecutar_fase1(proyecto_id, proyecto.pdf_path)

        return Fase1Resultado(
            fase=1,
            proyecto_id=proyecto_id,
            exito=True,
            mensaje="Fase 1 completed successfully",
            titulo_proyecto=resultado.get('titulo_proyecto'),
            num_conceptos=len(resultado.get('conceptos', [])),
            num_nodos=len(resultado.get('nodos', [])),
            conceptos=resultado.get('conceptos', []),
            datos=resultado
        )

    except Exception as e:
        logger.error(f"Error executing Fase 1 for proyecto {proyecto_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing Fase 1: {str(e)}"
        )


@router.post("/{proyecto_id}/fase2", response_model=Fase2Resultado)
async def ejecutar_fase2(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute Fase 2: Extract partidas.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Fase 2 execution result

    Raises:
        HTTPException: If project not found, user doesn't have access, or PDF not uploaded
    """
    manager = DatabaseManager(db)

    # Verify access
    verificar_acceso_proyecto(proyecto_id, current_user.id, manager, current_user.es_admin)

    # Get project
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PDF file uploaded for this project"
        )

    # Execute Fase 2
    service = ProcesamientoService(db)

    try:
        resultado = service.ejecutar_fase2(proyecto_id, proyecto.pdf_path)

        return Fase2Resultado(
            fase=2,
            proyecto_id=proyecto_id,
            exito=True,
            mensaje="Fase 2 completed successfully",
            num_partidas=len(resultado.get('conceptos_partidas', [])),
            partidas=resultado.get('conceptos_partidas', []),
            datos=resultado
        )

    except Exception as e:
        logger.error(f"Error executing Fase 2 for proyecto {proyecto_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing Fase 2: {str(e)}"
        )


@router.post("/{proyecto_id}/fase3", response_model=Fase3Resultado)
async def ejecutar_fase3(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute Fase 3: Calculate totals and detect discrepancies.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Fase 3 execution result

    Raises:
        HTTPException: If project not found, user doesn't have access, or PDF not uploaded
    """
    manager = DatabaseManager(db)

    # Verify access
    verificar_acceso_proyecto(proyecto_id, current_user.id, manager, current_user.es_admin)

    # Get project
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PDF file uploaded for this project"
        )

    # Execute Fase 3
    service = ProcesamientoService(db)

    try:
        resultado = service.ejecutar_fase3(proyecto_id, proyecto.pdf_path)

        # Prepare response with extended data for frontend
        datos_respuesta = {
            **resultado,
            'total_original': resultado.get('total_original', 0),
            'total_calculado': resultado.get('total_calculado', 0)
        }

        return Fase3Resultado(
            fase=3,
            proyecto_id=proyecto_id,
            exito=True,
            mensaje="Fase 3 completed successfully",
            total_presupuesto=resultado.get('total_presupuesto'),
            num_discrepancias=resultado.get('num_discrepancias', 0),
            discrepancias=resultado.get('discrepancias', []),
            datos=datos_respuesta
        )

    except Exception as e:
        logger.error(f"Error executing Fase 3 for proyecto {proyecto_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing Fase 3: {str(e)}"
        )


@router.post("/{proyecto_id}/fase4")
async def ejecutar_fase4(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute Fase 4: Complete descriptions and finalize.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Fase 4 execution result

    Raises:
        HTTPException: If project not found, user doesn't have access, or PDF not uploaded
    """
    manager = DatabaseManager(db)

    # Verify access
    verificar_acceso_proyecto(proyecto_id, current_user.id, manager, current_user.es_admin)

    # Get project
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PDF file uploaded for this project"
        )

    # Execute Fase 4
    service = ProcesamientoService(db)

    try:
        resultado = service.ejecutar_fase4(proyecto_id, proyecto.pdf_path)

        return {
            "fase": 4,
            "proyecto_id": proyecto_id,
            "exito": True,
            "mensaje": "Fase 4 completed successfully - Project finalized",
            "estadisticas": resultado.get('estadisticas', {}),
            "datos": resultado
        }

    except Exception as e:
        logger.error(f"Error executing Fase 4 for proyecto {proyecto_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing Fase 4: {str(e)}"
        )
