"""
Orquestador de Parsers V2
=========================

Detecta el tipo de documento PDF y delega al parser especializado apropiado.

Tipos de documentos soportados:
- TIPO_1: Datos inline + Sin descompuestos (Proyecto 7)
- TIPO_2: Datos al final + Sin descompuestos
- TIPO_3: Datos inline + Con descompuestos
- TIPO_4: Datos al final + Con descompuestos

Autor: Claude Code
Fecha: 2026-01-25
"""

import logging
import re
from typing import Dict, List, Tuple
from pathlib import Path

from .pdf_extractor import PDFExtractor
from .parsers.tipo1_inline_simple import ParserV2_Tipo1_InlineSimple

logger = logging.getLogger(__name__)


class PDFOrchestrator:
    """
    Orquestador que detecta el tipo de PDF y delega al parser correcto
    """

    # Tipos de documentos soportados
    TIPO_1_INLINE_SIMPLE = "TIPO_1_INLINE_SIMPLE"
    TIPO_2_FINAL_SIMPLE = "TIPO_2_FINAL_SIMPLE"
    TIPO_3_INLINE_DESCOMP = "TIPO_3_INLINE_DESCOMP"
    TIPO_4_FINAL_DESCOMP = "TIPO_4_FINAL_DESCOMP"

    def __init__(self, pdf_path: str, user_id: int, proyecto_id: int):
        """
        Args:
            pdf_path: Ruta al archivo PDF a procesar
            user_id: ID del usuario (REQUERIDO para nombres de archivos de log)
            proyecto_id: ID del proyecto (REQUERIDO para nombres de archivos de log)
        """
        self.pdf_path = Path(pdf_path)
        self.user_id = user_id
        self.proyecto_id = proyecto_id
        self.tipo_detectado = None
        self.parser = None

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    def parsear(self) -> Dict:
        """
        Método principal: detecta tipo de documento y lo parsea

        Returns:
            Dict con estructura completa:
            {
                'estructura': {...},           # Jerarquía de capítulos/subcapítulos/partidas
                'metadata': {
                    'tipo_documento': str,     # Tipo detectado
                    'parser_usado': str,       # Nombre del parser usado
                    ...
                },
                'estadisticas': {...}          # Resumen de resultados
            }
        """
        logger.info("=" * 80)
        logger.info(f"🎯 ORQUESTADOR V2 - Procesando: {self.pdf_path.name}")
        logger.info("=" * 80)

        # PASO 1: Detectar tipo de documento
        logger.info("")
        logger.info("📋 Paso 1/3: Detectando tipo de documento...")
        self.tipo_detectado = self._detectar_tipo()
        logger.info(f"   ✓ Tipo detectado: {self.tipo_detectado}")

        # PASO 2: Crear parser apropiado
        logger.info("")
        logger.info("🔧 Paso 2/3: Seleccionando parser especializado...")
        self.parser = self._crear_parser()
        logger.info(f"   ✓ Parser seleccionado: {self.parser.__class__.__name__}")

        # PASO 3: Ejecutar parser (4 fases)
        logger.info("")
        logger.info("🚀 Paso 3/3: Ejecutando parser...")
        resultado = self.parser.parsear()

        # Añadir metadata del orquestador
        resultado['metadata']['tipo_documento'] = self.tipo_detectado
        resultado['metadata']['parser_usado'] = self.parser.__class__.__name__

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ ORQUESTADOR V2 - Procesamiento completado")
        logger.info("=" * 80)

        return resultado

    def _detectar_tipo(self) -> str:
        """
        Detecta el tipo de documento PDF

        Analiza las primeras 50 líneas del documento (ya normalizadas por ColumnDetector)
        y clasifica según:
        1. Posición de datos numéricos (inline vs al final)
        2. Presencia de descompuestos

        Returns:
            str: Tipo de documento (TIPO_1, TIPO_2, TIPO_3 o TIPO_4)
        """
        # Extraer muestra del PDF (ya procesado por ColumnDetector)
        extractor = PDFExtractor(str(self.pdf_path), self.user_id, self.proyecto_id)
        datos = extractor.extraer_todo()
        lineas = datos['all_lines'][:50]  # Primeras 50 líneas

        logger.info(f"   → Analizando primeras {len(lineas)} líneas...")

        # Criterio 1: Detectar descompuestos
        tiene_descompuestos = self._tiene_descompuestos(lineas)
        logger.info(f"   → Descompuestos: {'SÍ' if tiene_descompuestos else 'NO'}")

        # Criterio 2: Detectar posición de datos
        datos_inline = self._datos_en_linea_header(lineas)
        logger.info(f"   → Datos inline: {'SÍ' if datos_inline else 'NO (al final)'}")

        # Clasificar según combinación
        if datos_inline and tiene_descompuestos:
            return self.TIPO_3_INLINE_DESCOMP
        elif datos_inline and not tiene_descompuestos:
            return self.TIPO_1_INLINE_SIMPLE  # Proyecto 7
        elif not datos_inline and tiene_descompuestos:
            return self.TIPO_4_FINAL_DESCOMP
        else:
            return self.TIPO_2_FINAL_SIMPLE

    def _tiene_descompuestos(self, lineas: List[str]) -> bool:
        """
        Detecta si el documento contiene descompuestos

        Los descompuestos son líneas que detallan componentes de una partida con formato:
        - "20 % Esponjamiento 0,2 6.160,20 1.232,04"
        - "% Mano de obra" o "Porcentajes"
        - "Mo:" o "Mat:" (abreviaturas)
        - Líneas con estructura: descripción + cantidad + precio (sin código de partida)

        Args:
            lineas: Lista de líneas del documento

        Returns:
            bool: True si tiene descompuestos, False si no
        """
        # Patrones MÁS ESPECÍFICOS para descompuestos reales
        patrones_descomp = [
            # Formato: "20 % Esponjamiento 0,2 6.160,20 1.232,04"
            # Uso [\d.,]+ para soportar separadores de miles (1.234,56)
            r'^\d+\s*%\s+\w+\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+',

            # Formatos tradicionales
            r'^\s*%\s*(mano|obra|material|materiales|m\.?o\.?)',  # % Mano de obra
            r'^\s*(mo|mat|maq):',  # Mo: Mat: Maq: (abreviaturas al inicio)
            r'porcentajes?\s*:',  # "Porcentajes:"
            r'descompuesto\s*:',  # "Descompuesto:"
            r'^\s*mano\s+de\s+obra\s*[:.]',  # "Mano de obra:" al inicio
            r'^\s*materiales?\s*[:.]',  # "Material:" o "Materiales:" al inicio
            r'cos\.?\s*indirecto',  # "Cos. indirecto" o "Coste indirecto"
        ]

        count = 0
        for linea in lineas:
            linea_lower = linea.lower()
            # Buscar patrones específicos de descompuestos
            for patron in patrones_descomp:
                if re.search(patron, linea_lower):
                    count += 1
                    logger.debug(f"      Patrón descompuesto detectado en: {linea[:60]}...")
                    # Con encontrar 1 línea con patrón claro es suficiente
                    # (algunos documentos tienen descompuestos solo ocasionalmente)
                    if count >= 1:
                        return True
                    break

        return False

    def _datos_en_linea_header(self, lineas: List[str]) -> bool:
        """
        Detecta si los datos numéricos (CANT/PRECIO/IMPORTE) vienen en la línea del código

        Analiza líneas buscando dos patrones:
        - INLINE: CODIGO UNIDAD RESUMEN CANT PRECIO IMPORTE (todo en 1 línea)
          Ejemplo: "m23U01C190 Ud DESMONTAJE DE PAPELERA 9,00 26,89 242,01"
        - FINAL: CODIGO UNIDAD RESUMEN (sin datos, vienen en líneas posteriores)
          Ejemplo: "01.01.01 m2 RASANTEO..." luego "1.565,00 0,65 1.017,25"

        Args:
            lineas: Lista de líneas del documento

        Returns:
            bool: True si datos inline, False si al final
        """
        # Patrón MÁS FLEXIBLE para códigos (incluye formatos como m23U01C190, 01.01.01, etc.)
        patron_codigo = re.compile(r'^[a-zA-Z0-9]{2,}[\w\.]*\s+\w+\s+[A-Z]')

        # Patrón inline: busca líneas que terminan con 3 números (CANT PRECIO IMPORTE)
        # Acepta varios formatos de números: 9,00 o 1.565,00 o 26,89
        patron_inline = re.compile(
            r'^.+?'  # Inicio flexible (código, unidad, resumen)
            r'\s+'  # Espacio
            r'\d+[.,]\d{2}'  # Cantidad (ej: 9,00 o 153,00 o 1.565,00)
            r'\s+'  # Espacio
            r'\d+[.,]\d{2}'  # Precio (ej: 26,89)
            r'\s+'  # Espacio
            r'\d+[.,]\d{2}'  # Importe (ej: 242,01)
            r'\s*$'  # Fin de línea
        )

        lineas_con_codigo = 0
        lineas_con_datos_inline = 0

        for linea in lineas:
            # Detectar si es una línea con código de partida
            if patron_codigo.match(linea):
                lineas_con_codigo += 1
                # Verificar si tiene datos inline (termina con 3 números)
                if patron_inline.match(linea):
                    lineas_con_datos_inline += 1
                    logger.debug(f"      Línea inline detectada: {linea[:80]}...")

        # Decisión: Si más del 50% de códigos tienen datos inline, es tipo inline
        if lineas_con_codigo > 0:
            porcentaje = (lineas_con_datos_inline / lineas_con_codigo) * 100
            logger.debug(f"      Análisis: {lineas_con_datos_inline}/{lineas_con_codigo} líneas con datos inline ({porcentaje:.1f}%)")
            return porcentaje > 50

        # Si no hay códigos detectados, asumir datos al final (más conservador)
        return False

    def _crear_parser(self):
        """
        Crea instancia del parser apropiado según el tipo detectado

        Returns:
            Instancia de parser (subclase de BaseParserV2)
        """
        # Mapa de tipos a clases de parser
        parsers_map = {
            self.TIPO_1_INLINE_SIMPLE: ParserV2_Tipo1_InlineSimple,      # Proyecto 7
            # self.TIPO_2_FINAL_SIMPLE: ParserV2_Tipo2_FinalSimple,      # TODO: Implementar
            # self.TIPO_3_INLINE_DESCOMP: ParserV2_Tipo3_InlineDescomp,  # TODO: Implementar
            # self.TIPO_4_FINAL_DESCOMP: ParserV2_Tipo4_FinalDescomp,    # TODO: Implementar
        }

        parser_class = parsers_map.get(self.tipo_detectado)

        if not parser_class:
            logger.warning(f"⚠️  Parser para tipo '{self.tipo_detectado}' no implementado aún")
            logger.warning(f"   → Usando TIPO_1 (Proyecto 7) como fallback")
            parser_class = ParserV2_Tipo1_InlineSimple

        return parser_class(str(self.pdf_path), self.user_id, self.proyecto_id)

    def get_tipo_detectado(self) -> str:
        """
        Retorna el tipo de documento detectado

        Returns:
            str: Tipo de documento o None si no se ha ejecutado parsear()
        """
        return self.tipo_detectado

    def __repr__(self):
        return f"PDFOrchestrator(pdf='{self.pdf_path.name}', tipo='{self.tipo_detectado}')"
