"""
Normalizador de datos extraídos.
Convierte strings a números, limpia textos, maneja formatos españoles.
"""

import re
import logging
from typing import Optional, Union

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Normalizer:
    """Normaliza datos de mediciones"""

    @staticmethod
    def limpiar_numero_espanol(texto: str) -> Optional[float]:
        """
        Convierte números en formato español a float

        Ejemplos:
            "1.605,90" -> 1605.90
            "630,00" -> 630.0
            "14,24" -> 14.24

        Args:
            texto: string con número en formato español

        Returns:
            float o None si no se puede convertir
        """
        if not texto:
            return None

        try:
            # Eliminar espacios
            texto = texto.strip()

            # Reemplazar punto (separador de miles) por nada
            texto = texto.replace('.', '')

            # Reemplazar coma (decimal) por punto
            texto = texto.replace(',', '.')

            return float(texto)

        except (ValueError, AttributeError):
            logger.warning(f"No se pudo convertir '{texto}' a número")
            return None

    @staticmethod
    def extraer_numeros_linea(linea: str) -> list:
        """
        Extrae todos los números de una línea

        Args:
            linea: string con posibles números

        Returns:
            lista de floats
        """
        # Patrón para números españoles: 1.234,56 o 234,56
        patron = r'\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+,\d+|\d+'

        matches = re.findall(patron, linea)
        numeros = []

        for match in matches:
            num = Normalizer.limpiar_numero_espanol(match)
            if num is not None:
                numeros.append(num)

        return numeros

    @staticmethod
    def extraer_tres_numeros_finales(linea: str) -> tuple:
        """
        Extrae los últimos 3 números de una línea (cantidad, precio, importe)

        Args:
            linea: string que termina con números

        Returns:
            tuple (cantidad, precio, importe) o (None, None, None)
        """
        numeros = Normalizer.extraer_numeros_linea(linea)

        if len(numeros) >= 3:
            # Los últimos 3 números
            return (numeros[-3], numeros[-2], numeros[-1])

        return (None, None, None)

    @staticmethod
    def limpiar_texto(texto: str) -> str:
        """
        Limpia y normaliza texto de descripciones

        Args:
            texto: string a limpiar

        Returns:
            string limpio
        """
        if not texto:
            return ""

        # Eliminar espacios múltiples
        texto = re.sub(r'\s+', ' ', texto)

        # Eliminar guiones finales de línea partida
        texto = texto.replace('- ', '')

        # Strip general
        texto = texto.strip()

        return texto

    @staticmethod
    def normalizar_unidad(unidad: str) -> str:
        """
        Normaliza unidades de medida

        Args:
            unidad: string con unidad (m, m2, Ud, etc.)

        Returns:
            unidad normalizada
        """
        if not unidad:
            return ""

        unidad = unidad.strip()

        # Normalizar variaciones de PA (Partida Alzada)
        # P:A:, P.A., P:A, p.a. -> PA
        if re.match(r'^[Pp][\.:]+[Aa][\.:]*$', unidad):
            return 'PA'

        unidad_lower = unidad.lower()

        # Mapeo de variaciones
        mapeo = {
            'ud': 'Ud',
            'u': 'Ud',
            'ml': 'm',
            'm.': 'm',
            'm2': 'm²',
            'm3': 'm³',
            'pa': 'PA',
        }

        return mapeo.get(unidad_lower, unidad.capitalize())

    @staticmethod
    def validar_importe(cantidad: float, precio: float, importe: float, tolerancia: float = 0.05) -> bool:
        """
        Valida que cantidad × precio ≈ importe

        Args:
            cantidad: cantidad
            precio: precio unitario
            importe: importe total
            tolerancia: margen de error permitido

        Returns:
            True si la validación pasa
        """
        if cantidad is None or precio is None or importe is None:
            return False

        calculado = round(cantidad * precio, 2)
        diferencia = abs(calculado - importe)

        return diferencia <= tolerancia

    @staticmethod
    def reconstruir_descripcion(lineas: list) -> str:
        """
        Une múltiples líneas de descripción en una sola

        Args:
            lineas: lista de strings

        Returns:
            descripción completa limpia
        """
        # Unir líneas
        descripcion = ' '.join(lineas)

        # Limpiar
        descripcion = Normalizer.limpiar_texto(descripcion)

        return descripcion
