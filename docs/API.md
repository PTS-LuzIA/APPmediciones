# APPmediciones - API Documentation

**Base URL**: `http://localhost:8001`
**API Version**: 1.0.0
**Authentication**: JWT Bearer Token

## 📚 Table of Contents

1. [Authentication](#authentication)
2. [Proyectos](#proyectos)
3. [Nodos](#nodos)
4. [Conceptos](#conceptos)
5. [Procesamiento](#procesamiento)

---

## Authentication

### POST `/api/auth/login`
Login and get JWT token.

**Request Body:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@appmediciones.local",
    "nombre_completo": "Administrador",
    "es_admin": true,
    "activo": true,
    "fecha_creacion": "2026-01-27T10:00:00",
    "fecha_actualizacion": "2026-01-27T10:00:00"
  }
}
```

### POST `/api/auth/register`
Register a new user.

**Request Body:**
```json
{
  "username": "usuario1",
  "email": "usuario1@example.com",
  "password": "password123",
  "nombre_completo": "Usuario Uno"
}
```

**Response:** Same as user object (without token)

### GET `/api/auth/me`
Get current authenticated user.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:** User object

### PUT `/api/auth/me`
Update current user information.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "email": "newemail@example.com",
  "nombre_completo": "Nuevo Nombre",
  "password": "newpassword123"
}
```

---

## Proyectos

### GET `/api/proyectos`
List all projects for current user.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 100)

**Response:**
```json
[
  {
    "id": 1,
    "usuario_id": 1,
    "nombre": "Proyecto de Prueba",
    "descripcion": "Descripción del proyecto",
    "pdf_path": "/uploads/u1_p1_presupuesto.pdf",
    "fase_actual": 2,
    "total_presupuesto": 150000.50,
    "fecha_creacion": "2026-01-27T10:00:00",
    "fecha_actualizacion": "2026-01-27T11:00:00"
  }
]
```

### POST `/api/proyectos`
Create a new project.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "nombre": "Nuevo Proyecto",
  "descripcion": "Descripción del nuevo proyecto"
}
```

**Response:** Project object (201 Created)

### GET `/api/proyectos/{id}`
Get a project by ID with statistics.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 1,
  "nombre": "Proyecto de Prueba",
  "descripcion": "...",
  "usuario_id": 1,
  "pdf_path": "...",
  "fase_actual": 2,
  "total_presupuesto": 150000.50,
  "num_capitulos": 5,
  "num_partidas": 42,
  "num_mediciones": 120,
  "fecha_creacion": "...",
  "fecha_actualizacion": "..."
}
```

### PUT `/api/proyectos/{id}`
Update a project.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "nombre": "Proyecto Actualizado",
  "descripcion": "Nueva descripción",
  "fase_actual": 3,
  "total_presupuesto": 175000.00
}
```

### DELETE `/api/proyectos/{id}`
Delete a project (204 No Content).

**Headers:**
```
Authorization: Bearer <token>
```

### GET `/api/proyectos/{id}/arbol`
Get complete project tree structure.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "proyecto": { ... },
  "arbol": [
    {
      "nodo_id": 1,
      "codigo_concepto": "01",
      "nivel": 1,
      "orden": 1,
      "padre_id": null,
      "concepto_tipo": "CAPITULO",
      "concepto_nombre": "DEMOLICIONES",
      "concepto_total": 25000.50,
      "ruta": "01",
      "ruta_orden": "0001"
    }
  ]
}
```

### GET `/api/proyectos/{id}/estadisticas`
Get project statistics.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "num_nodos": 150,
  "num_conceptos": 145,
  "num_capitulos": 5,
  "num_subcapitulos": 25,
  "num_partidas": 115,
  "num_descompuestos": 0,
  "num_mediciones": 320,
  "total_presupuesto": 150000.50,
  "niveles_profundidad": 4
}
```

---

## Nodos

### POST `/api/nodos?proyecto_id={id}`
Create a new nodo.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `proyecto_id`: Project ID (required)

**Request Body:**
```json
{
  "codigo_concepto": "01.01",
  "padre_id": 1,
  "nivel": 2,
  "orden": 1,
  "cantidad": 1.0
}
```

**Response:** Nodo object (201 Created)

### GET `/api/nodos/{id}`
Get a nodo by ID.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 1,
  "proyecto_id": 1,
  "codigo_concepto": "01.01",
  "padre_id": null,
  "nivel": 1,
  "orden": 1,
  "cantidad": 1.0,
  "fecha_creacion": "...",
  "fecha_actualizacion": "..."
}
```

### PUT `/api/nodos/{id}`
Update a nodo.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "cantidad": 2.5,
  "orden": 3
}
```

### DELETE `/api/nodos/{id}`
Delete a nodo (204 No Content).

**Headers:**
```
Authorization: Bearer <token>
```

### POST `/api/nodos/{id}/mover`
Move a nodo to new parent or position.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "nuevo_padre_id": 5,
  "nuevo_orden": 2
}
```

### GET `/api/nodos/{id}/hijos`
List all children of a nodo.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:** Array of nodo objects

---

## Conceptos

### GET `/api/conceptos?proyecto_id={id}`
List all conceptos for a project.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `proyecto_id`: Project ID (required)
- `tipo`: Filter by tipo (CAPITULO, SUBCAPITULO, PARTIDA, etc.)
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 100)

**Response:**
```json
[
  {
    "id": 1,
    "proyecto_id": 1,
    "codigo": "01",
    "tipo": "CAPITULO",
    "nombre": "DEMOLICIONES",
    "resumen": "Demoliciones y movimientos de tierra",
    "descripcion": null,
    "unidad": null,
    "precio": null,
    "cantidad_total": null,
    "importe_total": null,
    "total": 25000.50,
    "fecha_creacion": "...",
    "fecha_actualizacion": "..."
  }
]
```

### POST `/api/conceptos?proyecto_id={id}`
Create a new concepto.

**Headers:**
```
Authorization: Bearer <token>
```

**Query Parameters:**
- `proyecto_id`: Project ID (required)

**Request Body:**
```json
{
  "codigo": "01.02.05",
  "tipo": "PARTIDA",
  "nombre": "Excavación zanjas",
  "resumen": "Excavación de zanjas a máquina",
  "unidad": "m3",
  "precio": 25.50,
  "cantidad_total": 150.0,
  "importe_total": 3825.00
}
```

**Response:** Concepto object (201 Created)

### GET `/api/conceptos/{id}`
Get a concepto by ID.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:** Concepto object

### PUT `/api/conceptos/{id}`
Update a concepto.

**Headers:**
```
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "nombre": "Nombre actualizado",
  "precio": 27.00,
  "cantidad_total": 175.0,
  "importe_total": 4725.00
}
```

### DELETE `/api/conceptos/{id}`
Delete a concepto (204 No Content).

**Headers:**
```
Authorization: Bearer <token>
```

**Note:** Cannot delete if concepto is being used by any nodo.

### GET `/api/conceptos/{id}/usos`
Get where a concepto is being used.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": 1,
  "codigo": "01.02.05",
  "tipo": "PARTIDA",
  "nombre": "...",
  "num_usos": 3,
  "nodos_ids": [15, 28, 42],
  ...
}
```

---

## Procesamiento

### POST `/api/procesamiento/{proyecto_id}/upload-pdf`
Upload a PDF file to a project.

**Headers:**
```
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

**Form Data:**
- `file`: PDF file

**Response:**
```json
{
  "proyecto_id": 1,
  "pdf_path": "/uploads/u1_p1_presupuesto.pdf",
  "mensaje": "PDF uploaded successfully: u1_p1_presupuesto.pdf"
}
```

### POST `/api/procesamiento/{proyecto_id}/fase1`
Execute Fase 1: Extract structure.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "fase": 1,
  "proyecto_id": 1,
  "exito": true,
  "mensaje": "Fase 1 completed successfully",
  "titulo_proyecto": "PROYECTO DE CONSTRUCCIÓN",
  "num_conceptos": 25,
  "num_nodos": 25,
  "conceptos": [...],
  "datos": {...}
}
```

### POST `/api/procesamiento/{proyecto_id}/fase2`
Execute Fase 2: Extract partidas.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "fase": 2,
  "proyecto_id": 1,
  "exito": true,
  "mensaje": "Fase 2 completed successfully",
  "num_partidas": 115,
  "partidas": [...],
  "datos": {...}
}
```

### POST `/api/procesamiento/{proyecto_id}/fase3`
Execute Fase 3: Calculate totals and detect discrepancies.

**Headers:**
```
Authorization: Bearer <token>
```

**Response:**
```json
{
  "fase": 3,
  "proyecto_id": 1,
  "exito": true,
  "mensaje": "Fase 3 completed successfully",
  "total_presupuesto": 150000.50,
  "num_discrepancias": 2,
  "discrepancias": [
    {
      "codigo": "01.02",
      "diferencia": 125.50,
      "total_calculado": 12500.00,
      "total_pdf": 12625.50
    }
  ],
  "datos": {...}
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Error message describing what went wrong"
}
```

### 401 Unauthorized
```json
{
  "detail": "Could not validate credentials"
}
```

### 403 Forbidden
```json
{
  "detail": "Not authorized to access this resource"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal Server Error",
  "detail": "Error message (only in development mode)"
}
```

---

## Testing the API

### Using Swagger UI
1. Go to: http://localhost:8001/docs
2. Click "Authorize" button
3. Login and copy the token
4. Paste token in format: `Bearer <token>`
5. Try different endpoints

### Using curl

**Login:**
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

**List projects:**
```bash
curl -X GET http://localhost:8001/api/proyectos \
  -H "Authorization: Bearer <token>"
```

**Create project:**
```bash
curl -X POST http://localhost:8001/api/proyectos \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Test Project","descripcion":"Testing API"}'
```

---

## Authentication Flow

1. **Register** (optional): POST `/api/auth/register` with user data
2. **Login**: POST `/api/auth/login` with username/password
3. **Get Token**: Save the `access_token` from response
4. **Use Token**: Include in all requests: `Authorization: Bearer <token>`
5. **Token expires** after 480 minutes (8 hours) by default

---

## Notes

- All endpoints require authentication except `/health` and auth endpoints
- Users can only access their own projects (unless admin)
- JWT tokens expire after 8 hours (configurable in settings)
- File uploads limited to PDF format
- Cascading deletes: Deleting a proyecto deletes all nodos, conceptos, mediciones
- Conceptos cannot be deleted if they are referenced by any nodo

---

_For more details, visit the interactive documentation at http://localhost:8001/docs_
