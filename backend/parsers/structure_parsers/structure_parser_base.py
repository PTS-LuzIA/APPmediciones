"""
Clase base abstracta para parsers de estructura (FASE 1).

Define la interfaz común que todos los parsers de estructura deben implementar.
"""
import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class StructureParserBase(ABC):
    """
    Clase base abstracta para parsers de estructura jerárquica.

    Responsabilidades:
    - Extraer capítulos y subcapítulos
    - Detectar líneas TOTAL y asignar importes
    - Calcular totales faltantes
    - NO extraer partidas individuales (eso es FASE 2)
    """

    def __init__(self):
        self.estructura = {'capitulos': []}
        self.capitulo_actual = None
        self.ultimo_codigo = None
        self.mapa_nodos = {}

    @abstractmethod
    def parsear(self, lineas: List[str]) -> Dict:
        """
        Parsea las líneas y extrae la estructura jerárquica.

        Args:
            lineas: Lista de strings del PDF

        Returns:
            Dict con estructura jerárquica
        """
        pass

    def _procesar_capitulo(self, codigo: str, nombre: str):
        """Procesa un capítulo principal"""
        logger.debug(f"  📁 Capítulo: {codigo} - {nombre}")

        capitulo = {
            'codigo': codigo,
            'nombre': nombre,
            'subcapitulos': [],
            'total': None,
            'orden': len(self.estructura['capitulos'])
        }

        self.estructura['capitulos'].append(capitulo)
        self.capitulo_actual = capitulo
        self.ultimo_codigo = codigo
        self.mapa_nodos[codigo] = capitulo

    def _procesar_subcapitulo(self, codigo: str, nombre: str):
        """
        Procesa un subcapítulo de cualquier nivel.
        Crea automáticamente niveles intermedios si faltan.
        """
        if not self.capitulo_actual:
            logger.warning(f"⚠️  Subcapítulo {codigo} sin capítulo padre - ignorado")
            return

        logger.debug(f"  📂 Subcapítulo: {codigo} - {nombre}")

        # Asegurar que todos los niveles padres existen
        self._asegurar_niveles_intermedios(codigo)

        # Crear el nuevo subcapítulo
        nuevo_sub = {
            'codigo': codigo,
            'nombre': nombre,
            'subcapitulos': [],
            'total': None,
            'orden': 0
        }

        # Determinar dónde agregarlo según el nivel
        partes = codigo.split('.')

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
                nuevo_sub['orden'] = len(self.capitulo_actual['subcapitulos'])
                self.capitulo_actual['subcapitulos'].append(nuevo_sub)

        # Registrar en el mapa
        self.mapa_nodos[codigo] = nuevo_sub
        self.ultimo_codigo = codigo

    def _asegurar_niveles_intermedios(self, codigo: str):
        """Asegura que todos los niveles padres existen"""
        partes = codigo.split('.')

        for i in range(2, len(partes)):
            codigo_intermedio = '.'.join(partes[:i])

            if codigo_intermedio not in self.mapa_nodos:
                logger.info(f"  🔧 Creando nivel intermedio: {codigo_intermedio}")

                nombre_generico = f"SUBCAPÍTULO {codigo_intermedio}"

                nuevo_nivel = {
                    'codigo': codigo_intermedio,
                    'nombre': nombre_generico,
                    'subcapitulos': [],
                    'total': None,
                    'orden': 0,
                    '_generado': True
                }

                if i == 2:
                    nuevo_nivel['orden'] = len(self.capitulo_actual['subcapitulos'])
                    self.capitulo_actual['subcapitulos'].append(nuevo_nivel)
                else:
                    codigo_padre = '.'.join(partes[:i-1])
                    if codigo_padre in self.mapa_nodos:
                        padre = self.mapa_nodos[codigo_padre]
                        nuevo_nivel['orden'] = len(padre['subcapitulos'])
                        padre['subcapitulos'].append(nuevo_nivel)

                self.mapa_nodos[codigo_intermedio] = nuevo_nivel

    def _procesar_total(self, total_str: str, codigo_explicito: Optional[str] = None, tipo: Optional[str] = None):
        """Procesa una línea TOTAL y la asigna al código correspondiente"""
        codigo_target = codigo_explicito if codigo_explicito else self.ultimo_codigo

        if not codigo_target:
            logger.warning(f"⚠️  TOTAL encontrado pero no hay código")
            return

        # Limpiar y convertir a número
        total_limpio = total_str.replace('.', '').replace(',', '.')
        try:
            total = float(total_limpio)
        except ValueError:
            logger.warning(f"⚠️  No se pudo convertir total: {total_str}")
            return

        # Si el nodo no existe y es un SUBCAPÍTULO, crearlo
        if codigo_target not in self.mapa_nodos:
            if tipo and tipo in ['SUBCAPÍTULO', 'APARTADO'] and '.' in codigo_target:
                logger.info(f"  🔧 Creando subcapítulo desde TOTAL: {codigo_target}")
                self._procesar_subcapitulo(codigo_target, f"{tipo} {codigo_target}")

        # Asignar al nodo
        if codigo_target in self.mapa_nodos:
            nodo = self.mapa_nodos[codigo_target]
            nodo['total'] = total
            logger.debug(f"  💰 Total: {codigo_target} = {total:.2f} €")
        else:
            logger.warning(f"⚠️  Nodo no encontrado: {codigo_target}")

    def _calcular_totales_faltantes(self):
        """Calcula totales sumando hijos"""
        for capitulo in self.estructura['capitulos']:
            self._calcular_total_nodo(capitulo)

    def _calcular_total_nodo(self, nodo: Dict) -> float:
        """Calcula el total de un nodo recursivamente"""
        # Calcular totales de hijos primero
        for hijo in nodo.get('subcapitulos', []):
            self._calcular_total_nodo(hijo)

        # Si ya tiene total, usarlo
        if nodo.get('total') is not None:
            return nodo['total']

        # Si no, calcular sumando hijos
        if nodo.get('subcapitulos'):
            total_calculado = sum(
                hijo.get('total', 0.0) for hijo in nodo['subcapitulos']
            )
            nodo['total'] = total_calculado
            return total_calculado

        # Sin hijos ni total
        nodo['total'] = 0.0
        return 0.0
