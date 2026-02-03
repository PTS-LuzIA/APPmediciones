"""
Extractor de texto desde PDFs de mediciones.
Utiliza pdfplumber para extraer texto línea por línea preservando estructura.
Soporta detección automática de layouts de múltiples columnas.
"""

import pdfplumber
import logging
from pathlib import Path
from typing import List, Dict, Optional

try:
    from .column_detector import ColumnDetector
except ImportError:
    import sys
    from pathlib import Path
    parent_dir = str(Path(__file__).parent.parent)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    from parser.column_detector import ColumnDetector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extrae texto estructurado desde PDFs de mediciones"""

    def __init__(self, pdf_path: str, user_id: int, proyecto_id: int,
                 detect_columns: bool = True, remove_repeated_headers: bool = True):
        """
        Args:
            pdf_path: Ruta al archivo PDF
            user_id: ID del usuario (REQUERIDO, se incluye en nombres de archivos de log)
            proyecto_id: ID del proyecto (REQUERIDO, se incluye en nombres de archivos de log)
            detect_columns: Si True, detecta automáticamente layouts de múltiples columnas
                           y extrae cada columna por separado usando bounding boxes
            remove_repeated_headers: Si True, elimina cabeceras repetidas después de la primera aparición
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

        self.pages_text = []
        self.metadata = {}
        self.detect_columns = detect_columns
        self.remove_repeated_headers = remove_repeated_headers
        self.column_detector = ColumnDetector() if detect_columns else None
        self.layout_info = []  # Información de layout por página
        self.user_id = user_id
        self.proyecto_id = proyecto_id

        # Patrones comunes de cabeceras que se repiten en cada página
        # Se usan patrones genéricos que aplican a la mayoría de presupuestos
        # IMPORTANTE: Incluir variantes con columnas de mediciones (UDS, LONGITUD, etc.)
        self.header_patterns = [
            'PRESUPUESTO',
            'PRESUPUESTO Y MEDICIONES',  # Variante común en presupuestos con mediciones
            'CÓDIGO RESUMEN CANTIDAD PRECIO IMPORTE',
            'CÓDIGO RESUMEN UDS LONGITUD ANCHURA ALTURA PARCIALES CANTIDAD PRECIO IMPORTE',  # Versión extendida con mediciones
            # El nombre del proyecto se detectará dinámicamente
        ]

        # Patrones adicionales para coincidencia parcial (cabeceras que pueden variar)
        # Estos se verifican con "startswith" en lugar de coincidencia exacta
        self.header_partial_patterns = [
            'CÓDIGO RESUMEN',  # Cualquier cabecera que empiece así
            'PRESUPUESTO Y',   # "PRESUPUESTO Y MEDICIONES", etc.
        ]

    def extraer_todo(self) -> Dict:
        """
        Extrae todo el contenido del PDF

        Returns:
            dict: {
                'metadata': {...},
                'pages': [{'num': 1, 'text': '...', 'lines': [...], 'layout': {...}}, ...],
                'all_text': 'texto completo',
                'all_lines': ['línea1', 'línea2', ...],
                'layout_summary': {'total_columnas': int, 'paginas_multicolumna': int}
            }
        """
        import os

        # CACHÉ: Verificar si ya existe el texto extraído del PDF
        nombre_pdf = self.pdf_path.stem
        cache_dir = Path('logs/extracted_pdfs')

        # Limpiar nombre del PDF: quitar prefijos user_id/proyecto_id si existen
        # Formatos a limpiar:
        # - Nuevo: u{user_id}_p{proyecto_id}_{nombre} → {nombre}
        # - Antiguo: {user_id}_{nombre} → {nombre}
        import re
        nombre_limpio = nombre_pdf

        # Intentar quitar formato nuevo: u{user_id}_p{proyecto_id}_
        match = re.match(r'u\d+_p\d+_(.+)', nombre_pdf)
        if match:
            nombre_limpio = match.group(1)
        else:
            # Intentar quitar formato antiguo: {user_id}_
            if '_' in nombre_pdf:
                first_part = nombre_pdf.split('_')[0]
                if first_part.isdigit() and int(first_part) == self.user_id:
                    nombre_limpio = '_'.join(nombre_pdf.split('_')[1:])

        # Construir nombre de archivo de caché SIEMPRE incluyendo user_id y proyecto_id
        # Formato: u{user_id}_p{proyecto_id}_{nombre_limpio}_extracted.txt
        cache_filename = f"u{self.user_id}_p{self.proyecto_id}_{nombre_limpio}_extracted.txt"
        cache_file = cache_dir / cache_filename

        if cache_file.exists():
            logger.info(f"✓ Usando texto cacheado: {cache_file}")
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    lineas = [linea.rstrip('\n') for linea in f.readlines()]

                # Detectar título del proyecto desde caché
                titulo_proyecto = None
                for linea in lineas[:10]:
                    linea_limpia = linea.strip()
                    # Buscar línea larga que parezca título (no es cabecera estándar ni código)
                    if (len(linea_limpia) > 30 and
                        not linea_limpia.startswith(('CÓDIGO', 'PRESUPUESTO', 'CÓDIGO RESUMEN', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15')) and
                        linea_limpia not in self.header_patterns):
                        titulo_proyecto = linea_limpia
                        logger.info(f"📋 Título del proyecto detectado desde caché: '{titulo_proyecto}'")
                        break

                resultado = {
                    'metadata': {'archivo': self.pdf_path.name, 'from_cache': True},
                    'pages': [],
                    'all_text': '\n'.join(lineas),
                    'all_lines': lineas,
                    'layout_summary': {'total_columnas': 0, 'paginas_multicolumna': 0}
                }

                # Añadir título si se detectó
                if titulo_proyecto:
                    resultado['titulo_proyecto'] = titulo_proyecto

                return resultado
            except Exception as e:
                logger.warning(f"⚠️ Error leyendo caché, extrayendo de nuevo: {e}")

        resultado = {
            'metadata': {},
            'pages': [],
            'all_text': '',
            'all_lines': [],
            'layout_summary': {'total_columnas': 0, 'paginas_multicolumna': 0}
        }

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                # Extraer metadata
                resultado['metadata'] = {
                    'archivo': self.pdf_path.name,
                    'num_paginas': len(pdf.pages),
                    'info': pdf.metadata
                }

                logger.info(f"Extrayendo {len(pdf.pages)} páginas de {self.pdf_path.name}")

                # Extraer cada página
                for i, page in enumerate(pdf.pages, start=1):
                    page_data = self._extraer_pagina(page, i)
                    resultado['pages'].append(page_data)
                    resultado['all_lines'].extend(page_data['lines'])

                    # Actualizar resumen de layout
                    if page_data.get('layout'):
                        num_cols = page_data['layout'].get('num_columnas', 1)
                        if num_cols > 1:
                            resultado['layout_summary']['paginas_multicolumna'] += 1
                        resultado['layout_summary']['total_columnas'] = max(
                            resultado['layout_summary']['total_columnas'],
                            num_cols
                        )

                # Filtrar cabeceras repetidas si está habilitado
                if self.remove_repeated_headers:
                    lineas_originales = len(resultado['all_lines'])
                    resultado['all_lines'], titulo_proyecto = self._filtrar_cabeceras_repetidas(resultado['all_lines'])
                    # Guardar el título del proyecto en metadata
                    if titulo_proyecto:
                        resultado['titulo_proyecto'] = titulo_proyecto
                    lineas_filtradas = len(resultado['all_lines'])
                    if lineas_filtradas < lineas_originales:
                        logger.info(f"🧹 Cabeceras repetidas eliminadas: {lineas_originales} → {lineas_filtradas} líneas ({lineas_originales - lineas_filtradas} eliminadas)")

                # Filtrar pies de página con números de paginación
                lineas_antes_footer = len(resultado['all_lines'])
                resultado['all_lines'] = self._filtrar_pies_pagina(resultado['all_lines'])
                lineas_despues_footer = len(resultado['all_lines'])
                if lineas_despues_footer < lineas_antes_footer:
                    logger.info(f"🗑️  Pies de página eliminados: {lineas_antes_footer - lineas_despues_footer} líneas")

                # Reordenar totales de partida que aparecen después de TOTAL CAPÍTULO (problema de salto de página)
                resultado['all_lines'] = self._reordenar_totales_partida_tras_salto_pagina(resultado['all_lines'])

                # Fusionar líneas TOTAL fragmentadas (importe en línea separada)
                lineas_antes_fusion = len(resultado['all_lines'])
                resultado['all_lines'] = self._fusionar_totales_fragmentados(resultado['all_lines'])
                fusiones_realizadas = lineas_antes_fusion - len(resultado['all_lines'])
                if fusiones_realizadas > 0:
                    logger.info(f"🔗 Líneas TOTAL fusionadas: {fusiones_realizadas} fusiones")

                # NOTA: La fusión de datos numéricos separados ya NO es necesaria porque
                # las páginas de presupuesto se detectan y procesan con extract_text() estándar,
                # que preserva correctamente la alineación de números con partidas.
                # Fusionar números de forma global podía causar fusiones incorrectas.

                resultado['all_text'] = '\n'.join(resultado['all_lines'])

                # Log de información de columnas
                if resultado['layout_summary']['paginas_multicolumna'] > 0:
                    logger.info(
                        f"⚡ Detectadas {resultado['layout_summary']['paginas_multicolumna']} "
                        f"página(s) con múltiples columnas (máx: {resultado['layout_summary']['total_columnas']} columnas)"
                    )

                logger.info(f"✓ Extraídas {len(resultado['all_lines'])} líneas")

                # GUARDAR EN CACHÉ para reutilización
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        for linea in resultado['all_lines']:
                            f.write(linea + '\n')
                    logger.info(f"💾 Texto guardado en caché: {cache_file}")
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo guardar caché: {e}")

        except Exception as e:
            logger.error(f"Error extrayendo PDF: {e}")
            raise

        return resultado

    def _filtrar_cabeceras_repetidas(self, lineas: List[str]):
        """
        Filtra líneas de cabecera que se repiten en múltiples páginas.
        Mantiene solo la primera aparición de cada patrón de cabecera.

        Args:
            lineas: Lista de líneas de texto extraídas

        Returns:
            Tupla (lista de líneas filtradas, título del proyecto o None)
        """
        # Detectar dinámicamente el nombre del proyecto en las primeras 10 líneas
        # Típicamente aparece después de "PRESUPUESTO" y antes de "CÓDIGO RESUMEN..."
        patrones_dinamicos = list(self.header_patterns)
        titulo_proyecto = None  # Variable para guardar el título

        import re

        for i, linea in enumerate(lineas[:10]):
            linea_limpia = linea.strip()
            # Si es una línea larga que parece nombre de proyecto (no es capítulo ni código de partida)
            # IMPORTANTE: Excluir líneas que empiezan con códigos de partida (letras+números)
            # Ejemplos de códigos: DEM06, U01AB100, E04SM090, CABLE16, GR0001, etc.
            es_codigo_partida = bool(re.match(r'^[A-Z0-9]{2,}[\s\d]', linea_limpia))

            if (len(linea_limpia) > 30 and
                not linea_limpia.startswith(('CÓDIGO', 'PRESUPUESTO', 'CAPÍTULO', 'SUBCAPÍTULO',
                                            '01', '02', '03', '04', '05', '06', '07', '08', '09',
                                            '10', '11', '12', '13', '14', '15')) and
                not es_codigo_partida):
                # Verificar que no sea ya una cabecera conocida
                if linea_limpia not in patrones_dinamicos:
                    # Es probable que sea el nombre del proyecto
                    if titulo_proyecto is None:  # Capturar solo el primer título detectado
                        titulo_proyecto = linea_limpia
                        logger.info(f"📋 Título del proyecto detectado: '{titulo_proyecto}'")
                    patrones_dinamicos.append(linea_limpia)
                    logger.debug(f"Detectado nombre de proyecto como cabecera: '{linea_limpia[:60]}...'")

        lineas_filtradas = []
        cabeceras_vistas = set()

        for linea in lineas:
            linea_limpia = linea.strip()

            # IMPORTANTE: NUNCA filtrar líneas que contengan TOTAL (son datos importantes)
            if linea_limpia.upper().startswith('TOTAL'):
                lineas_filtradas.append(linea)
                continue

            # IMPORTANTE: NUNCA filtrar líneas que parecen códigos de partidas
            # Códigos de partida típicos: DEM06, U01AB100, E04SM090, CABLE16, GR0001, etc.
            es_codigo_partida = bool(re.match(r'^[A-Z0-9]{2,}[\s\d]', linea_limpia))
            if es_codigo_partida:
                lineas_filtradas.append(linea)
                continue

            # Verificar si es una cabecera conocida
            es_cabecera = False
            patron_coincidente = None

            # 1. Verificar coincidencia EXACTA con patrones dinámicos
            for patron in patrones_dinamicos:
                if linea_limpia == patron:
                    es_cabecera = True
                    patron_coincidente = patron
                    break

            # 2. Si no hubo coincidencia exacta, verificar patrones PARCIALES
            # Estos son cabeceras que pueden variar ligeramente
            if not es_cabecera and hasattr(self, 'header_partial_patterns'):
                for patron_parcial in self.header_partial_patterns:
                    if linea_limpia.startswith(patron_parcial):
                        es_cabecera = True
                        patron_coincidente = linea_limpia  # Usar línea completa como patrón
                        logger.debug(f"Cabecera parcial detectada: '{linea_limpia[:60]}' (patrón: '{patron_parcial}')")
                        break

            # Si es cabecera, aplicar lógica de filtrado
            if es_cabecera:
                # Si ya vimos esta cabecera, omitirla
                if patron_coincidente in cabeceras_vistas:
                    logger.debug(f"Cabecera repetida filtrada: '{linea_limpia[:60]}'")
                else:
                    # Primera vez que vemos esta cabecera, marcarla como vista
                    cabeceras_vistas.add(patron_coincidente)
                    lineas_filtradas.append(linea)
            else:
                # Si no es cabecera, añadirla siempre
                lineas_filtradas.append(linea)

        return lineas_filtradas, titulo_proyecto

    def _fusionar_datos_numericos_separados(self, lineas: List[str]) -> List[str]:
        """
        Detecta y fusiona líneas de datos numéricos separados con partidas.

        Problema: En algunos PDFs con layouts complejos, las columnas CANTIDAD/PRECIO/IMPORTE
        se extraen en líneas separadas debajo de las partidas en lugar de estar en la misma línea.

        Ejemplo ANTES:
            SYS UD SEGURIDAD Y SALUD
            Medidas de seguridad y salud durante la ejecución de las obras
            GYR UD GESTIÓN DE RESIDUOS
            Gestión de residuos de construcción y demolición.
            TOTAL CAPÍTULO C10 VARIOS.............................................................
            TOTAL.......................................................................................................
            CANTIDAD PRECIO IMPORTE
            0,30 15.000,00 4.500,00
            0,40 22.600,00 9.040,00

        Ejemplo DESPUÉS:
            SYS UD SEGURIDAD Y SALUD 0,30 15.000,00 4.500,00
            Medidas de seguridad y salud durante la ejecución de las obras
            GYR UD GESTIÓN DE RESIDUOS 0,40 22.600,00 9.040,00
            Gestión de residuos de construcción y demolición.
            TOTAL CAPÍTULO C10 VARIOS.............................................................
            TOTAL.......................................................................................................

        Args:
            lineas: Lista de líneas de texto extraídas

        Returns:
            Lista de líneas con datos numéricos fusionados en las partidas correspondientes
        """
        import re

        # Patrón para detectar líneas con código de partida y unidad (sin números al final)
        # Ej: "SYS UD SEGURIDAD Y SALUD", "GYR UD GESTIÓN DE RESIDUOS", "DEM06 m3 DEMOLICIÓN"
        patron_partida_sin_numeros = re.compile(
            r'^([A-Z][A-Z0-9]{1,19})\s+(m[2-3²³]?(?:/[a-z]+)?|ml|dm|cm|mm|km|m2|m3|dm2|dm3|cm2|cm3|ha|'
            r'ud|u|pa|h|l|kg|t|tm|kw|kwh|mwh|ur|u20r|p:a|mes|día|año|sem|hora)\s+([A-ZÁÉÍÓÚÑ].+)$',
            re.IGNORECASE
        )

        # Patrón para detectar líneas con solo 3 números (cantidad, precio, importe)
        # Formato español: "0,30 15.000,00 4.500,00"
        patron_tres_numeros = re.compile(
            r'^\s*(\d+(?:\.\d{3})*,\d{1,4})\s+(\d+(?:\.\d{3})*,\d{1,4})\s+(\d+(?:\.\d{3})*,\d{1,2})\s*$'
        )

        # Patrón para detectar header de columnas numéricas
        patron_header_numerico = re.compile(
            r'^\s*CANTIDAD\s+PRECIO\s+IMPORTE\s*$',
            re.IGNORECASE
        )

        lineas_procesadas = []
        partidas_pendientes = []  # Cola de partidas esperando datos numéricos
        numeros_pendientes = []   # Cola de líneas de números encontradas

        for i, linea in enumerate(lineas):
            linea_limpia = linea.strip()

            # 1. Si es un header de columnas numéricas, eliminarlo
            if patron_header_numerico.match(linea_limpia):
                logger.debug(f"  🗑️  Eliminando header numérico: '{linea_limpia}'")
                continue

            # 2. Si es una línea con solo 3 números, guardarla para fusionar
            match_numeros = patron_tres_numeros.match(linea_limpia)
            if match_numeros:
                cantidad = match_numeros.group(1)
                precio = match_numeros.group(2)
                importe = match_numeros.group(3)
                numeros_pendientes.append({
                    'cantidad': cantidad,
                    'precio': precio,
                    'importe': importe,
                    'linea_original': linea_limpia
                })
                logger.debug(f"  📊 Números detectados: {cantidad} {precio} {importe}")
                continue

            # 3. Si es una partida sin números, guardarla y marcar que espera datos
            match_partida = patron_partida_sin_numeros.match(linea_limpia)
            if match_partida:
                codigo = match_partida.group(1)
                unidad = match_partida.group(2)
                descripcion = match_partida.group(3)

                # Validar que no sea un TOTAL o algo parecido
                if codigo.upper() in ['TOTAL', 'SUBTOTAL', 'CODIGO', 'RESUMEN']:
                    lineas_procesadas.append(linea)
                    continue

                # Verificar si hay números pendientes para fusionar
                if numeros_pendientes:
                    # Tomar el primer conjunto de números pendientes
                    datos = numeros_pendientes.pop(0)
                    linea_fusionada = f"{codigo} {unidad} {descripcion} {datos['cantidad']} {datos['precio']} {datos['importe']}"
                    lineas_procesadas.append(linea_fusionada)
                    logger.debug(f"  ✅ Fusionada: {codigo} con números {datos['cantidad']} {datos['precio']} {datos['importe']}")
                else:
                    # No hay números disponibles todavía, guardar como pendiente
                    partidas_pendientes.append({
                        'indice': len(lineas_procesadas),
                        'codigo': codigo,
                        'unidad': unidad,
                        'descripcion': descripcion,
                        'linea_original': linea
                    })
                    lineas_procesadas.append(linea)
                    logger.debug(f"  ⏳ Partida pendiente: {codigo} (esperando números)")

                continue

            # 4. Procesar partidas pendientes si encontramos números antes de esta línea
            while partidas_pendientes and numeros_pendientes:
                partida = partidas_pendientes.pop(0)
                datos = numeros_pendientes.pop(0)

                # Reemplazar la línea original con la versión fusionada
                linea_fusionada = f"{partida['codigo']} {partida['unidad']} {partida['descripcion']} {datos['cantidad']} {datos['precio']} {datos['importe']}"
                lineas_procesadas[partida['indice']] = linea_fusionada
                logger.debug(f"  ✅ Fusionada pendiente: {partida['codigo']} con números {datos['cantidad']} {datos['precio']} {datos['importe']}")

            # 5. Si no es ninguno de los casos anteriores, añadir la línea normal
            lineas_procesadas.append(linea)

        # Al final, procesar cualquier partida o números pendientes
        while partidas_pendientes and numeros_pendientes:
            partida = partidas_pendientes.pop(0)
            datos = numeros_pendientes.pop(0)

            linea_fusionada = f"{partida['codigo']} {partida['unidad']} {partida['descripcion']} {datos['cantidad']} {datos['precio']} {datos['importe']}"
            lineas_procesadas[partida['indice']] = linea_fusionada
            logger.debug(f"  ✅ Fusionada final: {partida['codigo']} con números {datos['cantidad']} {datos['precio']} {datos['importe']}")

        # Advertir si quedaron pendientes sin procesar
        if partidas_pendientes:
            logger.warning(f"  ⚠️  {len(partidas_pendientes)} partidas sin datos numéricos: {[p['codigo'] for p in partidas_pendientes]}")

        if numeros_pendientes:
            logger.warning(f"  ⚠️  {len(numeros_pendientes)} conjuntos de números sin partida asociada")

        return lineas_procesadas

    def _filtrar_pies_pagina(self, lineas: List[str]) -> List[str]:
        """
        Filtra líneas de pie de página que contienen solo números de paginación.

        Detecta patrones comunes de paginación como:
        - Número solo: "1", "23", "89"
        - Número con espacios: "  23  "
        - Formatos: "Página 1", "Pág. 23", "- 5 -", etc.
        - Formato con fecha: "8 de mayo de 2024 Página 1"

        Args:
            lineas: Lista de líneas de texto extraídas

        Returns:
            Lista de líneas filtradas sin pies de página
        """
        import re

        # Patrones comunes de paginación en pies de página
        patrones_paginacion = [
            r'^\s*\d+\s*$',                    # Solo número: "23"
            r'^\s*-\s*\d+\s*-\s*$',            # Con guiones: "- 23 -"
            r'^\s*página\s+\d+\s*$',           # "Página 23" (case insensitive)
            r'^\s*pág\.?\s+\d+\s*$',           # "Pág. 23" o "Pag 23"
            r'^\s*page\s+\d+\s*$',             # "Page 23"
            r'^\s*p\.\s*\d+\s*$',              # "P. 23"
            r'^\s*\d+\s*/\s*\d+\s*$',          # "23 / 89" (página X de Y)
            r'^\s*\[\s*\d+\s*\]\s*$',          # "[23]"
            r'^\s*\d+\s+de\s+\w+\s+de\s+\d{4}\s+página\s+\d+\s*$',  # "8 de mayo de 2024 Página 1"
            r'^\s*\d+\s+de\s+\w+\s+de\s+\d{4}\s*$',  # "8 de mayo de 2024" (fecha sola)
        ]

        # Compilar patrones (case insensitive)
        patrones_compilados = [re.compile(p, re.IGNORECASE) for p in patrones_paginacion]

        lineas_filtradas = []

        for linea in lineas:
            linea_limpia = linea.strip()

            # Verificar si coincide con algún patrón de paginación
            es_pie_pagina = False
            for patron in patrones_compilados:
                if patron.match(linea_limpia):
                    es_pie_pagina = True
                    logger.debug(f"Pie de página detectado y eliminado: '{linea_limpia}'")
                    break

            # Solo añadir la línea si NO es pie de página
            if not es_pie_pagina:
                lineas_filtradas.append(linea)

        return lineas_filtradas

    def _reordenar_totales_partida_tras_salto_pagina(self, lineas: List[str]) -> List[str]:
        """
        Reordena totales de partida que aparecen DESPUÉS del TOTAL CAPÍTULO debido a saltos de página.

        Problema: En algunos PDFs, cuando hay un salto de página justo antes del TOTAL CAPÍTULO,
        los totales de la última partida (CANTIDAD PRECIO IMPORTE) aparecen DESPUÉS de la línea
        TOTAL CAPÍTULO debido a cómo se extraen las columnas.

        Ejemplo ANTES:
            Solera Edificación instalaciones 1 28,00 0,10 2,80   (última medición)
            PRESUPUESTO Y MEDICIONES                              (cabecera de página)
            TOTAL CAPÍTULO 02 CIMENTACIONES...................   (TOTAL sin importe)
            ANCHURA ALTURA PARCIALES CANTIDAD PRECIO IMPORTE     (cabecera fragmentada)
            44,83 20,92 937,84                                   (totales de última partida)
            ......... 12.050,55                                  (importe del capítulo)

        Ejemplo DESPUÉS:
            Solera Edificación instalaciones 1 28,00 0,10 2,80
            PRESUPUESTO Y MEDICIONES
            44,83 20,92 937,84                                   (movido ANTES del TOTAL)
            TOTAL CAPÍTULO 02 CIMENTACIONES................... 12.050,55 (fusionado)

        Args:
            lineas: Lista de líneas de texto

        Returns:
            Lista de líneas reordenadas
        """
        import re

        # Patrón para línea TOTAL CAPÍTULO/SUBCAPÍTULO sin importe
        patron_total_sin_importe = re.compile(
            r'^TOTAL\s+(SUBCAPÍTULO|CAPÍTULO|APARTADO)\s+([A-Z]?\d{1,2}(?:\.\d{1,2})*)\s+',
            re.IGNORECASE
        )

        # Patrón para línea con solo 3 números (totales de partida: cantidad, precio, importe)
        patron_tres_numeros = re.compile(
            r'^\s*(\d{1,3}(?:\.\d{3})*,\d{1,4})\s+(\d{1,3}(?:\.\d{3})*,\d{1,4})\s+(\d{1,3}(?:\.\d{3})*,\d{1,4})\s*$'
        )

        # Patrón para líneas que son basura (cabeceras fragmentadas)
        patron_basura = re.compile(
            r'^(ANCHURA|ALTURA|PARCIALES|CANTIDAD|PRECIO|IMPORTE|UDS|LONGITUD|CÓDIGO|RESUMEN|'
            r'PRESUPUESTO|CÓDIGO\s+RESUMEN)',
            re.IGNORECASE
        )

        lineas_procesadas = []
        i = 0

        while i < len(lineas):
            linea = lineas[i].strip()

            # Buscar línea TOTAL sin importe al final
            if patron_total_sin_importe.match(linea) and not re.search(r'\d{1,3}(?:\.\d{3})*,\d{2}\s*$', linea):
                # Encontramos un TOTAL sin importe, buscar si hay totales de partida después
                posicion_total = i
                totales_partida_linea = None
                totales_partida_idx = None

                # Buscar en las siguientes líneas (hasta 8)
                for j in range(i + 1, min(i + 8, len(lineas))):
                    linea_siguiente = lineas[j].strip()

                    # Saltar líneas vacías y basura
                    if not linea_siguiente or patron_basura.match(linea_siguiente):
                        continue

                    # ¿Es línea con 3 números (totales de partida)?
                    if patron_tres_numeros.match(linea_siguiente):
                        totales_partida_linea = linea_siguiente
                        totales_partida_idx = j
                        logger.info(f"🔄 Detectados totales de partida desplazados: '{totales_partida_linea}' (posición {j})")
                        break

                    # Si encontramos línea con puntos + importe, es el importe del TOTAL, no buscar más
                    if re.match(r'^\.{10,}', linea_siguiente):
                        break

                # Si encontramos totales de partida desplazados, reordenar
                if totales_partida_linea and totales_partida_idx:
                    # Añadir los totales de partida ANTES del TOTAL
                    lineas_procesadas.append(totales_partida_linea)
                    logger.info(f"🔄 Totales de partida movidos antes de TOTAL: '{totales_partida_linea}'")

                    # Añadir las líneas intermedias (excluyendo los totales que ya añadimos)
                    for k in range(i, totales_partida_idx):
                        if k != totales_partida_idx:  # Ya añadimos los totales
                            lineas_procesadas.append(lineas[k])

                    # Continuar desde después de los totales
                    i = totales_partida_idx + 1
                    continue

            # Si no es caso especial, añadir línea normal
            lineas_procesadas.append(lineas[i])
            i += 1

        return lineas_procesadas

    def _fusionar_totales_fragmentados(self, lineas: List[str]) -> List[str]:
        """
        Fusiona líneas TOTAL que están fragmentadas (importe en línea separada).

        Problema detectado: En algunos PDFs, las líneas TOTAL se extraen así:
            TOTAL CAPÍTULO 02 CIMENTACIONES...................
            ANCHURA ALTURA PARCIALES CANTIDAD PRECIO IMPORTE  (cabecera fragmentada)
            44,83 20,92 937,84
            ............................................................................................... 12.050,55

        Este método detecta estas situaciones y fusiona la línea TOTAL con su importe.

        Estrategia:
        1. Detectar líneas que empiezan con "TOTAL CAPÍTULO" o "TOTAL SUBCAPÍTULO" sin importe al final
        2. Buscar en las siguientes líneas (hasta 10) una que tenga puntos suspensivos + importe
        3. Fusionar ambas líneas
        4. Eliminar las líneas intermedias que son basura (cabeceras fragmentadas, etc.)

        Args:
            lineas: Lista de líneas de texto

        Returns:
            Lista de líneas con TOTALES fusionados
        """
        import re

        # Patrón para línea TOTAL sin importe al final
        # Ejemplo: "TOTAL CAPÍTULO 02 CIMENTACIONES..................."
        patron_total_sin_importe = re.compile(
            r'^TOTAL\s+(SUBCAPÍTULO|CAPÍTULO|APARTADO)?\s*([A-Z]?\d{1,2}(?:\.\d{1,2})*)\s+([A-ZÁÉÍÓÚÑ][^0-9]*?)\.{3,}\s*$',
            re.IGNORECASE
        )

        # Patrón alternativo: TOTAL sin tipo pero con código
        # Ejemplo: "TOTAL 02 CIMENTACIONES..................."
        patron_total_simple_sin_importe = re.compile(
            r'^TOTAL\s+(\d{1,2}(?:\.\d{1,2})*)\s+([A-ZÁÉÍÓÚÑ][^0-9]*?)\.{3,}\s*$',
            re.IGNORECASE
        )

        # Patrón para línea con puntos suspensivos + importe
        # Ejemplo: "............................................................................................... 12.050,55"
        patron_puntos_importe = re.compile(
            r'^\.{10,}\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$'
        )

        # Patrón para líneas que son basura (cabeceras fragmentadas, números sueltos, paginación)
        # Estas líneas se saltan al buscar el importe de un TOTAL fragmentado
        patron_basura = re.compile(
            r'^(ANCHURA|ALTURA|PARCIALES|CANTIDAD|PRECIO|IMPORTE|UDS|LONGITUD|CÓDIGO|RESUMEN|'
            r'PRESUPUESTO\s+Y\s+MEDICIONES|PRESUPUESTO|'  # Cabeceras de página
            r'Página\s+\d+|Pág\.?\s+\d+|'  # Paginación
            r'\d+,\d+\s+\d+,\d+\s+\d+,\d+|'  # Tres números separados (mediciones)
            r'[\d.,\s]+)$',  # Solo números y separadores
            re.IGNORECASE
        )

        # Patrón adicional para líneas que empiezan con palabras de cabecera
        patron_cabecera_fragmentada = re.compile(
            r'^(CÓDIGO\s+RESUMEN|ANCHURA\s+ALTURA|UDS\s+LONGITUD)',
            re.IGNORECASE
        )

        lineas_procesadas = []
        i = 0

        while i < len(lineas):
            linea = lineas[i].strip()

            # Verificar si es una línea TOTAL sin importe
            match_total = patron_total_sin_importe.match(linea)
            if not match_total:
                match_total = patron_total_simple_sin_importe.match(linea)

            if match_total:
                # Buscar el importe en las siguientes líneas
                importe_encontrado = None
                lineas_a_saltar = 0

                for j in range(i + 1, min(i + 10, len(lineas))):
                    linea_siguiente = lineas[j].strip()

                    # ¿Es línea con puntos + importe?
                    match_importe = patron_puntos_importe.match(linea_siguiente)
                    if match_importe:
                        importe_encontrado = match_importe.group(1)
                        lineas_a_saltar = j - i
                        break

                    # ¿Es basura que debemos saltar?
                    if (patron_basura.match(linea_siguiente) or
                        patron_cabecera_fragmentada.match(linea_siguiente) or
                        not linea_siguiente):
                        continue

                    # Si encontramos otra línea significativa (no basura), dejamos de buscar
                    # para evitar fusiones incorrectas
                    if linea_siguiente.startswith('TOTAL') or re.match(r'^\d{1,2}(?:\.\d{1,2})*\s+', linea_siguiente):
                        break

                if importe_encontrado:
                    # Fusionar: TOTAL ... + importe
                    linea_fusionada = linea.rstrip('.') + ' ' + importe_encontrado
                    lineas_procesadas.append(linea_fusionada)
                    logger.info(f"🔗 TOTAL fusionado: '{linea[:50]}...' + '{importe_encontrado}'")

                    # Saltar las líneas intermedias (basura + línea con importe)
                    i += lineas_a_saltar + 1
                    continue
                else:
                    # No encontramos importe, añadir línea tal cual
                    # ADVERTENCIA: El TOTAL no tiene importe - posible problema de extracción de PDF
                    logger.warning(f"⚠️ TOTAL sin importe detectado: '{linea[:80]}...' - El importe puede estar en una columna no extraída del PDF")
                    lineas_procesadas.append(lineas[i])
            else:
                # No es línea TOTAL fragmentada, añadir tal cual
                lineas_procesadas.append(lineas[i])

            i += 1

        return lineas_procesadas

    def _extraer_pagina(self, page, num_pagina: int) -> Dict:
        """
        Extrae el contenido de una página individual con detección de columnas

        Args:
            page: objeto página de pdfplumber
            num_pagina: número de página

        Returns:
            dict con texto, líneas y layout de la página
        """
        # Si la detección de columnas está desactivada, usar método simple
        if not self.detect_columns or not self.column_detector:
            # MEJORA: Usar layout=True para preservar mejor las columnas tabulares anchas
            texto = page.extract_text(layout=True, x_tolerance=3, y_tolerance=3)
            if not texto:
                return {'num': num_pagina, 'text': '', 'lines': [], 'layout': None}

            lineas = [linea.strip() for linea in texto.split('\n')]
            lineas = [l for l in lineas if l]

            return {
                'num': num_pagina,
                'text': texto,
                'lines': lineas,
                'layout': None
            }

        # Extraer palabras con posiciones para analizar layout
        words = page.extract_words()

        if not words:
            return {
                'num': num_pagina,
                'text': '',
                'lines': [],
                'layout': {'num_columnas': 0, 'tipo': 'vacio'}
            }

        # Analizar layout de la página
        layout_info = self.column_detector.analizar_layout(words)
        num_columnas = layout_info.get('num_columnas', 1)

        # VALIDACIÓN ESPECIAL: Detectar si es una página de presupuesto con tabla (no multicolumna real)
        # Las páginas de presupuesto tienen headers como "CÓDIGO RESUMEN CANTIDAD PRECIO IMPORTE"
        # y deben procesarse con extract_text() estándar, NO con extracción por bbox
        es_pagina_presupuesto = False
        if num_columnas > 1:
            # Extraer texto preliminar para verificar (usar layout=True para mejor detección)
            texto_preliminar = page.extract_text(layout=True, x_tolerance=3, y_tolerance=3)
            if texto_preliminar:
                lineas_preliminar = texto_preliminar.split('\n')
                for linea in lineas_preliminar[:10]:  # Revisar primeras 10 líneas
                    # Buscar header de tabla de presupuesto
                    if any(keyword in linea for keyword in [
                        'CÓDIGO RESUMEN CANTIDAD PRECIO IMPORTE',
                        'CODIGO RESUMEN CANTIDAD PRECIO IMPORTE',
                        'CAPÍTULO C',
                        'CAPITULO C',
                        'SUBCAPÍTULO',
                        'SUBCAPITULO'
                    ]):
                        es_pagina_presupuesto = True
                        logger.info(f"  Página {num_pagina}: Detectada como página de PRESUPUESTO (usando extract_text estándar)")
                        break

        # ESTRATEGIA 1: Columna simple O página de presupuesto - Usar método original (extract_text)
        # Más rápido y preserva mejor el orden original del PDF
        if num_columnas == 1 or es_pagina_presupuesto:
            # MEJORA: Usar layout=True para preservar mejor las columnas tabulares anchas
            # Esto ayuda cuando hay columnas de importes alineadas a la derecha que están lejos del texto principal
            texto = page.extract_text(layout=True, x_tolerance=3, y_tolerance=3)
            if not texto:
                lineas = []
            else:
                lineas = [linea.strip() for linea in texto.split('\n')]
                lineas = [l for l in lineas if l]

            return {
                'num': num_pagina,
                'text': texto or '',
                'lines': lineas,
                'layout': layout_info if not es_pagina_presupuesto else {'num_columnas': 1, 'tipo': 'presupuesto'}
            }

        # ESTRATEGIA 2: Múltiples columnas REALES - Dividir página físicamente y extraer cada columna
        # Necesario para preservar el orden correcto en PDFs con columnas
        else:
            logger.info(
                f"  Página {num_pagina}: {num_columnas} columnas detectadas "
                f"({layout_info['orientacion']}) - usando extracción por bbox"
            )

            # Obtener dimensiones de la página
            page_width = page.width
            page_height = page.height

            # Extraer cada columna dividiendo la página físicamente
            all_column_lines = []
            for i, col_info in enumerate(layout_info['columnas']):
                # Usar los rangos X detectados, pero asegurar que cubrimos toda la altura
                x_min = col_info['x_min']
                x_max = col_info['x_max']

                # Definir bounding box para esta columna
                bbox = (x_min, 0, x_max, page_height)

                # Extraer texto de esta región
                col_crop = page.within_bbox(bbox)
                col_text = col_crop.extract_text()

                if col_text:
                    col_lines = [l.strip() for l in col_text.split('\n') if l.strip()]
                    all_column_lines.extend(col_lines)
                    logger.debug(f"    Columna {i+1}: {len(col_lines)} líneas")

            return {
                'num': num_pagina,
                'text': '\n'.join(all_column_lines),
                'lines': all_column_lines,
                'layout': layout_info
            }

    def extraer_lineas(self) -> List[str]:
        """
        Extrae solo las líneas de texto del PDF

        Returns:
            lista de strings con cada línea
        """
        datos = self.extraer_todo()
        return datos['all_lines']

    def extraer_tablas(self) -> List[Dict]:
        """
        Extrae tablas detectadas en el PDF

        Returns:
            lista de tablas (cada tabla es lista de listas)
        """
        tablas = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for i, page in enumerate(pdf.pages, start=1):
                    page_tables = page.extract_tables()
                    if page_tables:
                        for j, tabla in enumerate(page_tables):
                            tablas.append({
                                'pagina': i,
                                'tabla_num': j + 1,
                                'data': tabla
                            })

                logger.info(f"✓ Extraídas {len(tablas)} tablas")

        except Exception as e:
            logger.error(f"Error extrayendo tablas: {e}")

        return tablas

    def extraer_con_posiciones(self) -> List[Dict]:
        """
        Extrae texto con información de posición (x, y)
        Útil para detectar columnas de números

        Returns:
            lista de diccionarios con texto y coordenadas
        """
        elementos = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    # Extraer palabras con posiciones
                    words = page.extract_words()

                    for word in words:
                        elementos.append({
                            'pagina': page_num,
                            'texto': word['text'],
                            'x0': word['x0'],
                            'y0': word['top'],
                            'x1': word['x1'],
                            'y1': word['bottom'],
                            'width': word['x1'] - word['x0'],
                            'height': word['bottom'] - word['top']
                        })

                logger.info(f"✓ Extraídos {len(elementos)} elementos con posición")

        except Exception as e:
            logger.error(f"Error extrayendo posiciones: {e}")

        return elementos

    def guardar_texto(self, output_path: str) -> None:
        """
        Guarda el texto extraído en un archivo .txt

        Args:
            output_path: ruta del archivo de salida
        """
        datos = self.extraer_todo()

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(datos['all_text'])

        logger.info(f"✓ Texto guardado en {output_path}")


def extraer_pdf(pdf_path: str, output_txt: Optional[str] = None) -> Dict:
    """
    Función helper para extraer rápidamente un PDF

    Args:
        pdf_path: ruta al PDF
        output_txt: ruta opcional para guardar texto

    Returns:
        dict con todos los datos extraídos
    """
    extractor = PDFExtractor(pdf_path)
    datos = extractor.extraer_todo()

    if output_txt:
        extractor.guardar_texto(output_txt)

    return datos


if __name__ == "__main__":
    # Test con el PDF de ejemplo
    pdf_ejemplo = "ejemplo/PROYECTO CALYPOFADO_extract.pdf"

    if Path(pdf_ejemplo).exists():
        print(f"Extrayendo {pdf_ejemplo}...")

        extractor = PDFExtractor(pdf_ejemplo)
        datos = extractor.extraer_todo()

        print(f"\n📄 Archivo: {datos['metadata']['archivo']}")
        print(f"📑 Páginas: {datos['metadata']['num_paginas']}")
        print(f"📝 Líneas totales: {len(datos['all_lines'])}")
        print(f"\n--- Primeras 10 líneas ---")
        for i, linea in enumerate(datos['all_lines'][:10], 1):
            print(f"{i:3d}: {linea}")

        # Guardar texto
        extractor.guardar_texto('data/ejemplo_extraido.txt')
        print("\n✓ Texto guardado en data/ejemplo_extraido.txt")
    else:
        print(f"❌ No se encuentra el archivo {pdf_ejemplo}")
