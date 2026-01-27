# APPmediciones - Quick Start Guide

Guía rápida para poner en marcha APPmediciones en entorno de desarrollo local.

## 📋 Pre-requisitos

- Python 3.12+
- PostgreSQL 15+
- Node.js 18+ (para frontend, más adelante)
- Git

## 🚀 Setup Inicial

### 1. Clonar/Navegar al Proyecto

```bash
cd /Volumes/DATOS_IA/G_Drive_LuzIA/IA/Proyectos/MVP/APPmediciones
```

### 2. Crear Base de Datos

```bash
# Conectar a PostgreSQL
psql -U postgres

# En el prompt de psql:
CREATE DATABASE appmediciones_db;
\q
```

### 3. Ejecutar Migrations

```bash
psql -U postgres -d appmediciones_db -f backend/database/migrations/001_initial_schema.sql
```

Deberías ver:
```
CREATE SCHEMA
CREATE TABLE
CREATE TABLE
...
status
-------------------------------------------------
Schema appmediciones creado exitosamente
```

### 4. Configurar Backend

```bash
cd backend

# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate  # En Mac/Linux
# o
venv\Scripts\activate  # En Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 5. Configurar Variables de Entorno (Opcional)

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar .env si necesitas cambiar algo
# Por defecto usa postgres local en puerto 5432
```

### 6. Iniciar Backend

```bash
# Desde backend/ con venv activado
uvicorn main:app --reload --port 8001
```

O directamente:

```bash
python main.py
```

Deberías ver:
```
============================================================
🚀 APPmediciones API v1.0.0
   Entorno: development
   Puerto: 8001
   Database: localhost:5432/appmediciones_db
============================================================
✓ Conexión a base de datos OK
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### 7. Verificar Instalación

Abre en tu navegador:

- **API Docs**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health
- **ReDoc**: http://localhost:8001/redoc

Deberías ver la documentación interactiva de FastAPI.

## 🧪 Probar la API

### Con curl:

```bash
# Health check
curl http://localhost:8001/health

# Respuesta esperada:
# {"status":"healthy","version":"1.0.0","environment":"development"}
```

### Con la interfaz Swagger (Recomendado):

1. Ve a http://localhost:8001/docs
2. Expande los endpoints disponibles
3. Prueba el endpoint `/health`
4. Haz click en "Try it out" → "Execute"

## 📊 Verificar Base de Datos

```bash
# Conectar a la base de datos
psql -U postgres -d appmediciones_db

# Listar tablas
\dt appmediciones.*

# Deberías ver:
#  Schema      |    Name     | Type  |  Owner
# -------------+-------------+-------+----------
#  appmediciones | conceptos   | table | postgres
#  appmediciones | mediciones  | table | postgres
#  appmediciones | nodos       | table | postgres
#  appmediciones | proyectos   | table | postgres
#  appmediciones | usuarios    | table | postgres

# Ver usuario admin por defecto
SELECT username, email, es_admin FROM appmediciones.usuarios;

# username | email                       | es_admin
# ---------+-----------------------------+----------
# admin    | admin@appmediciones.local   | t

# Salir
\q
```

## 📁 Estructura del Proyecto

```
APPmediciones/
├── backend/
│   ├── main.py              ← FastAPI app (INICIA AQUÍ)
│   ├── config.py            ← Configuración
│   ├── requirements.txt     ← Dependencias
│   │
│   ├── models/              ← Modelos SQLAlchemy
│   │   ├── proyecto.py
│   │   ├── nodo.py
│   │   ├── concepto.py
│   │   └── medicion.py
│   │
│   ├── database/
│   │   ├── connection.py    ← Conexión DB
│   │   ├── manager.py       ← CRUD operations
│   │   ├── queries.py       ← Queries recursivas
│   │   └── migrations/
│   │       └── 001_initial_schema.sql
│   │
│   ├── api/                 ← Endpoints (TODO)
│   └── parsers/             ← Procesamiento PDF (TODO)
│
├── docs/
│   └── ARQUITECTURA.md      ← Lee esto para entender el diseño
│
├── logs/                    ← Logs de la aplicación
├── uploads/                 ← PDFs subidos
└── README.md                ← Documentación principal
```

## 🔍 Próximos Pasos

Una vez que el backend está corriendo:

1. **Lee la arquitectura**: `docs/ARQUITECTURA.md`
2. **Crea un proyecto de prueba** (cuando estén los endpoints)
3. **Explora la API** en http://localhost:8001/docs
4. **Revisa los modelos** en `backend/models/`

## 🐛 Troubleshooting

### Error: "Database connection failed"

```bash
# Verificar que PostgreSQL está corriendo
psql -U postgres -l

# Verificar la base de datos existe
psql -U postgres -c "\l" | grep appmediciones

# Si no existe, crearla:
psql -U postgres -c "CREATE DATABASE appmediciones_db;"
```

### Error: "Module not found"

```bash
# Asegúrate de estar en el entorno virtual
source backend/venv/bin/activate

# Reinstalar dependencias
pip install -r backend/requirements.txt
```

### Error: "Port 8001 already in use"

```bash
# Encontrar proceso usando el puerto
lsof -i :8001

# Matar el proceso
kill -9 <PID>

# O cambiar puerto en backend/config.py o .env
API_PORT=8002
```

### Error: "Permission denied" en PostgreSQL

```bash
# Si tu usuario PostgreSQL no es 'postgres', ajusta en .env:
DATABASE_URL=postgresql://TU_USUARIO:TU_PASSWORD@localhost:5432/appmediciones_db
```

## 📚 Recursos

- **Documentación API**: http://localhost:8001/docs
- **Arquitectura**: docs/ARQUITECTURA.md
- **Proyecto Legacy**: /Volumes/DATOS_IA/G_Drive_LuzIA/IA/Proyectos/MVP/Mediciones

## 🎯 Para Desarrollo

### Activar logs detallados:

En `backend/.env`:
```bash
LOG_LEVEL=DEBUG
```

### Ejecutar con auto-reload:

```bash
uvicorn main:app --reload --port 8001
```

### Ver logs en tiempo real:

```bash
tail -f logs/backend.log
```

## ✅ Checklist de Verificación

- [ ] PostgreSQL corriendo
- [ ] Base de datos `appmediciones_db` creada
- [ ] Schema `appmediciones` con 5 tablas
- [ ] Usuario admin existe
- [ ] Entorno virtual creado y activado
- [ ] Dependencias instaladas
- [ ] Backend corriendo en puerto 8001
- [ ] API docs accesible en /docs
- [ ] Health check responde OK

Si todos los checks están OK, ¡estás listo para desarrollar! 🎉
