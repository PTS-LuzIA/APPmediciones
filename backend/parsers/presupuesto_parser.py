"""
Parser principal de presupuestos para arquitectura Nodos+Conceptos

Adaptado del parser_v2 del proyecto legacy pero reescrito para
la nueva arquitectura de dos tablas.
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys
from decimal import Decimal
import re

sys.path.append(str(Path(__file__).parent.parent))

from models import TipoConcepto
from parsers.pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)


class PresupuestoParser:
    """
    Parser de presupuestos que genera estructura de Nodos y Conceptos.

    Fases:
    1. Extracción de estructura (capítulos/subcapítulos)
    2. Extracción de partidas
    3. Validación y cálculo de totales
    4. Resolución de discrepancias (opcional)
    """

    def __init__(self, pdf_path: str, proyecto_id: int):
        self.pdf_path = pdf_path
        self.proyecto_id = proyecto_id
        self.extractor = PDFExtractor(pdf_path)

        # Resultados por fase
        self.fase1_resultado = {}
        self.fase2_resultado = {}
        self.fase3_resultado = {}

        # Estructura temporal
        self.conceptos = []  # Lista de conceptos a crear
        self.nodos = []      # Lista de nodos a crear

    def ejecutar_fase1(self) -> Dict[str, Any]:
        """
        FASE 1: Extrae estructura jerárquica (capítulos/subcapítulos).

        Returns:
            {
                'titulo_proyecto': str,
                'num_capitulos': int,
                'conceptos': [  # Conceptos tipo CAPITULO y SUBCAPITULO
                    {
                        'codigo': str,
                        'tipo': TipoConcepto,
                        'nombre': str,
                        'total': Decimal,
                        ...
                    }
                ],
                'nodos': [  # Estructura jerárquica
                    {
                        'codigo_concepto': str,
                        'padre_codigo': str | None,
                        'nivel': int,
                        'orden': int
                    }
                ]
            }
        """
        logger.info(f"🔧 [FASE 1] Extrayendo estructura del PDF: {Path(self.pdf_path).name}")

        # Extraer texto del PDF
        texto_completo = self.extractor.extraer_texto_completo()

        # Detectar título del proyecto
        titulo = self._detectar_titulo(texto_completo)

        # Detectar capítulos y subcapítulos
        estructura = self._detectar_estructura(texto_completo)

        # Generar conceptos y nodos
        conceptos, nodos = self._estructura_a_conceptos_nodos(estructura)

        self.fase1_resultado = {
            'titulo_proyecto': titulo,
            'num_capitulos': len([c for c in conceptos if c['tipo'] == TipoConcepto.CAPITULO]),
            'conceptos': conceptos,
            'nodos': nodos
        }

        logger.info(f"✓ Fase 1 completada: {self.fase1_resultado['num_capitulos']} capítulos detectados")
        return self.fase1_resultado

    def ejecutar_fase2(self) -> Dict[str, Any]:
        """
        FASE 2: Extrae partidas y las asocia a la estructura.

        Requiere que se haya ejecutado Fase 1.

        Returns:
            {
                'num_partidas': int,
                'conceptos_partidas': [  # Conceptos tipo PARTIDA
                    {
                        'codigo': str,
                        'tipo': TipoConcepto.PARTIDA,
                        'nombre': str,
                        'resumen': str,
                        'unidad': str,
                        'precio': Decimal,
                        ...
                    }
                ],
                'nodos_partidas': [  # Nodos de partidas
                    {
                        'codigo_concepto': str,
                        'padre_codigo': str,  # Código del capítulo/subcapítulo padre
                        'nivel': int,
                        'orden': int
                    }
                ]
            }
        """
        if not self.fase1_resultado:
            raise ValueError("Debe ejecutar Fase 1 antes de Fase 2")

        logger.info("🔧 [FASE 2] Extrayendo partidas del PDF")

        # Extraer partidas del PDF
        partidas = self._detectar_partidas()

        # Asociar partidas a estructura existente
        conceptos_partidas, nodos_partidas = self._asociar_partidas_a_estructura(partidas)

        self.fase2_resultado = {
            'num_partidas': len(conceptos_partidas),
            'conceptos_partidas': conceptos_partidas,
            'nodos_partidas': nodos_partidas
        }

        logger.info(f"✓ Fase 2 completada: {self.fase2_resultado['num_partidas']} partidas extraídas")
        return self.fase2_resultado

    def ejecutar_fase3(self) -> Dict[str, Any]:
        """
        FASE 3: Calcula totales recursivos y detecta discrepancias.

        Returns:
            {
                'totales_calculados': {codigo: total},
                'discrepancias': [
                    {
                        'codigo': str,
                        'total_pdf': Decimal,
                        'total_calculado': Decimal,
                        'diferencia': Decimal
                    }
                ]
            }
        """
        if not self.fase2_resultado:
            raise ValueError("Debe ejecutar Fase 2 antes de Fase 3")

        logger.info("🔧 [FASE 3] Calculando totales y detectando discrepancias")

        # Calcular totales de forma recursiva
        totales = self._calcular_totales_recursivos()

        # Detectar discrepancias
        discrepancias = self._detectar_discrepancias(totales)

        self.fase3_resultado = {
            'totales_calculados': totales,
            'discrepancias': discrepancias,
            'num_discrepancias': len(discrepancias)
        }

        logger.info(f"✓ Fase 3 completada: {len(discrepancias)} discrepancias detectadas")
        return self.fase3_resultado

    # =====================================================
    # MÉTODOS PRIVADOS - FASE 1
    # =====================================================

    def _detectar_titulo(self, texto: str) -> str:
        """Detecta el título del proyecto del PDF"""
        # Buscar en las primeras 500 caracteres
        inicio = texto[:500]

        # Patrones comunes
        patrones = [
            r'PRESUPUESTO[:\s]+(.+?)(?:\n|$)',
            r'PROYECTO[:\s]+(.+?)(?:\n|$)',
            r'OBRA[:\s]+(.+?)(?:\n|$)',
        ]

        for patron in patrones:
            match = re.search(patron, inicio, re.IGNORECASE)
            if match:
                titulo = match.group(1).strip()
                if len(titulo) > 10:
                    return titulo

        return "Presupuesto sin título"

    def _detectar_estructura(self, texto: str) -> List[Dict]:
        """
        Detecta la estructura de capítulos y subcapítulos.

        Returns:
            Lista de elementos estructurales con su jerarquía
        """
        estructura = []

        # Patrones para detectar capítulos (ej: "C01", "CAP 1", "CAPÍTULO 1")
        patron_capitulo = r'^([A-Z]\d{2}|CAP(?:ÍTULO)?\s*\d+)[.\s]+(.+?)\s+(\d+(?:[.,]\d{2})?)\s*€?$'

        # Patrones para detectar subcapítulos (ej: "C01.01", "1.1")
        patron_subcap = r'^([A-Z]\d{2}\.\d{2}(?:\.\d{2})?|\d+\.\d+(?:\.\d+)?)[.\s]+(.+?)\s+(\d+(?:[.,]\d{2})?)\s*€?$'

        lineas = texto.split('\n')

        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue

            # Detectar capítulo
            match_cap = re.match(patron_capitulo, linea)
            if match_cap:
                codigo = match_cap.group(1)
                nombre = match_cap.group(2).strip()
                total = Decimal(match_cap.group(3).replace(',', '.'))

                estructura.append({
                    'codigo': codigo,
                    'nombre': nombre,
                    'total': total,
                    'tipo': 'capitulo',
                    'nivel': 1
                })
                continue

            # Detectar subcapítulo
            match_sub = re.match(patron_subcap, linea)
            if match_sub:
                codigo = match_sub.group(1)
                nombre = match_sub.group(2).strip()
                total = Decimal(match_sub.group(3).replace(',', '.'))

                # Calcular nivel por número de puntos
                nivel = codigo.count('.') + 1

                estructura.append({
                    'codigo': codigo,
                    'nombre': nombre,
                    'total': total,
                    'tipo': 'subcapitulo',
                    'nivel': nivel
                })

        logger.debug(f"Detectados {len(estructura)} elementos de estructura")
        return estructura

    def _estructura_a_conceptos_nodos(self, estructura: List[Dict]) -> tuple:
        """
        Convierte la estructura detectada en Conceptos y Nodos.

        Returns:
            (conceptos, nodos)
        """
        conceptos = []
        nodos = []

        # Mapa para encontrar padres por código
        codigo_a_elemento = {}

        for idx, elem in enumerate(estructura):
            codigo = elem['codigo']
            tipo = TipoConcepto.CAPITULO if elem['tipo'] == 'capitulo' else TipoConcepto.SUBCAPITULO

            # Crear concepto
            concepto = {
                'codigo': codigo,
                'tipo': tipo,
                'nombre': elem['nombre'],
                'total': elem['total'],
                'resumen': None,
                'descripcion': None,
                'unidad': None,
                'precio': None
            }
            conceptos.append(concepto)

            # Buscar padre por código
            padre_codigo = self._encontrar_padre_por_codigo(codigo, codigo_a_elemento)

            # Crear nodo
            nodo = {
                'codigo_concepto': codigo,
                'padre_codigo': padre_codigo,
                'nivel': elem['nivel'],
                'orden': idx + 1,
                'cantidad': 1.0
            }
            nodos.append(nodo)

            codigo_a_elemento[codigo] = elem

        return conceptos, nodos

    def _encontrar_padre_por_codigo(self, codigo: str, elementos: Dict) -> Optional[str]:
        """
        Encuentra el código del padre basándose en la jerarquía del código.

        Ejemplos:
        - C01.01 → padre: C01
        - C01.01.02 → padre: C01.01
        - C01 → padre: None (es capítulo raíz)
        """
        if '.' not in codigo:
            return None  # Es un capítulo raíz

        # Obtener código padre quitando el último segmento
        partes = codigo.split('.')
        codigo_padre = '.'.join(partes[:-1])

        if codigo_padre in elementos:
            return codigo_padre

        return None

    # =====================================================
    # MÉTODOS PRIVADOS - FASE 2
    # =====================================================

    def _detectar_partidas(self) -> List[Dict]:
        """
        Detecta partidas en el PDF.

        Returns:
            Lista de partidas con su información
        """
        partidas = []

        # Patrón para partidas (ej: "E01ABC123  ud  Descripción  10,50  25,30  265,65")
        patron_partida = r'^([A-Z]\d{2}[A-Z]{3}\d{3})\s+(\w+)\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s*€?$'

        texto = self.extractor.extraer_texto_completo()
        lineas = texto.split('\n')

        for linea in lineas:
            linea = linea.strip()
            match = re.match(patron_partida, linea)

            if match:
                partida = {
                    'codigo': match.group(1),
                    'unidad': match.group(2),
                    'resumen': match.group(3).strip(),
                    'cantidad': Decimal(match.group(4).replace(',', '.')),
                    'precio': Decimal(match.group(5).replace(',', '.')),
                    'importe': Decimal(match.group(6).replace(',', '.'))
                }
                partidas.append(partida)

        logger.debug(f"Detectadas {len(partidas)} partidas")
        return partidas

    def _asociar_partidas_a_estructura(self, partidas: List[Dict]) -> tuple:
        """
        Asocia partidas a la estructura existente (capítulos/subcapítulos).

        Returns:
            (conceptos_partidas, nodos_partidas)
        """
        conceptos_partidas = []
        nodos_partidas = []

        # Obtener estructura existente de Fase 1
        nodos_existentes = self.fase1_resultado.get('nodos', [])

        # Crear mapa de códigos existentes
        codigos_existentes = {n['codigo_concepto'] for n in nodos_existentes}

        for idx, partida in enumerate(partidas):
            # Crear concepto de partida
            concepto = {
                'codigo': partida['codigo'],
                'tipo': TipoConcepto.PARTIDA,
                'nombre': partida['resumen'],
                'resumen': partida['resumen'],
                'unidad': partida['unidad'],
                'precio': partida['precio'],
                'cantidad_total': partida['cantidad'],
                'importe_total': partida['importe'],
                'descripcion': None
            }
            conceptos_partidas.append(concepto)

            # Encontrar padre (el subcapítulo o capítulo al que pertenece)
            padre_codigo = self._encontrar_padre_partida(partida['codigo'], codigos_existentes)

            # Calcular nivel (padre.nivel + 1)
            nivel_padre = self._obtener_nivel_padre(padre_codigo, nodos_existentes)

            # Crear nodo de partida
            nodo = {
                'codigo_concepto': partida['codigo'],
                'padre_codigo': padre_codigo,
                'nivel': nivel_padre + 1 if nivel_padre is not None else 3,
                'orden': idx + 1,
                'cantidad': 1.0
            }
            nodos_partidas.append(nodo)

        return conceptos_partidas, nodos_partidas

    def _encontrar_padre_partida(self, codigo_partida: str, codigos_existentes: set) -> Optional[str]:
        """
        Encuentra el padre de una partida basándose en los códigos existentes.

        Lógica:
        - Busca el subcapítulo/capítulo cuyo código sea prefijo del código de la partida
        - Ej: E01ABC123 → busca C01, C01.01, etc.
        """
        # Extraer prefijo de capítulo (primeros caracteres antes de letras/números)
        # Ej: E01ABC123 → "01" → buscar "C01"

        # TODO: Implementar lógica más sofisticada basada en contexto del PDF
        # Por ahora, asignamos a un capítulo genérico o al último detectado

        return None  # Placeholder

    def _obtener_nivel_padre(self, codigo_padre: Optional[str], nodos: List[Dict]) -> Optional[int]:
        """Obtiene el nivel del nodo padre"""
        if not codigo_padre:
            return None

        for nodo in nodos:
            if nodo['codigo_concepto'] == codigo_padre:
                return nodo['nivel']

        return None

    # =====================================================
    # MÉTODOS PRIVADOS - FASE 3
    # =====================================================

    def _calcular_totales_recursivos(self) -> Dict[str, Decimal]:
        """
        Calcula totales de forma recursiva sumando importes de partidas.

        Returns:
            {codigo: total_calculado}
        """
        # TODO: Implementar cálculo recursivo
        # Por ahora retorna diccionario vacío
        return {}

    def _detectar_discrepancias(self, totales_calculados: Dict) -> List[Dict]:
        """
        Detecta discrepancias entre totales del PDF y totales calculados.

        Returns:
            Lista de discrepancias
        """
        discrepancias = []

        # Obtener totales del PDF (de Fase 1)
        conceptos_fase1 = self.fase1_resultado.get('conceptos', [])

        for concepto in conceptos_fase1:
            codigo = concepto['codigo']
            total_pdf = concepto.get('total')
            total_calculado = totales_calculados.get(codigo)

            if total_pdf and total_calculado:
                diferencia = abs(total_pdf - total_calculado)

                # Umbral de 0.01€ para considerar discrepancia
                if diferencia > Decimal('0.01'):
                    discrepancias.append({
                        'codigo': codigo,
                        'total_pdf': total_pdf,
                        'total_calculado': total_calculado,
                        'diferencia': diferencia
                    })

        return discrepancias
