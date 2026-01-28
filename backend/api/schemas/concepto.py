"""
Pydantic schemas for Concepto
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal
from models import TipoConcepto


class ConceptoBase(BaseModel):
    """Base schema for Concepto"""
    codigo: str
    tipo: TipoConcepto
    nombre: Optional[str] = None
    resumen: Optional[str] = None
    descripcion: Optional[str] = None
    unidad: Optional[str] = None
    precio: Optional[Decimal] = None
    cantidad_total: Optional[Decimal] = None
    importe_total: Optional[Decimal] = None
    total: Optional[Decimal] = None


class ConceptoCreate(ConceptoBase):
    """Schema for creating a concepto"""
    pass


class ConceptoUpdate(BaseModel):
    """Schema for updating a concepto"""
    nombre: Optional[str] = None
    resumen: Optional[str] = None
    descripcion: Optional[str] = None
    unidad: Optional[str] = None
    precio: Optional[Decimal] = None
    cantidad_total: Optional[Decimal] = None
    importe_total: Optional[Decimal] = None
    total: Optional[Decimal] = None


class ConceptoResponse(ConceptoBase):
    """Schema for concepto response"""
    id: int
    proyecto_id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True


class ConceptoConUsos(ConceptoResponse):
    """Schema for concepto with usage information"""
    num_usos: int
    nodos_ids: list[int]
