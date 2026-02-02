# Resolución de Discrepancias con IA

## Descripción

El sistema ahora incluye funcionalidad para resolver automáticamente discrepancias de presupuesto detectadas en Fase 3 utilizando Claude AI de Anthropic.

## Características

- **Análisis Individual**: Resuelve una discrepancia específica usando IA
- **Análisis Masivo**: Resuelve todas las discrepancias de un proyecto en una sola operación
- **Detección Inteligente**: Claude analiza el texto del PDF para encontrar partidas faltantes
- **Explicaciones Detalladas**: Cada resolución incluye una explicación de las partidas encontradas

## Configuración

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar API Key de Anthropic

Añade tu API key al archivo `.env`:

```bash
# AI / LLM Services
ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

**Obtener API Key:**
1. Regístrate en [console.anthropic.com](https://console.anthropic.com/)
2. Ve a Settings > API Keys
3. Crea una nueva API key
4. Copia la key y añádela al `.env`

### 3. Verificar Configuración

El sistema mostrará un warning en los logs si la API key no está configurada:
```
⚠️ ANTHROPIC_API_KEY no configurada. El servicio de IA no funcionará.
```

## Uso

### Desde el Frontend

#### Resolución Individual

1. Ejecuta **Fase 3** en la página de edición del proyecto
2. Si hay discrepancias, verás una tabla con el botón **"🤖 Resolver con IA"** en cada fila
3. Haz clic en el botón para analizar esa discrepancia específica
4. La IA buscará partidas faltantes en el PDF y mostrará sugerencias

#### Resolución Masiva

1. Ejecuta **Fase 3** para detectar discrepancias
2. Haz clic en **"🤖 Resolver Todas con IA"** en la parte inferior de la tabla
3. El sistema procesará todas las discrepancias automáticamente
4. Verás un resumen con:
   - Exitosas vs Fallidas
   - Total de partidas agregadas
   - Errores (si los hay)

### Desde la API

#### Resolver Discrepancia Individual

```bash
POST /api/proyectos/{proyecto_id}/resolver-discrepancia?tipo=subcapitulo&elemento_id=123
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "codigo": "C08.01",
  "nombre": "CALLE TENERIFE",
  "diferencia_original": 2619.18,
  "partidas_agregadas": 1,
  "total_agregado": 2619.18,
  "partidas_sugeridas": [
    {
      "codigo": "REC POZ",
      "resumen": "PUESTA EN RASANTE DE POZO O ARQUETA",
      "unidad": "ud",
      "cantidad": 18.0,
      "precio": 145.51,
      "importe": 2619.18
    }
  ],
  "explicacion": "Se encontró la partida REC POZ que explica la diferencia..."
}
```

#### Resolver Todas las Discrepancias

```bash
POST /api/proyectos/{proyecto_id}/resolver-discrepancias-bulk
Authorization: Bearer {token}
```

**Respuesta:**
```json
{
  "resueltas_exitosas": 7,
  "resueltas_fallidas": 0,
  "total_partidas_agregadas": 7,
  "errores": []
}
```

## Arquitectura

### Archivos Modificados/Creados

1. **`services/ia_service.py`** (NUEVO)
   - Servicio principal de IA
   - Integración con Claude API
   - Extracción inteligente de secciones del PDF
   - Construcción de prompts optimizados

2. **`services/procesamiento_service.py`** (MODIFICADO)
   - `ejecutar_fase3()` ahora devuelve discrepancias enriquecidas
   - Incluye información de la base de datos (id, tipo, nombre)
   - Calcula totales originales y calculados

3. **`api/routes/proyectos.py`** (MODIFICADO)
   - Nuevo endpoint: `/resolver-discrepancia`
   - Nuevo endpoint: `/resolver-discrepancias-bulk`

4. **`api/routes/procesamiento.py`** (MODIFICADO)
   - Fase 3 ahora incluye `total_original` y `total_calculado` en la respuesta

5. **`requirements.txt`** (MODIFICADO)
   - Añadida dependencia: `anthropic==0.40.0`

6. **`.env.example`** (MODIFICADO)
   - Añadida variable: `ANTHROPIC_API_KEY`

### Flujo de Trabajo

```
┌─────────────┐
│  Frontend   │
│  Fase 3     │
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│  POST /fase3         │
│                      │
│  Detecta             │
│  Discrepancias       │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────────┐
│  Usuario hace clic en    │
│  "Resolver con IA"       │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────────┐
│  POST /resolver-discrepancia │
│                              │
│  1. Obtiene datos del nodo   │
│  2. Lee texto del PDF        │
│  3. Llama a Claude AI        │
│  4. Parsea respuesta         │
│  5. Devuelve sugerencias     │
└──────────────────────────────┘
```

## Prompt Engineering

El servicio de IA utiliza un prompt optimizado que incluye:

1. **Contexto de la discrepancia**: Código, nombre, diferencia
2. **Partidas existentes**: Lista completa de lo ya detectado
3. **Extracto relevante del PDF**: Solo la sección correspondiente
4. **Formato de respuesta**: JSON estructurado
5. **Validación de importes**: La suma debe aproximarse a la diferencia

### Ejemplo de Prompt

```
Eres un experto en presupuestos de construcción. Analiza la siguiente discrepancia detectada:

**DISCREPANCIA DETECTADA:**
- Tipo: subcapitulo
- Código: C08.01
- Nombre: CALLE TENERIFE
- Total esperado (PDF): 110,289.85 €
- Total calculado (partidas): 107,670.67 €
- **Diferencia: 2,619.18 €**

**PARTIDAS YA DETECTADAS:**
- DEM06: CORTE PAVIMENTO EXISTENTE | 630 Ml × 1.12 € = 705.60 €
- U01AB100: DEMOLICIÓN Y LEVANTADO... | 630 m × 5.40 € = 3,402.00 €
...

**EXTRACTO DEL PDF (sección C08.01):**
...

**RESPONDE ÚNICAMENTE CON UN JSON** en este formato...
```

## Limitaciones y Consideraciones

### Limitaciones Actuales

- **No auto-agrega partidas**: Actualmente solo sugiere partidas, no las agrega automáticamente a la BD
- **Requiere texto extraído**: El PDF debe haberse procesado y el texto debe estar disponible
- **Costo por llamada**: Cada resolución consume tokens de Claude API (aprox. $0.003 por análisis)

### Mejoras Futuras

1. **Auto-agregar partidas**: Opción para agregar automáticamente las partidas sugeridas
2. **Caché de resultados**: Almacenar análisis previos para evitar re-análisis
3. **Validación humana**: Flujo de aprobación para partidas sugeridas
4. **Múltiples modelos**: Soporte para OpenAI GPT-4, etc.
5. **Análisis de confianza**: Score de confianza para cada partida sugerida

## Troubleshooting

### Error: "AI analysis failed: Servicio de IA no configurado"

**Solución**: Configura `ANTHROPIC_API_KEY` en el archivo `.env`

### Error: "No se encontró texto extraído del PDF"

**Solución**:
1. Verifica que existe el archivo en `backend/logs/extracted_pdfs/`
2. Re-ejecuta Fase 1 para generar el texto extraído

### Las partidas sugeridas no coinciden

**Posibles causas**:
- El PDF tiene formato inconsistente
- La sección extraída no incluye las partidas faltantes
- El prompt necesita ajustes

**Solución**: Revisa el extracto del PDF en `logs/extracted_pdfs/` y ajusta el método `_extraer_seccion_relevante()` si es necesario.

## Costos Estimados

### Claude Sonnet 3.5 (Modelo usado)

- **Input**: $3 por millón de tokens
- **Output**: $15 por millón de tokens

### Ejemplo de Uso

- **Prompt típico**: ~2,000 tokens input
- **Respuesta típica**: ~500 tokens output
- **Costo por análisis**: ~$0.013

**Análisis completo (7 discrepancias)**:
- Total: ~$0.091

## Soporte

Para problemas o preguntas:
1. Revisa los logs del backend: `backend/logs/`
2. Verifica la configuración en `.env`
3. Comprueba que la API key de Anthropic es válida

---

**Versión**: 1.0
**Última actualización**: 2026-01-29
