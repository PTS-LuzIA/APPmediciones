"""
Modelo Nodo - Define la estructura jerárquica del presupuesto (árbol)
"""

from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Index
from sqlalchemy.orm import relationship
from .base import Base, SCHEMA_NAME


class Nodo(Base):
    """
    Nodo en el árbol jerárquico del presupuesto.

    Define la ESTRUCTURA, no los datos del elemento.
    Los datos están en la tabla Conceptos.

    Similar a los registros ~D del formato BC3/FIEBDC-3.

    Ejemplos:
    - Capítulo "C01" → Nodo(codigo_concepto="C01", padre_id=NULL, nivel=1)
    - Subcapítulo "C01.01" → Nodo(codigo_concepto="C01.01", padre_id=id_de_C01, nivel=2)
    - Partida "E001" → Nodo(codigo_concepto="E001", padre_id=id_de_C01.01, nivel=3)
    - Descompuesto "MO001" → Nodo(codigo_concepto="MO001", padre_id=id_de_E001, nivel=4)
    """
    __tablename__ = 'nodos'
    __table_args__ = (
        Index('idx_nodo_proyecto', 'proyecto_id'),
        Index('idx_nodo_padre', 'padre_id'),
        Index('idx_nodo_concepto', 'codigo_concepto'),
        Index('idx_nodo_nivel_orden', 'nivel', 'orden'),
        {'schema': SCHEMA_NAME}
    )

    # Identificación
    id = Column(Integer, primary_key=True)
    proyecto_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.proyectos.id'), nullable=False)
    padre_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.nodos.id'), nullable=True)  # NULL = raíz

    # Referencia al concepto (datos del elemento)
    codigo_concepto = Column(String(50), nullable=False)

    # Posición en la jerarquía
    nivel = Column(Integer, nullable=False)  # 0=raíz, 1=capítulo, 2=subcap, 3=partida, 4=descompuesto...
    orden = Column(Integer, nullable=False)  # Orden entre hermanos (mismo nivel, mismo padre)

    # Cantidad en la relación padre-hijo
    # Ejemplo: Si una partida usa 2.5 unidades de un material, cantidad=2.5
    cantidad = Column(Numeric(14, 4), default=1.0)

    # Relaciones
    proyecto = relationship("Proyecto", back_populates="nodos")
    padre = relationship("Nodo", remote_side=[id], back_populates="hijos")
    hijos = relationship("Nodo",
                        back_populates="padre",
                        cascade="all, delete-orphan",
                        order_by="Nodo.orden")

    def __repr__(self):
        return f"<Nodo(id={self.id}, concepto='{self.codigo_concepto}', nivel={self.nivel}, orden={self.orden})>"

    @property
    def es_raiz(self):
        """Verifica si este nodo es la raíz del árbol"""
        return self.padre_id is None

    @property
    def es_hoja(self):
        """Verifica si este nodo es una hoja (no tiene hijos)"""
        return len(self.hijos) == 0

    def obtener_ruta(self):
        """
        Obtiene la ruta completa desde la raíz hasta este nodo.
        Retorna una lista de códigos de concepto.

        Ejemplo: ['C01', 'C01.01', 'E001']
        """
        ruta = []
        nodo_actual = self
        while nodo_actual:
            ruta.insert(0, nodo_actual.codigo_concepto)
            nodo_actual = nodo_actual.padre
        return ruta

    def obtener_profundidad(self):
        """
        Calcula la profundidad del nodo (distancia desde la raíz).
        La raíz tiene profundidad 0.
        """
        profundidad = 0
        nodo_actual = self.padre
        while nodo_actual:
            profundidad += 1
            nodo_actual = nodo_actual.padre
        return profundidad
