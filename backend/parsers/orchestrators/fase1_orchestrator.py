"""
Orquestador de FASE 1 - Decide qué parser de estructura usar.

Detecta automáticamente el formato del presupuesto y selecciona el parser apropiado:
- EXPLÍCITO: usa StructureParserExplicit (proyecto 16 - ARENAL)
- IMPLÍCITO: usa StructureParserImplicit (proyecto 15 - NAVAS DE TOLOSA)

Autor: Claude Code
Fecha: 2026-01-25
"""
import logging
from typing import Dict, List
from ..structure_parsers import StructureParserExplicit, StructureParserImplicit

logger = logging.getLogger(__name__)


class Fase1Orchestrator:
    """
    Orquestador que detecta el formato y selecciona el parser de estructura apropiado.
    """

    @staticmethod
    def detectar_formato(lineas: List[str]) -> str:
        """
        Detecta si el presupuesto usa formato EXPLÍCITO o IMPLÍCITO.

        Formato EXPLÍCITO: usa palabras "CAPÍTULO" y "SUBCAPÍTULO" (ej: proyecto 16)
        Formato IMPLÍCITO: solo usa códigos sin palabras (ej: proyecto 15)

        Estrategia:
        - Buscar en las primeras 100 líneas si aparece "CAPÍTULO" o "SUBCAPÍTULO"
        - Si aparece al menos 2 veces, es formato explícito
        - Si no, es formato implícito

        Args:
            lineas: Lista de strings del PDF

        Returns:
            'EXPLICIT' o 'IMPLICIT'
        """
        contador_palabras = 0

        for linea in lineas[:100]:  # Solo primeras 100 líneas
            linea_upper = linea.upper()
            if 'CAPÍTULO' in linea_upper or 'SUBCAPÍTULO' in linea_upper or 'APARTADO' in linea_upper:
                contador_palabras += 1

            # Si encontramos al menos 2 ocurrencias, es formato explícito
            if contador_palabras >= 2:
                return 'EXPLICIT'

        # Si no encontramos suficientes ocurrencias, es formato implícito
        return 'IMPLICIT'

    @staticmethod
    def parsear(lineas: List[str]) -> Dict:
        """
        Parsea la estructura detectando automáticamente el formato.

        Args:
            lineas: Lista de strings del PDF

        Returns:
            Dict con estructura jerárquica y metadata del formato usado
        """
        # Detectar formato
        formato = Fase1Orchestrator.detectar_formato(lineas)
        logger.info(f"📋 Formato detectado: {formato}")

        # Seleccionar parser apropiado
        if formato == 'EXPLICIT':
            parser = StructureParserExplicit()
        else:
            parser = StructureParserImplicit()

        # Parsear
        estructura = parser.parsear(lineas)

        # Añadir metadata del formato usado
        estructura['metadata'] = {
            'formato': formato,
            'parser_usado': parser.__class__.__name__
        }

        return estructura
