"""
AbejaVerde·EO — Módulo: semaforo
==================================
Semáforo de riesgo apícola de 4 colores (Skill `abejaverde-riesgo-apicola`,
Manual Técnico Acelera Lab — Proyecto 4).

Cruza el TERRITORIO (NDVI Copernicus Sentinel-2 + clima) con la COLMENA
(bitácora de 3 preguntas del apicultor):

    P1  Fuerza de la población        → ALTA | MEDIA | BAJA
    P2  Reservas de miel y polen      → ALTA | MEDIA | BAJA
    P3  Postura de la reina           → ACTIVA | INACTIVA

Colores (de mayor a menor riesgo):
    ROJO      Riesgo crítico: sin floración, muchas bocas y reservas bajas.
    NARANJA   Alerta preventiva: la floración cae y hay que preparar alimento
              (cuenta regresiva), o lluvias intensas que impiden el pecoreo.
    AMARILLO  Vigilancia: hay flores, pero la colmena está débil o la reina
              detenida (problema local).
    VERDE     Equilibrio: buena floración, buenas reservas y reina activa.

Principio de diseño: las REGLAS deciden el color (resultado auditable y
reproducible). La IA (Gemini) solo redacta la acción recomendada.
Estas reglas son idénticas a las del motor en Google Apps Script
(`mvp_aceleralab/apps_script/motor_alertas_abejaverde.gs`) y a las del
simulador HTML, para que los tres den el mismo resultado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Umbrales de NDVI de la Skill (ajustables tras el piloto)
UMBRAL_CRITICO = 0.35
UMBRAL_BAJO = 0.50
UMBRAL_OPTIMO = 0.60

COLORES = ("ROJO", "NARANJA", "AMARILLO", "VERDE")

DESCRIPCION = {
    "ROJO":     "Riesgo crítico",
    "NARANJA":  "Alerta preventiva",
    "AMARILLO": "Vigilancia operativa",
    "VERDE":    "Equilibrio óptimo",
}

HEX = {
    "ROJO":     "#E06A5A",
    "NARANJA":  "#F2994A",
    "AMARILLO": "#F2C94C",
    "VERDE":    "#8CC98C",
}

EMOJI = {"ROJO": "🔴", "NARANJA": "🟠", "AMARILLO": "🟡", "VERDE": "🟢"}

ACCION_POR_DEFECTO = {
    "ROJO": ("Alimente hoy con jarabe de azúcar 1:1 (1 litro por colmena) y torta "
             "proteica; asegure agua limpia cerca y revise en 48 horas. Si necesita "
             "apoyo, avise al técnico."),
    "NARANJA": ("La floración está bajando: prepare jarabe 1:1 y torta proteica para la "
                "próxima visita, revise reservas en cada colmena y asegure agua cerca "
                "del apiario."),
    "AMARILLO": ("Hay flores, pero la colmena está débil: revise la postura de la reina "
                 "y la sanidad de la cría, reduzca la piquera si hace frío y una colmenas "
                 "débiles si es necesario."),
    "VERDE": ("Todo en orden: mantenga la revisión habitual y evalúe colocar alza "
              "melaria si los cuadros de miel están llenos."),
}


# ── Normalización de respuestas de la bitácora ───────────────────────────────

def leer_ndvi(valor) -> float:
    """Acepta 0.28, "0,28" o "0. 28 (Floración Muy Baja)". Devuelve NaN si no hay número."""
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = re.sub(r"\s+", "", str(valor or "")).replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", texto)
    return float(m.group(0)) if m else float("nan")


def nivel_poblacion(valor) -> str:
    t = str(valor or "").lower()
    if "alta" in t or "fuerte" in t:
        return "ALTA"
    if "media" in t or "normal" in t:
        return "MEDIA"
    if "baja" in t or "débil" in t or "debil" in t:
        return "BAJA"
    return "MEDIA"


def nivel_reservas(valor) -> str:
    t = str(valor or "").lower()
    if "baja" in t or "vací" in t or "vaci" in t:
        return "BAJA"
    if "alta" in t or "llena" in t:
        return "ALTA"
    return "MEDIA"


def estado_reina(valor) -> str:
    t = str(valor or "").lower()
    if any(k in t for k in ("inactiva", "detenida", "sin", "no ")):
        return "INACTIVA"
    return "ACTIVA"


def hay_lluvia_intensa(clima) -> bool:
    t = str(clima or "")
    return bool(re.search(r"lluvi", t, re.I) and re.search(r"(intens|fuert|torrenc|persist)", t, re.I))


# ── Regla del semáforo ───────────────────────────────────────────────────────

def calcular_semaforo(ndvi: float, p1: str, p2: str, p3: str, clima: str = "") -> str:
    """
    Devuelve ROJO, NARANJA, AMARILLO o VERDE.

    `p1`, `p2` y `p3` pueden venir como texto libre de la bitácora
    ("Alta (8 cuadros llenos)", "Bajas", "Activa"); se normalizan aquí.
    """
    if ndvi != ndvi:  # NaN
        raise ValueError("NDVI no válido")
    p1, p2, p3 = nivel_poblacion(p1), nivel_reservas(p2), estado_reina(p3)

    # ROJO: sin floración, muchas bocas y reservas bajas (o reina detenida).
    if ndvi < UMBRAL_CRITICO and p2 == "BAJA" and (p1 != "BAJA" or p3 == "INACTIVA"):
        return "ROJO"
    # NARANJA: territorio en crisis, colmena aún con reservas = cuenta regresiva.
    if ndvi < UMBRAL_CRITICO:
        return "NARANJA"
    # NARANJA: floración baja con reservas bajas o postura detenida.
    if ndvi < UMBRAL_BAJO and (p2 == "BAJA" or p3 == "INACTIVA"):
        return "NARANJA"
    # NARANJA: lluvias intensas que impiden el pecoreo.
    if hay_lluvia_intensa(clima):
        return "NARANJA"
    # AMARILLO: hay flores pero la colmena está débil (problema local).
    if p1 == "BAJA" or p2 == "BAJA" or p3 == "INACTIVA":
        return "AMARILLO"
    # AMARILLO: colmena bien, floración por debajo del óptimo.
    if ndvi < UMBRAL_OPTIMO:
        return "AMARILLO"
    return "VERDE"


# ── Resultado listo para notificar ───────────────────────────────────────────

@dataclass
class ResultadoSemaforo:
    apiario_id: str
    municipio: str
    ndvi: float
    semaforo: str
    accion: str
    clima: str = ""
    respuestas: dict = field(default_factory=dict)

    @property
    def descripcion(self) -> str:
        return DESCRIPCION[self.semaforo]

    @property
    def tiene_ndvi(self) -> bool:
        return self.ndvi == self.ndvi  # False si es NaN

    def texto_whatsapp(self) -> str:
        texto = (
            f"{EMOJI[self.semaforo]} *AbejaVerde·EO – Apiario {self.apiario_id}* ({self.municipio})\n"
            f"Semáforo: *{self.semaforo} – {self.descripcion}*\n\n"
            f"📋 *Acción recomendada esta semana:*\n{self.accion}"
        )
        if self.tiene_ndvi:
            texto += f"\n\n🛰️ NDVI Copernicus del entorno: {self.ndvi:.2f}"
        return texto


def evaluar_apiario(
    apiario_id: str,
    municipio: str,
    ndvi,
    p1: str,
    p2: str,
    p3: str,
    clima: str = "",
    accion: Optional[str] = None,
) -> ResultadoSemaforo:
    """Evalúa un apiario y devuelve el semáforo con su acción recomendada."""
    valor = leer_ndvi(ndvi)
    color = calcular_semaforo(valor, p1, p2, p3, clima)
    return ResultadoSemaforo(
        apiario_id=str(apiario_id),
        municipio=str(municipio),
        ndvi=valor,
        semaforo=color,
        accion=accion or ACCION_POR_DEFECTO[color],
        clima=str(clima or ""),
        respuestas={"P1": nivel_poblacion(p1), "P2": nivel_reservas(p2), "P3": estado_reina(p3)},
    )


# Correspondencia con el Margen de Maniobra (MdM) de la app Streamlit
SEMAFORO_DESDE_MDM = {
    "MARGEN_AMPLIO": "VERDE",
    "NORMAL": "VERDE",
    "CUENTA_REGRESIVA": "NARANJA",
    "CUENTA_REGRESIVA_CRITICA": "ROJO",
    "EMERGENCIA_TERRITORIAL": "ROJO",
    "REACCION_INMEDIATA": "AMARILLO",
}
