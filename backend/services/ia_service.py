"""
Servicio de IA para análisis de discrepancias con LLM externo (OpenRouter)
"""

import logging
import json
import time
import httpx
from pathlib import Path
from typing import Dict, Any, List, Optional

from config import settings

logger = logging.getLogger(__name__)

# Directorio para logs de LLM
LLM_LOGS_DIR = settings.LOGS_DIR / "llm_discrepancias"


class IAService:
    """
    Servicio para análisis de discrepancias usando OpenRouter API.
    Usa el modelo Gemini 2.5 Flash Lite por defecto.
    """

    def __init__(self):
        """Inicializa el servicio con la API key de OpenRouter"""
        self.api_key = settings.OPENROUTER_API_KEY
        if not self.api_key:
            logger.warning("⚠️ OPENROUTER_API_KEY no configurada. El servicio de IA no funcionará.")

        self.base_url = "https://openrouter.ai/api/v1"
        self.model = "google/gemini-2.5-flash-lite"

    def analizar_discrepancia(
        self,
        codigo: str,
        nombre: str,
        tipo: str,
        total_esperado: float,
        total_calculado: float,
        diferencia: float,
        partidas_existentes: List[Dict[str, Any]],
        texto_pdf: str
    ) -> Dict[str, Any]:
        """
        Analiza una discrepancia y sugiere partidas faltantes.

        Args:
            codigo: Código del capítulo/subcapítulo
            nombre: Nombre del capítulo/subcapítulo
            tipo: Tipo (capitulo o subcapitulo)
            total_esperado: Total declarado en el PDF
            total_calculado: Total calculado de partidas
            diferencia: Diferencia entre esperado y calculado
            partidas_existentes: Lista de partidas ya detectadas
            texto_pdf: Texto completo extraído del PDF

        Returns:
            Dict con análisis y partidas sugeridas
        """
        if not self.api_key:
            return {
                'exito': False,
                'error': 'Servicio de IA no configurado (falta OPENROUTER_API_KEY)',
                'partidas_sugeridas': []
            }

        try:
            # Construir prompt para el LLM
            prompt = self._construir_prompt_analisis(
                codigo, nombre, tipo, total_esperado, total_calculado,
                diferencia, partidas_existentes, texto_pdf
            )

            # Guardar prompt para debugging
            timestamp = int(time.time())
            LLM_LOGS_DIR.mkdir(parents=True, exist_ok=True)
            codigo_safe = codigo.replace('.', '_').replace('/', '_')

            prompt_file = LLM_LOGS_DIR / f"prompt_{tipo}_{codigo_safe}_{timestamp}.txt"
            try:
                with open(prompt_file, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                logger.info(f"💾 Prompt guardado: {prompt_file}")
            except Exception as e:
                logger.warning(f"No se pudo guardar prompt: {e}")

            # Llamar a OpenRouter API
            logger.info(f"🤖 Llamando a LLM ({self.model}) con temperatura=0 (determinismo máximo)")

            with httpx.Client(timeout=300.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"}
                    }
                )

                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(f"Error en LLM: {response.status_code} - {error_text}")
                    return {
                        'exito': False,
                        'error': f"Error del LLM: {response.status_code} - {error_text}",
                        'partidas_sugeridas': []
                    }

                result = response.json()
                respuesta_texto = result['choices'][0]['message']['content']

            # Guardar respuesta RAW del LLM para debugging
            raw_response_file = LLM_LOGS_DIR / f"raw_response_{tipo}_{codigo_safe}_{timestamp}.txt"
            try:
                with open(raw_response_file, 'w', encoding='utf-8') as f:
                    f.write(respuesta_texto)
                logger.info(f"💾 Respuesta RAW LLM guardada: {raw_response_file}")
            except Exception as e:
                logger.warning(f"No se pudo guardar respuesta RAW: {e}")

            # Parsear respuesta JSON
            try:
                resultado = json.loads(respuesta_texto)
            except json.JSONDecodeError:
                # Si la respuesta no es JSON válido, extraer JSON de la respuesta
                import re
                match = re.search(r'\{.*\}', respuesta_texto, re.DOTALL)
                if match:
                    resultado = json.loads(match.group())
                else:
                    resultado = {'partidas_sugeridas': [], 'explicacion': respuesta_texto}

            # Guardar respuesta parseada del LLM para debugging
            response_file = LLM_LOGS_DIR / f"response_{tipo}_{codigo_safe}_{timestamp}.json"
            try:
                with open(response_file, 'w', encoding='utf-8') as f:
                    json.dump(resultado, f, indent=2, ensure_ascii=False)
                logger.info(f"💾 Respuesta LLM parseada guardada: {response_file}")
            except Exception as e:
                logger.warning(f"No se pudo guardar respuesta parseada: {e}")

            logger.info(f"✓ IA analizó discrepancia {codigo}: {len(resultado.get('partidas_sugeridas', []))} partidas sugeridas")

            return {
                'exito': True,
                'partidas_sugeridas': resultado.get('partidas_sugeridas', []),
                'explicacion': resultado.get('explicacion', ''),
                'total_sugerido': sum(p.get('importe', 0) for p in resultado.get('partidas_sugeridas', []))
            }

        except Exception as e:
            logger.error(f"Error al analizar discrepancia con IA: {e}", exc_info=True)
            return {
                'exito': False,
                'error': str(e),
                'partidas_sugeridas': []
            }

    def _construir_prompt_analisis(
        self,
        codigo: str,
        nombre: str,
        tipo: str,
        total_esperado: float,
        total_calculado: float,
        diferencia: float,
        partidas_existentes: List[Dict[str, Any]],
        texto_pdf: str
    ) -> str:
        """Construye el prompt para el análisis de discrepancia"""

        # Listar códigos de partidas existentes
        codigos_existentes = [p['codigo'] for p in partidas_existentes]

        partidas_str = "\n".join([
            f"- {p.get('codigo', 'N/A')} = {p.get('importe', 0):.2f} €"
            for p in partidas_existentes[:20]
        ])

        # Extraer la sección relevante del PDF
        seccion_pdf = self._extraer_seccion_relevante(codigo, texto_pdf)

        prompt = f"""Eres un experto en análisis de presupuestos de construcción.

TAREA:
Analiza el {tipo} "{codigo} - {nombre}" y encuentra las partidas FALTANTES.

CONTEXTO IMPORTANTE:
- Total del PDF (CORRECTO): {total_esperado:.2f} €
- Total calculado (partidas actuales): {total_calculado:.2f} €
- Diferencia: {diferencia:.2f} €
- El total del PDF es SIEMPRE el valor correcto
- Faltan partidas que explican la diferencia

PARTIDAS YA EXTRAÍDAS ({len(partidas_existentes)}):
{partidas_str if partidas_str else "(Ninguna partida detectada)"}
{"... (y más)" if len(partidas_existentes) > 20 else ""}

TEXTO DEL PDF (secciones relevantes):
{seccion_pdf[:5000]}

INSTRUCCIONES:
1. Busca en el texto de arriba el {tipo} "{codigo}"
2. Identifica TODAS las partidas de ese {tipo}
3. Detecta cuáles NO están en la lista de partidas ya extraídas
4. Extrae SOLO las partidas faltantes con sus datos completos

IMPORTANTE:
- NO incluyas partidas que YA están extraídas (códigos: {', '.join(codigos_existentes[:10])})
- Los códigos de partidas pueden ser de cualquier formato (ej: "01.02.03", "m23U01A010", etc.)
- Extrae: código, unidad, resumen, descripción, cantidad, precio, importe
- El importe debe ser: cantidad × precio

IMPORTANTE - SOBRE DUPLICADOS:
- Si encuentras partidas con el mismo importe/cantidad/precio pero códigos diferentes, probablemente son duplicados
- NO agregues partidas que tengan valores idénticos a las ya extraídas, aunque el código sea ligeramente diferente
- UNIDAD: Extrae SOLO el código de unidad (máximo 10 caracteres):
  * Ejemplos válidos: "ud", "m2", "m3", "kg", "m", "h", "t", "l", "pa"
  * NO extraigas descripciones largas
  * Si la unidad aparece en el texto como "m3 EXCAVACIÓN...", extrae solo "m3"
  * Si no encuentras una unidad válida, usa "ud" por defecto
- RESUMEN: Título corto de la partida (máximo 80 caracteres, en mayúsculas)
  * Ejemplo: "EXCAVACIÓN EN ZANJA TERRENOS COMPACTOS"
- Si no encuentras partidas faltantes, devuelve un array vacío

Responde SOLO en JSON válido:
{{
  "explicacion": "Breve explicación de las partidas faltantes encontradas",
  "partidas_sugeridas": [
    {{
      "codigo": "01.02.03",
      "unidad": "m2",
      "resumen": "EXCAVACIÓN EN ZANJA TERRENOS COMPACTOS",
      "cantidad": 150.5,
      "precio": 12.50,
      "importe": 1881.25
    }}
  ]
}}"""

        return prompt

    def _extraer_seccion_relevante(self, codigo: str, texto_pdf: str) -> str:
        """
        Extrae la sección relevante del PDF que corresponde al código dado.

        Args:
            codigo: Código del capítulo/subcapítulo (ej: "C08.01")
            texto_pdf: Texto completo del PDF

        Returns:
            Sección relevante del texto
        """
        import re

        lines = texto_pdf.split('\n')
        seccion_lines = []
        capturando = False
        contador_lineas = 0

        for line in lines:
            # Detectar inicio de la sección
            if codigo in line and not capturando:
                capturando = True
                seccion_lines.append(line)
                continue

            # Si estamos capturando
            if capturando:
                # Detectar fin de la sección (siguiente capítulo/subcapítulo de mismo nivel o superior)
                if self._es_fin_seccion(line, codigo):
                    break

                seccion_lines.append(line)
                contador_lineas += 1

                # Limitar a 200 líneas para no exceder límites de tokens
                if contador_lineas > 200:
                    break

        if not seccion_lines:
            # Si no encontramos la sección específica, devolver todo el texto
            return texto_pdf[:5000]

        return '\n'.join(seccion_lines)

    def _es_fin_seccion(self, line: str, codigo_actual: str) -> bool:
        """
        Determina si una línea marca el fin de la sección actual.

        Args:
            line: Línea a analizar
            codigo_actual: Código de la sección actual (ej: "C08.01")

        Returns:
            True si la línea marca el fin de la sección
        """
        import re

        # Detectar códigos de capítulos/subcapítulos
        # Patrones: C01, C08.01, C08.08.01, etc.
        patron = r'\b(C\d+(?:\.\d+)*)\b'
        match = re.search(patron, line)

        if not match:
            return False

        codigo_encontrado = match.group(1)

        # Si el código encontrado es el actual, no es fin de sección
        if codigo_encontrado == codigo_actual:
            return False

        # Contar niveles de profundidad
        nivel_actual = codigo_actual.count('.')
        nivel_encontrado = codigo_encontrado.count('.')

        # Es fin de sección si:
        # 1. Es un código de mismo nivel o superior
        # 2. O es un código diferente del mismo nivel
        if nivel_encontrado <= nivel_actual:
            # Verificar que no sea un subcapítulo del actual
            if not codigo_encontrado.startswith(codigo_actual + '.'):
                return True

        return False


# Instancia singleton
_ia_service = None


def get_ia_service() -> IAService:
    """Obtiene la instancia singleton del servicio de IA"""
    global _ia_service
    if _ia_service is None:
        _ia_service = IAService()
    return _ia_service
