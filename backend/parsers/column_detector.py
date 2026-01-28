"""
Detector de columnas en PDFs
Analiza el layout de palabras para detectar estructuras multicolumna
"""

import logging
from typing import List, Dict
from collections import defaultdict

logger = logging.getLogger(__name__)


class ColumnDetector:
    """Detecta layouts de múltiples columnas en páginas PDF"""

    def __init__(self, threshold: float = 0.3):
        """
        Args:
            threshold: Umbral para detectar separación entre columnas (0-1)
        """
        self.threshold = threshold

    def analizar_layout(self, words: List[Dict]) -> Dict:
        """
        Analiza el layout de una página basándose en posiciones de palabras

        Args:
            words: Lista de palabras extraídas con posiciones (de pdfplumber)
                   Cada palabra tiene: text, x0, x1, top, bottom

        Returns:
            dict con información del layout:
            {
                'num_columnas': int,
                'tipo': str,  # 'simple', 'multicolumna'
                'orientacion': str,  # 'vertical', 'horizontal'
                'columnas': [{'x_min': float, 'x_max': float, 'palabras': int}, ...]
            }
        """
        if not words:
            return {
                'num_columnas': 0,
                'tipo': 'vacio',
                'orientacion': None,
                'columnas': []
            }

        # Agrupar palabras por posición X (detectar columnas verticales)
        x_positions = [word['x0'] for word in words]

        # Si hay muy pocas palabras, es columna simple
        if len(x_positions) < 10:
            return {
                'num_columnas': 1,
                'tipo': 'simple',
                'orientacion': 'vertical',
                'columnas': [{
                    'x_min': min(x_positions),
                    'x_max': max(x_positions),
                    'palabras': len(words)
                }]
            }

        # Calcular distribución de palabras en el eje X
        x_min = min(x_positions)
        x_max = max(x_positions)
        x_range = x_max - x_min

        if x_range < 100:  # Muy estrecho, columna simple
            return {
                'num_columnas': 1,
                'tipo': 'simple',
                'orientacion': 'vertical',
                'columnas': [{
                    'x_min': x_min,
                    'x_max': x_max,
                    'palabras': len(words)
                }]
            }

        # Dividir el espacio en bins para detectar gaps
        num_bins = 20
        bin_width = x_range / num_bins
        bins = defaultdict(int)

        for x in x_positions:
            bin_idx = int((x - x_min) / bin_width)
            if bin_idx >= num_bins:
                bin_idx = num_bins - 1
            bins[bin_idx] += 1

        # Buscar gaps significativos (bins con pocas palabras)
        avg_density = len(words) / num_bins
        gap_threshold = avg_density * self.threshold

        gaps = []
        for i in range(num_bins):
            if bins[i] < gap_threshold:
                gaps.append(i)

        # Agrupar gaps consecutivos
        gap_groups = []
        if gaps:
            current_group = [gaps[0]]
            for gap in gaps[1:]:
                if gap == current_group[-1] + 1:
                    current_group.append(gap)
                else:
                    gap_groups.append(current_group)
                    current_group = [gap]
            gap_groups.append(current_group)

        # Determinar número de columnas basándose en gaps significativos
        num_columnas = len(gap_groups) + 1 if gap_groups else 1

        # Si solo detectamos 1 columna, retornar layout simple
        if num_columnas == 1:
            return {
                'num_columnas': 1,
                'tipo': 'simple',
                'orientacion': 'vertical',
                'columnas': [{
                    'x_min': x_min,
                    'x_max': x_max,
                    'palabras': len(words)
                }]
            }

        # Crear información de columnas
        columnas = []
        col_boundaries = [x_min]

        for gap_group in gap_groups:
            gap_center = (gap_group[0] + gap_group[-1]) / 2
            boundary_x = x_min + (gap_center * bin_width)
            col_boundaries.append(boundary_x)

        col_boundaries.append(x_max)

        # Contar palabras en cada columna
        for i in range(len(col_boundaries) - 1):
            col_x_min = col_boundaries[i]
            col_x_max = col_boundaries[i + 1]

            palabras_en_col = sum(
                1 for word in words
                if col_x_min <= word['x0'] < col_x_max
            )

            columnas.append({
                'x_min': col_x_min,
                'x_max': col_x_max,
                'palabras': palabras_en_col
            })

        return {
            'num_columnas': num_columnas,
            'tipo': 'multicolumna' if num_columnas > 1 else 'simple',
            'orientacion': 'vertical',
            'columnas': columnas
        }
