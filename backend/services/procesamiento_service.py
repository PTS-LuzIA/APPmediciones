"""
Procesamiento Service - Lógica de negocio para procesamiento de PDFs
Actualizado para usar PDFOrchestrator (parser_v2)
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
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
        Ejecuta Fase 1: Extracción de estructura jerárquica (capítulos/subcapítulos).

        Guarda solo capítulos y subcapítulos en BD, sin partidas.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado de Fase 1 con estructura extraída
        """
        logger.info(f"🔧 [FASE 1] Iniciando para proyecto {proyecto_id}")

        # Obtener user_id del proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            raise ValueError(f"Proyecto {proyecto_id} no encontrado")

        # Limpiar datos anteriores antes de procesar
        self.manager.limpiar_datos_fase1(proyecto_id)

        # Crear orchestrator y obtener parser
        orchestrator = PDFOrchestrator(pdf_path, proyecto.usuario_id, proyecto_id)

        # Detectar tipo y crear parser
        orchestrator.tipo_detectado = orchestrator._detectar_tipo()
        parser = orchestrator._crear_parser()

        # Ejecutar solo Fase 1
        parser.ejecutar_fase1()

        # Obtener resultado de fase 1
        fase1_resultado = parser.fase1_resultado
        estructura = fase1_resultado.get('estructura', {})

        # Guardar en BD solo capítulos y subcapítulos (sin partidas)
        self._guardar_fase1_en_bd(proyecto_id, estructura)

        # Actualizar proyecto
        proyecto.fase_actual = 1
        self.db.commit()

        logger.info(f"✅ Fase 1 completada - Capítulos: {fase1_resultado.get('num_capitulos', 0)}, Subcapítulos: {fase1_resultado.get('num_subcapitulos', 0)}")

        return {
            'estructura': estructura,
            'metadata': {
                'tipo_documento': orchestrator.tipo_detectado,
                'parser_usado': parser.__class__.__name__
            },
            'estadisticas': {
                'num_capitulos': fase1_resultado.get('num_capitulos', 0),
                'num_subcapitulos': fase1_resultado.get('num_subcapitulos', 0)
            }
        }

    def ejecutar_fase2(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 2: Extracción de partidas.

        Requiere que Fase 1 esté completada.
        Guarda las partidas con sus datos numéricos en BD.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado de Fase 2 con partidas extraídas
        """
        logger.info(f"🔧 [FASE 2] Iniciando para proyecto {proyecto_id}")

        # Obtener user_id del proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            raise ValueError(f"Proyecto {proyecto_id} no encontrado")

        # Verificar que Fase 1 esté completada
        if proyecto.fase_actual < 1:
            raise ValueError("Debe ejecutar Fase 1 antes de Fase 2")

        # Limpiar partidas anteriores antes de procesar
        self.manager.limpiar_datos_fase2(proyecto_id)

        # Crear orchestrator y obtener parser
        orchestrator = PDFOrchestrator(pdf_path, proyecto.usuario_id, proyecto_id)

        # Detectar tipo y crear parser
        orchestrator.tipo_detectado = orchestrator._detectar_tipo()
        parser = orchestrator._crear_parser()

        # Ejecutar Fases 1 y 2 (necesitamos fase 1 para contexto)
        parser.ejecutar_fase1()
        parser.ejecutar_fase2()

        # Obtener resultado de fase 2
        fase2_resultado = parser.fase2_resultado
        estructura = fase2_resultado.get('estructura_completa', {})

        # Guardar en BD solo las partidas (capítulos ya están de Fase 1)
        self._guardar_fase2_en_bd(proyecto_id, estructura)

        # Actualizar proyecto
        proyecto.fase_actual = 2
        self.db.commit()

        # Recalcular totales para mostrar diferencias
        logger.info("  🔄 Recalculando totales desde la base de datos...")
        self._recalcular_totales_proyecto(proyecto_id)

        logger.info(f"✅ Fase 2 completada - Partidas: {fase2_resultado.get('num_partidas', 0)}")

        return {
            'estructura': estructura,
            'estadisticas': {
                'num_partidas': fase2_resultado.get('num_partidas', 0),
                'num_partidas_con_datos': fase2_resultado.get('num_partidas_con_datos', 0)
            }
        }

    def ejecutar_fase3(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 3: Validación de totales.

        Requiere que Fases 1 y 2 estén completadas.
        Valida que los totales calculados coincidan con los del PDF.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado de Fase 3 con validación de totales
        """
        logger.info(f"🔧 [FASE 3] Iniciando para proyecto {proyecto_id}")

        # Obtener user_id del proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            raise ValueError(f"Proyecto {proyecto_id} no encontrado")

        # Verificar que Fases 1 y 2 estén completadas
        if proyecto.fase_actual < 2:
            raise ValueError("Debe ejecutar Fases 1 y 2 antes de Fase 3")

        # Fase 3 no requiere limpieza (solo valida datos existentes)

        # Crear orchestrator y obtener parser
        orchestrator = PDFOrchestrator(pdf_path, proyecto.usuario_id, proyecto_id)

        # Detectar tipo y crear parser
        orchestrator.tipo_detectado = orchestrator._detectar_tipo()
        parser = orchestrator._crear_parser()

        # Ejecutar Fases 1, 2 y 3
        parser.ejecutar_fase1()
        parser.ejecutar_fase2()
        parser.ejecutar_fase3()

        # Obtener resultado de fase 3
        fase3_resultado = parser.fase3_resultado

        # Obtener discrepancias y enriquecerlas con información de la BD
        discrepancias_parser = fase3_resultado.get('discrepancias', [])
        discrepancias_enriquecidas = []
        total_original = 0.0
        total_calculado = 0.0

        for disc in discrepancias_parser:
            codigo = disc.get('codigo', '')

            # Buscar el nodo en la base de datos
            nodo = self.db.execute(
                text("""
                    SELECT n.id, n.nivel, c.tipo, c.nombre, c.codigo
                    FROM appmediciones.nodos n
                    INNER JOIN appmediciones.conceptos c ON n.codigo_concepto = c.codigo
                    WHERE n.proyecto_id = :pid AND c.codigo = :codigo
                    LIMIT 1
                """),
                {'pid': proyecto_id, 'codigo': codigo}
            ).fetchone()

            if nodo:
                disc_enriquecida = {
                    'id': nodo[0],
                    'tipo': 'capitulo' if nodo[2] == 'CAPITULO' else 'subcapitulo',
                    'codigo': codigo,
                    'nombre': nodo[3],
                    'total_original': float(disc.get('total_declarado', 0.0)),
                    'total_calculado': float(disc.get('total_real', 0.0)),
                    'diferencia': float(disc.get('diferencia', 0.0))
                }
                discrepancias_enriquecidas.append(disc_enriquecida)
                total_original += disc_enriquecida['total_original']
                total_calculado += disc_enriquecida['total_calculado']

        # Actualizar proyecto con presupuesto total si disponible
        if fase3_resultado and fase3_resultado.get('presupuesto_total'):
            proyecto.presupuesto_total = fase3_resultado['presupuesto_total']

        # Actualizar proyecto
        proyecto.fase_actual = 3
        self.db.commit()

        # Recalcular totales para asegurar que las diferencias estén actualizadas
        logger.info("  🔄 Recalculando totales desde la base de datos...")
        self._recalcular_totales_proyecto(proyecto_id)

        # Recalcular discrepancias desde la BD (después de recalcular totales)
        logger.info("  🔍 Recalculando discrepancias desde la base de datos...")
        discrepancias_bd = self._calcular_discrepancias_desde_bd(proyecto_id)

        logger.info(f"✅ Fase 3 completada - {len(discrepancias_bd)} discrepancias detectadas (desde BD)")

        return {
            'num_discrepancias': len(discrepancias_bd),
            'discrepancias': discrepancias_bd,
            'total_original': sum(d['total_original'] for d in discrepancias_bd),
            'total_calculado': sum(d['total_calculado'] for d in discrepancias_bd),
            'validacion': fase3_resultado.get('validacion', {}),
            'presupuesto_total': fase3_resultado.get('presupuesto_total'),
            'estadisticas': fase3_resultado.get('estadisticas', {})
        }

    def ejecutar_fase4(self, proyecto_id: int, pdf_path: str) -> Dict[str, Any]:
        """
        Ejecuta Fase 4: Completar descripciones y finalizar.

        Requiere que Fases 1, 2 y 3 estén completadas.
        Completa información faltante y marca el proyecto como finalizado.

        Args:
            proyecto_id: ID del proyecto
            pdf_path: Ruta al PDF

        Returns:
            Resultado final completo
        """
        logger.info(f"🔧 [FASE 4] Iniciando para proyecto {proyecto_id}")

        # Obtener user_id del proyecto
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            raise ValueError(f"Proyecto {proyecto_id} no encontrado")

        # Verificar que Fases 1, 2 y 3 estén completadas
        if proyecto.fase_actual < 3:
            raise ValueError("Debe ejecutar Fases 1, 2 y 3 antes de Fase 4")

        # Fase 4 no requiere limpieza (solo completa información existente)

        # Crear orchestrator y obtener parser
        orchestrator = PDFOrchestrator(pdf_path, proyecto.usuario_id, proyecto_id)

        # Detectar tipo y crear parser
        orchestrator.tipo_detectado = orchestrator._detectar_tipo()
        parser = orchestrator._crear_parser()

        # Ejecutar todas las 4 fases
        parser.ejecutar_fase1()
        parser.ejecutar_fase2()
        parser.ejecutar_fase3()
        parser.ejecutar_fase4()

        # Obtener resultado final
        resultado_final = parser._compilar_resultado_final()

        # Actualizar proyecto con metadata final
        metadata = resultado_final.get('metadata', {})
        if metadata.get('titulo_proyecto'):
            proyecto.nombre = metadata['titulo_proyecto']

        # Actualizar proyecto
        proyecto.fase_actual = 4
        proyecto.estado = 'completado'
        self.db.commit()

        logger.info(f"✅ Fase 4 completada - Proyecto finalizado")

        return resultado_final

    # =====================================================
    # MÉTODOS PRIVADOS
    # =====================================================

    def _guardar_fase1_en_bd(self, proyecto_id: int, estructura: Dict[str, Any]):
        """
        Guarda el resultado de Fase 1 en la base de datos.

        Crea solo capítulos y subcapítulos (sin partidas).

        Args:
            proyecto_id: ID del proyecto
            estructura: Estructura jerárquica de capítulos/subcapítulos
        """
        logger.info(f"💾 Guardando Fase 1 en BD para proyecto {proyecto_id}")

        # Obtener nodo raíz
        nodo_raiz = self.manager.obtener_nodo_raiz(proyecto_id)
        if not nodo_raiz:
            logger.error(f"Nodo raíz no encontrado para proyecto {proyecto_id}")
            return

        # Mapa para tracking de nodos creados
        codigo_a_nodo_id = {}

        # Procesar cada capítulo (sin partidas, solo estructura)
        capitulos = estructura.get('capitulos', [])
        for capitulo in capitulos:
            self._procesar_capitulo_fase1(
                proyecto_id=proyecto_id,
                capitulo_data=capitulo,
                padre_id=nodo_raiz.id,
                codigo_a_nodo_id=codigo_a_nodo_id,
                nivel=1
            )

        logger.info(f"✓ Fase 1 guardada: {len(capitulos)} capítulos con sus subcapítulos")

    def _procesar_capitulo_fase1(
        self,
        proyecto_id: int,
        capitulo_data: Dict[str, Any],
        padre_id: int,
        codigo_a_nodo_id: Dict[str, int],
        nivel: int
    ):
        """
        Procesa un capítulo/subcapítulo recursivamente (Fase 1 - sin partidas).

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
        tipo = TipoConcepto.CAPITULO if nivel == 1 else TipoConcepto.SUBCAPITULO

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

        # Procesar subcapítulos recursivamente (sin partidas en Fase 1)
        for subcapitulo in capitulo_data.get('subcapitulos', []):
            self._procesar_capitulo_fase1(
                proyecto_id=proyecto_id,
                capitulo_data=subcapitulo,
                padre_id=nodo.id,
                codigo_a_nodo_id=codigo_a_nodo_id,
                nivel=nivel + 1
            )

    def _guardar_fase2_en_bd(self, proyecto_id: int, estructura: Dict[str, Any]):
        """
        Guarda el resultado de Fase 2 en la base de datos.

        Crea solo las partidas (capítulos ya existen de Fase 1).

        Args:
            proyecto_id: ID del proyecto
            estructura: Estructura completa con capítulos y partidas
        """
        logger.info(f"💾 Guardando Fase 2 en BD para proyecto {proyecto_id}")

        # Obtener mapa de códigos a nodos existentes (capítulos de Fase 1)
        from sqlalchemy import text
        result = self.db.execute(
            text("SELECT id, codigo_concepto FROM appmediciones.nodos WHERE proyecto_id = :pid"),
            {'pid': proyecto_id}
        )
        codigo_a_nodo_id = {row[1]: row[0] for row in result}

        # Procesar cada capítulo para extraer partidas
        capitulos = estructura.get('capitulos', [])
        total_partidas = 0

        for capitulo in capitulos:
            total_partidas += self._procesar_partidas_fase2(
                proyecto_id=proyecto_id,
                capitulo_data=capitulo,
                codigo_a_nodo_id=codigo_a_nodo_id
            )

        # Actualizar totales de partidas sumando todos los nodos
        self._actualizar_totales_partidas(proyecto_id)

        logger.info(f"✓ Fase 2 guardada: {total_partidas} partidas")

    def _procesar_partidas_fase2(
        self,
        proyecto_id: int,
        capitulo_data: Dict[str, Any],
        codigo_a_nodo_id: Dict[str, int]
    ) -> int:
        """
        Procesa las partidas de un capítulo recursivamente (Fase 2).

        Args:
            proyecto_id: ID del proyecto
            capitulo_data: Datos del capítulo/subcapítulo
            codigo_a_nodo_id: Mapa de códigos a IDs de nodos

        Returns:
            Número de partidas guardadas
        """
        total_partidas = 0

        # Obtener padre_id del capítulo actual
        codigo_capitulo = capitulo_data.get('codigo')
        padre_id = codigo_a_nodo_id.get(codigo_capitulo)

        if not padre_id:
            logger.warning(f"No se encontró nodo para capítulo {codigo_capitulo}")
            return 0

        # Log para debugging
        num_partidas_directas = len(capitulo_data.get('partidas', []))
        num_subcaps = len(capitulo_data.get('subcapitulos', []))
        logger.debug(f"📦 Procesando {codigo_capitulo}: {num_partidas_directas} partidas directas, {num_subcaps} subcapítulos")

        # Procesar partidas de este capítulo
        for partida in capitulo_data.get('partidas', []):
            codigo = partida.get('codigo')
            resumen = partida.get('resumen', '')
            unidad = partida.get('unidad', '')
            cantidad = partida.get('cantidad', 0.0)
            precio = partida.get('precio', 0.0)
            importe = partida.get('importe', 0.0)

            # Crear concepto de partida si no existe
            concepto_existente = self.manager.obtener_concepto(proyecto_id, codigo)
            if not concepto_existente:
                self.manager.crear_concepto(
                    proyecto_id=proyecto_id,
                    codigo=codigo,
                    tipo=TipoConcepto.PARTIDA,
                    nombre=resumen,
                    resumen=resumen,
                    descripcion=partida.get('descripcion', ''),
                    unidad=unidad,
                    precio=precio,
                    cantidad_total=0,  # Se calculará después sumando todos los nodos
                    importe_total=0    # Se calculará después
                )

            # Crear nodo de partida
            nodo = self.manager.crear_nodo(
                proyecto_id=proyecto_id,
                codigo_concepto=codigo,
                padre_id=padre_id,
                nivel=capitulo_data.get('nivel', 1) + 1,
                orden=partida.get('orden', 0),
                cantidad=cantidad
            )

            codigo_a_nodo_id[codigo] = nodo.id
            total_partidas += 1

        # Procesar subcapítulos recursivamente
        for subcapitulo in capitulo_data.get('subcapitulos', []):
            total_partidas += self._procesar_partidas_fase2(
                proyecto_id=proyecto_id,
                capitulo_data=subcapitulo,
                codigo_a_nodo_id=codigo_a_nodo_id
            )

        return total_partidas

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

        # Actualizar totales de partidas sumando todos los nodos
        self._actualizar_totales_partidas(proyecto_id)

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
                cantidad_total=0,  # Se calculará después sumando todos los nodos
                importe_total=0    # Se calculará después
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

    def _recalcular_totales_proyecto(self, proyecto_id: int):
        """
        Recalcula todos los totales_calculados del proyecto desde las hojas hacia la raíz.

        Args:
            proyecto_id: ID del proyecto
        """
        logger.info(f"  Recalculando totales para proyecto {proyecto_id}...")

        try:
            # Obtener todos los conceptos ordenados por nivel descendente (hojas primero)
            conceptos = self.db.execute(
                text("""
                    SELECT DISTINCT c.codigo, n.nivel
                    FROM appmediciones.conceptos c
                    INNER JOIN appmediciones.nodos n ON c.codigo = n.codigo_concepto
                        AND c.proyecto_id = n.proyecto_id
                    WHERE c.proyecto_id = :pid
                        AND c.tipo IN ('CAPITULO', 'SUBCAPITULO')
                    ORDER BY n.nivel DESC
                """),
                {'pid': proyecto_id}
            ).fetchall()

            for concepto in conceptos:
                codigo = concepto[0]

                # Calcular total_calculado (suma de hijos)
                # IMPORTANTE: Para partidas, redondear CADA importe antes de sumar (método contable)
                self.db.execute(
                    text("""
                        UPDATE appmediciones.conceptos c
                        SET total_calculado = (
                            SELECT COALESCE(SUM(CASE
                                WHEN c2.tipo = 'PARTIDA' THEN ROUND(n.cantidad * COALESCE(c2.precio, 0), 2)
                                ELSE c2.total_calculado
                            END), 0)
                            FROM appmediciones.nodos n
                            INNER JOIN appmediciones.conceptos c2
                                ON n.codigo_concepto = c2.codigo
                                AND c2.proyecto_id = n.proyecto_id
                            WHERE n.proyecto_id = :pid
                                AND n.padre_id = (
                                    SELECT id FROM appmediciones.nodos
                                    WHERE proyecto_id = :pid
                                        AND codigo_concepto = :codigo
                                    LIMIT 1
                                )
                        )
                        WHERE c.proyecto_id = :pid AND c.codigo = :codigo
                    """),
                    {'pid': proyecto_id, 'codigo': codigo}
                )

            self.db.commit()
            logger.info(f"  ✓ Totales recalculados para {len(conceptos)} conceptos")

        except Exception as e:
            logger.error(f"  ❌ Error recalculando totales: {e}")
            self.db.rollback()
            raise

    def _actualizar_totales_partidas(self, proyecto_id: int):
        """
        Actualiza cantidad_total e importe_total de todas las partidas.

        Para cada concepto de tipo PARTIDA:
        - cantidad_total = suma de n.cantidad de todos los nodos que usan ese concepto
        - importe_total = suma de (n.cantidad × c.precio) de todos los nodos

        Args:
            proyecto_id: ID del proyecto
        """
        logger.info(f"  Actualizando totales de partidas para proyecto {proyecto_id}...")

        try:
            self.db.execute(
                text("""
                    UPDATE appmediciones.conceptos c
                    SET
                        cantidad_total = (
                            SELECT COALESCE(SUM(n.cantidad), 0)
                            FROM appmediciones.nodos n
                            WHERE n.proyecto_id = :pid
                                AND n.codigo_concepto = c.codigo
                        ),
                        importe_total = (
                            SELECT COALESCE(SUM(ROUND(n.cantidad * COALESCE(c.precio, 0), 2)), 0)
                            FROM appmediciones.nodos n
                            WHERE n.proyecto_id = :pid
                                AND n.codigo_concepto = c.codigo
                        )
                    WHERE c.proyecto_id = :pid
                        AND c.tipo = 'PARTIDA'
                """),
                {'pid': proyecto_id}
            )

            self.db.commit()
            logger.info(f"  ✓ Totales de partidas actualizados")

        except Exception as e:
            logger.error(f"  ❌ Error actualizando totales de partidas: {e}")
            self.db.rollback()
            raise

    def _calcular_discrepancias_desde_bd(self, proyecto_id: int) -> list:
        """
        Calcula las discrepancias comparando totales PDF vs totales calculados desde la BD.

        Args:
            proyecto_id: ID del proyecto

        Returns:
            Lista de discrepancias con formato:
            [
                {
                    'id': nodo_id,
                    'codigo': codigo,
                    'nombre': nombre,
                    'tipo': 'capitulo' o 'subcapitulo',
                    'total_original': total_pdf,
                    'total_calculado': total_bd,
                    'diferencia': diferencia_abs
                }
            ]
        """
        logger.info(f"  Calculando discrepancias desde BD para proyecto {proyecto_id}...")

        try:
            # Obtener conceptos con discrepancias
            # Umbral: diferencia absoluta >= 0.05€ (descarta errores de redondeo)
            discrepancias_query = self.db.execute(
                text("""
                    SELECT
                        n.id,
                        c.codigo,
                        c.nombre,
                        c.tipo,
                        c.total as total_pdf,
                        c.total_calculado,
                        ABS(COALESCE(c.total, 0) - COALESCE(c.total_calculado, 0)) as diferencia,
                        CASE
                            WHEN COALESCE(c.total, 0) > 0 THEN
                                ABS(COALESCE(c.total, 0) - COALESCE(c.total_calculado, 0)) / c.total * 100
                            ELSE 0
                        END as porcentaje
                    FROM appmediciones.conceptos c
                    INNER JOIN appmediciones.nodos n ON c.codigo = n.codigo_concepto
                        AND c.proyecto_id = n.proyecto_id
                    WHERE c.proyecto_id = :pid
                        AND c.tipo IN ('CAPITULO', 'SUBCAPITULO')
                        AND c.total IS NOT NULL
                        AND c.total > 0
                        AND ABS(COALESCE(c.total, 0) - COALESCE(c.total_calculado, 0)) >= 0.05
                    ORDER BY c.codigo
                """),
                {'pid': proyecto_id}
            ).fetchall()

            discrepancias = []
            for row in discrepancias_query:
                disc = {
                    'id': row[0],
                    'codigo': row[1],
                    'nombre': row[2],
                    'tipo': 'capitulo' if row[3] == 'CAPITULO' else 'subcapitulo',
                    'total_original': float(row[4] or 0.0),
                    'total_calculado': float(row[5] or 0.0),
                    'diferencia': float(row[6] or 0.0)
                }
                discrepancias.append(disc)

            logger.info(f"  ✓ {len(discrepancias)} discrepancias encontradas desde BD")
            return discrepancias

        except Exception as e:
            logger.error(f"  ❌ Error calculando discrepancias desde BD: {e}")
            return []
