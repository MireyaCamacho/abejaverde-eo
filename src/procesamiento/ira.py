"""
AbejaVerde·EO — Módulo: IRA
Índice de Riesgo Apícola-Ecosistémico

Fórmula:
    IRA = (w1 × f_NDVI) + (w2 × f_Fenologia) + (w3 × f_Tsup)
        + (w4 × f_Tcolmena) + (w5 × f_HR) + (w6 × f_Precip) + (w7 × f_Agua)

Pesos (plan V2):
    f_NDVI       25% — variación vegetación vs. media histórica
    f_Fenologia  15% — posición dentro del ciclo estacional (LSP)
    f_Tsup       20% — anomalía temperatura superficial terrestre
    f_Tcolmena   20% — desviación T° interna vs. homeostasis (~35°C) ★ IoT
    f_HR          8% — humedad relativa interna anómala ★ IoT
    f_Precip      7% — déficit o exceso vs. promedio histórico mensual
    f_Agua        5% — disponibilidad agua superficial en radio 500m

Clasificación de riesgo:
    🟢 BAJO   0–33  — Ecosistema estable   → Sin acción inmediata
    🟡 MEDIO 34–66  — Señales emergentes   → Monitoreo intensificado
    🔴 ALTO  67–100 — Estrés activo        → Alerta urgente al apicultor

Anomalía base:
    anomalia_X = (X_observado − X_media_histórica) / σ_histórica

Cada f_X es un score de riesgo normalizado 0–1:
    0 = sin riesgo, 1 = máximo riesgo

Nota sobre datos IoT ausentes:
    Cuando no hay datos IoT (f_Tcolmena, f_HR), sus pesos se
    redistribuyen proporcionalmente entre las variables satelitales.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
import math


# ── CONSTANTES ────────────────────────────────────────────────────────────────

PESOS = {
    "ndvi":      0.25,
    "fenologia": 0.15,
    "tsup":      0.20,
    "tcolmena":  0.20,
    "hr":        0.08,
    "precip":    0.07,
    "agua":      0.05,
}

# Pesos satelitales sin IoT (redistribuidos para sumar 1.0)
PESOS_SIN_IOT = {
    "ndvi":      0.375,
    "fenologia": 0.225,
    "tsup":      0.300,
    "precip":    0.065,   # proporcional al peso original
    "agua":      0.035,
}

TCOLMENA_OPTIMA = 35.0   # °C — homeostasis zona de cría
TCOLMENA_MIN    = 34.5   # °C — límite inferior aceptable
TCOLMENA_MAX    = 35.5   # °C — límite superior aceptable
TCOLMENA_CRITICO_LOW  = 33.0
TCOLMENA_CRITICO_HIGH = 37.0

HR_OPTIMA  = (40.0, 65.0)  # %
HR_ALTA    = 75.0           # % — inicio riesgo
HR_CRITICA = 85.0           # % — riesgo alto


# ── DATACLASSES DE ENTRADA ────────────────────────────────────────────────────

@dataclass
class DatosSatelitales:
    """Variables derivadas de Copernicus para una fecha y apiario dado."""
    # Sentinel-2
    ndvi_actual:        float
    ndvi_media:         float          # media histórica (línea base 2022-2024)
    ndvi_sigma:         float          # desviación estándar histórica

    # ERA5-Land / Sentinel-3
    tsup_actual:        float          # temperatura superficial °C
    tsup_media:         float
    tsup_sigma:         float

    # ERA5-Land
    precip_actual_mm:   float          # precipitación acumulada 15 días (mm)
    precip_media_mm:    float
    precip_sigma_mm:    float

    # Water Bodies CLMS + JRC
    agua_pct_activa:    float          # % cuerpos de agua activos vs. histórico (0-100)

    # LSP CLMS (fenología)
    fecha_actual:       Optional[date] = None
    lsp_sos:            Optional[date] = None   # Start of Season
    lsp_pos:            Optional[date] = None   # Peak of Season
    lsp_eos:            Optional[date] = None   # End of Season
    lsp_ampl:           Optional[float] = None  # Amplitude — intensidad floración


@dataclass
class DatosIoT:
    """Variables biológicas de la colmena inteligente."""
    tcolmena:    Optional[float] = None   # temperatura zona de cría (°C)
    hr_interna:  Optional[float] = None   # humedad relativa interna (%)
    disponible:  bool = False

    def __post_init__(self):
        self.disponible = (
            self.tcolmena is not None or
            self.hr_interna is not None
        )


@dataclass
class ResultadoIRA:
    """Resultado completo del cálculo IRA."""
    score:          float               # 0–100
    nivel:          str                 # BAJO / MEDIO / ALTO
    color:          str                 # verde / amarillo / rojo
    accion:         str                 # recomendación al apicultor
    tiene_iot:      bool

    componentes: dict = field(default_factory=dict)
    anomalias:   dict = field(default_factory=dict)
    alertas:     list = field(default_factory=list)


# ── FUNCIONES DE RIESGO (f_X) — retornan 0 (sin riesgo) a 1 (máximo riesgo) ─

def _sigmoide_riesgo(x: float, umbral: float = 1.5, escala: float = 1.0) -> float:
    """
    Transforma una anomalía estandarizada en un score de riesgo 0-1
    usando una función sigmoide suavizada.
    x > 0 → riesgo creciente (para variables donde exceso = riesgo)
    x < 0 → riesgo creciente (para variables donde déficit = riesgo, pasar -x)
    """
    return 1.0 / (1.0 + math.exp(-(x - umbral) / escala))


def f_ndvi(ndvi_actual: float, ndvi_media: float, ndvi_sigma: float) -> tuple[float, float]:
    """
    Riesgo NDVI: déficit respecto al histórico → mayor riesgo.
    Retorna (score_riesgo_0_1, anomalia_estandarizada).
    """
    if ndvi_sigma <= 0:
        return 0.0, 0.0
    anomalia = (ndvi_actual - ndvi_media) / ndvi_sigma
    # Déficit = anomalía negativa → inversión de signo para score de riesgo
    riesgo = _sigmoide_riesgo(-anomalia, umbral=1.0, escala=0.8)
    return round(riesgo, 4), round(anomalia, 3)


def f_fenologia(
    fecha_actual: Optional[date],
    lsp_sos: Optional[date],
    lsp_pos: Optional[date],
    lsp_eos: Optional[date],
    lsp_ampl: Optional[float],
    ndvi_anomalia: float,
) -> tuple[float, str]:
    """
    Riesgo fenológico: combina la posición en el ciclo estacional
    con la intensidad de la floración (AMPL) y la anomalía NDVI.
    Retorna (score_riesgo_0_1, fase_actual).
    """
    # Sin datos LSP — usar NDVI como proxy
    if any(x is None for x in [fecha_actual, lsp_sos, lsp_pos, lsp_eos]):
        riesgo_proxy = max(0.0, min(1.0, (-ndvi_anomalia + 1.0) / 2.0))
        return round(riesgo_proxy, 4), "SIN_LSP"

    hoy = fecha_actual

    if hoy < lsp_sos:
        fase = "PRE_TEMPORADA"
        riesgo_base = 0.3      # antes de que empiece — moderado

    elif lsp_sos <= hoy <= lsp_pos:
        fase = "FLORACION_ACTIVA"
        riesgo_base = 0.0      # plena floración — sin riesgo

    elif lsp_pos < hoy <= lsp_eos:
        fase = "FLORACION_DECLINANDO"
        # Progresión lineal del riesgo hacia el fin de temporada
        dias_total = (lsp_eos - lsp_pos).days
        dias_trans = (hoy - lsp_pos).days
        progresion = dias_trans / max(dias_total, 1)
        riesgo_base = 0.3 * progresion

    else:
        fase = "FUERA_TEMPORADA"
        riesgo_base = 0.7      # fuera de temporada — riesgo alto

    # Penalización por amplitud baja (floración débil)
    penal_ampl = 0.0
    if lsp_ampl is not None and lsp_ampl < 0.4:
        penal_ampl = 0.2 * (1.0 - lsp_ampl / 0.4)

    riesgo = min(1.0, riesgo_base + penal_ampl)
    return round(riesgo, 4), fase


def f_tsup(tsup_actual: float, tsup_media: float, tsup_sigma: float) -> tuple[float, float]:
    """
    Riesgo temperatura superficial: anomalía positiva sostenida → estrés térmico.
    """
    if tsup_sigma <= 0:
        return 0.0, 0.0
    anomalia = (tsup_actual - tsup_media) / tsup_sigma
    riesgo = _sigmoide_riesgo(abs(anomalia), umbral=1.5, escala=0.7)
    return round(riesgo, 4), round(anomalia, 3)


def f_tcolmena(tcolmena: Optional[float]) -> tuple[float, str]:
    """
    Riesgo temperatura interna de la colmena vs. homeostasis (35°C).
    Retorna (score_riesgo_0_1, estado).
    """
    if tcolmena is None:
        return None, "SIN_IOT"

    desviacion = abs(tcolmena - TCOLMENA_OPTIMA)

    if TCOLMENA_MIN <= tcolmena <= TCOLMENA_MAX:
        return 0.0, "OPTIMA"
    elif TCOLMENA_CRITICO_LOW <= tcolmena < TCOLMENA_MIN:
        # Hipotermia leve — colonia pequeña o reina débil
        riesgo = 0.3 + 0.7 * (TCOLMENA_MIN - tcolmena) / (TCOLMENA_MIN - TCOLMENA_CRITICO_LOW)
        return round(min(1.0, riesgo), 4), "BAJA"
    elif TCOLMENA_MAX < tcolmena <= TCOLMENA_CRITICO_HIGH:
        # Hipertermia leve — estrés calórico o enjambrazón
        riesgo = 0.3 + 0.7 * (tcolmena - TCOLMENA_MAX) / (TCOLMENA_CRITICO_HIGH - TCOLMENA_MAX)
        return round(min(1.0, riesgo), 4), "ALTA"
    elif tcolmena < TCOLMENA_CRITICO_LOW:
        return 1.0, "CRITICA_BAJA"
    else:
        return 1.0, "CRITICA_ALTA"


def f_hr(hr_interna: Optional[float]) -> tuple[float, str]:
    """
    Riesgo humedad relativa interna: exceso sostenido → enfermedades fúngicas.
    """
    if hr_interna is None:
        return None, "SIN_IOT"

    hr_min, hr_max = HR_OPTIMA

    if hr_min <= hr_interna <= hr_max:
        return 0.0, "OPTIMA"
    elif hr_max < hr_interna <= HR_ALTA:
        riesgo = 0.4 * (hr_interna - hr_max) / (HR_ALTA - hr_max)
        return round(riesgo, 4), "ELEVADA"
    elif HR_ALTA < hr_interna <= HR_CRITICA:
        riesgo = 0.4 + 0.6 * (hr_interna - HR_ALTA) / (HR_CRITICA - HR_ALTA)
        return round(riesgo, 4), "ALTA"
    elif hr_interna > HR_CRITICA:
        return 1.0, "CRITICA"
    else:
        # Humedad muy baja
        riesgo = 0.2 * (hr_min - hr_interna) / hr_min
        return round(min(1.0, riesgo), 4), "BAJA"


def f_precip(
    precip_actual: float,
    precip_media: float,
    precip_sigma: float,
) -> tuple[float, float]:
    """
    Riesgo precipitación: déficit respecto al histórico → mayor riesgo.
    """
    if precip_sigma <= 0:
        return 0.0, 0.0
    anomalia = (precip_actual - precip_media) / precip_sigma
    # Déficit = anomalía negativa = mayor riesgo
    riesgo = _sigmoide_riesgo(-anomalia, umbral=0.8, escala=0.7)
    return round(riesgo, 4), round(anomalia, 3)


def f_agua(agua_pct_activa: float) -> float:
    """
    Riesgo disponibilidad de agua: caída en % de cuerpos de agua activos.
    agua_pct_activa: 0-100, donde 100 = disponibilidad histórica completa.
    """
    if agua_pct_activa >= 80:
        return 0.0
    elif agua_pct_activa >= 50:
        return 0.4 * (80 - agua_pct_activa) / 30
    elif agua_pct_activa >= 20:
        return 0.4 + 0.4 * (50 - agua_pct_activa) / 30
    else:
        return round(0.8 + 0.2 * (20 - agua_pct_activa) / 20, 4)


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────────────────

def calcular_ira(
    sat: DatosSatelitales,
    iot: Optional[DatosIoT] = None,
) -> ResultadoIRA:
    """
    Calcula el Índice de Riesgo Apícola-Ecosistémico (IRA).

    Args:
        sat:  variables satelitales del apiario (Copernicus)
        iot:  variables IoT de la colmena (opcional)

    Returns:
        ResultadoIRA con score 0-100, nivel, acción y detalle de componentes
    """
    iot = iot or DatosIoT()

    # ── Calcular cada componente ──────────────────────────────────────────────
    r_ndvi,    anom_ndvi    = f_ndvi(sat.ndvi_actual, sat.ndvi_media, sat.ndvi_sigma)
    r_feno,    fase         = f_fenologia(
                                sat.fecha_actual, sat.lsp_sos, sat.lsp_pos,
                                sat.lsp_eos, sat.lsp_ampl, anom_ndvi)
    r_tsup,    anom_tsup    = f_tsup(sat.tsup_actual, sat.tsup_media, sat.tsup_sigma)
    r_tcolm,   estado_tcolm = f_tcolmena(iot.tcolmena)
    r_hr,      estado_hr    = f_hr(iot.hr_interna)
    r_precip,  anom_precip  = f_precip(sat.precip_actual_mm, sat.precip_media_mm, sat.precip_sigma_mm)
    r_agua                  = f_agua(sat.agua_pct_activa)

    # ── Aplicar pesos — redistribuir si falta IoT ────────────────────────────
    tiene_iot = iot.disponible

    if tiene_iot:
        pesos = PESOS
        r_tcolm_safe = r_tcolm if r_tcolm is not None else 0.0
        r_hr_safe    = r_hr    if r_hr    is not None else 0.0
    else:
        pesos = PESOS_SIN_IOT
        r_tcolm_safe = 0.0
        r_hr_safe    = 0.0

    if tiene_iot:
        score_raw = (
            pesos["ndvi"]      * r_ndvi      +
            pesos["fenologia"] * r_feno      +
            pesos["tsup"]      * r_tsup      +
            pesos["tcolmena"]  * r_tcolm_safe+
            pesos["hr"]        * r_hr_safe   +
            pesos["precip"]    * r_precip    +
            pesos["agua"]      * r_agua
        )
    else:
        score_raw = (
            pesos["ndvi"]      * r_ndvi   +
            pesos["fenologia"] * r_feno   +
            pesos["tsup"]      * r_tsup   +
            pesos["precip"]    * r_precip +
            pesos["agua"]      * r_agua
        )

    score = round(min(100.0, max(0.0, score_raw * 100)), 1)

    # ── Clasificación y mensajes ──────────────────────────────────────────────
    if score <= 33:
        nivel  = "BAJO"
        color  = "verde"
        accion = "Ecosistema estable. Sin acción inmediata. Continúe monitoreo rutinario."
    elif score <= 66:
        nivel  = "MEDIO"
        color  = "amarillo"
        accion = "Señales de alerta emergente. Intensifique el monitoreo. Revise colmenas esta semana."
    else:
        nivel  = "ALTO"
        color  = "rojo"
        accion = "Estrés ecosistémico activo. Alerta urgente. Intervenga en las próximas 24–48 horas."

    # ── Alertas específicas ───────────────────────────────────────────────────
    alertas = _generar_alertas(
        r_ndvi, fase, r_tsup, r_tcolm, estado_tcolm,
        r_hr, estado_hr, r_precip, r_agua, tiene_iot
    )

    return ResultadoIRA(
        score     = score,
        nivel     = nivel,
        color     = color,
        accion    = accion,
        tiene_iot = tiene_iot,
        componentes = {
            "ndvi":      round(r_ndvi * 100, 1),
            "fenologia": round(r_feno * 100, 1),
            "fase":      fase,
            "tsup":      round(r_tsup * 100, 1),
            "tcolmena":  round(r_tcolm_safe * 100, 1) if tiene_iot else "N/D",
            "hr":        round(r_hr_safe * 100, 1)    if tiene_iot else "N/D",
            "precip":    round(r_precip * 100, 1),
            "agua":      round(r_agua * 100, 1),
        },
        anomalias = {
            "ndvi":   anom_ndvi,
            "tsup":   anom_tsup,
            "precip": anom_precip,
        },
        alertas = alertas,
    )


def _generar_alertas(
    r_ndvi, fase, r_tsup, r_tcolm, estado_tcolm,
    r_hr, estado_hr, r_precip, r_agua, tiene_iot
) -> list[dict]:
    """Genera lista de alertas específicas basadas en los componentes."""
    alertas = []

    # Alerta alimentación
    if r_ndvi > 0.6 and fase in ("FUERA_TEMPORADA", "FLORACION_DECLINANDO", "SIN_LSP"):
        alertas.append({
            "tipo":    "ALIMENTACION",
            "nivel":   "ROJA",
            "mensaje": "Escasez de néctar detectada. Inicie alimentación suplementaria en los próximos 3 días.",
        })
    elif r_ndvi < 0.2 and fase == "FLORACION_ACTIVA":
        alertas.append({
            "tipo":    "ALIMENTACION",
            "nivel":   "VERDE",
            "mensaje": "Floración activa. Su colmena está produciendo. No alimente. Prepare alzas.",
        })

    # Alerta agua
    if r_agua > 0.6:
        alertas.append({
            "tipo":    "AGUA",
            "nivel":   "ROJA",
            "mensaje": "Posible escasez de agua cerca del apiario. Verifique que cada colmena tenga al menos 1 litro de agua fresca disponible.",
        })
    elif r_agua > 0.35:
        alertas.append({
            "tipo":    "AGUA",
            "nivel":   "AMARILLA",
            "mensaje": "Nivel de agua en la zona disminuyendo. Revise las fuentes de agua cercanas esta semana.",
        })

    # Alerta colmena (IoT)
    if tiene_iot and r_tcolm is not None and r_tcolm > 0.6:
        alertas.append({
            "tipo":    "VISITA_REINA",
            "nivel":   "URGENTE",
            "mensaje": f"Temperatura de colmena {estado_tcolm}. Su colmena no mantiene homeostasis. Visite en 24–48h. Revise postura de la reina, población y signos de enfermedad.",
        })

    # Alerta HR (IoT)
    if tiene_iot and r_hr is not None and r_hr > 0.5:
        alertas.append({
            "tipo":    "HUMEDAD",
            "nivel":   "AMARILLA",
            "mensaje": f"Humedad interna de colmena {estado_hr}. Verifique ventilación y revise signos de enfermedades fúngicas.",
        })

    # Alerta calor
    if r_tsup > 0.7:
        alertas.append({
            "tipo":    "OLA_CALOR",
            "nivel":   "ROJA",
            "mensaje": "Temperatura superficial alta anómala. Garantice sombra y agua en abundancia cerca del apiario.",
        })

    return alertas


# ── CÁLCULO EN SERIE TEMPORAL ─────────────────────────────────────────────────

def calcular_ira_serie(registros: list[dict]) -> list[dict]:
    """
    Calcula el IRA para una lista de registros mensuales.

    Cada registro es un dict con:
        fecha, ndvi, ndvi_media, ndvi_sigma,
        tsup, tsup_media, tsup_sigma,
        precip_mm, precip_media_mm, precip_sigma_mm,
        agua_pct_activa,
        [tcolmena], [hr_interna],        # opcionales IoT
        [lsp_sos], [lsp_pos], [lsp_eos], # opcionales LSP
        [lsp_ampl]
    """
    resultados = []
    for r in registros:
        sat = DatosSatelitales(
            ndvi_actual      = r["ndvi"],
            ndvi_media       = r["ndvi_media"],
            ndvi_sigma       = r["ndvi_sigma"],
            tsup_actual      = r["tsup"],
            tsup_media       = r["tsup_media"],
            tsup_sigma       = r["tsup_sigma"],
            precip_actual_mm = r["precip_mm"],
            precip_media_mm  = r["precip_media_mm"],
            precip_sigma_mm  = r["precip_sigma_mm"],
            agua_pct_activa  = r.get("agua_pct_activa", 80.0),
            fecha_actual     = r.get("fecha"),
            lsp_sos          = r.get("lsp_sos"),
            lsp_pos          = r.get("lsp_pos"),
            lsp_eos          = r.get("lsp_eos"),
            lsp_ampl         = r.get("lsp_ampl"),
        )
        iot = DatosIoT(
            tcolmena   = r.get("tcolmena"),
            hr_interna = r.get("hr_interna"),
        )
        resultado = calcular_ira(sat, iot)
        resultados.append({
            "fecha":      str(r.get("fecha", "")),
            "ira_score":  resultado.score,
            "nivel":      resultado.nivel,
            "color":      resultado.color,
            "accion":     resultado.accion,
            "alertas":    resultado.alertas,
            "tiene_iot":  resultado.tiene_iot,
        })
    return resultados


# ── DEMO ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("═" * 60)
    print("  AbejaVerde·EO — IRA v2")
    print("  Apiario San Juan de Rioseco, Cundinamarca")
    print("  Pesos: NDVI 25% | Feno 15% | Tsup 20%")
    print("         Tcolm 20% | HR 8% | Precip 7% | Agua 5%")
    print("═" * 60)

    # Línea base de referencia (calibrada con datos reales 17 meses)
    linea_base = dict(
        ndvi_media       = 0.595,
        ndvi_sigma       = 0.140,
        tsup_media       = 22.0,
        tsup_sigma       = 0.70,
        precip_media_mm  = 200.0,
        precip_sigma_mm  = 90.0,
    )

    escenarios = [
        {
            "nombre": "Junio 2024 — pico máximo real (NDVI 0.817, precip 380mm)",
            "sat": DatosSatelitales(
                ndvi_actual=0.817, tsup_actual=22.5,
                precip_actual_mm=380, agua_pct_activa=92,
                lsp_sos=date(2024, 4, 15), lsp_pos=date(2024, 6, 1),
                lsp_eos=date(2024, 8, 1), lsp_ampl=0.75,
                fecha_actual=date(2024, 6, 15),
                **linea_base,
            ),
            "iot": DatosIoT(tcolmena=35.1, hr_interna=52.0),
        },
        {
            "nombre": "Enero 2025 — escasez real (NDVI 0.437, precip baja)",
            "sat": DatosSatelitales(
                ndvi_actual=0.437, tsup_actual=22.8,
                precip_actual_mm=38, agua_pct_activa=55,
                fecha_actual=date(2025, 1, 15),
                **linea_base,
            ),
            "iot": None,
        },
        {
            "nombre": "Abril 2025 — Fenómeno del Niño (NDVI 0.379, mínimo histórico)",
            "sat": DatosSatelitales(
                ndvi_actual=0.379, tsup_actual=24.1,
                precip_actual_mm=22, agua_pct_activa=28,
                lsp_sos=date(2025, 4, 20), lsp_pos=date(2025, 6, 1),
                lsp_eos=date(2025, 8, 1), lsp_ampl=0.31,
                fecha_actual=date(2025, 4, 10),
                **linea_base,
            ),
            "iot": DatosIoT(tcolmena=33.8, hr_interna=71.0),
        },
        {
            "nombre": "Mayo 2024 — floración alta con IoT confirmando (NDVI 0.773)",
            "sat": DatosSatelitales(
                ndvi_actual=0.773, tsup_actual=21.8,
                precip_actual_mm=310, agua_pct_activa=88,
                lsp_sos=date(2024, 4, 15), lsp_pos=date(2024, 6, 1),
                lsp_eos=date(2024, 8, 1), lsp_ampl=0.75,
                fecha_actual=date(2024, 5, 15),
                **linea_base,
            ),
            "iot": DatosIoT(tcolmena=35.3, hr_interna=58.0),
        },
    ]

    for e in escenarios:
        resultado = calcular_ira(e["sat"], e.get("iot"))
        iot_tag = "con IoT" if resultado.tiene_iot else "sin IoT"
        print(f"\n📅 {e['nombre']} ({iot_tag})")
        print(f"   IRA: {resultado.score:5.1f} — {resultado.nivel:5s}  {resultado.color}")
        print(f"   {resultado.accion}")
        comp = resultado.componentes
        print(f"   Componentes → NDVI:{comp['ndvi']:4.0f} | Feno:{comp['fenologia']:4.0f} | "
              f"Tsup:{comp['tsup']:4.0f} | Precip:{comp['precip']:4.0f} | Agua:{comp['agua']:4.0f}", end="")
        if resultado.tiene_iot:
            print(f" | Tcolm:{comp['tcolmena']:4.0f} | HR:{comp['hr']:4.0f}")
        else:
            print()
        if resultado.alertas:
            for a in resultado.alertas:
                print(f"   ⚠️  [{a['nivel']}] {a['tipo']}: {a['mensaje'][:80]}...")
