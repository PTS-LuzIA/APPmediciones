"""
Proyecto Service - Lógica de negocio para proyectos
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from database.manager import DatabaseManager
from models import Proyecto

logger = logging.getLogger(__name__)


class ProyectoService:
    """
    Servicio para gestionar proyectos.

    Proporciona lógica de negocio sobre los proyectos.
    """

    def __init__(self, db: Session):
        self.db = db
        self.manager = DatabaseManager(db)

    def crear_proyecto_completo(
        self,
        usuario_id: int,
        nombre: str,
        descripcion: str = None,
        pdf_path: str = None
    ) -> Proyecto:
        """
        Crea un proyecto completo con su estructura inicial.

        Args:
            usuario_id: ID del usuario propietario
            nombre: Nombre del proyecto
            descripcion: Descripción opcional
            pdf_path: Ruta al PDF opcional

        Returns:
            Proyecto creado
        """
        # Crear proyecto
        proyecto = self.manager.crear_proyecto(usuario_id, nombre, descripcion)

        # Actualizar PDF si se proporciona
        if pdf_path:
            proyecto.pdf_path = pdf_path
            proyecto.pdf_nombre = Path(pdf_path).name
            self.db.commit()

        logger.info(f"✓ Proyecto completo creado: {proyecto.id} - {nombre}")
        return proyecto

    def obtener_proyecto_completo(self, proyecto_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene un proyecto con toda su información.

        Returns:
            {
                'proyecto': Proyecto,
                'arbol': [],
                'estadisticas': {}
            }
        """
        proyecto = self.manager.obtener_proyecto(proyecto_id)
        if not proyecto:
            return None

        # Obtener árbol completo
        arbol = self.manager.obtener_arbol_completo(proyecto_id)

        # Obtener estadísticas
        estadisticas = self.manager.queries.obtener_estadisticas_proyecto(proyecto_id)

        return {
            'proyecto': proyecto,
            'arbol': arbol,
            'estadisticas': estadisticas
        }

    def validar_integridad_proyecto(self, proyecto_id: int) -> Dict[str, Any]:
        """
        Valida la integridad de un proyecto.

        Returns:
            {
                'valido': bool,
                'problemas': []
            }
        """
        problemas = self.manager.queries.verificar_integridad_arbol(proyecto_id)

        return {
            'valido': len(problemas) == 0,
            'problemas': problemas,
            'num_problemas': len(problemas)
        }
