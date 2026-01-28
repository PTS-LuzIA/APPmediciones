"""
Nodo Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.dependencies import get_db, get_current_user, get_database_manager
from api.schemas.nodo import (
    NodoCreate,
    NodoUpdate,
    NodoResponse,
    NodoCompleto,
    NodoMover,
    NodoConHijos
)
from database.manager import DatabaseManager
from models import Usuario

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


@router.post("", response_model=NodoResponse, status_code=status.HTTP_201_CREATED)
async def crear_nodo(
    nodo_data: NodoCreate,
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Create a new nodo.

    Args:
        nodo_data: Nodo creation data
        proyecto_id: Project ID
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Created nodo

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    # Verify access
    verificar_acceso_proyecto(proyecto_id, current_user.id, manager, current_user.es_admin)

    # Verify concepto exists
    concepto = manager.obtener_concepto(proyecto_id, nodo_data.codigo_concepto)
    if not concepto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Concepto '{nodo_data.codigo_concepto}' not found"
        )

    # Create nodo
    nodo = manager.crear_nodo(
        proyecto_id=proyecto_id,
        codigo_concepto=nodo_data.codigo_concepto,
        padre_id=nodo_data.padre_id,
        nivel=nodo_data.nivel,
        orden=nodo_data.orden,
        cantidad=nodo_data.cantidad
    )

    return NodoResponse.model_validate(nodo)


@router.get("/{nodo_id}", response_model=NodoResponse)
async def obtener_nodo(
    nodo_id: int,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Get a nodo by ID.

    Args:
        nodo_id: Nodo ID
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Nodo

    Raises:
        HTTPException: If nodo not found or user doesn't have access
    """
    nodo = manager.obtener_nodo(nodo_id)

    if not nodo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nodo not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(nodo.proyecto_id, current_user.id, manager, current_user.es_admin)

    return NodoResponse.model_validate(nodo)


@router.put("/{nodo_id}", response_model=NodoResponse)
async def actualizar_nodo(
    nodo_id: int,
    nodo_update: NodoUpdate,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Update a nodo.

    Args:
        nodo_id: Nodo ID
        nodo_update: Nodo update data
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Updated nodo

    Raises:
        HTTPException: If nodo not found or user doesn't have access
    """
    nodo = manager.obtener_nodo(nodo_id)

    if not nodo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nodo not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(nodo.proyecto_id, current_user.id, manager, current_user.es_admin)

    # Update nodo
    updated_nodo = manager.actualizar_nodo(
        nodo_id,
        cantidad=nodo_update.cantidad,
        orden=nodo_update.orden
    )

    return NodoResponse.model_validate(updated_nodo)


@router.delete("/{nodo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_nodo(
    nodo_id: int,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Delete a nodo.

    Args:
        nodo_id: Nodo ID
        current_user: Current authenticated user
        manager: Database manager

    Raises:
        HTTPException: If nodo not found or user doesn't have access
    """
    nodo = manager.obtener_nodo(nodo_id)

    if not nodo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nodo not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(nodo.proyecto_id, current_user.id, manager, current_user.es_admin)

    manager.eliminar_nodo(nodo_id)
    return None


@router.post("/{nodo_id}/mover", response_model=NodoResponse)
async def mover_nodo(
    nodo_id: int,
    mover_data: NodoMover,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Move a nodo to a new parent or position.

    Args:
        nodo_id: Nodo ID
        mover_data: Move operation data
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Moved nodo

    Raises:
        HTTPException: If nodo not found or user doesn't have access
    """
    nodo = manager.obtener_nodo(nodo_id)

    if not nodo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nodo not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(nodo.proyecto_id, current_user.id, manager, current_user.es_admin)

    # Move nodo
    try:
        moved_nodo = manager.mover_nodo(
            nodo_id,
            nuevo_padre_id=mover_data.nuevo_padre_id,
            nuevo_orden=mover_data.nuevo_orden
        )
        return NodoResponse.model_validate(moved_nodo)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{nodo_id}/hijos", response_model=List[NodoResponse])
async def listar_hijos_nodo(
    nodo_id: int,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    List all children of a nodo.

    Args:
        nodo_id: Nodo ID
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        List of child nodos

    Raises:
        HTTPException: If nodo not found or user doesn't have access
    """
    nodo = manager.obtener_nodo(nodo_id)

    if not nodo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nodo not found"
        )

    # Verify access to project
    verificar_acceso_proyecto(nodo.proyecto_id, current_user.id, manager, current_user.es_admin)

    # Get children
    hijos = manager.listar_hijos_nodo(nodo_id)

    return [NodoResponse.model_validate(hijo) for hijo in hijos]
