"""
Proyecto Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import sys
from pathlib import Path
import hashlib
import shutil

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.dependencies import get_db, get_current_user, get_database_manager
from api.schemas.proyecto import (
    ProyectoCreate,
    ProyectoUpdate,
    ProyectoResponse,
    ProyectoCompleto,
    ProyectoArbol,
    EstadisticasProyecto
)
from database.manager import DatabaseManager
from database.queries import QueryHelper
from models import Usuario
from services.proyecto_service import ProyectoService
from services.procesamiento_service import ProcesamientoService
from config import settings

router = APIRouter()


@router.get("", response_model=List[ProyectoResponse])
async def listar_proyectos(
    skip: int = 0,
    limit: int = 100,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    List all projects for current user.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        List of projects
    """
    proyectos = manager.listar_proyectos(current_user.id, offset=skip, limite=limit)
    return [ProyectoResponse.model_validate(p) for p in proyectos]


@router.post("", response_model=ProyectoResponse, status_code=status.HTTP_201_CREATED)
async def crear_proyecto(
    proyecto_data: ProyectoCreate,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Create a new project.

    Args:
        proyecto_data: Project creation data
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Created project
    """
    proyecto = manager.crear_proyecto(
        usuario_id=current_user.id,
        nombre=proyecto_data.nombre,
        descripcion=proyecto_data.descripcion
    )
    return ProyectoResponse.model_validate(proyecto)


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Upload a PDF file and create a new project.

    Args:
        file: PDF file to upload
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        dict with proyecto_id

    Raises:
        HTTPException: If file is not a PDF or exceeds size limit
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )

    # Read file content
    file_content = await file.read()

    # Validate file size
    if len(file_content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed ({settings.MAX_UPLOAD_SIZE / 1024 / 1024} MB)"
        )

    # Calculate file hash
    file_hash = hashlib.md5(file_content).hexdigest()

    # Create project name from filename
    proyecto_nombre = file.filename.replace('.pdf', '')

    # Save file
    file_path = settings.UPLOADS_DIR / f"u{current_user.id}_p_{file_hash}_{file.filename}"
    with open(file_path, 'wb') as f:
        f.write(file_content)

    # Create project
    proyecto = manager.crear_proyecto(
        usuario_id=current_user.id,
        nombre=proyecto_nombre,
        descripcion=f"Proyecto creado desde PDF: {file.filename}"
    )

    # Update project with PDF info
    from models import Proyecto
    proyecto_obj = manager.session.query(Proyecto).filter_by(id=proyecto.id).first()
    if proyecto_obj:
        proyecto_obj.pdf_path = str(file_path)
        proyecto_obj.pdf_nombre = file.filename
        proyecto_obj.pdf_hash = file_hash
        manager.session.commit()

    # Process PDF using PDFOrchestrator
    try:
        procesamiento_service = ProcesamientoService(manager.session)
        resultado = procesamiento_service.procesar_pdf_completo(
            proyecto_id=proyecto.id,
            user_id=current_user.id,
            pdf_path=str(file_path)
        )

        # Get statistics from result
        stats = resultado.get('estadisticas', {})

        return {
            "proyecto_id": proyecto.id,
            "nombre": proyecto.nombre,
            "pdf_nombre": file.filename,
            "message": "PDF uploaded and processed successfully",
            "procesamiento": {
                "tipo_documento": resultado.get('metadata', {}).get('tipo_documento'),
                "parser_usado": resultado.get('metadata', {}).get('parser_usado'),
                "num_capitulos": stats.get('num_capitulos', 0),
                "num_subcapitulos": stats.get('num_subcapitulos', 0),
                "num_partidas": stats.get('num_partidas', 0)
            }
        }

    except Exception as e:
        # If processing fails, still return success for upload but log error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error processing PDF: {str(e)}")

        return {
            "proyecto_id": proyecto.id,
            "nombre": proyecto.nombre,
            "pdf_nombre": file.filename,
            "message": "PDF uploaded successfully but processing failed",
            "error": str(e)
        }


@router.get("/{proyecto_id}", response_model=ProyectoCompleto)
async def obtener_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a project by ID with statistics.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Project with statistics

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    service = ProyectoService(db)
    resultado = service.obtener_proyecto_completo(proyecto_id)

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    proyecto_obj = resultado["proyecto"]
    estadisticas = resultado.get("estadisticas", {})

    # Check user has access
    if proyecto_obj.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Create response with statistics
    return ProyectoCompleto(
        id=proyecto_obj.id,
        usuario_id=proyecto_obj.usuario_id,
        nombre=proyecto_obj.nombre,
        descripcion=proyecto_obj.descripcion,
        pdf_path=proyecto_obj.pdf_path,
        fase_actual=proyecto_obj.fase_actual,
        total_presupuesto=proyecto_obj.total_presupuesto,
        fecha_creacion=proyecto_obj.fecha_creacion,
        fecha_actualizacion=proyecto_obj.fecha_actualizacion,
        num_capitulos=estadisticas.get("num_capitulos", 0),
        num_partidas=estadisticas.get("num_partidas", 0),
        num_mediciones=estadisticas.get("num_mediciones", 0)
    )



@router.put("/{proyecto_id}", response_model=ProyectoResponse)
async def actualizar_proyecto(
    proyecto_id: int,
    proyecto_update: ProyectoUpdate,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Update a project.

    Args:
        proyecto_id: Project ID
        proyecto_update: Project update data
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Updated project

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this project"
        )

    # Update project
    updated_proyecto = manager.actualizar_proyecto(
        proyecto_id,
        nombre=proyecto_update.nombre,
        descripcion=proyecto_update.descripcion,
        fase_actual=proyecto_update.fase_actual,
        total_presupuesto=proyecto_update.total_presupuesto
    )

    return ProyectoResponse.model_validate(updated_proyecto)


@router.delete("/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Delete a project.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        manager: Database manager

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this project"
        )

    manager.eliminar_proyecto(proyecto_id)
    return None


@router.get("/{proyecto_id}/arbol", response_model=ProyectoArbol)
async def obtener_arbol_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete project tree structure.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Project with complete tree

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    manager = DatabaseManager(db)
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Get tree
    query_helper = QueryHelper(db)
    arbol = query_helper.obtener_arbol_completo(proyecto_id)

    return ProyectoArbol(
        proyecto=ProyectoResponse.model_validate(proyecto),
        arbol=arbol
    )


@router.get("/{proyecto_id}/estadisticas", response_model=EstadisticasProyecto)
async def obtener_estadisticas_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get project statistics.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Project statistics

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    manager = DatabaseManager(db)
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Get statistics
    query_helper = QueryHelper(db)
    stats = query_helper.obtener_estadisticas_proyecto(proyecto_id)

    return EstadisticasProyecto(**stats)
