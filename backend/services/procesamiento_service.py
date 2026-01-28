"""
Procesamiento Service - Lógica de negocio para procesamiento de PDFs
Actualizado para usar PDFOrchestrator (parser_v2)
"""

from sqlalchemy.orm import Session
from typing import Dict, Any
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from database.manager import DatabaseManager
from parsers.orchestrator import PDFOrchestrator
from models import TipoConcepto

logger = logging.getLogger(__name__)


class ProcesamientoService:
    """
    Servicio para procesamiento de PDFs usando PDFOrchestrator v2.
    """

    def __init__(self, db: Session):
        self.db = db
        self.manager = DatabaseManager(db)

    def procesar_pdf_completo(self, proyecto_id: int, user_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Procesa un PDF completamente usando PDFOrchestrator v2.

        Args:
            proyecto_id: ID del proyecto
            user_id: ID del usuario
            pdf_path: Ruta al archivo PDF

        Returns:
            Resultado completo del procesamiento
        """
        logger.info(f"🚀 Iniciando procesamiento completo del PDF para proyecto {proyecto_id}")

        try:
            # Crear orchestrador
            orchestrator = PDFOrchestrator(pdf_path, user_id, proyecto_id)

            # Ejecutar procesamiento (4 fases automáticas)
            resultado = orchestrator.parsear()

            # Guardar resultados en base de datos
            self._guardar_resultado_completo_en_bd(proyecto_id, resultado)

            logger.info(f"✅ Procesamiento completo exitoso para proyecto {proyecto_id}")
            return resultado

        except Exception as e:
            logger.error(f"❌ Error procesando PDF: {str(e)}")
            raise

    def ejecutar_fase1(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 1: Extracción de estructura.
        
        Nota: El nuevo sistema procesa todo automáticamente.
        Este método es legacy y redirige al procesamiento completo.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado parcial de Fase 1
        """
        logger.info(f"🔧 [FASE 1] Iniciando para proyecto {proyecto_id}")
        
        # Obtener user_id del proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            raise ValueError(f"Proyecto {proyecto_id} no encontrado")
        
        # Ejecutar procesamiento completo
        resultado = self.procesar_pdf_completo(proyecto_id, proyecto.usuario_id, pdf_path)
        
        # Devolver solo la estructura (compatibilidad con API anterior)
        logger.info(f"✓ Fase 1 completada")
        return {
            'estructura': resultado.get('estructura', {}),
            'metadata': resultado.get('metadata', {}),
            'estadisticas': resultado.get('estadisticas', {})
        }

    def ejecutar_fase2(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 2: Extracción de partidas.
        
        Nota: El nuevo sistema procesa todo automáticamente.
        Este método es legacy y redirige al procesamiento completo.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado parcial de Fase 2
        """
        logger.info(f"🔧 [FASE 2] Iniciando para proyecto {proyecto_id}")
        
        # Obtener user_id del proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            raise ValueError(f"Proyecto {proyecto_id} no encontrado")
        
        # Si ya está procesado, no reprocesar
        if proyecto.fase_actual >= 2:
            logger.info("✓ Proyecto ya procesado, retornando resultado existente")
            return {'message': 'Proyecto ya procesado', 'fase_actual': proyecto.fase_actual}
        
        # Ejecutar procesamiento completo
        resultado = self.procesar_pdf_completo(proyecto_id, proyecto.usuario_id, pdf_path)
        
        logger.info(f"✓ Fase 2 completada")
        return resultado

    def ejecutar_fase3(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 3: Cálculo de totales y validación.
        
        Nota: El nuevo sistema procesa todo automáticamente.
        Este método es legacy y redirige al procesamiento completo.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado parcial de Fase 3
        """
        logger.info(f"🔧 [FASE 3] Iniciando para proyecto {proyecto_id}")
        
        # Obtener user_id del proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            raise ValueError(f"Proyecto {proyecto_id} no encontrado")
        
        # Si ya está procesado, no reprocesar
        if proyecto.fase_actual >= 3:
            logger.info("✓ Proyecto ya procesado, retornando resultado existente")
            return {'message': 'Proyecto ya procesado', 'fase_actual': proyecto.fase_actual}
        
        # Ejecutar procesamiento completo
        resultado = self.procesar_pdf_completo(proyecto_id, proyecto.usuario_id, pdf_path)
        
        logger.info(f"✓ Fase 3 completada")
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

    def _guardar_resultado_completo_en_bd(self, proyecto_id: int, resultado: Dict[str, Any]):
        """
        Guarda el resultado completo del parser v2 en la base de datos.

        Args:
            proyecto_id: ID del proyecto
            resultado: Resultado del PDFOrchestrator con estructura completa
        """
        logger.info(f"💾 Guardando resultado en base de datos para proyecto {proyecto_id}")

        # Actualizar proyecto con metadata
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            logger.error(f"Proyecto {proyecto_id} no encontrado")
            return

        # Actualizar título si se detectó
        metadata = resultado.get('metadata', {})
        if metadata.get('titulo_proyecto'):
            proyecto.nombre = metadata['titulo_proyecto']

        proyecto.fase_actual = 4  # Procesamiento completo
        self.db.commit()

        # Obtener nodo raíz
        nodo_raiz = self.manager.obtener_nodo_raiz(proyecto_id)
        if not nodo_raiz:
            logger.error(f"Nodo raíz no encontrado para proyecto {proyecto_id}")
            return

        # Procesar estructura jerárquica
        estructura = resultado.get('estructura', {})
        capitulos = estructura.get('capitulos', [])

        # Mapa para tracking de nodos creados
        codigo_a_nodo_id = {}

        # Procesar cada capítulo
        for capitulo in capitulos:
            self._procesar_capitulo_recursivo(
                proyecto_id=proyecto_id,
                capitulo_data=capitulo,
                padre_id=nodo_raiz.id,
                codigo_a_nodo_id=codigo_a_nodo_id,
                nivel=1
            )

        # Estadísticas
        stats = resultado.get('estadisticas', {})
        logger.info(f"✅ Guardado completo:")
        logger.info(f"   - Capítulos: {stats.get('num_capitulos', 0)}")
        logger.info(f"   - Subcapítulos: {stats.get('num_subcapitulos', 0)}")
        logger.info(f"   - Partidas: {stats.get('num_partidas', 0)}")

    def _procesar_capitulo_recursivo(
        self,
        proyecto_id: int,
        capitulo_data: Dict[str, Any],
        padre_id: int,
        codigo_a_nodo_id: Dict[str, int],
        nivel: int
    ):
        """
        Procesa un capítulo/subcapítulo recursivamente.

        Args:
            proyecto_id: ID del proyecto
            capitulo_data: Datos del capítulo/subcapítulo
            padre_id: ID del nodo padre
            codigo_a_nodo_id: Mapa de códigos a IDs de nodos
            nivel: Nivel en la jerarquía
        """
        codigo = capitulo_data.get('codigo')
        nombre = capitulo_data.get('nombre', '')
        total = capitulo_data.get('total')

        # Determinar tipo
        tiene_subcapitulos = len(capitulo_data.get('subcapitulos', [])) > 0
        tiene_partidas = len(capitulo_data.get('partidas', [])) > 0

        if nivel == 1 or tiene_subcapitulos:
            tipo = TipoConcepto.CAPITULO if nivel == 1 else TipoConcepto.SUBCAPITULO
        else:
            tipo = TipoConcepto.SUBCAPITULO

        # Crear concepto si no existe
        concepto_existente = self.manager.obtener_concepto(proyecto_id, codigo)
        if not concepto_existente:
            self.manager.crear_concepto(
                proyecto_id=proyecto_id,
                codigo=codigo,
                tipo=tipo,
                nombre=nombre,
                total=total
            )

        # Crear nodo
        nodo = self.manager.crear_nodo(
            proyecto_id=proyecto_id,
            codigo_concepto=codigo,
            padre_id=padre_id,
            nivel=nivel,
            orden=capitulo_data.get('orden', 0),
            cantidad=1.0
        )

        codigo_a_nodo_id[codigo] = nodo.id

        # Procesar subcapítulos recursivamente
        for subcapitulo in capitulo_data.get('subcapitulos', []):
            self._procesar_capitulo_recursivo(
                proyecto_id=proyecto_id,
                capitulo_data=subcapitulo,
                padre_id=nodo.id,
                codigo_a_nodo_id=codigo_a_nodo_id,
                nivel=nivel + 1
            )

        # Procesar partidas
        for partida in capitulo_data.get('partidas', []):
            self._procesar_partida(
                proyecto_id=proyecto_id,
                partida_data=partida,
                padre_id=nodo.id,
                codigo_a_nodo_id=codigo_a_nodo_id,
                nivel=nivel + 1
            )

    def _procesar_partida(
        self,
        proyecto_id: int,
        partida_data: Dict[str, Any],
        padre_id: int,
        codigo_a_nodo_id: Dict[str, int],
        nivel: int
    ):
        """
        Procesa una partida y la guarda en la base de datos.

        Args:
            proyecto_id: ID del proyecto
            partida_data: Datos de la partida
            padre_id: ID del nodo padre
            codigo_a_nodo_id: Mapa de códigos a IDs de nodos
            nivel: Nivel en la jerarquía
        """
        codigo = partida_data.get('codigo')
        resumen = partida_data.get('resumen', '')
        unidad = partida_data.get('unidad', '')
        cantidad = partida_data.get('cantidad', 0.0)
        precio = partida_data.get('precio', 0.0)
        importe = partida_data.get('importe', 0.0)

        # Crear concepto de partida si no existe
        concepto_existente = self.manager.obtener_concepto(proyecto_id, codigo)
        if not concepto_existente:
            self.manager.crear_concepto(
                proyecto_id=proyecto_id,
                codigo=codigo,
                tipo=TipoConcepto.PARTIDA,
                nombre=resumen,
                resumen=resumen,
                unidad=unidad,
                precio=precio,
                cantidad_total=cantidad,
                importe_total=importe
            )

        # Crear nodo de partida
        nodo = self.manager.crear_nodo(
            proyecto_id=proyecto_id,
            codigo_concepto=codigo,
            padre_id=padre_id,
            nivel=nivel,
            orden=partida_data.get('orden', 0),
            cantidad=cantidad
        )

        codigo_a_nodo_id[codigo] = nodo.id
