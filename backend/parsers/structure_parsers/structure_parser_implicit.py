"""
Parser de estructura para formato IMPLÍCITO.

Formato IMPLÍCITO: presupuestos que NO usan palabras "CAPÍTULO" y "SUBCAPÍTULO"
sino solo códigos (ejemplo: proyecto 15 - NAVAS DE TOLOSA).

Características:
- Busca líneas con código "01 NOMBRE" para capítulos
- Busca líneas con código "01.04 NOMBRE" para subcapítulos
- Debe diferenciar subcapítulos de partidas (las partidas tienen unidades)
- Más permisivo pero con validaciones de unidades

Autor: Claude Code
Fecha: 2026-01-25
"""
import re
import logging
from typing import Dict, List
from .structure_parser_base import StructureParserBase

logger = logging.getLogger(__name__)


class StructureParserImplicit(StructureParserBase):
    """
    Parser especializado para formato IMPLÍCITO sin palabras clave.
    """

    # Patrón capítulo: "01 NOMBRE" o "C01 NOMBRE" (sin palabra CAPÍTULO)
    # MODIFICADO: Ahora acepta códigos alfanuméricos (C01, C10, etc.) además de numéricos
    PATRON_CAPITULO = re.compile(
        r'^([A-Z]?\d{1,2})\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\-/\.,:;()]+)$'
    )

    # Patrón subcapítulo: "01.04 NOMBRE" o "C08.01 NOMBRE" (sin palabra SUBCAPÍTULO)
    # MODIFICADO: Ahora acepta códigos alfanuméricos (C08.01, C10.02, etc.) además de numéricos
    PATRON_SUBCAPITULO = re.compile(
        r'^([A-Z]?\d{1,2}(?:\.\d{1,2})+)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\-/\.,:;()]+)$'
    )

    # Unidades comunes que indican que es una partida, no un subcapítulo
    UNIDADES_PARTIDA = {
        'M', 'M2', 'M3', 'ML', 'UD', 'U', 'KG', 'T', 'TM', 'PA', 'H', 'L',
        'DM2', 'DM3', 'CM2', 'CM3', 'HA', 'KM', 'DM', 'CM', 'MM',
        'KW', 'KWH', 'MWH', 'UR', 'U20R', 'P:A', 'M23U01C190',
        'APUDM23E01DKAM0220', 'APUI_001', 'M23M02PTD010'
    }

    # Patrón TOTAL con código: "TOTAL 01.04.01 ... 12.345,67" o "TOTAL C08.01 ... 110.289,85"
    # MODIFICADO: Ahora acepta códigos alfanuméricos
    PATRON_TOTAL_CON_PUNTOS = re.compile(
        r'^TOTAL\s+([A-Z]?\d{1,2}(?:\.\d{1,2})*)[\s\.]+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
        re.IGNORECASE
    )

    # Patrón TOTAL sin código: "TOTAL 12.345,67"
    PATRON_TOTAL_SIN_CODIGO = re.compile(
        r'^TOTAL\s+([\d.,]+)\s*$',
        re.IGNORECASE
    )

    def parsear(self, lineas: List[str]) -> Dict:
        """
        Parsea líneas en formato IMPLÍCITO.

        Args:
            lineas: Lista de strings del PDF

        Returns:
            Dict con estructura jerárquica
        """
        logger.info(f"🔧 Parser IMPLÍCITO - {len(lineas)} líneas")

        self.estructura = {'capitulos': []}
        self.capitulo_actual = None
        self.ultimo_codigo = None
        self.mapa_nodos = {}

        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue

            # Capítulo
            match_cap = self.PATRON_CAPITULO.match(linea)
            if match_cap:
                codigo = match_cap.group(1)
                nombre = match_cap.group(2).strip()

                # Validaciones
                if codigo in ['0', '00']:
                    continue
                if 'página' in nombre.lower() or 'pagina' in nombre.lower():
                    continue

                # NUEVA VALIDACIÓN: Rechazar códigos muy largos (>3 caracteres)
                if len(codigo) > 3:
                    logger.debug(f"  ⚠️  Capítulo rechazado (código muy largo): {codigo}")
                    continue

                # Validar que no sea una partida
                palabras = nombre.split()
                if palabras and palabras[0].upper() in self.UNIDADES_PARTIDA:
                    logger.debug(f"  ⚠️  Capítulo rechazado (parece partida): {codigo} {nombre[:40]}")
                    continue

                self._procesar_capitulo(codigo, nombre)
                continue

            # Subcapítulo (validar que no sea partida)
            match_sub = self.PATRON_SUBCAPITULO.match(linea)
            if match_sub:
                codigo = match_sub.group(1)
                nombre = match_sub.group(2).strip()

                # Validar que no sea una partida
                palabras = nombre.split()
                if palabras:
                    primera_palabra = palabras[0].upper()
                    # Si la primera palabra es una unidad Y hay más texto, es una partida
                    if primera_palabra in self.UNIDADES_PARTIDA and len(palabras) > 1:
                        logger.debug(f"  ⚠️  Subcapítulo rechazado (es partida): {codigo} {nombre[:40]}")
                        continue

                self._procesar_subcapitulo(codigo, nombre)
                continue

            # TOTAL con puntos
            match_total_puntos = self.PATRON_TOTAL_CON_PUNTOS.match(linea)
            if match_total_puntos:
                codigo = match_total_puntos.group(1)
                total_str = match_total_puntos.group(2)
                self._procesar_total(total_str, codigo_explicito=codigo)
                continue

            # TOTAL sin código
            match_total_sin = self.PATRON_TOTAL_SIN_CODIGO.match(linea)
            if match_total_sin:
                total_str = match_total_sin.group(1)
                self._procesar_total(total_str, codigo_explicito=None)
                continue

        # Calcular totales faltantes
        self._calcular_totales_faltantes()

        logger.info(f"✓ Parsing completado: {len(self.estructura['capitulos'])} capítulos")
        return self.estructura

    def _procesar_subcapitulo(self, codigo: str, nombre: str):
        """
        Procesa un subcapítulo de cualquier nivel.
        Sobrescribe el método base para agregar lógica de adopción forzada.

        NUEVA FUNCIONALIDAD: Maneja códigos inconsistentes (ej: CAPÍTULO C01 → SUBCAPÍTULO C08.01)
        mediante detección contextual - si el prefijo no coincide con el capítulo actual,
        lo asigna al último capítulo detectado (adopción forzada).
        """
        if not self.capitulo_actual:
            logger.warning(f"⚠️  Subcapítulo {codigo} sin capítulo padre - ignorado")
            return

        logger.debug(f"  📂 Subcapítulo: {codigo} - {nombre}")

        # NUEVA VALIDACIÓN: Verificar si el código del subcapítulo es coherente con el capítulo actual
        # Extraer el prefijo del código del subcapítulo (parte antes del primer punto)
        partes = codigo.split('.')
        prefijo_subcap = partes[0] if len(partes) > 1 else None
        codigo_capitulo = self.capitulo_actual['codigo']

        adopted = False  # Flag para marcar si fue adoptado forzadamente

        if prefijo_subcap and prefijo_subcap != codigo_capitulo:
            # El prefijo NO coincide con el capítulo actual (ej: C08 vs C01)
            logger.warning(f"⚠️  Código inconsistente detectado: Subcapítulo {codigo} bajo Capítulo {codigo_capitulo}")
            logger.warning(f"   → Asignación forzada por contexto (el subcapítulo sigue al capítulo en el documento)")
            adopted = True

        # Asegurar que todos los niveles padres existen
        # IMPORTANTE: Con códigos adoptados, necesitamos crear los niveles intermedios manualmente
        self._asegurar_niveles_intermedios_adoptados(codigo, adopted)

        # Crear el nuevo subcapítulo
        nuevo_sub = {
            'codigo': codigo,
            'nombre': nombre,
            'subcapitulos': [],
            'total': None,
            'orden': 0  # Se ajustará al agregarlo
        }

        # Marcar si fue adoptado forzadamente (para debugging)
        if adopted:
            nuevo_sub['_adopted'] = True
            nuevo_sub['_codigo_capitulo_padre'] = codigo_capitulo

        # Determinar dónde agregarlo según el nivel
        if len(partes) == 2:
            # Nivel 1: agregar directamente al capítulo
            nuevo_sub['orden'] = len(self.capitulo_actual['subcapitulos'])
            self.capitulo_actual['subcapitulos'].append(nuevo_sub)
        else:
            # Nivel 2+: agregar al padre correspondiente
            codigo_padre = '.'.join(partes[:-1])

            if codigo_padre in self.mapa_nodos:
                padre = self.mapa_nodos[codigo_padre]
                nuevo_sub['orden'] = len(padre['subcapitulos'])
                padre['subcapitulos'].append(nuevo_sub)
            else:
                logger.warning(f"⚠️  Padre {codigo_padre} no encontrado para {codigo}")
                # Fallback: agregar a capítulo
                nuevo_sub['orden'] = len(self.capitulo_actual['subcapitulos'])
                self.capitulo_actual['subcapitulos'].append(nuevo_sub)

        # Registrar en el mapa
        self.mapa_nodos[codigo] = nuevo_sub
        self.ultimo_codigo = codigo

    def _asegurar_niveles_intermedios_adoptados(self, codigo: str, adopted: bool):
        """
        Asegura que todos los niveles padres existen, manejando códigos adoptados.
        """
        partes = codigo.split('.')

        if len(partes) <= 2:
            return

        for i in range(2, len(partes)):
            codigo_intermedio = '.'.join(partes[:i])

            if codigo_intermedio in self.mapa_nodos:
                continue

            logger.info(f"  🔧 Creando nivel intermedio adoptado: {codigo_intermedio}")

            nombre_generico = f"SUBCAPÍTULO {codigo_intermedio}"

            nuevo_nivel = {
                'codigo': codigo_intermedio,
                'nombre': nombre_generico,
                'subcapitulos': [],
                'total': None,
                'orden': 0,
                '_generado': True
            }

            if adopted:
                nuevo_nivel['_adopted'] = True
                nuevo_nivel['_codigo_capitulo_padre'] = self.capitulo_actual['codigo']

            if i == 2:
                nuevo_nivel['orden'] = len(self.capitulo_actual['subcapitulos'])
                self.capitulo_actual['subcapitulos'].append(nuevo_nivel)
            else:
                codigo_padre = '.'.join(partes[:i-1])
                if codigo_padre in self.mapa_nodos:
                    padre = self.mapa_nodos[codigo_padre]
                    nuevo_nivel['orden'] = len(padre['subcapitulos'])
                    padre['subcapitulos'].append(nuevo_nivel)
                else:
                    logger.warning(f"⚠️  Padre {codigo_padre} no encontrado, agregando {codigo_intermedio} al capítulo")
                    nuevo_nivel['orden'] = len(self.capitulo_actual['subcapitulos'])
                    self.capitulo_actual['subcapitulos'].append(nuevo_nivel)

            self.mapa_nodos[codigo_intermedio] = nuevo_nivel
