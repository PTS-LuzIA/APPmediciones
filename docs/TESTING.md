# APPmediciones - Testing Guide

This guide provides step-by-step instructions for testing the APPmediciones backend API.

## Prerequisites

- Backend running on http://localhost:8001
- PostgreSQL database set up and migrations applied
- Admin user exists (default: username=`admin`, password=`admin123`)

## Testing Tools

### 1. Swagger UI (Recommended for Manual Testing)
- **URL**: http://localhost:8001/docs
- **Advantages**: Interactive, no setup required, automatic schema validation
- **Best for**: Quick manual testing, exploring API

### 2. curl (Command Line)
- **Advantages**: Scriptable, works everywhere
- **Best for**: Automation, CI/CD pipelines

### 3. Postman/Insomnia
- **Advantages**: Collections, environments, history
- **Best for**: Complex workflows, team collaboration

---

## Test Scenarios

### Scenario 1: User Registration and Authentication

#### Step 1: Register a New User

**Using Swagger:**
1. Go to http://localhost:8001/docs
2. Find `POST /api/auth/register`
3. Click "Try it out"
4. Enter:
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "testpass123",
  "nombre_completo": "Test User"
}
```
5. Click "Execute"
6. Verify response status: **201 Created**

**Using curl:**
```bash
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "testpass123",
    "nombre_completo": "Test User"
  }'
```

**Expected Result:**
```json
{
  "id": 2,
  "username": "testuser",
  "email": "test@example.com",
  "nombre_completo": "Test User",
  "es_admin": false,
  "activo": true,
  "fecha_creacion": "2026-01-27T...",
  "fecha_actualizacion": "2026-01-27T..."
}
```

#### Step 2: Login

**Using Swagger:**
1. Find `POST /api/auth/login`
2. Click "Try it out"
3. Enter:
```json
{
  "username": "testuser",
  "password": "testpass123"
}
```
4. Click "Execute"
5. **Copy the `access_token`** from response

**Using curl:**
```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }' | jq -r '.access_token'
```

**Expected Result:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 2,
    "username": "testuser",
    ...
  }
}
```

#### Step 3: Authorize in Swagger

1. Click the **"Authorize"** button (🔒) at the top
2. Enter: `Bearer <your-token>` (replace `<your-token>` with the actual token)
3. Click "Authorize"
4. Close the dialog

Now all subsequent requests will include the token automatically.

#### Step 4: Get Current User Info

**Using Swagger:**
1. Find `GET /api/auth/me`
2. Click "Try it out" → "Execute"
3. Verify you get your user info

---

### Scenario 2: Project Management

#### Step 1: Create a Project

**Using Swagger:**
1. Find `POST /api/proyectos`
2. Click "Try it out"
3. Enter:
```json
{
  "nombre": "Proyecto Test 1",
  "descripcion": "Proyecto de prueba para testing"
}
```
4. Click "Execute"
5. **Note the `id`** in the response (e.g., `id: 1`)

**Expected Result:**
```json
{
  "id": 1,
  "usuario_id": 2,
  "nombre": "Proyecto Test 1",
  "descripcion": "Proyecto de prueba para testing",
  "pdf_path": null,
  "fase_actual": 0,
  "total_presupuesto": null,
  "fecha_creacion": "...",
  "fecha_actualizacion": "..."
}
```

#### Step 2: List Projects

**Using Swagger:**
1. Find `GET /api/proyectos`
2. Click "Try it out" → "Execute"
3. Verify you see your created project

#### Step 3: Get Project Details

**Using Swagger:**
1. Find `GET /api/proyectos/{id}`
2. Enter the project ID from Step 1
3. Click "Execute"
4. Verify you get project with statistics (num_capitulos, num_partidas, etc.)

#### Step 4: Update Project

**Using Swagger:**
1. Find `PUT /api/proyectos/{id}`
2. Enter the project ID
3. Enter:
```json
{
  "nombre": "Proyecto Test 1 - Actualizado",
  "descripcion": "Descripción actualizada"
}
```
4. Click "Execute"
5. Verify changes are reflected

---

### Scenario 3: Concepto Management

#### Step 1: Create a Capítulo

**Using Swagger:**
1. Find `POST /api/conceptos`
2. Query parameter `proyecto_id`: Enter your project ID (e.g., 1)
3. Request body:
```json
{
  "codigo": "01",
  "tipo": "CAPITULO",
  "nombre": "DEMOLICIONES",
  "resumen": "Demoliciones y movimientos de tierra",
  "total": 25000.00
}
```
4. Click "Execute"
5. **Note the concepto ID**

#### Step 2: Create a Subcapítulo

```json
{
  "codigo": "01.01",
  "tipo": "SUBCAPITULO",
  "nombre": "DEMOLICIONES MANUALES",
  "resumen": "Demoliciones realizadas manualmente",
  "total": 5000.00
}
```

#### Step 3: Create a Partida

```json
{
  "codigo": "01.01.01",
  "tipo": "PARTIDA",
  "nombre": "Demolición muro ladrillo",
  "resumen": "Demolición manual de muro de ladrillo",
  "unidad": "m2",
  "precio": 25.50,
  "cantidad_total": 150.0,
  "importe_total": 3825.00
}
```

#### Step 4: List Conceptos

**Using Swagger:**
1. Find `GET /api/conceptos`
2. Query parameter `proyecto_id`: Enter your project ID
3. Optional: Filter by `tipo=PARTIDA`
4. Click "Execute"
5. Verify you see all created conceptos

---

### Scenario 4: Nodo (Tree Structure) Management

#### Step 1: Create Root Nodo (Capítulo)

**Using Swagger:**
1. Find `POST /api/nodos`
2. Query parameter `proyecto_id`: Enter your project ID (e.g., 1)
3. Request body:
```json
{
  "codigo_concepto": "01",
  "padre_id": null,
  "nivel": 1,
  "orden": 1,
  "cantidad": 1.0
}
```
4. Click "Execute"
5. **Note the nodo ID** (e.g., `id: 1`)

#### Step 2: Create Child Nodo (Subcapítulo)

```json
{
  "codigo_concepto": "01.01",
  "padre_id": 1,
  "nivel": 2,
  "orden": 1,
  "cantidad": 1.0
}
```
**Note the nodo ID** (e.g., `id: 2`)

#### Step 3: Create Grandchild Nodo (Partida)

```json
{
  "codigo_concepto": "01.01.01",
  "padre_id": 2,
  "nivel": 3,
  "orden": 1,
  "cantidad": 1.0
}
```

#### Step 4: Get Project Tree

**Using Swagger:**
1. Find `GET /api/proyectos/{id}/arbol`
2. Enter your project ID
3. Click "Execute"
4. Verify you see hierarchical tree structure:
   - 01 (nivel 1)
     - 01.01 (nivel 2, padre_id: 1)
       - 01.01.01 (nivel 3, padre_id: 2)

#### Step 5: List Children of a Nodo

**Using Swagger:**
1. Find `GET /api/nodos/{id}/hijos`
2. Enter nodo ID `1` (the capítulo)
3. Click "Execute"
4. Verify you see the subcapítulo (01.01) as a child

#### Step 6: Move a Nodo

**Using Swagger:**
1. Create another capítulo at root level (e.g., código "02")
2. Find `POST /api/nodos/{id}/mover`
3. Enter the subcapítulo nodo ID (e.g., 2)
4. Request body:
```json
{
  "nuevo_padre_id": <id-of-capitulo-02>,
  "nuevo_orden": 1
}
```
5. Click "Execute"
6. Get tree again to verify the move

---

### Scenario 5: PDF Processing

#### Step 1: Upload PDF

**Using Swagger:**
1. Find `POST /api/procesamiento/{proyecto_id}/upload-pdf`
2. Enter your project ID
3. Click "Try it out"
4. Click "Choose File" and select a PDF presupuesto
5. Click "Execute"

**Using curl:**
```bash
curl -X POST http://localhost:8001/api/procesamiento/1/upload-pdf \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/presupuesto.pdf"
```

**Expected Result:**
```json
{
  "proyecto_id": 1,
  "pdf_path": "/uploads/u2_p1_presupuesto.pdf",
  "mensaje": "PDF uploaded successfully: u2_p1_presupuesto.pdf"
}
```

#### Step 2: Execute Fase 1 (Extract Structure)

**Using Swagger:**
1. Find `POST /api/procesamiento/{proyecto_id}/fase1`
2. Enter your project ID
3. Click "Execute"
4. Wait for processing (may take 10-30 seconds)

**Expected Result:**
```json
{
  "fase": 1,
  "proyecto_id": 1,
  "exito": true,
  "mensaje": "Fase 1 completed successfully",
  "titulo_proyecto": "PROYECTO DE CONSTRUCCIÓN...",
  "num_conceptos": 25,
  "num_nodos": 25,
  "conceptos": [...],
  "datos": {...}
}
```

**Verify:**
- Get project tree: `GET /api/proyectos/1/arbol`
- Should see capítulos and subcapítulos
- List conceptos: Should see CAPITULO and SUBCAPITULO types

#### Step 3: Execute Fase 2 (Extract Partidas)

**Using Swagger:**
1. Find `POST /api/procesamiento/{proyecto_id}/fase2`
2. Enter your project ID
3. Click "Execute"
4. Wait for processing (may take 30-60 seconds)

**Expected Result:**
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

**Verify:**
- Get project tree: Should now include partidas
- List conceptos filtered by `tipo=PARTIDA`: Should see all partidas
- Get statistics: `GET /api/proyectos/1/estadisticas`

#### Step 4: Execute Fase 3 (Calculate Totals)

**Using Swagger:**
1. Find `POST /api/procesamiento/{proyecto_id}/fase3`
2. Enter your project ID
3. Click "Execute"
4. Wait for processing

**Expected Result:**
```json
{
  "fase": 3,
  "proyecto_id": 1,
  "exito": true,
  "mensaje": "Fase 3 completed successfully",
  "total_presupuesto": 150000.50,
  "num_discrepancias": 2,
  "discrepancias": [...],
  "datos": {...}
}
```

**Verify:**
- Project `total_presupuesto` should be updated
- Check for discrepancies between calculated and PDF totals

---

### Scenario 6: Concepto Usage Tracking

#### Step 1: Check Concepto Usage

**Using Swagger:**
1. Get a concepto ID that is used in the tree
2. Find `GET /api/conceptos/{id}/usos`
3. Enter the concepto ID
4. Click "Execute"

**Expected Result:**
```json
{
  "id": 5,
  "codigo": "01.01",
  "tipo": "SUBCAPITULO",
  "nombre": "...",
  "num_usos": 1,
  "nodos_ids": [2],
  ...
}
```

#### Step 2: Try to Delete a Used Concepto

**Using Swagger:**
1. Find `DELETE /api/conceptos/{id}`
2. Enter a concepto ID that is in use
3. Click "Execute"

**Expected Result:** 400 Bad Request
```json
{
  "detail": "Cannot delete concepto: it is used by 1 nodo(s)"
}
```

#### Step 3: Delete an Unused Concepto

1. Create a concepto that is not added to the tree
2. Try to delete it
3. Should succeed with 204 No Content

---

## Automated Testing Script

Save this as `test_api.sh`:

```bash
#!/bin/bash

BASE_URL="http://localhost:8001"

echo "=== Testing APPmediciones API ==="

# 1. Login
echo "1. Login..."
TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access_token')

if [ -z "$TOKEN" ]; then
  echo "❌ Login failed"
  exit 1
fi
echo "✓ Login successful"

# 2. Create Project
echo "2. Creating project..."
PROJECT_ID=$(curl -s -X POST "$BASE_URL/api/proyectos" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Test Project","descripcion":"Automated test"}' \
  | jq -r '.id')

echo "✓ Project created: ID=$PROJECT_ID"

# 3. Create Concepto
echo "3. Creating concepto..."
CONCEPTO_ID=$(curl -s -X POST "$BASE_URL/api/conceptos?proyecto_id=$PROJECT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"codigo":"01","tipo":"CAPITULO","nombre":"TEST CAPITULO","total":10000}' \
  | jq -r '.id')

echo "✓ Concepto created: ID=$CONCEPTO_ID"

# 4. Create Nodo
echo "4. Creating nodo..."
NODO_ID=$(curl -s -X POST "$BASE_URL/api/nodos?proyecto_id=$PROJECT_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"codigo_concepto":"01","padre_id":null,"nivel":1,"orden":1,"cantidad":1.0}' \
  | jq -r '.id')

echo "✓ Nodo created: ID=$NODO_ID"

# 5. Get Project Tree
echo "5. Getting project tree..."
curl -s -X GET "$BASE_URL/api/proyectos/$PROJECT_ID/arbol" \
  -H "Authorization: Bearer $TOKEN" | jq '.arbol'

echo "✓ Tree retrieved"

# 6. Get Statistics
echo "6. Getting statistics..."
curl -s -X GET "$BASE_URL/api/proyectos/$PROJECT_ID/estadisticas" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo "✓ Statistics retrieved"

echo "=== All tests passed! ==="
```

Make it executable:
```bash
chmod +x test_api.sh
./test_api.sh
```

---

## Common Issues and Solutions

### Issue: 401 Unauthorized
**Solution:**
- Verify token is valid (not expired)
- Re-login to get new token
- Check token format: `Bearer <token>` (with space)

### Issue: 403 Forbidden
**Solution:**
- Verify you're the owner of the resource
- Or that you're an admin user
- Check user permissions

### Issue: 404 Not Found
**Solution:**
- Verify the ID exists
- Check you're using the correct endpoint
- Ensure resource wasn't deleted

### Issue: 400 Bad Request - Cannot delete concepto
**Solution:**
- Check `/api/conceptos/{id}/usos` to see where it's used
- Delete the nodos using it first
- Or keep the concepto

### Issue: 500 Internal Server Error
**Solution:**
- Check backend logs: `tail -f logs/backend.log`
- Verify database connection
- Check for missing data in request

---

## Performance Testing

### Load Test with Apache Bench

```bash
# Login first to get token
TOKEN="<your-token>"

# Test list proyectos (100 requests, 10 concurrent)
ab -n 100 -c 10 \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/proyectos
```

### Expected Performance
- Simple GET: < 50ms
- POST with DB write: < 100ms
- Tree query: < 200ms
- PDF processing:
  - Fase 1: 10-30 seconds
  - Fase 2: 30-90 seconds
  - Fase 3: 5-15 seconds

---

## Next Steps

After manual testing is complete:
1. Write unit tests (pytest)
2. Write integration tests
3. Set up CI/CD pipeline
4. Frontend integration testing
5. End-to-end testing

---

_For more information, see [API.md](API.md) for complete API documentation._
