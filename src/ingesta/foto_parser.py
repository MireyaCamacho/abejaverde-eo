"""
AbejaVerde·EO — Módulo: foto_parser
=====================================
Análisis de fotos del entorno apícola usando visión por IA (Claude).

El apicultor es el puente entre los datos satelitales (Copernicus)
y los datos del nodo IoT. Sus ojos capturan lo que ningún satélite
puede ver desde 800 km de altura:
    - Qué árbol está floreciendo HOY a 50 metros de la colmena
    - Si la quebrada bajó de nivel esta semana
    - Si las abejas están agitadas en la piquera
    - Si hay cultivos con agroquímicos cerca

Este módulo convierte esas fotos en variables estructuradas
que alimentan el IRA y mejoran la precisión de las alertas.

Variables que extrae de una foto:
    FLORA
        - Especie o tipo de planta identificada
        - Estado de floración (activa / próxima / terminada)
        - Cobertura estimada (%)
        - Valor melífero (alto / medio / bajo)
        - Potencial impacto en NDVI

    AGUA
        - Tipo de fuente (quebrada / charco / rio / bebedero)
        - Nivel estimado (normal / bajo / seco)
        - Accesibilidad para abejas
        - Turbidez aproximada

    COLMENA
        - Actividad en piquera (alta / normal / baja)
        - Señales de estrés visibles
        - Comportamiento defensivo
        - Estado de la entrada

    PAISAJE
        - Cobertura vegetal estimada (%)
        - Zonas de floración visibles
        - Presencia de cultivos o presión antrópica
        - Condiciones del cielo / clima aparente
        - NDVI proxy estimado por visión

    TEXTO LIBRE (descripción del apicultor)
        - Cualquier observación que el apicultor quiera registrar
        - Se procesa con NLP para extraer variables relevantes

Outputs:
    data/processed/observaciones_campo.csv
    data/processed/flora_detectada.csv

Uso básico:
    from src.ingesta.foto_parser import FotoParser
    parser = FotoParser()
    resultado = parser.analizar_foto("foto_colmena.jpg", tipo="colmena")
    print(resultado)

Uso con texto libre del apicultor:
    resultado = parser.analizar_descripcion(
        "Hoy vi que la acacia amarilla que está al norte del apiario
         ya está floreciendo. La quebrada está bajita pero hay agua."
    )
"""

from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

TIPOS_FOTO = ["flora", "agua", "colmena", "paisaje", "general"]

# Variables que el sistema extrae de cada tipo de foto
VARIABLES_POR_TIPO = {
    "flora": [
        "especie_detectada", "nombre_comun", "estado_floracion",
        "cobertura_pct", "valor_melifero", "impacto_ndvi_estimado",
        "fecha_estimada_fin_floracion",
    ],
    "agua": [
        "tipo_fuente", "nivel_estimado", "accesibilidad_abejas",
        "turbidez", "distancia_estimada_m", "riesgo_contaminacion",
    ],
    "colmena": [
        "actividad_piquera", "carga_corbiculas_visible",
        "comportamiento_defensivo", "senales_estres",
        "estado_entrada", "abejas_por_minuto_estimado",
    ],
    "paisaje": [
        "cobertura_vegetal_pct", "zonas_floracion_visibles",
        "presencia_cultivos", "presion_antopica",
        "condicion_cielo", "ndvi_proxy_estimado",
        "cuerpos_agua_visibles",
    ],
    "general": [
        "elementos_identificados", "estado_ecosistema",
        "observaciones_relevantes", "nivel_riesgo_estimado",
    ],
}

# Prompt del sistema para análisis de fotos apícolas
PROMPT_SISTEMA = """Eres el analizador de fotos de AbejaVerde·EO, sistema de alertas apícolas
para pequeños apicultores colombianos.

CONTEXTO GEOGRÁFICO:
Apiario piloto en San Juan de Rioseco, Cundinamarca (4.875°N, -74.635°O).
Zona de transición entre el valle del Magdalena y la cordillera Oriental.
Altitud: 400-900 msnm. Clima cálido-templado, bosque subandino.

FLORA MELÍFERA CLAVE DE LA ZONA (reconocerlas cuando estén visibles):
- Cassia spectabilis / Senna spectabilis (cañafístulo, lluvia de oro) — flores amarillas abundantes, ALTO valor melífero
- Tabebuia chrysantha (guayacán amarillo) — flores amarillas en copa desnuda, ALTO valor
- Leucaena leucocephala (leucaena) — flores blancas pequeñas tipo pompa, ALTO valor
- Gliricidia sepium (matarratón) — flores rosadas-lila, MEDIO valor
- Eucalyptus sp. (eucalipto) — flores blancas, ALTO valor, si hay plantaciones
- Musa paradisiaca (plátano/banano) — inflorescencia roja, BAJO valor directo pero indica humedad
- Anacardium occidentale (marañón) — flores pequeñas crema, MEDIO valor
- Tithonia diversifolia (botón de oro) — flores amarillas tipo girasol, ALTO valor
- Inga sp. (guamo) — flores blancas filamentosas, ALTO valor
- Poáceas (pastizales) — sin valor melífero
- Acacia mangium — flores crema en racimos, ALTO valor
- Citrus sp. (naranjo, limón, mandarina) — flores blancas aromáticas, MUY ALTO valor

SEÑALES FENOLÓGICAS IMPORTANTES:
- Follaje amarillo-dorado nuevo en árboles del bosque = pre-floración inminente
- Árboles con copa completamente en flor y sin hojas = floración plena
- Flores blancas dispersas en dosel = floración activa de varias especies
- Tonos café-rojizos en follaje = estrés hídrico o post-floración

Tu misión: extraer variables que complementen Sentinel-2 NDVI, ERA5 y sensores IoT.
RESPONDE SIEMPRE en JSON válido. Si no puedes determinar un valor, usa null.
"""

PROMPT_FLORA = """Analiza esta foto de vegetación o flora cercana a un apiario.
Extrae las siguientes variables en JSON:
{
  "especie_detectada": "nombre científico si es posible",
  "nombre_comun": "nombre común en Colombia",
  "familia_botanica": "familia de la planta",
  "estado_floracion": "activa|proxima|terminada|sin_flores",
  "cobertura_pct": numero entre 0 y 100,
  "valor_melifero": "alto|medio|bajo|desconocido",
  "tipo_recurso": "nectar|polen|ambos|ninguno",
  "impacto_ndvi_estimado": "positivo|neutro|negativo",
  "fecha_estimada_fin_floracion": "estimacion en dias o null",
  "otras_especies_visibles": ["lista de otras plantas si aplica"],
  "observacion": "nota adicional relevante para apicultura"
}"""

PROMPT_AGUA = """Analiza esta foto de una fuente de agua cercana a un apiario.
Extrae las siguientes variables en JSON:
{
  "tipo_fuente": "quebrada|rio|charco|laguna|bebedero_artificial|pozo|otro",
  "nivel_estimado": "normal|bajo|muy_bajo|seco|desbordado",
  "tendencia": "bajando|estable|subiendo|desconocida",
  "accesibilidad_abejas": "buena|dificil|imposible",
  "orillas": "accesibles|pronunciadas|sin_orillas",
  "turbidez": "clara|turbia|muy_turbia",
  "cobertura_superficial": "abierta|parcialmente_cubierta|cubierta",
  "distancia_estimada_m": numero o null,
  "riesgo_contaminacion": "bajo|medio|alto",
  "observacion": "nota adicional relevante"
}"""

PROMPT_COLMENA = """Analiza esta foto de una colmena o de la actividad en la piquera.
Extrae las siguientes variables en JSON:
{
  "actividad_piquera": "muy_alta|alta|normal|baja|nula",
  "abejas_visibles": "muchas|moderadas|pocas|ninguna",
  "carga_corbiculas_visible": true o false,
  "color_carga_estimado": "amarillo|naranja|blanco|verde|null",
  "comportamiento_defensivo": "tranquilas|alertas|defensivas|agresivas",
  "senales_estres": ["lista de señales observadas o lista vacia"],
  "abejas_muertas_visibles": true o false,
  "estado_entrada": "normal|bloqueada|dañada|propolis_excesivo",
  "hora_estimada_foto": "mañana|tarde|atardecer|null",
  "temperatura_ambiente_estimada": "fria|fresca|templada|caliente",
  "observacion": "nota adicional relevante"
}"""

PROMPT_PAISAJE = """Analiza esta foto del paisaje o entorno de un apiario en los Andes colombianos.
Extrae las siguientes variables en JSON:
{
  "cobertura_vegetal_pct": numero entre 0 y 100,
  "tipo_vegetacion_dominante": "bosque|arbustos|pastizal|cultivos|mixto",
  "zonas_floracion_visibles": true o false,
  "descripcion_floracion": "descripcion breve o null",
  "presencia_cultivos": true o false,
  "tipos_cultivos_estimados": ["lista o lista vacia"],
  "presion_antopica": "baja|moderada|alta",
  "condicion_cielo": "despejado|parcial|nublado|lluvia",
  "visibilidad": "buena|moderada|baja",
  "cuerpos_agua_visibles": true o false,
  "ndvi_proxy_estimado": numero entre 0.1 y 0.9,
  "potencial_melifero_zona": "alto|medio|bajo",
  "observacion": "nota adicional relevante para apicultura"
}"""

PROMPT_DESCRIPCION = """El siguiente texto es una observación de campo de un apicultor colombiano
sobre su apiario. Extrae variables relevantes para el sistema de alertas AbejaVerde·EO en JSON:
{
  "floracion_mencionada": true o false,
  "especies_floracion": ["lista de plantas mencionadas"],
  "estado_floracion_reportado": "activa|proxima|terminada|null",
  "agua_mencionada": true o false,
  "nivel_agua_reportado": "normal|bajo|seco|null",
  "comportamiento_abejas_reportado": "descripcion o null",
  "clima_reportado": "descripcion o null",
  "alertas_apicultor": ["lista de alertas que menciona el apicultor"],
  "acciones_realizadas": ["lista de acciones que menciona"],
  "sentiment_general": "positivo|neutro|preocupado|urgente",
  "variables_ira_afectadas": ["lista de variables del IRA que impacta"],
  "resumen": "resumen en una oración"
}

Texto del apicultor:"""


# ── CLASE PRINCIPAL ───────────────────────────────────────────────────────────

class FotoParser:
    """
    Analiza fotos del entorno apícola usando Claude vision API.
    Convierte imágenes en variables estructuradas para el IRA.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._cliente = None
        self.directorio_salida = Path("data/processed")
        self.directorio_salida.mkdir(parents=True, exist_ok=True)

    def _get_cliente(self):
        """Inicializa el cliente Anthropic (lazy)."""
        if self._cliente is None:
            try:
                import anthropic
                self._cliente = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "Instala anthropic: pip install anthropic\n"
                    "Y define ANTHROPIC_API_KEY en .env"
                )
        return self._cliente

    def _imagen_a_base64(self, ruta: Union[str, Path]) -> tuple[str, str]:
        """Convierte imagen a base64 y detecta el media type."""
        ruta = Path(ruta)
        sufijo = ruta.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png",  ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(sufijo, "image/jpeg")
        with open(ruta, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("utf-8")
        return data, media_type

    def analizar_foto(
        self,
        ruta_imagen: Union[str, Path],
        tipo: str = "general",
        municipio: str = "San Juan de Rioseco",
        apiario_id: str = "API_SJR_01",
        guardar: bool = True,
    ) -> dict:
        """
        Analiza una foto y extrae variables apícolas.

        Args:
            ruta_imagen: ruta al archivo de imagen
            tipo: "flora" | "agua" | "colmena" | "paisaje" | "general"
            municipio: nombre del municipio del apiario
            apiario_id: identificador del apiario
            guardar: si True, guarda el resultado en CSV

        Returns:
            dict con variables extraídas + metadata
        """
        if tipo not in TIPOS_FOTO:
            raise ValueError(f"Tipo debe ser uno de: {TIPOS_FOTO}")

        prompts = {
            "flora":    PROMPT_FLORA,
            "agua":     PROMPT_AGUA,
            "colmena":  PROMPT_COLMENA,
            "paisaje":  PROMPT_PAISAJE,
            "general":  PROMPT_PAISAJE,
        }
        prompt_usuario = prompts[tipo]

        logger.info(f"📷 Analizando foto tipo '{tipo}' — {ruta_imagen}")

        try:
            imagen_b64, media_type = self._imagen_a_base64(ruta_imagen)
            cliente = self._get_cliente()

            respuesta = cliente.messages.create(
                model      = "claude-opus-4-6",
                max_tokens = 1000,
                system     = PROMPT_SISTEMA,
                messages   = [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type":       "base64",
                                "media_type": media_type,
                                "data":       imagen_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f"Municipio: {municipio}. "
                                f"Fecha: {datetime.now().strftime('%Y-%m-%d')}.\n\n"
                                + prompt_usuario
                            ),
                        },
                    ],
                }],
            )

            texto = respuesta.content[0].text.strip()

            # Extraer JSON de la respuesta
            if "```json" in texto:
                texto = texto.split("```json")[1].split("```")[0].strip()
            elif "```" in texto:
                texto = texto.split("```")[1].split("```")[0].strip()

            variables = json.loads(texto)

        except Exception as e:
            logger.error(f"❌ Error analizando foto: {e}")
            variables = {"error": str(e), "tipo": tipo}

        resultado = {
            "timestamp":   datetime.now().isoformat(),
            "apiario_id":  apiario_id,
            "municipio":   municipio,
            "tipo_foto":   tipo,
            "ruta_imagen": str(ruta_imagen),
            **variables,
        }

        if guardar and "error" not in variables:
            self._guardar_observacion(resultado, tipo)

        return resultado

    def analizar_descripcion(
        self,
        texto: str,
        municipio: str = "San Juan de Rioseco",
        apiario_id: str = "API_SJR_01",
        guardar: bool = True,
    ) -> dict:
        """
        Analiza una descripción de texto libre del apicultor.
        Extrae variables estructuradas del lenguaje natural.

        Args:
            texto: descripción libre del apicultor
            municipio: nombre del municipio
            apiario_id: identificador del apiario

        Returns:
            dict con variables extraídas
        """
        logger.info(f"📝 Analizando descripción del apicultor ({len(texto)} chars)")

        try:
            cliente = self._get_cliente()
            respuesta = cliente.messages.create(
                model      = "claude-opus-4-6",
                max_tokens = 800,
                system     = PROMPT_SISTEMA,
                messages   = [{
                    "role":    "user",
                    "content": PROMPT_DESCRIPCION + f"\n\n'{texto}'",
                }],
            )

            texto_resp = respuesta.content[0].text.strip()
            if "```json" in texto_resp:
                texto_resp = texto_resp.split("```json")[1].split("```")[0].strip()
            elif "```" in texto_resp:
                texto_resp = texto_resp.split("```")[1].split("```")[0].strip()

            variables = json.loads(texto_resp)

        except Exception as e:
            logger.error(f"❌ Error analizando descripción: {e}")
            variables = {"error": str(e)}

        resultado = {
            "timestamp":   datetime.now().isoformat(),
            "apiario_id":  apiario_id,
            "municipio":   municipio,
            "tipo_foto":   "descripcion_texto",
            "texto_original": texto,
            **variables,
        }

        if guardar and "error" not in variables:
            self._guardar_observacion(resultado, "descripcion")

        return resultado

    def _guardar_observacion(self, resultado: dict, tipo: str) -> Path:
        """Guarda la observación en CSV acumulativo."""
        ruta = self.directorio_salida / "observaciones_campo.csv"
        df_nueva = pd.DataFrame([resultado])

        if ruta.exists():
            df_existente = pd.read_csv(ruta)
            df = pd.concat([df_existente, df_nueva], ignore_index=True)
        else:
            df = df_nueva

        df.to_csv(ruta, index=False)
        logger.info(f"💾 Observación guardada: {ruta}")
        return ruta

    def generar_resumen_campo(
        self,
        ruta_csv: Union[str, Path] = "data/processed/observaciones_campo.csv",
        ultimas_n: int = 10,
    ) -> dict:
        """
        Genera un resumen de las últimas observaciones de campo.
        Útil para alimentar el contexto del IRA.
        """
        ruta = Path(ruta_csv)
        if not ruta.exists():
            return {"observaciones": 0, "resumen": "Sin observaciones registradas"}

        df = pd.read_csv(ruta, parse_dates=["timestamp"])
        df = df.sort_values("timestamp", ascending=False).head(ultimas_n)

        resumen = {
            "observaciones":       len(df),
            "ultima_observacion":  str(df["timestamp"].iloc[0])[:10] if len(df) else None,
            "tipos_reportados":    df["tipo_foto"].value_counts().to_dict(),
            "floracion_activa":    None,
            "agua_nivel":          None,
            "actividad_colmena":   None,
        }

        # Extraer señales clave
        flora_rows = df[df["tipo_foto"] == "flora"]
        if not flora_rows.empty and "estado_floracion" in flora_rows.columns:
            resumen["floracion_activa"] = (
                flora_rows["estado_floracion"].iloc[0] == "activa"
            )

        agua_rows = df[df["tipo_foto"] == "agua"]
        if not agua_rows.empty and "nivel_estimado" in agua_rows.columns:
            resumen["agua_nivel"] = agua_rows["nivel_estimado"].iloc[0]

        colmena_rows = df[df["tipo_foto"] == "colmena"]
        if not colmena_rows.empty and "actividad_piquera" in colmena_rows.columns:
            resumen["actividad_colmena"] = colmena_rows["actividad_piquera"].iloc[0]

        return resumen


# ── INTEGRACIÓN CON EL IRA ────────────────────────────────────────────────────

def ajustar_ira_con_observaciones(
    ira_score: float,
    observaciones: dict,
) -> tuple[float, list[str]]:
    """
    Ajusta el IRA con base en las observaciones de campo del apicultor.
    Las observaciones de campo pueden confirmar o contradecir las señales satelitales.

    Args:
        ira_score: score IRA calculado con datos satelitales e IoT
        observaciones: dict del resumen de campo (de generar_resumen_campo)

    Returns:
        (ira_ajustado, lista_de_ajustes)
    """
    ajustes = []
    score   = ira_score

    # Floración confirmada en campo → reduce riesgo si IRA era alto por NDVI bajo
    if observaciones.get("floracion_activa") is True:
        if score > 40:
            score  = max(score - 8, score * 0.85)
            ajustes.append("Floración activa confirmada por apicultor (-8 pts IRA)")

    # Agua baja confirmada en campo → aumenta riesgo
    nivel_agua = observaciones.get("agua_nivel")
    if nivel_agua in ("muy_bajo", "seco"):
        score  = min(score + 10, 100)
        ajustes.append(f"Agua {nivel_agua} confirmada por apicultor (+10 pts IRA)")
    elif nivel_agua == "bajo":
        score  = min(score + 5, 100)
        ajustes.append("Agua baja confirmada por apicultor (+5 pts IRA)")

    # Actividad baja en colmena → aumenta riesgo
    actividad = observaciones.get("actividad_colmena")
    if actividad in ("baja", "nula"):
        score  = min(score + 12, 100)
        ajustes.append(f"Actividad de colmena {actividad} reportada (+12 pts IRA)")
    elif actividad in ("alta", "muy_alta"):
        score  = max(score - 5, 0)
        ajustes.append("Actividad alta de colmena reportada (-5 pts IRA)")

    return round(score, 1), ajustes


# ── DEMO ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    print("═" * 55)
    print("  AbejaVerde·EO — foto_parser")
    print("  Análisis de fotos del entorno apícola con IA")
    print("═" * 55)

    parser = FotoParser()

    # Demo 1: analizar descripción de texto del apicultor
    descripcion_demo = """
    Hoy fui al apiario y vi que la acacia amarilla que está al norte
    ya está floreciendo bien. Las abejas estaban muy activas.
    La quebrada La Honda está bajita pero todavía tiene agua.
    Puse agua en el bebedero porque el nivel está bajo.
    Las colmenas 2 y 4 estaban muy cargadas, creo que pronto toca cosechar.
    """

    print("\n📝 Demo: analizando descripción del apicultor...")
    print(f"   Texto: {descripcion_demo[:80]}...")

    if not parser.api_key or parser.api_key == "":
        print("\n⚠️  ANTHROPIC_API_KEY no configurada.")
        print("   Para usar el análisis real:")
        print("   1. Obtener API key en https://console.anthropic.com")
        print("   2. Agregar ANTHROPIC_API_KEY=sk-ant-... en .env")
        print("\n   Simulando respuesta de demo:")

        resultado_demo = {
            "floracion_mencionada":        True,
            "especies_floracion":          ["acacia amarilla"],
            "estado_floracion_reportado":  "activa",
            "agua_mencionada":             True,
            "nivel_agua_reportado":        "bajo",
            "comportamiento_abejas_reportado": "muy activas, cargadas",
            "sentiment_general":           "positivo",
            "variables_ira_afectadas":     ["f_NDVI", "f_Agua", "f_Tcolmena"],
            "resumen": "Floración activa de acacia con abejas productivas, agua baja en quebrada.",
        }
        for k, v in resultado_demo.items():
            print(f"   {k}: {v}")
    else:
        resultado = parser.analizar_descripcion(descripcion_demo)
        print("\n   Resultado:")
        for k, v in resultado.items():
            if k not in ["timestamp", "apiario_id", "municipio", "texto_original", "tipo_foto"]:
                print(f"   {k}: {v}")

    # Demo 2: ajustar IRA con observaciones
    print("\n🧠 Demo: ajustar IRA con observaciones de campo")
    obs = {"floracion_activa": True, "agua_nivel": "bajo", "actividad_colmena": "alta"}
    ira_original = 37.0
    ira_ajustado, ajustes = ajustar_ira_con_observaciones(ira_original, obs)
    print(f"   IRA original (satélite + IoT): {ira_original}")
    print(f"   IRA ajustado con campo:        {ira_ajustado}")
    for a in ajustes:
        print(f"   → {a}")

    print("\n✅ foto_parser listo.")
    print("   Para analizar una foto real:")
    print("   parser = FotoParser()")
    print("   resultado = parser.analizar_foto('mi_foto.jpg', tipo='flora')")
