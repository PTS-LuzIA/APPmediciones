"""
Query Helper - Queries complejas y recursivas
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
from decimal import Decimal


class QueryHelper:
    """
    Helper para queries complejas, especialmente recursivas.

    Proporciona métodos para:
    - Obtener árbol completo con recursión
    - Calcular totales recursivos
    - Búsquedas jerárquicas
    """

    def __init__(self, session: Session):
        self.session = session

    def obtener_arbol_completo(self, proyecto_id: int) -> List[Dict[str, Any]]:
        """
        Obtiene el árbol completo del proyecto con datos de conceptos.

        Usa query recursiva (WITH RECURSIVE) para recorrer el árbol.

        Returns:
            Lista de diccionarios con estructura:
            {
                'nodo_id': int,
                'padre_id': int,
                'codigo_concepto': str,
                'nivel': int,
                'orden': int,
                'cantidad': Decimal,
                'tipo': str,
                'nombre': str,
                'precio': Decimal,
                'total': Decimal,
                ...
            }
        """
        query = text("""
            WITH RECURSIVE arbol AS (
                -- Nodos raíz (padre_id IS NULL)
                SELECT
                    n.id as nodo_id,
                    n.proyecto_id,
                    n.padre_id,
                    n.codigo_concepto,
                    n.nivel,
                    n.orden,
                    n.cantidad,
                    ARRAY[n.orden] as ruta_orden,
                    ARRAY[n.id] as ruta_ids,
                    c.tipo::text,
                    c.nombre,
                    c.resumen,
                    c.descripcion,
                    c.unidad,
                    c.precio,
                    c.total,
                    c.total_calculado,
                    c.cantidad_total,
                    c.importe_total,
                    -- NUEVO: Importe calculado del nodo (cantidad del nodo × precio)
                    n.cantidad * COALESCE(c.precio, 0) as importe
                FROM appmediciones.nodos n
                LEFT JOIN appmediciones.conceptos c
                    ON n.codigo_concepto = c.codigo
                    AND n.proyecto_id = c.proyecto_id
                WHERE n.proyecto_id = :proyecto_id
                  AND n.padre_id IS NULL

                UNION ALL

                -- Nodos hijos (recursivo)
                SELECT
                    n.id as nodo_id,
                    n.proyecto_id,
                    n.padre_id,
                    n.codigo_concepto,
                    n.nivel,
                    n.orden,
                    n.cantidad,
                    a.ruta_orden || n.orden,
                    a.ruta_ids || n.id,
                    c.tipo::text,
                    c.nombre,
                    c.resumen,
                    c.descripcion,
                    c.unidad,
                    c.precio,
                    c.total,
                    c.total_calculado,
                    c.cantidad_total,
                    c.importe_total,
                    -- NUEVO: Importe calculado del nodo (cantidad del nodo × precio)
                    n.cantidad * COALESCE(c.precio, 0) as importe
                FROM appmediciones.nodos n
                INNER JOIN arbol a ON n.padre_id = a.nodo_id
                LEFT JOIN appmediciones.conceptos c
                    ON n.codigo_concepto = c.codigo
                    AND n.proyecto_id = c.proyecto_id
            )
            SELECT * FROM arbol
            ORDER BY ruta_orden;
        """)

        result = self.session.execute(query, {"proyecto_id": proyecto_id})
        rows = result.fetchall()

        # Convertir a lista de diccionarios
        return [dict(row._mapping) for row in rows]

    def calcular_total_recursivo(
        self,
        nodo_id: int,
        tipo_calculo: str = "suma_partidas"
    ) -> Decimal:
        """
        Calcula el total de un nodo sumando recursivamente sus descendientes.

        Args:
            nodo_id: ID del nodo
            tipo_calculo: Tipo de cálculo
                - 'suma_partidas': Suma importes de partidas
                - 'suma_conceptos': Suma totales de conceptos
                - 'descompuesto': Calcula total de descompuesto (cantidad × precio)

        Returns:
            Total calculado
        """
        if tipo_calculo == "suma_partidas":
            query = text("""
                WITH RECURSIVE descendientes AS (
                    -- Nodo inicial
                    SELECT id, codigo_concepto, cantidad
                    FROM appmediciones.nodos
                    WHERE id = :nodo_id

                    UNION ALL

                    -- Descendientes
                    SELECT n.id, n.codigo_concepto, n.cantidad
                    FROM appmediciones.nodos n
                    INNER JOIN descendientes d ON n.padre_id = d.id
                )
                SELECT COALESCE(SUM(d.cantidad * COALESCE(c.precio, 0)), 0) as total
                FROM descendientes d
                INNER JOIN appmediciones.conceptos c
                    ON d.codigo_concepto = c.codigo
                WHERE c.tipo = 'PARTIDA';
            """)
        elif tipo_calculo == "descompuesto":
            query = text("""
                WITH RECURSIVE descomp AS (
                    -- Nodo inicial
                    SELECT id, codigo_concepto, cantidad, 1.0 as factor_acumulado
                    FROM appmediciones.nodos
                    WHERE id = :nodo_id

                    UNION ALL

                    -- Hijos inmediatos con factor acumulado
                    SELECT
                        n.id,
                        n.codigo_concepto,
                        n.cantidad,
                        d.factor_acumulado * n.cantidad
                    FROM appmediciones.nodos n
                    INNER JOIN descomp d ON n.padre_id = d.id
                )
                SELECT COALESCE(SUM(c.precio * d.factor_acumulado), 0) as total
                FROM descomp d
                INNER JOIN appmediciones.conceptos c
                    ON d.codigo_concepto = c.codigo
                WHERE d.id != :nodo_id;  -- Excluir el nodo raíz
            """)
        else:
            query = text("""
                WITH RECURSIVE descendientes AS (
                    SELECT id, codigo_concepto
                    FROM appmediciones.nodos
                    WHERE id = :nodo_id

                    UNION ALL

                    SELECT n.id, n.codigo_concepto
                    FROM appmediciones.nodos n
                    INNER JOIN descendientes d ON n.padre_id = d.id
                )
                SELECT COALESCE(SUM(c.total), 0) as total
                FROM descendientes d
                INNER JOIN appmediciones.conceptos c
                    ON d.codigo_concepto = c.codigo;
            """)

        result = self.session.execute(query, {"nodo_id": nodo_id})
        row = result.fetchone()
        return Decimal(str(row[0])) if row else Decimal('0')

    def buscar_nodos_por_concepto(
        self,
        proyecto_id: int,
        codigo_concepto: str
    ) -> List[Dict[str, Any]]:
        """
        Busca todos los nodos que usan un concepto específico.

        Útil para ver dónde se usa un concepto reutilizable.

        Args:
            proyecto_id: ID del proyecto
            codigo_concepto: Código del concepto a buscar

        Returns:
            Lista de nodos con su ruta en el árbol
        """
        query = text("""
            WITH RECURSIVE ruta AS (
                -- Nodo buscado
                SELECT
                    n.id,
                    n.padre_id,
                    n.codigo_concepto,
                    n.nivel,
                    ARRAY[n.codigo_concepto] as ruta_codigos,
                    1 as profundidad
                FROM appmediciones.nodos n
                WHERE n.proyecto_id = :proyecto_id
                  AND n.codigo_concepto = :codigo_concepto

                UNION ALL

                -- Ascender al padre
                SELECT
                    n.id,
                    n.padre_id,
                    n.codigo_concepto,
                    n.nivel,
                    n.codigo_concepto || r.ruta_codigos,
                    r.profundidad + 1
                FROM appmediciones.nodos n
                INNER JOIN ruta r ON n.id = r.padre_id
            )
            SELECT
                id,
                codigo_concepto,
                nivel,
                array_to_string(ruta_codigos, ' → ') as ruta
            FROM ruta
            WHERE padre_id IS NULL  -- Solo la ruta completa
            ORDER BY nivel;
        """)

        result = self.session.execute(
            query,
            {"proyecto_id": proyecto_id, "codigo_concepto": codigo_concepto}
        )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]

    def obtener_estadisticas_proyecto(self, proyecto_id: int) -> Dict[str, Any]:
        """
        Obtiene estadísticas del proyecto.

        Returns:
            {
                'num_capitulos': int,
                'num_subcapitulos': int,
                'num_partidas': int,
                'num_descompuestos': int,
                'profundidad_maxima': int,
                'total_nodos': int
            }
        """
        query = text("""
            SELECT
                COUNT(CASE WHEN c.tipo = 'CAPITULO' THEN 1 END) as num_capitulos,
                COUNT(CASE WHEN c.tipo = 'SUBCAPITULO' THEN 1 END) as num_subcapitulos,
                COUNT(CASE WHEN c.tipo = 'PARTIDA' THEN 1 END) as num_partidas,
                COUNT(CASE WHEN c.tipo IN ('DESCOMPUESTO', 'MANO_OBRA', 'MATERIAL', 'MAQUINARIA') THEN 1 END) as num_descompuestos,
                MAX(n.nivel) as profundidad_maxima,
                COUNT(*) as total_nodos
            FROM appmediciones.nodos n
            LEFT JOIN appmediciones.conceptos c
                ON n.codigo_concepto = c.codigo
                AND n.proyecto_id = c.proyecto_id
            WHERE n.proyecto_id = :proyecto_id;
        """)

        result = self.session.execute(query, {"proyecto_id": proyecto_id})
        row = result.fetchone()
        return dict(row._mapping) if row else {}

    def verificar_integridad_arbol(self, proyecto_id: int) -> List[Dict[str, Any]]:
        """
        Verifica la integridad del árbol.

        Busca:
        - Nodos huérfanos (padre no existe)
        - Conceptos referenciados que no existen
        - Ciclos en el árbol (padre apuntando a hijo)

        Returns:
            Lista de problemas encontrados
        """
        problemas = []

        # Nodos huérfanos
        query_huerfanos = text("""
            SELECT n.id, n.codigo_concepto, n.padre_id
            FROM appmediciones.nodos n
            LEFT JOIN appmediciones.nodos p ON n.padre_id = p.id
            WHERE n.proyecto_id = :proyecto_id
              AND n.padre_id IS NOT NULL
              AND p.id IS NULL;
        """)

        result = self.session.execute(query_huerfanos, {"proyecto_id": proyecto_id})
        for row in result:
            problemas.append({
                'tipo': 'nodo_huerfano',
                'nodo_id': row.id,
                'codigo': row.codigo_concepto,
                'padre_id_invalido': row.padre_id
            })

        # Conceptos no encontrados
        query_conceptos = text("""
            SELECT n.id, n.codigo_concepto
            FROM appmediciones.nodos n
            LEFT JOIN appmediciones.conceptos c
                ON n.codigo_concepto = c.codigo
                AND n.proyecto_id = c.proyecto_id
            WHERE n.proyecto_id = :proyecto_id
              AND c.id IS NULL;
        """)

        result = self.session.execute(query_conceptos, {"proyecto_id": proyecto_id})
        for row in result:
            problemas.append({
                'tipo': 'concepto_no_encontrado',
                'nodo_id': row.id,
                'codigo': row.codigo_concepto
            })

        return problemas
