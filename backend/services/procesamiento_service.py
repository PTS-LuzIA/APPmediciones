"""
Procesamiento Service - Lógica de negocio para procesamiento de PDFs
"""

from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from database.manager import DatabaseManager
from parsers import PresupuestoParser
from models import TipoConcepto

logger = logging.getLogger(__name__)


class ProcesamientoService:
    """
    Servicio para procesamiento de PDFs en 4 fases.
    """

    def __init__(self, db: Session):
        self.db = db
        self.manager = DatabaseManager(db)

    def ejecutar_fase1(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 1: Extracción de estructura.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado de Fase 1
        """
        logger.info(f"🔧 [FASE 1] Iniciando para proyecto {proyecto_id}")

        # Crear parser
        parser = PresupuestoParser(pdf_path, proyecto_id)

        # Ejecutar Fase 1
        resultado = parser.ejecutar_fase1()

        # Guardar en base de datos
        self._guardar_fase1_en_bd(proyecto_id, resultado)

        logger.info(f"✓ Fase 1 completada y guardada en BD")
        return resultado

    def ejecutar_fase2(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 2: Extracción de partidas.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado de Fase 2
        """
        logger.info(f"🔧 [FASE 2] Iniciando para proyecto {proyecto_id}")

        # Crear parser
        parser = PresupuestoParser(pdf_path, proyecto_id)

        # Ejecutar Fase 1 (necesaria para tener estructura)
        parser.ejecutar_fase1()

        # Ejecutar Fase 2
        resultado = parser.ejecutar_fase2()

        # Guardar en base de datos
        self._guardar_fase2_en_bd(proyecto_id, resultado)

        logger.info(f"✓ Fase 2 completada y guardada en BD")
        return resultado

    def ejecutar_fase3(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 3: Cálculo de totales y validación.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado de Fase 3
        """
        logger.info(f"🔧 [FASE 3] Iniciando para proyecto {proyecto_id}")

        # Crear parser
        parser = PresupuestoParser(pdf_path, proyecto_id)

        # Ejecutar fases 1 y 2
        parser.ejecutar_fase1()
        parser.ejecutar_fase2()

        # Ejecutar Fase 3
        resultado = parser.ejecutar_fase3()

        logger.info(f"✓ Fase 3 completada: {resultado['num_discrepancias']} discrepancias")
        return resultado

    # =====================================================
    # MÉTODOS PRIVADOS
    # =====================================================

    def _guardar_fase1_en_bd(self, proyecto_id: int, resultado: Dict[str, Any]):
        """
        Guarda el resultado de Fase 1 en la base de datos.

        Crea:
        - Conceptos (CAPITULO, SUBCAPITULO)
        - Nodos (estructura jerárquica)
        """
        # Actualizar título del proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if proyecto and resultado.get('titulo_proyecto'):
            proyecto.nombre = resultado['titulo_proyecto']
            proyecto.fase_actual = 1
            self.db.commit()

        # Obtener nodo raíz
        nodo_raiz = self.manager.obtener_nodo_raiz(proyecto_id)

        # Crear conceptos
        conceptos = resultado.get('conceptos', [])
        for concepto_data in conceptos:
            # Verificar si ya existe
            concepto_existente = self.manager.obtener_concepto(proyecto_id, concepto_data['codigo'])
            if concepto_existente:
                continue

            self.manager.crear_concepto(
                proyecto_id=proyecto_id,
                codigo=concepto_data['codigo'],
                tipo=concepto_data['tipo'],
                nombre=concepto_data.get('nombre'),
                total=concepto_data.get('total'),
                resumen=concepto_data.get('resumen'),
                descripcion=concepto_data.get('descripcion')
            )

        # Crear nodos
        nodos = resultado.get('nodos', [])
        codigo_a_nodo_id = {}  # Mapa para encontrar IDs de nodos padres

        for nodo_data in nodos:
            # Determinar padre_id
            padre_codigo = nodo_data.get('padre_codigo')
            if padre_codigo:
                padre_id = codigo_a_nodo_id.get(padre_codigo)
            else:
                padre_id = nodo_raiz.id if nodo_raiz else None

            # Crear nodo
            nodo = self.manager.crear_nodo(
                proyecto_id=proyecto_id,
                codigo_concepto=nodo_data['codigo_concepto'],
                padre_id=padre_id,
                nivel=nodo_data.get('nivel'),
                orden=nodo_data.get('orden'),
                cantidad=nodo_data.get('cantidad', 1.0)
            )

            # Guardar en mapa
            codigo_a_nodo_id[nodo_data['codigo_concepto']] = nodo.id

        logger.info(f"✓ Fase 1 guardada: {len(conceptos)} conceptos, {len(nodos)} nodos")

    def _guardar_fase2_en_bd(self, proyecto_id: int, resultado: Dict[str, Any]):
        """
        Guarda el resultado de Fase 2 en la base de datos.

        Crea:
        - Conceptos (PARTIDA)
        - Nodos (partidas en la estructura)
        """
        # Actualizar proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if proyecto:
            proyecto.fase_actual = 2
            self.db.commit()

        # Crear conceptos de partidas
        conceptos_partidas = resultado.get('conceptos_partidas', [])
        for concepto_data in conceptos_partidas:
            # Verificar si ya existe
            concepto_existente = self.manager.obtener_concepto(proyecto_id, concepto_data['codigo'])
            if concepto_existente:
                continue

            self.manager.crear_concepto(
                proyecto_id=proyecto_id,
                codigo=concepto_data['codigo'],
                tipo=TipoConcepto.PARTIDA,
                nombre=concepto_data.get('nombre'),
                resumen=concepto_data.get('resumen'),
                unidad=concepto_data.get('unidad'),
                precio=concepto_data.get('precio'),
                cantidad_total=concepto_data.get('cantidad_total'),
                importe_total=concepto_data.get('importe_total')
            )

        # Crear nodos de partidas
        nodos_partidas = resultado.get('nodos_partidas', [])

        # Obtener mapa de códigos a nodos existentes
        nodos_existentes = self.db.query(
            "SELECT id, codigo_concepto FROM appmediciones.nodos WHERE proyecto_id = :pid",
            {'pid': proyecto_id}
        ).fetchall()
        codigo_a_nodo_id = {n[1]: n[0] for n in nodos_existentes}

        for nodo_data in nodos_partidas:
            # Determinar padre_id
            padre_codigo = nodo_data.get('padre_codigo')
            padre_id = codigo_a_nodo_id.get(padre_codigo) if padre_codigo else None

            # Crear nodo
            self.manager.crear_nodo(
                proyecto_id=proyecto_id,
                codigo_concepto=nodo_data['codigo_concepto'],
                padre_id=padre_id,
                nivel=nodo_data.get('nivel'),
                orden=nodo_data.get('orden'),
                cantidad=nodo_data.get('cantidad', 1.0)
            )

        logger.info(f"✓ Fase 2 guardada: {len(conceptos_partidas)} partidas")
