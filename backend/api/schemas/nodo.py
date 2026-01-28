"""
Pydantic schemas for Nodo
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


class NodoBase(BaseModel):
    """Base schema for Nodo"""
    codigo_concepto: str
    padre_id: Optional[int] = None
    nivel: int
    orden: int
    cantidad: Decimal = Decimal("1.0")


class NodoCreate(NodoBase):
    """Schema for creating a nodo"""
    pass


class NodoUpdate(BaseModel):
    """Schema for updating a nodo"""
    cantidad: Optional[Decimal] = None
    orden: Optional[int] = None


class NodoResponse(NodoBase):
    """Schema for nodo response"""
    id: int
    proyecto_id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True


class NodoCompleto(NodoResponse):
    """Schema for complete nodo with concepto data"""
    concepto_nombre: Optional[str] = None
    concepto_tipo: Optional[str] = None
    concepto_precio: Optional[Decimal] = None
    concepto_unidad: Optional[str] = None
    total_calculado: Optional[Decimal] = None


class NodoMover(BaseModel):
    """Schema for moving a nodo"""
    nuevo_padre_id: Optional[int] = None
    nuevo_orden: int


class NodoConHijos(NodoResponse):
    """Schema for nodo with children"""
    hijos: List['NodoConHijos'] = []

    class Config:
        from_attributes = True


# Needed for self-referential model
NodoConHijos.model_rebuild()
