"""
Parser de estructura para formato EXPLÍCITO.

Formato EXPLÍCITO: presupuestos que usan las palabras "CAPÍTULO" y "SUBCAPÍTULO"
explícitamente en el texto (ejemplo: proyecto 16 - ARENAL).

Características:
- Busca líneas que contengan "CAPÍTULO XX" o "SUBCAPÍTULO XX.YY"
- Las partidas NO tienen estas palabras, solo códigos con unidades
- Muy estricto: si no dice "SUBCAPÍTULO", no es un subcapítulo

Autor: Claude Code
Fecha: 2026-01-25
"""
import re
import logging
from typing import Dict, List
from .structure_parser_base import StructureParserBase

logger = logging.getLogger(__name__)


class StructureParserExplicit(StructureParserBase):
    """
    Parser especializado para formato EXPLÍCITO con palabras clave.
    """

    def __init__(self):
        super().__init__()
        self.esperando_total_en_siguiente_linea = False  # Flag para capturar total en línea siguiente

    # Patrón capítulo: "CAPÍTULO 01 NOMBRE" o "CAPÍTULO C01 NOMBRE" (palabra CAPÍTULO obligatoria)
    # MODIFICADO: Ahora acepta códigos alfanuméricos (C01, C10, etc.) además de numéricos
    PATRON_CAPITULO = re.compile(
        r'^CAPÍTULO\s+([A-Z]?\d{1,2})\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\-/\.,:;()]+)$'
    )

    # Patrón subcapítulo: "SUBCAPÍTULO 01.04 NOMBRE" o "SUBCAPÍTULO C08.01 NOMBRE" (palabra SUBCAPÍTULO obligatoria)
    # MODIFICADO: Ahora acepta códigos alfanuméricos (C08.01, C10.02, etc.) además de numéricos
    PATRON_SUBCAPITULO = re.compile(
        r'^(?:SUBCAPÍTULO|APARTADO)\s+([A-Z]?\d{1,2}(?:\.\d{1,2})+)\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\-/\.,:;()]+)$'
    )

    # Patrón para detectar códigos con unidades (partidas, no subcapítulos)
    # Ejemplo: "04.01 UD SEGURIDAD Y SALUD"
    PATRON_CODIGO_CON_UNIDAD = re.compile(
        r'^(\d{1,2}(?:\.\d{1,2})+)\s+(UD|U|M|M2|M3|ML|KG|T|PA|H|L|P:A)\s+',
        re.IGNORECASE
    )

    # Patrón TOTAL con código: "TOTAL SUBCAPÍTULO 01.04.01 ... 12.345,67" o "TOTAL SUBCAPÍTULO C08.01 ... 110.289,85"
    # MODIFICADO: Ahora acepta códigos alfanuméricos (C08.01, etc.)
    PATRON_TOTAL_CON_CODIGO = re.compile(
        r'^TOTAL\s+(SUBCAPÍTULO|CAPÍTULO|APARTADO)\s+([A-Z]?[\d\.]+)\s+.*?([\d.,]+)\s*$',
        re.IGNORECASE
    )

    # Patrón TOTAL con puntos: "TOTAL 01.04....... 12.345,67" o "TOTAL C08.01........ 110.289,85"
    # MODIFICADO: Ahora acepta códigos alfanuméricos
    PATRON_TOTAL_CON_PUNTOS = re.compile(
        r'^TOTAL\s+([A-Z]?\d{1,2}(?:\.\d{1,2})*)[\s\.]+(\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
        re.IGNORECASE
    )

    # Patrón TOTAL sin código: "TOTAL 12.345,67" o "....... 12.345,67" (línea solo con puntos e importe)
    PATRON_TOTAL_SIN_CODIGO = re.compile(
        r'^(?:TOTAL\s+|[\s\.]+)(\d{1,3}(?:\.\d{3})*,\d{2})\s*$',
        re.IGNORECASE
    )

    # Patrón RESUMEN: "01 MOVIMIENTOS DE TIERRAS....... 58.340,10 2,70" (formato resumen de presupuesto)
    # Usar non-greedy matching y asegurar que capturamos el número completo al final
    PATRON_TOTAL_RESUMEN = re.compile(
        r'^(\d{1,2})\s+[A-ZÁÉÍÓÚÑ][\sA-ZÁÉÍÓÚÑa-záéíóúñ\-/,;:()]+?[\s\.]+(\d{1,3}(?:\.\d{3})*,\d{2})\s+[\d,]+\s*$',
        re.IGNORECASE
    )

    def parsear(self, lineas: List[str]) -> Dict:
        """
        Parsea líneas en formato EXPLÍCITO.

        Args:
            lineas: Lista de strings del PDF

        Returns:
            Dict con estructura jerárquica
        """
        logger.info(f"🔧 Parser EXPLÍCITO - {len(lineas)} líneas")

        self.estructura = {'capitulos': []}
        self.capitulo_actual = None
        self.ultimo_codigo = None
        self.mapa_nodos = {}
        self.esperando_total_en_siguiente_linea = False

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
                    logger.debug(f"  ⚠️  Capítulo inválido: {codigo}")
                    continue
                if 'página' in nombre.lower() or 'pagina' in nombre.lower():
                    logger.debug(f"  ⚠️  Parece número de página: {codigo} {nombre}")
                    continue

                # NUEVA VALIDACIÓN: Rechazar códigos muy largos (>3 caracteres)
                # Ej: "U01AB100" (8 chars), "DEM06" (5 chars) → son códigos de partida, NO capítulos
                if len(codigo) > 3:
                    logger.debug(f"  ⚠️  Capítulo rechazado (código muy largo, parece partida): {codigo}")
                    continue

                self._procesar_capitulo(codigo, nombre)
                continue

            # Validar si es un código con unidad (partida, no subcapítulo)
            # Ejemplo: "04.01 UD SEGURIDAD" debe ser ignorado como subcapítulo
            if self.PATRON_CODIGO_CON_UNIDAD.match(linea):
                # Es una partida, no un subcapítulo - ignorar
                logger.debug(f"  ⚠️  Código con unidad (partida): {linea[:60]}")
                continue

            # Subcapítulo (debe tener palabra clave)
            match_sub = self.PATRON_SUBCAPITULO.match(linea)
            if match_sub:
                codigo = match_sub.group(1)
                nombre = match_sub.group(2).strip()
                self._procesar_subcapitulo(codigo, nombre)
                continue

            # TOTAL con código explícito
            match_total_cod = self.PATRON_TOTAL_CON_CODIGO.match(linea)
            if match_total_cod:
                tipo = match_total_cod.group(1).upper()
                codigo = match_total_cod.group(2)
                total_str = match_total_cod.group(3)

                # Si el total_str solo tiene puntos (sin dígitos), esperar siguiente línea
                if total_str.replace('.', '').replace(',', '').replace(' ', '').isdigit():
                    self._procesar_total(total_str, codigo_explicito=codigo, tipo=tipo)
                else:
                    # Total viene en siguiente línea
                    self.esperando_total_en_siguiente_linea = True
                    logger.debug(f"  ⏳ Total para {codigo} viene en siguiente línea")
                continue

            # TOTAL con puntos
            match_total_puntos = self.PATRON_TOTAL_CON_PUNTOS.match(linea)
            if match_total_puntos:
                codigo = match_total_puntos.group(1)
                total_str = match_total_puntos.group(2)
                self._procesar_total(total_str, codigo_explicito=codigo)
                continue

            # TOTAL sin código (o línea solo con puntos e importe)
            match_total_sin = self.PATRON_TOTAL_SIN_CODIGO.match(linea)
            if match_total_sin:
                total_str = match_total_sin.group(1)
                # Solo procesar si estamos esperando el total en la siguiente línea
                if self.esperando_total_en_siguiente_linea:
                    self._procesar_total(total_str, codigo_explicito=None)
                    self.esperando_total_en_siguiente_linea = False
                    continue
                # O si la línea empieza con "TOTAL"
                elif linea.upper().startswith('TOTAL'):
                    self._procesar_total(total_str, codigo_explicito=None)
                    continue

            # TOTAL en formato RESUMEN: "01 MOVIMIENTOS DE TIERRAS....... 58.340,10 2,70"
            match_resumen = self.PATRON_TOTAL_RESUMEN.match(linea)
            if match_resumen:
                codigo = match_resumen.group(1)
                total_str = match_resumen.group(2)
                self._procesar_total(total_str, codigo_explicito=codigo)
                logger.debug(f"  📊 Total desde resumen: CAP {codigo} = {total_str}")
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
        # IMPORTANTE: Con códigos adoptados (ej: C08.08.01 bajo C01), el método base
        # no puede encontrar el padre C08.08 porque busca por código exacto.
        # Necesitamos crear los niveles intermedios manualmente en estos casos.
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

        Para códigos adoptados (ej: C08.08.01 bajo capítulo C01), crea los niveles
        intermedios (C08.08) aunque el prefijo no coincida con el capítulo.
        """
        partes = codigo.split('.')

        # Si solo tiene 2 partes (ej: C08.01), no hay niveles intermedios
        if len(partes) <= 2:
            return

        # Crear todos los niveles intermedios necesarios
        for i in range(2, len(partes)):
            codigo_intermedio = '.'.join(partes[:i])

            # Si ya existe en el mapa, continuar
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

            # Si fue adoptado, marcar también el nivel intermedio
            if adopted:
                nuevo_nivel['_adopted'] = True
                nuevo_nivel['_codigo_capitulo_padre'] = self.capitulo_actual['codigo']

            # Determinar dónde agregar el nivel intermedio
            if i == 2:
                # Primer nivel: agregar al capítulo actual
                nuevo_nivel['orden'] = len(self.capitulo_actual['subcapitulos'])
                self.capitulo_actual['subcapitulos'].append(nuevo_nivel)
            else:
                # Niveles superiores: agregar al padre correspondiente
                codigo_padre = '.'.join(partes[:i-1])
                if codigo_padre in self.mapa_nodos:
                    padre = self.mapa_nodos[codigo_padre]
                    nuevo_nivel['orden'] = len(padre['subcapitulos'])
                    padre['subcapitulos'].append(nuevo_nivel)
                else:
                    # Si no existe el padre, agregar al capítulo (fallback)
                    logger.warning(f"⚠️  Padre {codigo_padre} no encontrado, agregando {codigo_intermedio} al capítulo")
                    nuevo_nivel['orden'] = len(self.capitulo_actual['subcapitulos'])
                    self.capitulo_actual['subcapitulos'].append(nuevo_nivel)

            # Registrar en el mapa
            self.mapa_nodos[codigo_intermedio] = nuevo_nivel
