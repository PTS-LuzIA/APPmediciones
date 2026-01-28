"""
Clase base abstracta para todos los parsers V2
Define la interfaz común que deben implementar todos los parsers especializados
"""

from abc import ABC, abstractmethod
from typing import Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BaseParserV2(ABC):
    """
    Clase base abstracta para parsers V2

    Todos los parsers especializados deben heredar de esta clase
    e implementar el método parsear()
    """

    def __init__(self, pdf_path: str, user_id: int, proyecto_id: int):
        """
        Args:
            pdf_path: Ruta al archivo PDF a parsear
            user_id: ID del usuario (REQUERIDO para nombres de archivos de log)
            proyecto_id: ID del proyecto (REQUERIDO para nombres de archivos de log)
        """
        self.pdf_path = Path(pdf_path)
        self.pdf_name = self.pdf_path.stem
        self.user_id = user_id
        self.proyecto_id = proyecto_id

        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    @abstractmethod
    def parsear(self) -> Dict:
        """
        Método principal de parseo (debe ser implementado por subclases)

        Returns:
            Dict con estructura:
            {
                'estructura': {...},      # Jerarquía de capítulos/subcapítulos/partidas
                'metadata': {...},        # Información del documento
                'estadisticas': {...}     # Resumen de resultados
            }
        """
        pass

    def get_tipo(self) -> str:
        """
        Retorna el tipo de parser

        Returns:
            str: Identificador del tipo (ej: "TIPO_2_FINAL_SIMPLE")
        """
        return self.__class__.__name__

    def __repr__(self):
        return f"{self.__class__.__name__}(pdf='{self.pdf_name}')"
