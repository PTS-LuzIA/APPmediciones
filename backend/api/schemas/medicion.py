"""
Pydantic schemas for Medicion
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal
from models import TipoMedicion


class MedicionBase(BaseModel):
    """Base schema for Medicion"""
    tipo: TipoMedicion
    texto: str
    n_unidades: Optional[Decimal] = None
    largo: Optional[Decimal] = None
    ancho: Optional[Decimal] = None
    alto: Optional[Decimal] = None
    formula: Optional[str] = None
    resultado: Decimal
    orden: int = 1


class MedicionCreate(MedicionBase):
    """Schema for creating a medicion"""
    pass


class MedicionUpdate(BaseModel):
    """Schema for updating a medicion"""
    tipo: Optional[TipoMedicion] = None
    texto: Optional[str] = None
    n_unidades: Optional[Decimal] = None
    largo: Optional[Decimal] = None
    ancho: Optional[Decimal] = None
    alto: Optional[Decimal] = None
    formula: Optional[str] = None
    resultado: Optional[Decimal] = None
    orden: Optional[int] = None


class MedicionResponse(MedicionBase):
    """Schema for medicion response"""
    id: int
    nodo_id: int
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True
