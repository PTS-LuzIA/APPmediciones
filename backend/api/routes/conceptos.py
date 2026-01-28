"""
Concepto Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.dependencies import get_db, get_current_user, get_database_manager
from api.schemas.concepto import (
    ConceptoCreate,
    ConceptoUpdate,
    ConceptoResponse,
    ConceptoConUsos
)
from database.manager import DatabaseManager
from models import Usuario, TipoConcepto

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


@router.get("", response_model=List[ConceptoResponse])
async def listar_conceptos(
    proyecto_id: int,
    tipo: Optional[TipoConcepto] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    List all conceptos for a project with optional filters.

    Args:
        proyecto_id: Project ID
        tipo: Filter by concepto type (optional)
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        List of conceptos

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    # Verify access
    verificar_acceso_proyecto(proyecto_id, current_user.id, manager, current_user.es_admin)

    # Get conceptos
    conceptos = manager.listar_conceptos(proyecto_id, tipo=tipo, skip=skip, limit=limit)

    return [ConceptoResponse.model_validate(c) for c in conceptos]


@router.post("", response_model=ConceptoResponse, status_code=status.HTTP_201_CREATED)
async def crear_concepto(
    concepto_data: ConceptoCreate,
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Create a new concepto.

    Args:
        concepto_data: Concepto creation data
        proyecto_id: Project ID
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Created concepto

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    # Verify access
    verificar_acceso_proyecto(proyecto_id, current_user.id, manager, current_user.es_admin)

    # Check if concepto with same code already exists
    existing = manager.obtener_concepto(proyecto_id, concepto_data.codigo)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Concepto with code '{concepto_data.codigo}' already exists in this project"
        )

    # Create concepto
    concepto = manager.crear_concepto(
        proyecto_id=proyecto_id,
        codigo=concepto_data.codigo,
        tipo=concepto_data.tipo,
        nombre=concepto_data.nombre,
        resumen=concepto_data.resumen,
        descripcion=concepto_data.descripcion,
        unidad=concepto_data.unidad,
        precio=concepto_data.precio,
        cantidad_total=concepto_data.cantidad_total,
        importe_total=concepto_data.importe_total,
        total=concepto_data.total
    )

    return ConceptoResponse.model_validate(concepto)


@router.get("/{concepto_id}", response_model=ConceptoResponse)
async def obtener_concepto(
    concepto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a concepto by ID.

    Args:
        concepto_id: Concepto ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Concepto

    Raises:
        HTTPException: If concepto not found or user doesn't have access
    """
    manager = DatabaseManager(db)

    # Get concepto by ID
    from models import Concepto
    concepto = db.query(Concepto).filter(Concepto.id == concepto_id).first()

    if not concepto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concepto not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(concepto.proyecto_id, current_user.id, manager, current_user.es_admin)

    return ConceptoResponse.model_validate(concepto)


@router.put("/{concepto_id}", response_model=ConceptoResponse)
async def actualizar_concepto(
    concepto_id: int,
    concepto_update: ConceptoUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a concepto.

    Args:
        concepto_id: Concepto ID
        concepto_update: Concepto update data
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated concepto

    Raises:
        HTTPException: If concepto not found or user doesn't have access
    """
    manager = DatabaseManager(db)

    # Get concepto by ID
    from models import Concepto
    concepto = db.query(Concepto).filter(Concepto.id == concepto_id).first()

    if not concepto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concepto not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(concepto.proyecto_id, current_user.id, manager, current_user.es_admin)

    # Update concepto
    updated_concepto = manager.actualizar_concepto(
        concepto_id,
        nombre=concepto_update.nombre,
        resumen=concepto_update.resumen,
        descripcion=concepto_update.descripcion,
        unidad=concepto_update.unidad,
        precio=concepto_update.precio,
        cantidad_total=concepto_update.cantidad_total,
        importe_total=concepto_update.importe_total,
        total=concepto_update.total
    )

    return ConceptoResponse.model_validate(updated_concepto)


@router.delete("/{concepto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_concepto(
    concepto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a concepto.

    Args:
        concepto_id: Concepto ID
        current_user: Current authenticated user
        db: Database session

    Raises:
        HTTPException: If concepto not found or user doesn't have access or concepto is in use
    """
    manager = DatabaseManager(db)

    # Get concepto by ID
    from models import Concepto
    concepto = db.query(Concepto).filter(Concepto.id == concepto_id).first()

    if not concepto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concepto not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(concepto.proyecto_id, current_user.id, manager, current_user.es_admin)

    # Check if concepto is in use
    nodos_usando = manager.obtener_nodos_por_concepto(concepto.proyecto_id, concepto.codigo)
    if nodos_usando:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete concepto: it is used by {len(nodos_usando)} nodo(s)"
        )

    manager.eliminar_concepto(concepto_id)
    return None


@router.get("/{concepto_id}/usos", response_model=ConceptoConUsos)
async def obtener_usos_concepto(
    concepto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get where a concepto is being used.

    Args:
        concepto_id: Concepto ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Concepto with usage information

    Raises:
        HTTPException: If concepto not found or user doesn't have access
    """
    manager = DatabaseManager(db)

    # Get concepto by ID
    from models import Concepto
    concepto = db.query(Concepto).filter(Concepto.id == concepto_id).first()

    if not concepto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Concepto not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(concepto.proyecto_id, current_user.id, manager, current_user.es_admin)

    # Get nodos using this concepto
    nodos_usando = manager.obtener_nodos_por_concepto(concepto.proyecto_id, concepto.codigo)

    return ConceptoConUsos(
        **ConceptoResponse.model_validate(concepto).model_dump(),
        num_usos=len(nodos_usando),
        nodos_ids=[n.id for n in nodos_usando]
    )
