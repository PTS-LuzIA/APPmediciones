"""
Modelo Proyecto - Representa un presupuesto completo
"""

from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base, SCHEMA_NAME


class Proyecto(Base):
    """
    Proyecto de presupuesto (contenedor principal)

    Un proyecto contiene:
    - Nodos (estructura jerárquica)
    - Conceptos (datos de elementos)
    - Usuarios asignados
    """
    __tablename__ = 'proyectos'
    __table_args__ = (
        Index('idx_proyecto_usuario', 'usuario_id'),
        {'schema': SCHEMA_NAME}
    )

    # Identificación
    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, nullable=False)  # Referencia a tabla usuarios
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)

    # Metadata del PDF procesado
    pdf_path = Column(String(500))
    pdf_nombre = Column(String(200))
    pdf_hash = Column(String(64))  # SHA256 para detectar duplicados

    # Totales
    presupuesto_total = Column(Numeric(14, 2), default=0)
    presupuesto_calculado = Column(Numeric(14, 2))

    # Metadata de procesamiento
    layout_detectado = Column(String(50))  # 'simple', 'multicolumna'
    numero_paginas = Column(Integer)
    fase_actual = Column(Integer, default=0)  # 0, 1, 2, 3, 4

    # Fechas
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Estado
    estado = Column(String(20), default='borrador')  # borrador, en_proceso, completado

    # Relaciones
    nodos = relationship("Nodo", back_populates="proyecto", cascade="all, delete-orphan")
    conceptos = relationship("Concepto", back_populates="proyecto", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Proyecto(id={self.id}, nombre='{self.nombre}', total={self.presupuesto_total})>"
