"""
Modelo Concepto - Datos de cada elemento del presupuesto
"""

from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text, DateTime, Index, UniqueConstraint, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .base import Base, SCHEMA_NAME


class TipoConcepto(str, enum.Enum):
    """
    Tipos de conceptos en el presupuesto.
    Compatible con BC3/FIEBDC-3.
    """
    RAIZ = "RAIZ"                    # Nodo raíz (invisible en UI)
    CAPITULO = "CAPITULO"            # Capítulo principal
    SUBCAPITULO = "SUBCAPITULO"      # Subcapítulo (cualquier nivel)
    PARTIDA = "PARTIDA"              # Partida / Unidad de obra
    DESCOMPUESTO = "DESCOMPUESTO"    # Descomposición de una partida
    MANO_OBRA = "MANO_OBRA"          # Mano de obra en descompuesto
    MATERIAL = "MATERIAL"            # Material en descompuesto
    MAQUINARIA = "MAQUINARIA"        # Maquinaria en descompuesto
    AUXILIAR = "AUXILIAR"            # Partida auxiliar


class Concepto(Base):
    """
    Concepto del presupuesto (capítulo, partida, descompuesto, etc.)

    Contiene todos los DATOS del elemento, independiente de su posición
    en la estructura jerárquica.

    Similar a los registros ~C del formato BC3/FIEBDC-3.

    Un mismo concepto puede aparecer en múltiples lugares del presupuesto
    (reutilización), cada aparición será un Nodo diferente apuntando al
    mismo Concepto.
    """
    __tablename__ = 'conceptos'
    __table_args__ = (
        Index('idx_concepto_proyecto', 'proyecto_id'),
        Index('idx_concepto_codigo', 'codigo'),
        Index('idx_concepto_tipo', 'tipo'),
        UniqueConstraint('proyecto_id', 'codigo', name='uq_concepto_proyecto_codigo'),
        {'schema': SCHEMA_NAME}
    )

    # Identificación
    id = Column(Integer, primary_key=True)
    proyecto_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.proyectos.id'), nullable=False)
    codigo = Column(String(50), nullable=False)  # Único dentro del proyecto

    # Tipo de concepto
    tipo = Column(Enum(TipoConcepto), nullable=False)

    # Datos comunes
    nombre = Column(String(500))
    resumen = Column(String(500))      # Título corto (para partidas)
    descripcion = Column(Text)         # Descripción larga completa

    # Datos económicos
    unidad = Column(String(20))        # ud, m, m2, m3, kg, h, etc.
    precio = Column(Numeric(14, 4))    # Precio unitario

    # Para capítulos y subcapítulos (totales del PDF)
    total = Column(Numeric(14, 2))              # Total leído del PDF
    total_calculado = Column(Numeric(14, 2))    # Total calculado (suma de hijos)

    # Para partidas (cantidades totales en el proyecto)
    cantidad_total = Column(Numeric(14, 4))     # Suma de todas las mediciones
    importe_total = Column(Numeric(14, 2))      # cantidad_total * precio

    # Flags
    tiene_mediciones = Column(Integer, default=0)       # Booleano: tiene mediciones auxiliares
    mediciones_validadas = Column(Integer, default=0)   # Booleano: mediciones validadas

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    proyecto = relationship("Proyecto", back_populates="conceptos")
    mediciones = relationship("Medicion", back_populates="concepto", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Concepto(codigo='{self.codigo}', tipo={self.tipo}, nombre='{self.nombre[:30]}...')>"

    @property
    def es_contenedor(self):
        """Verifica si es un contenedor (capítulo o subcapítulo)"""
        return self.tipo in (TipoConcepto.CAPITULO, TipoConcepto.SUBCAPITULO, TipoConcepto.RAIZ)

    @property
    def es_medible(self):
        """Verifica si es un elemento que puede tener mediciones"""
        return self.tipo == TipoConcepto.PARTIDA

    @property
    def es_descomponible(self):
        """Verifica si puede tener descomposición"""
        return self.tipo in (TipoConcepto.PARTIDA, TipoConcepto.DESCOMPUESTO)

    def calcular_importe(self):
        """
        Calcula el importe total: cantidad_total * precio
        """
        if self.cantidad_total and self.precio:
            self.importe_total = self.cantidad_total * self.precio
            return self.importe_total
        return None
