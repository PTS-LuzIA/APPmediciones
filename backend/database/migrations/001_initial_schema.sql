-- =====================================================
-- APPmediciones - Schema Inicial
-- =====================================================
-- Versión: 1.0.0
-- Fecha: 2026-01-27
-- Descripción: Estructura de dos tablas (Nodos + Conceptos)
--              Compatible con BC3/FIEBDC-3
-- =====================================================

-- Crear schema
CREATE SCHEMA IF NOT EXISTS appmediciones;

-- Set search path
SET search_path TO appmediciones;

-- =====================================================
-- TABLA: usuarios
-- =====================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre_completo VARCHAR(200),
    empresa VARCHAR(200),
    activo BOOLEAN DEFAULT TRUE,
    es_admin BOOLEAN DEFAULT FALSE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso TIMESTAMP
);

CREATE INDEX idx_usuario_username ON usuarios(username);
CREATE INDEX idx_usuario_email ON usuarios(email);

-- =====================================================
-- TABLA: proyectos
-- =====================================================

CREATE TABLE IF NOT EXISTS proyectos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,

    -- PDF metadata
    pdf_path VARCHAR(500),
    pdf_nombre VARCHAR(200),
    pdf_hash VARCHAR(64),

    -- Totales
    presupuesto_total NUMERIC(14, 2) DEFAULT 0,
    presupuesto_calculado NUMERIC(14, 2),

    -- Metadata de procesamiento
    layout_detectado VARCHAR(50),
    numero_paginas INTEGER,
    fase_actual INTEGER DEFAULT 0,

    -- Estado
    estado VARCHAR(20) DEFAULT 'borrador',

    -- Fechas
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_proyecto_usuario ON proyectos(usuario_id);
CREATE INDEX idx_proyecto_estado ON proyectos(estado);
CREATE INDEX idx_proyecto_pdf_hash ON proyectos(pdf_hash);

-- =====================================================
-- TABLA: conceptos (DATOS de los elementos)
-- =====================================================

CREATE TYPE tipo_concepto AS ENUM (
    'RAIZ',
    'CAPITULO',
    'SUBCAPITULO',
    'PARTIDA',
    'DESCOMPUESTO',
    'MANO_OBRA',
    'MATERIAL',
    'MAQUINARIA',
    'AUXILIAR'
);

CREATE TABLE IF NOT EXISTS conceptos (
    id SERIAL PRIMARY KEY,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    codigo VARCHAR(50) NOT NULL,
    tipo tipo_concepto NOT NULL,

    -- Datos comunes
    nombre VARCHAR(500),
    resumen VARCHAR(500),
    descripcion TEXT,

    -- Datos económicos
    unidad VARCHAR(20),
    precio NUMERIC(14, 4),

    -- Para capítulos/subcapítulos
    total NUMERIC(14, 2),
    total_calculado NUMERIC(14, 2),

    -- Para partidas
    cantidad_total NUMERIC(14, 4),
    importe_total NUMERIC(14, 2),

    -- Flags
    tiene_mediciones INTEGER DEFAULT 0,
    mediciones_validadas INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_concepto_proyecto_codigo UNIQUE (proyecto_id, codigo)
);

CREATE INDEX idx_concepto_proyecto ON conceptos(proyecto_id);
CREATE INDEX idx_concepto_codigo ON conceptos(codigo);
CREATE INDEX idx_concepto_tipo ON conceptos(tipo);

-- =====================================================
-- TABLA: nodos (ESTRUCTURA jerárquica)
-- =====================================================

CREATE TABLE IF NOT EXISTS nodos (
    id SERIAL PRIMARY KEY,
    proyecto_id INTEGER NOT NULL REFERENCES proyectos(id) ON DELETE CASCADE,
    padre_id INTEGER REFERENCES nodos(id) ON DELETE CASCADE,
    codigo_concepto VARCHAR(50) NOT NULL,

    -- Posición en jerarquía
    nivel INTEGER NOT NULL,
    orden INTEGER NOT NULL,

    -- Cantidad en relación padre-hijo
    cantidad NUMERIC(14, 4) DEFAULT 1.0
);

CREATE INDEX idx_nodo_proyecto ON nodos(proyecto_id);
CREATE INDEX idx_nodo_padre ON nodos(padre_id);
CREATE INDEX idx_nodo_concepto ON nodos(codigo_concepto);
CREATE INDEX idx_nodo_nivel_orden ON nodos(nivel, orden);

-- =====================================================
-- TABLA: mediciones
-- =====================================================

CREATE TYPE tipo_medicion AS ENUM (
    'NORMAL',
    'PARCIAL',
    'ACUMULADA'
);

CREATE TABLE IF NOT EXISTS mediciones (
    id SERIAL PRIMARY KEY,
    concepto_id INTEGER NOT NULL REFERENCES conceptos(id) ON DELETE CASCADE,

    -- Descripción
    comentario VARCHAR(500),
    tipo tipo_medicion DEFAULT 'NORMAL',

    -- Dimensiones
    unidades NUMERIC(14, 4) DEFAULT 1.0,
    largo NUMERIC(14, 4) DEFAULT 1.0,
    ancho NUMERIC(14, 4) DEFAULT 1.0,
    alto NUMERIC(14, 4) DEFAULT 1.0,

    -- Resultado
    subtotal NUMERIC(14, 4),

    -- Orden
    orden INTEGER NOT NULL
);

CREATE INDEX idx_medicion_concepto ON mediciones(concepto_id);
CREATE INDEX idx_medicion_orden ON mediciones(orden);

-- =====================================================
-- FUNCIONES Y TRIGGERS
-- =====================================================

-- Trigger para actualizar fecha_actualizacion en proyectos
CREATE OR REPLACE FUNCTION update_proyecto_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_proyecto_timestamp
BEFORE UPDATE ON proyectos
FOR EACH ROW
EXECUTE FUNCTION update_proyecto_timestamp();

-- Trigger para actualizar updated_at en conceptos
CREATE OR REPLACE FUNCTION update_concepto_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_concepto_timestamp
BEFORE UPDATE ON conceptos
FOR EACH ROW
EXECUTE FUNCTION update_concepto_timestamp();

-- =====================================================
-- VISTAS ÚTILES
-- =====================================================

-- Vista: Árbol completo con datos de conceptos
CREATE OR REPLACE VIEW vista_arbol_completo AS
WITH RECURSIVE arbol AS (
    -- Nodos raíz (sin padre)
    SELECT
        n.id,
        n.proyecto_id,
        n.padre_id,
        n.codigo_concepto,
        n.nivel,
        n.orden,
        n.cantidad,
        ARRAY[n.orden] as ruta_orden,
        c.tipo,
        c.nombre,
        c.resumen,
        c.unidad,
        c.precio,
        c.total,
        c.cantidad_total,
        c.importe_total
    FROM nodos n
    LEFT JOIN conceptos c ON n.codigo_concepto = c.codigo AND n.proyecto_id = c.proyecto_id
    WHERE n.padre_id IS NULL

    UNION ALL

    -- Nodos hijos (recursivo)
    SELECT
        n.id,
        n.proyecto_id,
        n.padre_id,
        n.codigo_concepto,
        n.nivel,
        n.orden,
        n.cantidad,
        a.ruta_orden || n.orden,
        c.tipo,
        c.nombre,
        c.resumen,
        c.unidad,
        c.precio,
        c.total,
        c.cantidad_total,
        c.importe_total
    FROM nodos n
    INNER JOIN arbol a ON n.padre_id = a.id
    LEFT JOIN conceptos c ON n.codigo_concepto = c.codigo AND n.proyecto_id = c.proyecto_id
)
SELECT * FROM arbol;

-- =====================================================
-- DATOS INICIALES
-- =====================================================

-- Usuario administrador por defecto
-- Password: admin123 (cambiar en producción)
INSERT INTO usuarios (username, email, password_hash, nombre_completo, es_admin)
VALUES (
    'admin',
    'admin@appmediciones.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5/z3qgV7n3Zk6',  -- admin123
    'Administrador',
    TRUE
) ON CONFLICT (username) DO NOTHING;

-- =====================================================
-- COMENTARIOS EN TABLAS
-- =====================================================

COMMENT ON SCHEMA appmediciones IS 'Schema para APPmediciones - Sistema de gestión de presupuestos';

COMMENT ON TABLE proyectos IS 'Proyectos de presupuesto';
COMMENT ON TABLE conceptos IS 'Conceptos (datos) - Capítulos, partidas, descompuestos, etc.';
COMMENT ON TABLE nodos IS 'Nodos (estructura jerárquica) - Define el árbol del presupuesto';
COMMENT ON TABLE mediciones IS 'Mediciones dimensionales de partidas';
COMMENT ON TABLE usuarios IS 'Usuarios del sistema';

COMMENT ON COLUMN nodos.padre_id IS 'ID del nodo padre (NULL = raíz)';
COMMENT ON COLUMN nodos.codigo_concepto IS 'Código del concepto al que apunta este nodo';
COMMENT ON COLUMN nodos.cantidad IS 'Cantidad del hijo en el padre (para descompuestos)';
COMMENT ON COLUMN conceptos.tipo IS 'Tipo: RAIZ, CAPITULO, SUBCAPITULO, PARTIDA, DESCOMPUESTO, MANO_OBRA, MATERIAL, MAQUINARIA, AUXILIAR';

-- =====================================================
-- FIN DEL SCRIPT
-- =====================================================

COMMIT;

-- Verificación
SELECT 'Schema appmediciones creado exitosamente' AS status;
SELECT table_name FROM information_schema.tables WHERE table_schema = 'appmediciones' ORDER BY table_name;
