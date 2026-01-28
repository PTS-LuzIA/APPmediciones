"""
Pydantic schemas for PDF procesamiento
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class PDFUploadResponse(BaseModel):
    """Schema for PDF upload response"""
    proyecto_id: int
    pdf_path: str
    mensaje: str


class FaseResultado(BaseModel):
    """Schema for fase execution result"""
    fase: int
    proyecto_id: int
    exito: bool
    mensaje: str
    datos: Optional[Dict[str, Any]] = None


class Fase1Resultado(FaseResultado):
    """Schema for Fase 1 result"""
    titulo_proyecto: Optional[str] = None
    num_conceptos: int = 0
    num_nodos: int = 0
    conceptos: List[Dict[str, Any]] = []


class Fase2Resultado(FaseResultado):
    """Schema for Fase 2 result"""
    num_partidas: int = 0
    partidas: List[Dict[str, Any]] = []


class Fase3Resultado(FaseResultado):
    """Schema for Fase 3 result"""
    total_presupuesto: Optional[float] = None
    num_discrepancias: int = 0
    discrepancias: List[Dict[str, Any]] = []
