"""
Database Manager - CRUD operations para APPmediciones
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
import logging
import sys
from pathlib import Path

# Añadir el directorio backend al path
sys.path.append(str(Path(__file__).parent.parent))

from models import Proyecto, Nodo, Concepto, Medicion, TipoConcepto
from database.queries import QueryHelper

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gestor de base de datos para APPmediciones.

    Proporciona métodos CRUD y operaciones complejas sobre la estructura jerárquica.
    """

    def __init__(self, session: Session):
        self.session = session
        self.queries = QueryHelper(session)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        self.session.close()

    # =====================================================
    # PROYECTOS
    # =====================================================

    def crear_proyecto(self, usuario_id: int, nombre: str, descripcion: str = None) -> Proyecto:
        """
        Crea un nuevo proyecto.

        Args:
            usuario_id: ID del usuario propietario
            nombre: Nombre del proyecto
            descripcion: Descripción opcional

        Returns:
            Proyecto creado
        """
        proyecto = Proyecto(
            usuario_id=usuario_id,
            nombre=nombre,
            descripcion=descripcion,
            estado='borrador'
        )

        self.session.add(proyecto)
        self.session.flush()

        # Crear nodo raíz
        self._crear_nodo_raiz(proyecto.id)

        self.session.commit()
        logger.info(f"✓ Proyecto creado: {proyecto.id} - {nombre}")
        return proyecto

    def obtener_proyecto(self, proyecto_id: int) -> Optional[Proyecto]:
        """Obtiene un proyecto por ID"""
        return self.session.query(Proyecto).filter_by(id=proyecto_id).first()

    def listar_proyectos(self, usuario_id: int, limite: int = 50, offset: int = 0) -> List[Proyecto]:
        """Lista proyectos de un usuario"""
        return (
            self.session.query(Proyecto)
            .filter_by(usuario_id=usuario_id)
            .order_by(Proyecto.fecha_creacion.desc())
            .limit(limite)
            .offset(offset)
            .all()
        )

    def eliminar_proyecto(self, proyecto_id: int) -> bool:
        """
        Elimina un proyecto y toda su estructura (cascade).

        Returns:
            True si se eliminó, False si no existía
        """
        proyecto = self.obtener_proyecto(proyecto_id)
        if not proyecto:
            return False

        self.session.delete(proyecto)
        self.session.commit()
        logger.info(f"✓ Proyecto eliminado: {proyecto_id}")
        return True

    # =====================================================
    # CONCEPTOS
    # =====================================================

    def crear_concepto(
        self,
        proyecto_id: int,
        codigo: str,
        tipo: TipoConcepto,
        nombre: str = None,
        **kwargs
    ) -> Concepto:
        """
        Crea un nuevo concepto.

        Args:
            proyecto_id: ID del proyecto
            codigo: Código único del concepto
            tipo: Tipo de concepto
            nombre: Nombre del concepto
            **kwargs: Otros campos (resumen, precio, unidad, etc.)

        Returns:
            Concepto creado
        """
        concepto = Concepto(
            proyecto_id=proyecto_id,
            codigo=codigo,
            tipo=tipo,
            nombre=nombre,
            **kwargs
        )

        self.session.add(concepto)
        self.session.commit()
        logger.debug(f"✓ Concepto creado: {codigo} ({tipo})")
        return concepto

    def obtener_concepto(self, proyecto_id: int, codigo: str) -> Optional[Concepto]:
        """Obtiene un concepto por código"""
        return (
            self.session.query(Concepto)
            .filter_by(proyecto_id=proyecto_id, codigo=codigo)
            .first()
        )

    def obtener_concepto_por_id(self, concepto_id: int) -> Optional[Concepto]:
        """Obtiene un concepto por ID"""
        return self.session.query(Concepto).filter_by(id=concepto_id).first()

    def listar_conceptos(
        self,
        proyecto_id: int,
        tipo: TipoConcepto = None,
        limite: int = 1000
    ) -> List[Concepto]:
        """
        Lista conceptos de un proyecto.

        Args:
            proyecto_id: ID del proyecto
            tipo: Filtrar por tipo (opcional)
            limite: Máximo de resultados

        Returns:
            Lista de conceptos
        """
        query = self.session.query(Concepto).filter_by(proyecto_id=proyecto_id)

        if tipo:
            query = query.filter_by(tipo=tipo)

        return query.order_by(Concepto.codigo).limit(limite).all()

    def actualizar_concepto(
        self,
        proyecto_id: int,
        codigo: str,
        **campos
    ) -> Optional[Concepto]:
        """
        Actualiza campos de un concepto.

        Args:
            proyecto_id: ID del proyecto
            codigo: Código del concepto
            **campos: Campos a actualizar

        Returns:
            Concepto actualizado o None si no existe
        """
        concepto = self.obtener_concepto(proyecto_id, codigo)
        if not concepto:
            return None

        for campo, valor in campos.items():
            if hasattr(concepto, campo):
                setattr(concepto, campo, valor)

        self.session.commit()
        logger.debug(f"✓ Concepto actualizado: {codigo}")
        return concepto

    # =====================================================
    # NODOS (Estructura Jerárquica)
    # =====================================================

    def crear_nodo(
        self,
        proyecto_id: int,
        codigo_concepto: str,
        padre_id: int = None,
        nivel: int = None,
        orden: int = None,
        cantidad: float = 1.0
    ) -> Nodo:
        """
        Crea un nodo en la estructura jerárquica.

        Args:
            proyecto_id: ID del proyecto
            codigo_concepto: Código del concepto al que apunta
            padre_id: ID del nodo padre (None = raíz)
            nivel: Nivel jerárquico (se calcula si no se proporciona)
            orden: Orden entre hermanos (se calcula si no se proporciona)
            cantidad: Cantidad en relación padre-hijo

        Returns:
            Nodo creado
        """
        # Calcular nivel si no se proporciona
        if nivel is None:
            if padre_id is None:
                nivel = 0
            else:
                padre = self.session.query(Nodo).filter_by(id=padre_id).first()
                nivel = padre.nivel + 1 if padre else 0

        # Calcular orden si no se proporciona
        if orden is None:
            orden = self._calcular_siguiente_orden(proyecto_id, padre_id)

        nodo = Nodo(
            proyecto_id=proyecto_id,
            padre_id=padre_id,
            codigo_concepto=codigo_concepto,
            nivel=nivel,
            orden=orden,
            cantidad=cantidad
        )

        self.session.add(nodo)
        self.session.commit()
        logger.debug(f"✓ Nodo creado: {codigo_concepto} (nivel={nivel}, orden={orden})")
        return nodo

    def obtener_nodo(self, nodo_id: int) -> Optional[Nodo]:
        """Obtiene un nodo por ID"""
        return self.session.query(Nodo).filter_by(id=nodo_id).first()

    def obtener_nodo_raiz(self, proyecto_id: int) -> Optional[Nodo]:
        """Obtiene el nodo raíz de un proyecto"""
        return (
            self.session.query(Nodo)
            .filter_by(proyecto_id=proyecto_id, padre_id=None)
            .first()
        )

    def listar_hijos(self, nodo_id: int) -> List[Nodo]:
        """
        Lista los hijos directos de un nodo, ordenados por 'orden'.

        Args:
            nodo_id: ID del nodo padre

        Returns:
            Lista de nodos hijos
        """
        return (
            self.session.query(Nodo)
            .filter_by(padre_id=nodo_id)
            .order_by(Nodo.orden)
            .all()
        )

    def obtener_arbol_completo(self, proyecto_id: int) -> List[Dict[str, Any]]:
        """
        Obtiene el árbol completo del proyecto con datos de conceptos.

        Returns:
            Lista de nodos con datos jerárquicos y de conceptos
        """
        return self.queries.obtener_arbol_completo(proyecto_id)

    def eliminar_nodo(self, nodo_id: int) -> bool:
        """
        Elimina un nodo y todos sus descendientes (cascade).

        Returns:
            True si se eliminó, False si no existía
        """
        nodo = self.obtener_nodo(nodo_id)
        if not nodo:
            return False

        self.session.delete(nodo)
        self.session.commit()
        logger.debug(f"✓ Nodo eliminado: {nodo_id}")
        return True

    def mover_nodo(
        self,
        nodo_id: int,
        nuevo_padre_id: int = None,
        nuevo_orden: int = None
    ) -> Optional[Nodo]:
        """
        Mueve un nodo a una nueva posición en el árbol.

        Args:
            nodo_id: ID del nodo a mover
            nuevo_padre_id: ID del nuevo padre (None = mover a raíz)
            nuevo_orden: Nuevo orden entre hermanos (None = al final)

        Returns:
            Nodo actualizado o None si no existe
        """
        nodo = self.obtener_nodo(nodo_id)
        if not nodo:
            return None

        # Actualizar padre
        nodo.padre_id = nuevo_padre_id

        # Recalcular nivel
        if nuevo_padre_id is None:
            nodo.nivel = 0
        else:
            padre = self.obtener_nodo(nuevo_padre_id)
            nodo.nivel = padre.nivel + 1 if padre else 0

        # Actualizar orden
        if nuevo_orden is not None:
            nodo.orden = nuevo_orden
        else:
            nodo.orden = self._calcular_siguiente_orden(nodo.proyecto_id, nuevo_padre_id)

        self.session.commit()
        logger.debug(f"✓ Nodo movido: {nodo_id} → padre={nuevo_padre_id}")
        return nodo

    # =====================================================
    # MEDICIONES
    # =====================================================

    def crear_medicion(
        self,
        concepto_id: int,
        comentario: str = None,
        unidades: float = 1.0,
        largo: float = 1.0,
        ancho: float = 1.0,
        alto: float = 1.0,
        orden: int = None
    ) -> Medicion:
        """
        Crea una medición para una partida.

        Args:
            concepto_id: ID del concepto (debe ser tipo PARTIDA)
            comentario: Descripción de la medición
            unidades, largo, ancho, alto: Dimensiones
            orden: Orden de la medición (se calcula si no se proporciona)

        Returns:
            Medición creada
        """
        if orden is None:
            orden = self._calcular_siguiente_orden_medicion(concepto_id)

        medicion = Medicion(
            concepto_id=concepto_id,
            comentario=comentario,
            unidades=unidades,
            largo=largo,
            ancho=ancho,
            alto=alto,
            orden=orden
        )

        # Calcular subtotal
        medicion.calcular_subtotal()

        self.session.add(medicion)
        self.session.commit()
        logger.debug(f"✓ Medición creada: {medicion.subtotal} para concepto {concepto_id}")
        return medicion

    def listar_mediciones(self, concepto_id: int) -> List[Medicion]:
        """Lista mediciones de un concepto"""
        return (
            self.session.query(Medicion)
            .filter_by(concepto_id=concepto_id)
            .order_by(Medicion.orden)
            .all()
        )

    # =====================================================
    # MÉTODOS PRIVADOS
    # =====================================================

    def _crear_nodo_raiz(self, proyecto_id: int) -> Nodo:
        """Crea el nodo raíz del proyecto"""
        # Primero crear concepto raíz
        concepto_raiz = Concepto(
            proyecto_id=proyecto_id,
            codigo="ROOT",
            tipo=TipoConcepto.RAIZ,
            nombre="Raíz"
        )
        self.session.add(concepto_raiz)
        self.session.flush()

        # Crear nodo raíz
        nodo_raiz = Nodo(
            proyecto_id=proyecto_id,
            padre_id=None,
            codigo_concepto="ROOT",
            nivel=0,
            orden=0,
            cantidad=1.0
        )
        self.session.add(nodo_raiz)
        self.session.flush()

        return nodo_raiz

    def _calcular_siguiente_orden(self, proyecto_id: int, padre_id: int = None) -> int:
        """Calcula el siguiente orden para hermanos"""
        max_orden = (
            self.session.query(Nodo.orden)
            .filter_by(proyecto_id=proyecto_id, padre_id=padre_id)
            .order_by(Nodo.orden.desc())
            .first()
        )
        return (max_orden[0] + 1) if max_orden else 1

    def _calcular_siguiente_orden_medicion(self, concepto_id: int) -> int:
        """Calcula el siguiente orden para mediciones"""
        max_orden = (
            self.session.query(Medicion.orden)
            .filter_by(concepto_id=concepto_id)
            .order_by(Medicion.orden.desc())
            .first()
        )
        return (max_orden[0] + 1) if max_orden else 1
