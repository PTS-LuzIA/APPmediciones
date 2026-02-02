"""
Database Manager - CRUD operations para APPmediciones
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
import logging
import sys
from pathlib import Path

# Añadir el directorio backend al path
sys.path.append(str(Path(__file__).parent.parent))

from models import Proyecto, Nodo, Concepto, Medicion, TipoConcepto, Usuario
from database.queries import QueryHelper
from utils.security import hash_password

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gestor de base de datos para APPmediciones.

    Proporciona métodos CRUD y operaciones complejas sobre la estructura jerárquica.
    """

    def __init__(self, session: Session):
        self.session = session
        self.queries = QueryHelper(session)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        self.session.close()

    # =====================================================
    # USUARIOS
    # =====================================================

    def crear_usuario(
        self,
        username: str,
        email: str,
        password: str,
        nombre_completo: str = None,
        empresa: str = None,
        es_admin: bool = False
    ) -> Usuario:
        """
        Crea un nuevo usuario.

        Args:
            username: Nombre de usuario único
            email: Email único
            password: Contraseña en texto plano (se hasheará)
            nombre_completo: Nombre completo opcional
            empresa: Empresa opcional
            es_admin: Si es administrador

        Returns:
            Usuario creado
        """
        usuario = Usuario(
            username=username,
            email=email,
            password_hash=hash_password(password),
            nombre_completo=nombre_completo,
            empresa=empresa,
            es_admin=es_admin,
            activo=True
        )

        self.session.add(usuario)
        self.session.commit()
        logger.info(f"✓ Usuario creado: {username}")
        return usuario

    def obtener_usuario(self, usuario_id: int) -> Optional[Usuario]:
        """Obtiene un usuario por ID"""
        return self.session.query(Usuario).filter_by(id=usuario_id).first()

    def actualizar_usuario(
        self,
        usuario_id: int,
        email: str = None,
        nombre_completo: str = None,
        password: str = None
    ) -> Optional[Usuario]:
        """
        Actualiza datos de un usuario.

        Args:
            usuario_id: ID del usuario
            email: Nuevo email (opcional)
            nombre_completo: Nuevo nombre (opcional)
            password: Nueva contraseña en texto plano (opcional)

        Returns:
            Usuario actualizado o None si no existe
        """
        usuario = self.obtener_usuario(usuario_id)
        if not usuario:
            return None

        if email:
            usuario.email = email
        if nombre_completo:
            usuario.nombre_completo = nombre_completo
        if password:
            usuario.password_hash = hash_password(password)

        self.session.commit()
        logger.info(f"✓ Usuario actualizado: {usuario_id}")
        return usuario

    # =====================================================
    # PROYECTOS
    # =====================================================

    def crear_proyecto(self, usuario_id: int, nombre: str, descripcion: str = None) -> Proyecto:
        """
        Crea un nuevo proyecto.

        Args:
            usuario_id: ID del usuario propietario
            nombre: Nombre del proyecto
            descripcion: Descripción opcional

        Returns:
            Proyecto creado
        """
        proyecto = Proyecto(
            usuario_id=usuario_id,
            nombre=nombre,
            descripcion=descripcion,
            estado='borrador'
        )

        self.session.add(proyecto)
        self.session.flush()

        # Crear nodo raíz
        self._crear_nodo_raiz(proyecto.id)

        self.session.commit()
        logger.info(f"✓ Proyecto creado: {proyecto.id} - {nombre}")
        return proyecto

    def obtener_proyecto(self, proyecto_id: int) -> Optional[Proyecto]:
        """Obtiene un proyecto por ID"""
        return self.session.query(Proyecto).filter_by(id=proyecto_id).first()

    def listar_proyectos(self, usuario_id: int, limite: int = 50, offset: int = 0) -> List[Proyecto]:
        """Lista proyectos de un usuario"""
        return (
            self.session.query(Proyecto)
            .filter_by(usuario_id=usuario_id)
            .order_by(Proyecto.fecha_creacion.desc())
            .limit(limite)
            .offset(offset)
            .all()
        )

    def eliminar_proyecto(self, proyecto_id: int) -> bool:
        """
        Elimina un proyecto y toda su estructura (cascade).

        Returns:
            True si se eliminó, False si no existía
        """
        proyecto = self.obtener_proyecto(proyecto_id)
        if not proyecto:
            return False

        self.session.delete(proyecto)
        self.session.commit()
        logger.info(f"✓ Proyecto eliminado: {proyecto_id}")
        return True

    # =====================================================
    # CONCEPTOS
    # =====================================================

    def crear_concepto(
        self,
        proyecto_id: int,
        codigo: str,
        tipo: TipoConcepto,
        nombre: str = None,
        **kwargs
    ) -> Concepto:
        """
        Crea un nuevo concepto.

        Args:
            proyecto_id: ID del proyecto
            codigo: Código único del concepto
            tipo: Tipo de concepto
            nombre: Nombre del concepto
            **kwargs: Otros campos (resumen, precio, unidad, etc.)

        Returns:
            Concepto creado
        """
        concepto = Concepto(
            proyecto_id=proyecto_id,
            codigo=codigo,
            tipo=tipo,
            nombre=nombre,
            **kwargs
        )

        self.session.add(concepto)
        self.session.commit()
        logger.debug(f"✓ Concepto creado: {codigo} ({tipo})")
        return concepto

    def obtener_concepto(self, proyecto_id: int, codigo: str) -> Optional[Concepto]:
        """Obtiene un concepto por código"""
        return (
            self.session.query(Concepto)
            .filter_by(proyecto_id=proyecto_id, codigo=codigo)
            .first()
        )

    def obtener_concepto_por_id(self, concepto_id: int) -> Optional[Concepto]:
        """Obtiene un concepto por ID"""
        return self.session.query(Concepto).filter_by(id=concepto_id).first()

    def listar_conceptos(
        self,
        proyecto_id: int,
        tipo: TipoConcepto = None,
        limite: int = 1000
    ) -> List[Concepto]:
        """
        Lista conceptos de un proyecto.

        Args:
            proyecto_id: ID del proyecto
            tipo: Filtrar por tipo (opcional)
            limite: Máximo de resultados

        Returns:
            Lista de conceptos
        """
        query = self.session.query(Concepto).filter_by(proyecto_id=proyecto_id)

        if tipo:
            query = query.filter_by(tipo=tipo)

        return query.order_by(Concepto.codigo).limit(limite).all()

    def actualizar_concepto(
        self,
        proyecto_id: int,
        codigo: str,
        **campos
    ) -> Optional[Concepto]:
        """
        Actualiza campos de un concepto.

        Args:
            proyecto_id: ID del proyecto
            codigo: Código del concepto
            **campos: Campos a actualizar

        Returns:
            Concepto actualizado o None si no existe
        """
        concepto = self.obtener_concepto(proyecto_id, codigo)
        if not concepto:
            return None

        for campo, valor in campos.items():
            if hasattr(concepto, campo):
                setattr(concepto, campo, valor)

        self.session.commit()
        logger.debug(f"✓ Concepto actualizado: {codigo}")
        return concepto

    # =====================================================
    # NODOS (Estructura Jerárquica)
    # =====================================================

    def crear_nodo(
        self,
        proyecto_id: int,
        codigo_concepto: str,
        padre_id: int = None,
        nivel: int = None,
        orden: int = None,
        cantidad: float = 1.0
    ) -> Nodo:
        """
        Crea un nodo en la estructura jerárquica.

        Args:
            proyecto_id: ID del proyecto
            codigo_concepto: Código del concepto al que apunta
            padre_id: ID del nodo padre (None = raíz)
            nivel: Nivel jerárquico (se calcula si no se proporciona)
            orden: Orden entre hermanos (se calcula si no se proporciona)
            cantidad: Cantidad en relación padre-hijo

        Returns:
            Nodo creado
        """
        # Calcular nivel si no se proporciona
        if nivel is None:
            if padre_id is None:
                nivel = 0
            else:
                padre = self.session.query(Nodo).filter_by(id=padre_id).first()
                nivel = padre.nivel + 1 if padre else 0

        # Calcular orden si no se proporciona
        if orden is None:
            orden = self._calcular_siguiente_orden(proyecto_id, padre_id)

        nodo = Nodo(
            proyecto_id=proyecto_id,
            padre_id=padre_id,
            codigo_concepto=codigo_concepto,
            nivel=nivel,
            orden=orden,
            cantidad=cantidad
        )

        self.session.add(nodo)
        self.session.commit()
        logger.debug(f"✓ Nodo creado: {codigo_concepto} (nivel={nivel}, orden={orden})")
        return nodo

    def obtener_nodo(self, nodo_id: int) -> Optional[Nodo]:
        """Obtiene un nodo por ID"""
        return self.session.query(Nodo).filter_by(id=nodo_id).first()

    def obtener_nodo_raiz(self, proyecto_id: int) -> Optional[Nodo]:
        """Obtiene el nodo raíz de un proyecto"""
        return (
            self.session.query(Nodo)
            .filter_by(proyecto_id=proyecto_id, padre_id=None)
            .first()
        )

    def listar_hijos(self, nodo_id: int) -> List[Nodo]:
        """
        Lista los hijos directos de un nodo, ordenados por 'orden'.

        Args:
            nodo_id: ID del nodo padre

        Returns:
            Lista de nodos hijos
        """
        return (
            self.session.query(Nodo)
            .filter_by(padre_id=nodo_id)
            .order_by(Nodo.orden)
            .all()
        )

    def obtener_arbol_completo(self, proyecto_id: int) -> List[Dict[str, Any]]:
        """
        Obtiene el árbol completo del proyecto con datos de conceptos.

        Returns:
            Lista de nodos con datos jerárquicos y de conceptos
        """
        return self.queries.obtener_arbol_completo(proyecto_id)

    def construir_arbol_jerarquico(self, proyecto_id: int) -> List[Dict[str, Any]]:
        """
        Construye el árbol jerárquico completo con estructura anidada.

        Convierte la lista plana de nodos en una estructura jerárquica donde:
        - Capítulos son nodos de nivel 1
        - Cada capítulo/subcapítulo tiene arrays 'subcapitulos' y 'partidas' (vacíos si no tiene)

        Returns:
            Lista de capítulos con estructura anidada
        """
        # Obtener flat list from DB
        nodos_flat = self.queries.obtener_arbol_completo(proyecto_id)

        if not nodos_flat:
            return []

        # Build maps
        nodos_map = {}
        for nodo in nodos_flat:
            nodo_id = nodo['nodo_id']
            nodos_map[nodo_id] = {
                'id': nodo_id,
                'codigo': nodo['codigo_concepto'],
                'nombre': nodo.get('nombre', ''),
                'resumen': nodo.get('resumen', ''),
                'descripcion': nodo.get('descripcion', ''),
                'tipo': nodo.get('tipo', ''),
                'nivel': nodo['nivel'],
                'orden': nodo['orden'],
                'unidad': nodo.get('unidad', ''),
                'cantidad': float(nodo.get('cantidad') or 0),  # Cantidad del nodo específico
                'cantidad_total': float(nodo.get('cantidad_total') or 0),  # Total del concepto (para resúmenes)
                'precio': float(nodo.get('precio') or 0),
                'total': float(nodo.get('total') or 0),
                'total_calculado': float(nodo.get('total_calculado') or 0) if nodo.get('total_calculado') else None,
                'importe': float(nodo.get('importe') or 0),  # Importe del nodo (cantidad × precio)
                'importe_total': float(nodo.get('importe_total') or 0),  # Total del concepto (para resúmenes)
                'padre_id': nodo['padre_id'],
                'subcapitulos': [],
                'partidas': []
            }

        # Build hierarchy - find root nodes (nivel=0 or padre_id=None)
        root_nodes = [n for n in nodos_map.values() if n['padre_id'] is None or n['nivel'] == 0]

        # Build children relationships
        for nodo in nodos_map.values():
            if nodo['padre_id'] and nodo['padre_id'] in nodos_map:
                padre = nodos_map[nodo['padre_id']]
                # If it's a partida, add to partidas array, otherwise to subcapitulos
                if nodo['tipo'] == 'PARTIDA':
                    padre['partidas'].append(nodo)
                else:
                    padre['subcapitulos'].append(nodo)

        # Get only capitulos (children of root or nivel=1)
        capitulos = []
        for root in root_nodes:
            # Root nodes' children are capitulos
            capitulos.extend(root['subcapitulos'])

        # If no children, root nodes themselves are capitulos
        if not capitulos and root_nodes:
            capitulos = root_nodes

        return capitulos

    def eliminar_nodo(self, nodo_id: int) -> bool:
        """
        Elimina un nodo y todos sus descendientes (cascade).

        Returns:
            True si se eliminó, False si no existía
        """
        nodo = self.obtener_nodo(nodo_id)
        if not nodo:
            return False

        self.session.delete(nodo)
        self.session.commit()
        logger.debug(f"✓ Nodo eliminado: {nodo_id}")
        return True

    def mover_nodo(
        self,
        nodo_id: int,
        nuevo_padre_id: int = None,
        nuevo_orden: int = None
    ) -> Optional[Nodo]:
        """
        Mueve un nodo a una nueva posición en el árbol.

        Args:
            nodo_id: ID del nodo a mover
            nuevo_padre_id: ID del nuevo padre (None = mover a raíz)
            nuevo_orden: Nuevo orden entre hermanos (None = al final)

        Returns:
            Nodo actualizado o None si no existe
        """
        nodo = self.obtener_nodo(nodo_id)
        if not nodo:
            return None

        # Actualizar padre
        nodo.padre_id = nuevo_padre_id

        # Recalcular nivel
        if nuevo_padre_id is None:
            nodo.nivel = 0
        else:
            padre = self.obtener_nodo(nuevo_padre_id)
            nodo.nivel = padre.nivel + 1 if padre else 0

        # Actualizar orden
        if nuevo_orden is not None:
            nodo.orden = nuevo_orden
        else:
            nodo.orden = self._calcular_siguiente_orden(nodo.proyecto_id, nuevo_padre_id)

        self.session.commit()
        logger.debug(f"✓ Nodo movido: {nodo_id} → padre={nuevo_padre_id}")
        return nodo

    # =====================================================
    # MEDICIONES
    # =====================================================

    def crear_medicion(
        self,
        concepto_id: int,
        comentario: str = None,
        unidades: float = 1.0,
        largo: float = 1.0,
        ancho: float = 1.0,
        alto: float = 1.0,
        orden: int = None
    ) -> Medicion:
        """
        Crea una medición para una partida.

        Args:
            concepto_id: ID del concepto (debe ser tipo PARTIDA)
            comentario: Descripción de la medición
            unidades, largo, ancho, alto: Dimensiones
            orden: Orden de la medición (se calcula si no se proporciona)

        Returns:
            Medición creada
        """
        if orden is None:
            orden = self._calcular_siguiente_orden_medicion(concepto_id)

        medicion = Medicion(
            concepto_id=concepto_id,
            comentario=comentario,
            unidades=unidades,
            largo=largo,
            ancho=ancho,
            alto=alto,
            orden=orden
        )

        # Calcular subtotal
        medicion.calcular_subtotal()

        self.session.add(medicion)
        self.session.commit()
        logger.debug(f"✓ Medición creada: {medicion.subtotal} para concepto {concepto_id}")
        return medicion

    def listar_mediciones(self, concepto_id: int) -> List[Medicion]:
        """Lista mediciones de un concepto"""
        return (
            self.session.query(Medicion)
            .filter_by(concepto_id=concepto_id)
            .order_by(Medicion.orden)
            .all()
        )

    # =====================================================
    # LIMPIEZA DE DATOS POR FASE
    # =====================================================

    def limpiar_datos_fase1(self, proyecto_id: int):
        """
        Limpia todos los datos del proyecto excepto el nodo raíz.

        Se ejecuta antes de Fase 1 para evitar duplicados.
        Elimina: capítulos, subcapítulos y partidas (nodos y conceptos).

        Args:
            proyecto_id: ID del proyecto a limpiar
        """
        logger.info(f"🗑️  Limpiando datos de Fase 1 para proyecto {proyecto_id}")

        # Obtener nodo raíz
        nodo_raiz = self.obtener_nodo_raiz(proyecto_id)
        if not nodo_raiz:
            logger.warning(f"No se encontró nodo raíz para proyecto {proyecto_id}")
            return

        # Eliminar todos los nodos excepto el raíz
        nodos_eliminados = self.session.execute(
            text("""
                DELETE FROM appmediciones.nodos
                WHERE proyecto_id = :pid AND id != :raiz_id
            """),
            {'pid': proyecto_id, 'raiz_id': nodo_raiz.id}
        ).rowcount

        # Eliminar todos los conceptos excepto el raíz (ROOT)
        conceptos_eliminados = self.session.execute(
            text("""
                DELETE FROM appmediciones.conceptos
                WHERE proyecto_id = :pid AND codigo != 'ROOT'
            """),
            {'pid': proyecto_id}
        ).rowcount

        self.session.commit()
        logger.info(f"  ✓ Eliminados {nodos_eliminados} nodos y {conceptos_eliminados} conceptos")

    def limpiar_datos_fase2(self, proyecto_id: int):
        """
        Limpia solo las partidas del proyecto.

        Se ejecuta antes de Fase 2 para evitar duplicados.
        Elimina: solo partidas (nodos y conceptos de tipo PARTIDA).
        Mantiene: capítulos y subcapítulos.

        Args:
            proyecto_id: ID del proyecto a limpiar
        """
        logger.info(f"🗑️  Limpiando datos de Fase 2 (solo partidas) para proyecto {proyecto_id}")

        # Eliminar nodos de partidas
        nodos_eliminados = self.session.execute(
            text("""
                DELETE FROM appmediciones.nodos
                WHERE proyecto_id = :pid
                AND codigo_concepto IN (
                    SELECT codigo FROM appmediciones.conceptos
                    WHERE proyecto_id = :pid AND tipo = 'PARTIDA'
                )
            """),
            {'pid': proyecto_id}
        ).rowcount

        # Eliminar conceptos de partidas
        conceptos_eliminados = self.session.execute(
            text("""
                DELETE FROM appmediciones.conceptos
                WHERE proyecto_id = :pid AND tipo = 'PARTIDA'
            """),
            {'pid': proyecto_id}
        ).rowcount

        self.session.commit()
        logger.info(f"  ✓ Eliminadas {conceptos_eliminados} partidas ({nodos_eliminados} nodos)")

    # =====================================================
    # MÉTODOS PRIVADOS
    # =====================================================

    def _crear_nodo_raiz(self, proyecto_id: int) -> Nodo:
        """Crea el nodo raíz del proyecto"""
        # Primero crear concepto raíz
        concepto_raiz = Concepto(
            proyecto_id=proyecto_id,
            codigo="ROOT",
            tipo=TipoConcepto.RAIZ,
            nombre="Raíz"
        )
        self.session.add(concepto_raiz)
        self.session.flush()

        # Crear nodo raíz
        nodo_raiz = Nodo(
            proyecto_id=proyecto_id,
            padre_id=None,
            codigo_concepto="ROOT",
            nivel=0,
            orden=0,
            cantidad=1.0
        )
        self.session.add(nodo_raiz)
        self.session.flush()

        return nodo_raiz

    def _calcular_siguiente_orden(self, proyecto_id: int, padre_id: int = None) -> int:
        """Calcula el siguiente orden para hermanos"""
        max_orden = (
            self.session.query(Nodo.orden)
            .filter_by(proyecto_id=proyecto_id, padre_id=padre_id)
            .order_by(Nodo.orden.desc())
            .first()
        )
        return (max_orden[0] + 1) if max_orden else 1

    def _calcular_siguiente_orden_medicion(self, concepto_id: int) -> int:
        """Calcula el siguiente orden para mediciones"""
        max_orden = (
            self.session.query(Medicion.orden)
            .filter_by(concepto_id=concepto_id)
            .order_by(Medicion.orden.desc())
            .first()
        )
        return (max_orden[0] + 1) if max_orden else 1
