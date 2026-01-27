# Arquitectura de APPmediciones

## Visión General

APPmediciones utiliza una **arquitectura de dos tablas** para representar presupuestos de construcción de forma flexible y compatible con el estándar BC3/FIEBDC-3.

## Principio Fundamental: Separación Estructura-Datos

### Problema de Arquitecturas Tradicionales

Las arquitecturas tradicionales mezclan estructura y datos en tablas separadas rígidas:

```
❌ Arquitectura Tradicional (rígida):
┌─────────────┐
│  Capítulos  │
├─────────────┤
│ id          │
│ codigo      │
│ nombre      │◄─── DATOS mezclados
│ total       │    con ESTRUCTURA
│ orden       │
└─────────────┘
       │
       │ 1:N
       ▼
┌─────────────┐
│Subcapítulos │
├─────────────┤
│ id          │
│ capitulo_id │◄─── Jerarquía fija
│ codigo      │    (solo 2 niveles)
│ nombre      │
│ nivel       │
└─────────────┘
       │
       │ 1:N
       ▼
┌─────────────┐
│  Partidas   │
├─────────────┤
│ id          │
│ subcap_id   │
│ codigo      │
│ precio      │
└─────────────┘

Limitaciones:
- ❌ Partidas NO pueden estar directamente en capítulos
- ❌ NO soporta descompuestos (partidas con sub-elementos)
- ❌ NO permite reutilización de conceptos
- ❌ Jerarquía limitada a 3 niveles
```

### Solución: Arquitectura de Dos Tablas

Separamos **ESTRUCTURA** (árbol jerárquico) de **DATOS** (conceptos):

```
✅ Arquitectura APPmediciones (flexible):

┌──────────────────────────────────────────────────────┐
│                    NODOS (Árbol)                     │
│                                                      │
│  Define DÓNDE está cada elemento en la jerarquía    │
└──────────────────────────────────────────────────────┘
                        │
                        │ apunta a
                        ▼
┌──────────────────────────────────────────────────────┐
│                  CONCEPTOS (Datos)                   │
│                                                      │
│  Define QUÉ ES cada elemento (datos económicos)     │
└──────────────────────────────────────────────────────┘

Ventajas:
✅ Jerarquía ilimitada (N niveles)
✅ Un concepto puede aparecer en múltiples lugares
✅ Soporta descompuestos nativamente
✅ Partidas directas en capítulos
✅ Compatible con BC3/FIEBDC-3
```

## Modelo de Datos Detallado

### Tabla: NODOS (Estructura)

Define **la estructura jerárquica** del presupuesto (árbol).

```sql
CREATE TABLE nodos (
    id              SERIAL PRIMARY KEY,
    proyecto_id     INTEGER NOT NULL,
    padre_id        INTEGER,              -- NULL = raíz
    codigo_concepto VARCHAR(50) NOT NULL, -- Apunta al concepto

    -- Posición
    nivel           INTEGER NOT NULL,     -- 0, 1, 2, 3...
    orden           INTEGER NOT NULL,     -- Orden entre hermanos

    -- Cantidad (para descompuestos)
    cantidad        NUMERIC(14,4) DEFAULT 1.0
);
```

**Características:**
- `padre_id = NULL` → Nodo raíz (invisible)
- `padre_id != NULL` → Nodo hijo
- `codigo_concepto` → Referencia al concepto (datos)
- `cantidad` → Cantidad del hijo en el padre (ej: 2.5 kg de cemento por m² de mortero)

**Ejemplo Real:**

```
Proyecto: "Reforma Edificio"
│
├─ Nodo(id=1, padre=NULL, concepto="ROOT", nivel=0, orden=0)
│  │
│  ├─ Nodo(id=2, padre=1, concepto="C01", nivel=1, orden=1)
│  │  │  CAPÍTULO: "Demoliciones"
│  │  │
│  │  ├─ Nodo(id=3, padre=2, concepto="C01.01", nivel=2, orden=1)
│  │  │  │  SUBCAPÍTULO: "Demoliciones interiores"
│  │  │  │
│  │  │  └─ Nodo(id=4, padre=3, concepto="E001", nivel=3, orden=1)
│  │  │     │  PARTIDA: "Demolición tabique" (25 €/m²)
│  │  │     │
│  │  │     ├─ Nodo(id=5, padre=4, concepto="MO001", nivel=4, orden=1, cant=0.5)
│  │  │     │     DESCOMPUESTO: "Peón ordinario" (15 €/h × 0.5h = 7.5 €)
│  │  │     │
│  │  │     └─ Nodo(id=6, padre=4, concepto="MAQ001", nivel=4, orden=2, cant=0.2)
│  │  │           DESCOMPUESTO: "Compresor" (10 €/h × 0.2h = 2 €)
│  │  │
│  │  └─ Nodo(id=7, padre=2, concepto="E002", nivel=2, orden=2)
│  │        PARTIDA directa en CAPÍTULO (sin subcapítulo)
│  │
│  └─ Nodo(id=8, padre=1, concepto="C02", nivel=1, orden=2)
│        CAPÍTULO: "Albañilería"
```

### Tabla: CONCEPTOS (Datos)

Define **los datos económicos** de cada elemento.

```sql
CREATE TYPE tipo_concepto AS ENUM (
    'RAIZ', 'CAPITULO', 'SUBCAPITULO', 'PARTIDA',
    'DESCOMPUESTO', 'MANO_OBRA', 'MATERIAL', 'MAQUINARIA'
);

CREATE TABLE conceptos (
    id                  SERIAL PRIMARY KEY,
    proyecto_id         INTEGER NOT NULL,
    codigo              VARCHAR(50) UNIQUE NOT NULL,
    tipo                tipo_concepto NOT NULL,

    -- Datos descriptivos
    nombre              VARCHAR(500),
    resumen             VARCHAR(500),
    descripcion         TEXT,

    -- Datos económicos
    unidad              VARCHAR(20),      -- m, m2, m3, kg, h, ud...
    precio              NUMERIC(14,4),    -- Precio unitario

    -- Para capítulos/subcapítulos
    total               NUMERIC(14,2),    -- Total del PDF
    total_calculado     NUMERIC(14,2),    -- Total calculado

    -- Para partidas
    cantidad_total      NUMERIC(14,4),    -- Suma mediciones
    importe_total       NUMERIC(14,2)     -- cantidad × precio
);
```

**Ejemplo Real:**

```sql
-- CAPÍTULO
Concepto(
    codigo = "C01",
    tipo = "CAPITULO",
    nombre = "DEMOLICIONES",
    total = 15000.00
)

-- SUBCAPÍTULO
Concepto(
    codigo = "C01.01",
    tipo = "SUBCAPITULO",
    nombre = "Demoliciones interiores",
    total = 8500.00
)

-- PARTIDA
Concepto(
    codigo = "E001",
    tipo = "PARTIDA",
    nombre = "Demolición de tabique de ladrillo hueco",
    resumen = "DEMOLICIÓN TABIQUE L.H. 7cm",
    unidad = "m2",
    precio = 25.00,
    cantidad_total = 150.00,
    importe_total = 3750.00
)

-- DESCOMPUESTO (Mano de obra)
Concepto(
    codigo = "MO001",
    tipo = "MANO_OBRA",
    nombre = "Peón ordinario",
    unidad = "h",
    precio = 15.00
)

-- DESCOMPUESTO (Maquinaria)
Concepto(
    codigo = "MAQ001",
    tipo = "MAQUINARIA",
    nombre = "Compresor portátil",
    unidad = "h",
    precio = 10.00
)
```

## Operaciones Comunes

### 1. Obtener Árbol Completo

```sql
WITH RECURSIVE arbol AS (
    -- Nodos raíz
    SELECT n.*, c.nombre, c.tipo, c.precio
    FROM nodos n
    LEFT JOIN conceptos c ON n.codigo_concepto = c.codigo
    WHERE n.padre_id IS NULL

    UNION ALL

    -- Nodos hijos (recursivo)
    SELECT n.*, c.nombre, c.tipo, c.precio
    FROM nodos n
    INNER JOIN arbol a ON n.padre_id = a.id
    LEFT JOIN conceptos c ON n.codigo_concepto = c.codigo
)
SELECT * FROM arbol
ORDER BY nivel, orden;
```

### 2. Calcular Total Recursivo

```sql
-- Total de un capítulo sumando sus partidas recursivamente
WITH RECURSIVE total_recursivo AS (
    -- Nodo inicial (capítulo)
    SELECT
        id,
        codigo_concepto,
        nivel,
        CAST(0 AS NUMERIC) as total
    FROM nodos
    WHERE codigo_concepto = 'C01'

    UNION ALL

    -- Sumar hijos
    SELECT
        n.id,
        n.codigo_concepto,
        n.nivel,
        CASE
            WHEN c.tipo = 'PARTIDA' THEN n.cantidad * c.importe_total
            ELSE tr.total
        END
    FROM nodos n
    INNER JOIN total_recursivo tr ON n.padre_id = tr.id
    LEFT JOIN conceptos c ON n.codigo_concepto = c.codigo
)
SELECT SUM(total) FROM total_recursivo;
```

### 3. Reutilización de Conceptos

Un mismo concepto puede aparecer en múltiples lugares:

```sql
-- Concepto "Excavación manual" usado en 3 lugares diferentes
INSERT INTO conceptos (codigo, tipo, nombre, precio, unidad)
VALUES ('EXC001', 'PARTIDA', 'Excavación manual', 25.50, 'm3');

-- Aparece en Capítulo 1, Subcapítulo 1.1 (100 m3)
INSERT INTO nodos (proyecto_id, padre_id, codigo_concepto, cantidad, nivel, orden)
VALUES (1, 10, 'EXC001', 100.0, 3, 1);

-- Aparece en Capítulo 2, Subcapítulo 2.3 (50 m3)
INSERT INTO nodos (proyecto_id, padre_id, codigo_concepto, cantidad, nivel, orden)
VALUES (1, 25, 'EXC001', 50.0, 3, 2);

-- Aparece en Capítulo 3, directamente (25 m3)
INSERT INTO nodos (proyecto_id, padre_id, codigo_concepto, cantidad, nivel, orden)
VALUES (1, 30, 'EXC001', 25.0, 2, 1);

-- Total usado: 100 + 50 + 25 = 175 m3
-- Importe total: 175 × 25.50 = 4,462.50 €
```

## Comparación con BC3/FIEBDC-3

| BC3 | APPmediciones | Descripción |
|-----|---------------|-------------|
| `~V` | `proyecto` | Versión y metadatos |
| `~C` | `concepto` | Concepto (código, tipo, datos) |
| `~D` | `nodo` | Descomposición (estructura) |
| `~M` | `medicion` | Mediciones auxiliares |
| `~T` | `concepto.descripcion` | Textos descriptivos |

## Ventajas de Esta Arquitectura

### ✅ Flexibilidad Total

- ✅ Jerarquía ilimitada (N niveles)
- ✅ Partidas directas en capítulos (sin subcapítulo dummy)
- ✅ Descompuestos de partidas (mano obra, materiales, maquinaria)
- ✅ Descompuestos de descompuestos (recursivo)

### ✅ Reutilización

- ✅ Un concepto puede aparecer en múltiples lugares
- ✅ Cambiar precio de un concepto actualiza todos los usos
- ✅ No hay duplicación de datos económicos

### ✅ Compatible con BC3

- ✅ Importar/Exportar BC3 directo
- ✅ Misma lógica de separación estructura-datos
- ✅ Soporte nativo para todos los tipos de BC3

### ✅ Queries Eficientes

- ✅ Queries recursivas estándar (WITH RECURSIVE)
- ✅ Índices optimizados por jerarquía
- ✅ Vista materializada para árbol completo

### ✅ Escalable

- ✅ No hay límite de niveles jerárquicos
- ✅ Soporta proyectos de cualquier complejidad
- ✅ Performance predecible con índices

## Desventajas y Consideraciones

### ⚠️ Complejidad de Queries

- Las queries recursivas son más complejas que JOINs simples
- Requiere conocimiento de SQL avanzado
- **Solución**: Crear vistas y funciones helper

### ⚠️ Integridad Referencial

- Los nodos apuntan a conceptos por código (no FK directa)
- Requiere validación en capa de aplicación
- **Solución**: Triggers y constraints personalizados

### ⚠️ Curva de Aprendizaje

- Desarrolladores deben entender separación estructura-datos
- Requiere documentación clara
- **Solución**: Este documento + ejemplos + tests

## Próximos Pasos

1. ✅ Modelos SQLAlchemy creados
2. ✅ Schema SQL completo
3. ⏭️ Database Manager con queries recursivas
4. ⏭️ Parsers adaptados a nueva estructura
5. ⏭️ API REST para CRUD de nodos y conceptos
6. ⏭️ Frontend con visualización de árbol
7. ⏭️ Importador/Exportador BC3
