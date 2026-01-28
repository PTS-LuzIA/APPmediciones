# APPmediciones

**Estado**: ✅ **BACKEND COMPLETO** - Ready for Testing
**Versión**: 1.0.0
**Fecha**: 2026-01-27

Sistema de gestión de presupuestos de construcción basado en estructura jerárquica (compatible con BC3/FIEBDC-3).

## 📖 Documentation Quick Links

- 🚀 **[QUICKSTART.md](QUICKSTART.md)** - Step-by-step setup instructions
- 📋 **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - What has been implemented
- 🏗️ **[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)** - Detailed architecture
- 🛣️ **[docs/API.md](docs/API.md)** - Complete API reference (35 endpoints)
- 🧪 **[docs/TESTING.md](docs/TESTING.md)** - Testing guide with examples
- 📊 **[STATUS.md](STATUS.md)** - Current state and roadmap

## 🏗️ Arquitectura

Este proyecto utiliza una **estructura de dos tablas** para máxima flexibilidad:

1. **Tabla `nodos`**: Define la estructura jerárquica (árbol)
2. **Tabla `conceptos`**: Contiene los datos de cada elemento (capítulos, partidas, descompuestos)

### Ventajas de esta arquitectura:
- ✅ Soporte nativo para descompuestos (partidas con sub-elementos)
- ✅ Un concepto puede aparecer en múltiples lugares del presupuesto
- ✅ Compatible con formato BC3/FIEBDC-3
- ✅ Jerarquía ilimitada (capítulo → subcap → partida → descompuesto)
- ✅ Partidas pueden estar directamente en capítulos sin necesidad de subcapítulos dummy

Ver [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para más detalles.

## 🔗 Proyecto Legacy

Este proyecto es una reescritura limpia del sistema original.

**Si necesitas consultar código legacy o parsers antiguos:**
- Proyecto original: `/Volumes/DATOS_IA/G_Drive_LuzIA/IA/Proyectos/MVP/Mediciones`
- Código reutilizable:
  - PDF Extractor: `Mediciones/src/parser_v2/pdf_extractor.py`
  - Structure Parsers: `Mediciones/src/parser_v2/structure_parsers/`
  - Line Classifier: `Mediciones/src/parser_v2/line_classifier.py`
  - Auth/JWT: `Mediciones/src/api_v2/auth.py`

## 🚀 Quick Start (Desarrollo Local)

### 1. Base de Datos
```bash
# Crear base de datos
psql -U postgres
CREATE DATABASE appmediciones_db;
\q

# Ejecutar migrations
psql -U postgres -d appmediciones_db -f backend/database/migrations/001_initial_schema.sql
```

### 2. Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configurar variables de entorno (opcional, hay defaults)
cp .env.example .env

# Iniciar servidor
uvicorn main:app --reload --port 8001
```

Backend disponible en: http://localhost:8001
API docs: http://localhost:8001/docs

### 3. Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend disponible en: http://localhost:3001

## 📊 Modelo de Datos

### Nodo (Estructura del árbol)
```python
Nodo:
  - id
  - proyecto_id
  - padre_id          # NULL = nodo raíz
  - codigo_concepto   # Referencia al concepto
  - nivel             # 0, 1, 2, 3...
  - orden             # Orden entre hermanos
  - cantidad          # Cantidad del hijo en el padre
```

### Concepto (Datos del elemento)
```python
Concepto:
  - id
  - proyecto_id
  - codigo            # Único por proyecto
  - tipo              # RAIZ, CAPITULO, SUBCAPITULO, PARTIDA, DESCOMPUESTO, etc.
  - nombre
  - resumen
  - descripcion
  - unidad
  - precio
  - total             # Para capítulos/subcapítulos
  - total_calculado
```

### Medicion (Mediciones auxiliares)
```python
Medicion:
  - id
  - concepto_id
  - comentario
  - tipo              # NORMAL, PARCIAL, ACUMULADA
  - unidades          # N
  - largo
  - ancho
  - alto
  - subtotal          # N × Largo × Ancho × Alto
```

Ver [docs/MODELO_DATOS.md](docs/MODELO_DATOS.md) para diagrama ER completo.

## 🎯 Sistema de Fases

El procesamiento de PDFs se divide en 4 fases:

1. **Fase 1**: Extracción de estructura jerárquica (capítulos/subcapítulos)
2. **Fase 2**: Clasificación de líneas y extracción de partidas
3. **Fase 3**: Cálculo recursivo de totales y validación
4. **Fase 4**: Resolución de discrepancias con IA (opcional)

## 📝 Diferencias vs Proyecto Legacy

| Aspecto | Legacy (Mediciones) | Nuevo (APPmediciones) |
|---------|---------------------|----------------------|
| **Estructura** | 3 tablas separadas | 2 tablas (nodos + conceptos) |
| **Jerarquía** | Semi-plana con nivel | Árbol real con padre_id |
| **Descompuestos** | No soportado | Soportado nativamente |
| **BC3** | No compatible | Compatible |
| **Partidas en capítulo** | Requiere subcapítulo dummy | Natural |
| **Reutilización** | No | Sí (mismo concepto, múltiples nodos) |
| **Schema BD** | `v2` | `appmediciones` |
| **Puerto Backend** | 8000 | 8001 |
| **Puerto Frontend** | 3000 | 3001 |

## 🛠️ Stack Tecnológico

### Backend
- **Framework**: FastAPI 0.109+
- **ORM**: SQLAlchemy 2.0+
- **Database**: PostgreSQL 15+
- **Auth**: JWT (python-jose)
- **PDF**: PyMuPDF + pdfplumber
- **Python**: 3.12+

### Frontend
- **Framework**: Next.js 14
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui
- **State**: React Query + Zustand

## 📂 Estructura del Proyecto

```
APPmediciones/
├── backend/
│   ├── models/              # Modelos SQLAlchemy
│   ├── database/            # Gestión de BD y queries
│   ├── parsers/             # Procesamiento de PDFs
│   ├── services/            # Lógica de negocio
│   ├── api/                 # FastAPI routes y schemas
│   └── utils/               # Utilidades
├── frontend/
│   └── src/
│       ├── app/             # Next.js app router
│       └── components/      # Componentes React
├── docs/                    # Documentación
├── tests/                   # Tests unitarios e integración
├── logs/                    # Logs de la aplicación
└── uploads/                 # PDFs subidos por usuarios
```

## 🧪 Testing

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## 🐳 Docker (Pre-Producción)

Para desplegar en producción, usar Docker Compose:

```bash
docker-compose up -d
```

(Configuración Docker pendiente - en fase de desarrollo usamos setup local)

## 📄 Licencia

[Especificar licencia]

## 👥 Contribuir

1. Fork del proyecto
2. Crear branch (`git checkout -b feature/nueva-feature`)
3. Commit cambios (`git commit -m 'Add nueva feature'`)
4. Push al branch (`git push origin feature/nueva-feature`)
5. Abrir Pull Request

## 📞 Soporte

Para dudas o problemas, consultar la documentación en `/docs` o abrir un issue.
