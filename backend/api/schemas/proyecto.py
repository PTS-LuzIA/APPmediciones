"""
Pydantic schemas for Proyecto
"""

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class ProyectoBase(BaseModel):
    """Base schema for Proyecto"""
    nombre: str
    descripcion: Optional[str] = None


class ProyectoCreate(ProyectoBase):
    """Schema for creating a proyecto"""
    pass


class ProyectoUpdate(BaseModel):
    """Schema for updating a proyecto"""
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    fase_actual: Optional[int] = None
    presupuesto_total: Optional[Decimal] = None


class ProyectoResponse(ProyectoBase):
    """Schema for proyecto response"""
    id: int
    usuario_id: int
    pdf_path: Optional[str] = None
    fase_actual: int
    presupuesto_total: Decimal = Decimal(0)
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    tiene_mediciones_auxiliares: bool = False
    num_capitulos: int = 0

    class Config:
        from_attributes = True


class ProyectoCompleto(ProyectoResponse):
    """Schema for complete proyecto with statistics"""
    num_capitulos: int = 0
    num_partidas: int = 0
    num_mediciones: int = 0


class ProyectoArbol(BaseModel):
    """Schema for proyecto tree structure"""
    proyecto: ProyectoResponse
    arbol: List[Dict[str, Any]]


class EstadisticasProyecto(BaseModel):
    """Schema for proyecto statistics"""
    num_nodos: int
    num_conceptos: int
    num_capitulos: int
    num_subcapitulos: int
    num_partidas: int
    num_descompuestos: int
    num_mediciones: int
    presupuesto_total: Decimal = Decimal(0)
    niveles_profundidad: int
