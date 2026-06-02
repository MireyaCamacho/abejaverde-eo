"""
AbejaVerde·EO — Módulo: agua_disponibilidad
=============================================
Análisis integrado de disponibilidad de agua para el apiario.

Este módulo (src/procesamiento/) combina todas las fuentes de agua
disponibles y genera el score f_agua para el IRA y la alerta específica
de agua para el apicultor.

Fuentes integradas:
    CLMS Water Bodies  → cuerpos de agua activos (10 días, 300m)
    JRC Global Surface Water → presencia histórica (30m)
    ERA5 precipitación → proxy cuando no hay datos directos
    IoT humedad        → confirmación biológica del estrés hídrico

Cruces clave:
    1. ¿Hay agua cerca? (JRC histórico)
    2. ¿Está activa ahora? (CLMS actual)
    3. ¿Ha llovido suficiente? (ERA5)
    4. ¿La colmena muestra estrés? (IoT HR)

Outputs:
    data/processed/agua_superficial.csv   — serie de disponibilidad
    data/processed/alertas_agua.csv       — alertas generadas
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── CONSTANTES ────────────────────────────────────────────────────────────────

RADIO_ACCESO_M      = 500    # metros — radio de acceso de las abejas al agua
LITROS_MIN_COLMENA  = 1.0   # litros/día mínimos por colmena

# Umbrales de disponibilidad
PCT_NORMAL          = 80.0  # % cuerpos activos → sin alerta
PCT_ALERTA          = 50.0  # % → alerta amarilla
PCT_CRITICO         = 20.0  # % → alerta roja

# Umbrales de precipitación mensual para estimación de agua
PRECIP_NORMAL_MM    = 150.0
PRECIP_BAJA_MM      = 75.0
PRECIP_CRITICA_MM   = 30.0


# ── SCORE INTEGRADO DE AGUA ───────────────────────────────────────────────────

def calcular_score_agua(
    pct_activa:   float,
    precip_mm:    Optional[float] = None,
    hr_colmena:   Optional[float] = None,
) -> dict:
    """
    Calcula el score integrado de disponibilidad de agua (0-1).
    Combina las tres fuentes disponibles con pesos según disponibilidad.

    Score 0 = agua abundante (sin riesgo)
    Score 1 = sequía crítica (máximo riesgo)

    Args:
        pct_activa:  % de cuerpos de agua activos (Water Bodies o estimado ERA5)
        precip_mm:   precipitación mensual ERA5 (opcional, complementa)
        hr_colmena:  humedad relativa interna IoT (opcional, señal biológica)

    Returns:
        dict con score, nivel, componentes y mensaje
    """
    scores = {}
    pesos  = {}

    # ── Componente 1: cuerpos de agua activos (fuente primaria) ──────────────
    if pct_activa >= PCT_NORMAL:
        scores["agua_superficial"] = 0.0
    elif pct_activa >= PCT_ALERTA:
        scores["agua_superficial"] = (PCT_NORMAL - pct_activa) / (PCT_NORMAL - PCT_ALERTA) * 0.5
    elif pct_activa >= PCT_CRITICO:
        scores["agua_superficial"] = 0.5 + (PCT_ALERTA - pct_activa) / (PCT_ALERTA - PCT_CRITICO) * 0.4
    else:
        scores["agua_superficial"] = 0.9 + min(0.1, (PCT_CRITICO - pct_activa) / PCT_CRITICO * 0.1)

    pesos["agua_superficial"] = 0.6

    # ── Componente 2: precipitación ERA5 (fuente secundaria) ─────────────────
    if precip_mm is not None:
        if precip_mm >= PRECIP_NORMAL_MM:
            scores["precipitacion"] = 0.0
        elif precip_mm >= PRECIP_BAJA_MM:
            scores["precipitacion"] = (PRECIP_NORMAL_MM - precip_mm) / \
                                      (PRECIP_NORMAL_MM - PRECIP_BAJA_MM) * 0.5
        elif precip_mm >= PRECIP_CRITICA_MM:
            scores["precipitacion"] = 0.5 + (PRECIP_BAJA_MM - precip_mm) / \
                                      (PRECIP_BAJA_MM - PRECIP_CRITICA_MM) * 0.4
        else:
            scores["precipitacion"] = 0.9

        pesos["precipitacion"] = 0.3
        pesos["agua_superficial"] = 0.5

    # ── Componente 3: humedad colmena IoT (señal biológica) ──────────────────
    if hr_colmena is not None:
        # HR baja → las abejas están deshidratadas → falta agua
        # HR alta → no necesariamente problemas de agua
        if hr_colmena < 35:
            scores["hr_colmena"] = 0.8   # HR muy baja → estrés severo
        elif hr_colmena < 45:
            scores["hr_colmena"] = 0.4
        else:
            scores["hr_colmena"] = 0.0   # HR normal → sin señal de estrés hídrico

        pesos["hr_colmena"] = 0.1
        # Redistribuir pesos para que sumen 1
        total_peso = sum(pesos.values())
        pesos = {k: v / total_peso for k, v in pesos.items()}

    # ── Score ponderado ───────────────────────────────────────────────────────
    total_peso = sum(pesos.values())
    score = sum(
        scores[k] * (pesos[k] / total_peso)
        for k in scores
        if k in pesos
    )
    score = round(min(1.0, max(0.0, score)), 3)

    # ── Clasificación ─────────────────────────────────────────────────────────
    if score < 0.2:
        nivel, color = "NORMAL",  "verde"
    elif score < 0.45:
        nivel, color = "REDUCIDA", "amarillo"
    elif score < 0.7:
        nivel, color = "ESCASA",   "naranja"
    else:
        nivel, color = "CRITICA",  "rojo"

    return {
        "score_agua":    score,
        "nivel":         nivel,
        "color":         color,
        "componentes":   scores,
        "pct_activa":    pct_activa,
    }


# ── ANÁLISIS DE SERIE TEMPORAL ────────────────────────────────────────────────

def analizar_disponibilidad_serie(
    df_agua:  pd.DataFrame,
    df_era5:  Optional[pd.DataFrame] = None,
    df_iot:   Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Analiza la disponibilidad de agua para toda la serie temporal.
    Integra todas las fuentes disponibles en un score mensual.

    Returns:
        DataFrame con: fecha, pct_activa, score_agua, nivel, color,
                       precip_mm (si ERA5), hr_colmena (si IoT)
    """
    df = df_agua.copy()
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.to_period("M").dt.to_timestamp()

    # Agregar precipitación ERA5
    if df_era5 is not None and not df_era5.empty and "precip_mm" in df_era5.columns:
        df_e = df_era5[["fecha", "precip_mm"]].copy()
        df_e["fecha"] = pd.to_datetime(df_e["fecha"]).dt.to_period("M").dt.to_timestamp()
        df = df.merge(df_e, on="fecha", how="left")

    # Agregar HR IoT
    if df_iot is not None and not df_iot.empty and "hr_interna" in df_iot.columns:
        col_ts = "fecha" if "fecha" in df_iot.columns else "timestamp"
        df_i   = df_iot[[col_ts, "hr_interna"]].copy()
        df_i[col_ts] = pd.to_datetime(df_i[col_ts]).dt.to_period("M").dt.to_timestamp()
        df_i = df_i.rename(columns={col_ts: "fecha", "hr_interna": "hr_colmena"})
        df = df.merge(df_i, on="fecha", how="left")

    # Calcular score integrado para cada fila
    resultados = []
    for _, row in df.iterrows():
        res = calcular_score_agua(
            pct_activa  = row.get("pct_agua_activa", 50.0),
            precip_mm   = row.get("precip_mm"),
            hr_colmena  = row.get("hr_colmena"),
        )
        resultados.append(res)

    df["score_agua"] = [r["score_agua"] for r in resultados]
    df["nivel_agua"] = [r["nivel"]      for r in resultados]
    df["color_agua"] = [r["color"]      for r in resultados]

    logger.info(
        f"💧 Análisis de agua completado: {len(df)} meses | "
        f"críticos: {(df['nivel_agua'] == 'CRITICA').sum()} | "
        f"escasos: {(df['nivel_agua'] == 'ESCASA').sum()}"
    )
    return df


# ── LÍNEA BASE DE AGUA ────────────────────────────────────────────────────────

def construir_linea_base_agua(
    df:             pd.DataFrame,
    periodo_inicio: int = 2022,
    periodo_fin:    int = 2024,
) -> pd.DataFrame:
    """
    Construye la línea base mensual de disponibilidad de agua.
    Usa los valores reales del piloto como referencia.
    """
    df = df.copy()
    df["mes"] = pd.to_datetime(df["fecha"]).dt.month
    df["año"] = pd.to_datetime(df["fecha"]).dt.year

    df_ref = df[(df["año"] >= periodo_inicio) & (df["año"] <= periodo_fin)]
    if df_ref.empty:
        df_ref = df

    lb = (
        df_ref
        .groupby("mes")["pct_agua_activa"]
        .agg(
            agua_media = "mean",
            agua_sigma = "std",
            agua_n     = "count",
        )
        .reset_index()
    )
    lb["agua_sigma"] = lb["agua_sigma"].fillna(5.0).clip(lower=2.0)
    return lb


# ── ALERTAS DE AGUA ───────────────────────────────────────────────────────────

def generar_alertas_agua_serie(
    df:          pd.DataFrame,
    n_colmenas:  int = 1,
) -> pd.DataFrame:
    """
    Genera alertas de agua para todos los meses de la serie.

    Returns:
        DataFrame con alertas activas (solo meses con nivel != NORMAL)
    """
    alertas = []
    litros_dia = n_colmenas * LITROS_MIN_COLMENA

    for _, row in df.iterrows():
        nivel = row.get("nivel_agua", "NORMAL")
        if nivel == "NORMAL":
            continue

        fecha_str = pd.Timestamp(row["fecha"]).strftime("%B %Y")
        pct       = row.get("pct_agua_activa", 0)
        precip    = row.get("precip_mm", None)

        if nivel == "CRITICA":
            mensaje = (
                f"URGENTE — {fecha_str}: Sequía crítica. "
                f"Agua superficial al {pct:.0f}% del normal. "
                f"Sus {n_colmenas} colmenas necesitan {litros_dia:.0f} L/día. "
                f"Instale bebedero artificial a menos de 200m."
            )
            if precip is not None:
                mensaje += f" Precipitación del mes: {precip:.0f}mm."
        elif nivel == "ESCASA":
            mensaje = (
                f"ALERTA — {fecha_str}: Agua escasa. "
                f"Cuerpos de agua al {pct:.0f}% del nivel normal. "
                f"Verifique fuentes de agua a menos de 500m del apiario."
            )
        else:
            mensaje = (
                f"AVISO — {fecha_str}: Agua reducida ({pct:.0f}%). "
                f"Monitoree las fuentes de agua esta semana."
            )

        alertas.append({
            "fecha":     row["fecha"],
            "nivel":     nivel,
            "pct_agua":  pct,
            "precip_mm": precip,
            "mensaje":   mensaje,
        })

    df_alertas = pd.DataFrame(alertas) if alertas else pd.DataFrame()
    logger.info(f"⚠️  {len(df_alertas)} alertas de agua generadas")
    return df_alertas


# ── RECOMENDACIÓN DE BEBEDEROS ────────────────────────────────────────────────

def recomendar_bebedero(
    pct_activa:  float,
    n_colmenas:  int   = 1,
    radio_m:     float = RADIO_ACCESO_M,
) -> dict:
    """
    Genera recomendación específica sobre instalación de bebedero artificial.
    """
    litros_dia = n_colmenas * LITROS_MIN_COLMENA

    if pct_activa >= PCT_NORMAL:
        return {
            "necesita_bebedero": False,
            "recomendacion":     "Fuentes naturales suficientes. Sin acción requerida.",
        }
    elif pct_activa >= PCT_ALERTA:
        return {
            "necesita_bebedero": True,
            "urgencia":          "PREVENTIVA",
            "capacidad_litros":  round(litros_dia * 3, 1),   # 3 días de reserva
            "distancia_max_m":   radio_m,
            "recomendacion":     (
                f"Instale un bebedero con {litros_dia * 3:.0f}L de capacidad "
                f"(3 días de reserva) a menos de {radio_m:.0f}m del apiario. "
                f"Rellene cada 3 días."
            ),
        }
    else:
        return {
            "necesita_bebedero": True,
            "urgencia":          "INMEDIATA",
            "capacidad_litros":  round(litros_dia * 7, 1),   # 1 semana de reserva
            "distancia_max_m":   200,                         # más cerca en emergencia
            "recomendacion":     (
                f"URGENTE: Instale bebedero de {litros_dia * 7:.0f}L "
                f"a menos de 200m del apiario. "
                f"La falta de agua puede matar colonias en 48-72h en calor. "
                f"Rellene diariamente."
            ),
        }


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_disponibilidad(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/agua_superficial.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, date_format="%Y-%m-%d")
    logger.info(f"💾 Disponibilidad de agua guardada: {ruta}")
    return ruta


def guardar_alertas_agua(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/alertas_agua.csv",
) -> Path:
    if df.empty:
        return Path(ruta)
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, date_format="%Y-%m-%d")
    logger.info(f"💾 Alertas de agua guardadas: {ruta}")
    return ruta


# ── DEMO CON DATOS REALES DEL PILOTO ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    MESES_ES = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}

    print("═" * 60)
    print("  AbejaVerde·EO — agua_disponibilidad")
    print("  Apiario San Juan de Rioseco — datos reales piloto")
    print("═" * 60)

    FECHAS = pd.date_range("2024-01", "2025-05", freq="MS")

    df_agua = pd.DataFrame({
        "fecha":           FECHAS,
        "pct_agua_activa": [11.7,50.6,81.7,105,105,105,58.3,81.7,105,105,
                            89.4,64.2,14.8,16.3,89.4,8.6,105],
    })

    df_era5 = pd.DataFrame({
        "fecha":     FECHAS,
        "precip_mm": [30,130,210,280,380,310,150,210,300,280,230,165,
                      38,42,230,22,405],
    })

    # Análisis integrado
    df_analisis = analizar_disponibilidad_serie(df_agua, df_era5)

    print(f"\n💧 Disponibilidad integrada de agua:")
    for _, r in df_analisis.iterrows():
        mes   = MESES_ES[r["fecha"].month]
        año   = r["fecha"].year
        pct   = r["pct_agua_activa"]
        prec  = r.get("precip_mm", 0)
        score = r["score_agua"]
        nivel = r["nivel_agua"]
        bar   = "█" * int(pct / 8)
        flag  = "⚠️ " if nivel in ("CRITICA","ESCASA") else "   "
        print(f"   {flag}{mes} {año}  agua={pct:5.1f}%  precip={prec:4.0f}mm  "
              f"score={score:.2f}  [{nivel}]  {bar}")

    # Alertas
    alertas = generar_alertas_agua_serie(df_analisis, n_colmenas=10)
    print(f"\n⚠️  Alertas de agua generadas: {len(alertas)}")
    for _, a in alertas.iterrows():
        print(f"   [{a['nivel']}] {a['mensaje'][:80]}...")

    # Recomendación de bebedero para el mes más crítico (abril 2025)
    print(f"\n🪣 Recomendación bebedero — Abril 2025 (8.6% agua, 22mm precip):")
    rec = recomendar_bebedero(8.6, n_colmenas=10)
    print(f"   Necesita bebedero: {rec['necesita_bebedero']}")
    print(f"   Urgencia: {rec.get('urgencia','N/A')}")
    print(f"   Capacidad: {rec.get('capacidad_litros','N/A')} litros")
    print(f"   {rec['recomendacion']}")

    guardar_disponibilidad(df_analisis)
    guardar_alertas_agua(alertas)
