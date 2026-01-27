"""
Modelo Medicion - Mediciones dimensionales de partidas
"""

from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text, Index, Enum
from sqlalchemy.orm import relationship
import enum
from .base import Base, SCHEMA_NAME


class TipoMedicion(str, enum.Enum):
    """Tipos de medición"""
    NORMAL = "NORMAL"          # Medición normal
    PARCIAL = "PARCIAL"        # Medición parcial
    ACUMULADA = "ACUMULADA"    # Medición acumulada


class Medicion(Base):
    """
    Medición dimensional de una partida.

    Fórmula: subtotal = unidades × largo × ancho × alto

    Similar a los registros ~M del formato BC3/FIEBDC-3.

    Ejemplos:
    - Excavación: 5 (uds) × 10.5 (largo) × 3.2 (ancho) × 1.5 (alto) = 252 m3
    - Pintura: 1 (ud) × 50.0 (largo) × 2.5 (alto) = 125 m2
    - Tubería: 10 (uds) × 3.5 (largo) = 35 m
    """
    __tablename__ = 'mediciones'
    __table_args__ = (
        Index('idx_medicion_concepto', 'concepto_id'),
        Index('idx_medicion_orden', 'orden'),
        {'schema': SCHEMA_NAME}
    )

    # Identificación
    id = Column(Integer, primary_key=True)
    concepto_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.conceptos.id'), nullable=False)

    # Descripción
    comentario = Column(String(500))   # Descripción de la medición
    tipo = Column(Enum(TipoMedicion), default=TipoMedicion.NORMAL)

    # Dimensiones (fórmula de cálculo)
    unidades = Column(Numeric(14, 4), default=1.0)  # N
    largo = Column(Numeric(14, 4), default=1.0)     # Largo
    ancho = Column(Numeric(14, 4), default=1.0)     # Ancho
    alto = Column(Numeric(14, 4), default=1.0)      # Alto

    # Resultado
    subtotal = Column(Numeric(14, 4))  # N × Largo × Ancho × Alto

    # Orden de aparición
    orden = Column(Integer, nullable=False)

    # Relaciones
    concepto = relationship("Concepto", back_populates="mediciones")

    def __repr__(self):
        return f"<Medicion(id={self.id}, subtotal={self.subtotal}, comentario='{self.comentario[:30]}...')>"

    def calcular_subtotal(self):
        """
        Calcula el subtotal basándose en las dimensiones.

        Reglas:
        - Si una dimensión es NULL, se toma como 1.0
        - subtotal = unidades × largo × ancho × alto
        """
        n = self.unidades or 1.0
        l = self.largo or 1.0
        a = self.ancho or 1.0
        h = self.alto or 1.0

        self.subtotal = n * l * a * h
        return self.subtotal

    @property
    def formula_texto(self):
        """
        Genera una representación textual de la fórmula.

        Ejemplos:
        - "5 × 10.5 × 3.2 × 1.5 = 252.00"
        - "1 × 50.0 × 2.5 = 125.00"
        """
        partes = []

        if self.unidades and self.unidades != 1.0:
            partes.append(f"{self.unidades}")

        if self.largo and self.largo != 1.0:
            partes.append(f"{self.largo}")

        if self.ancho and self.ancho != 1.0:
            partes.append(f"{self.ancho}")

        if self.alto and self.alto != 1.0:
            partes.append(f"{self.alto}")

        if not partes:
            return f"{self.subtotal or 0}"

        formula = " × ".join(partes)
        return f"{formula} = {self.subtotal or 0}"
