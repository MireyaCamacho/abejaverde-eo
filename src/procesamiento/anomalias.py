"""
AbejaVerde·EO — Módulo: anomalias
===================================
Cálculo consolidado de anomalías cruzando todas las fuentes de datos.

Este módulo toma las series individuales (NDVI, ERA5, IoT, agua)
y produce una tabla unificada de anomalías por fecha y apiario,
lista para alimentar el IRA y el motor de alertas.

Flujo:
    ndvi_series.csv   ─┐
    era5_series.csv   ─┤─→ anomalias.py → anomalias.csv → IRA → alertas
    iot_clean.csv     ─┤
    agua_superficial  ─┘

Anomalía estandarizada:
    z_X = (X_observado − X_media_histórica) / σ_histórica

Señal de doble evidencia (plan V2):
    Una alerta solo se activa cuando hay convergencia entre:
    - Señal satelital (NDVI y/o ERA5 anómalos)
    - Señal biológica (IoT anómalo), cuando disponible

Outputs:
    data/processed/anomalias.csv   — anomalías por fecha y apiario
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────────────────

def calcular_anomalias_consolidadas(
    df_ndvi:   pd.DataFrame,
    df_era5:   pd.DataFrame,
    df_agua:   Optional[pd.DataFrame]  = None,
    df_iot:    Optional[pd.DataFrame]  = None,
    apiario_id: str = "API_SJR_01",
) -> pd.DataFrame:
    """
    Consolida anomalías de todas las fuentes en una tabla mensual unificada.

    Args:
        df_ndvi:    Serie NDVI con columnas fecha, ndvi, anomalia (de sentinel2_ndvi)
        df_era5:    Serie ERA5 con columnas fecha, temp_c, precip_mm, anom_temp, anom_precip
        df_agua:    Serie agua con columnas fecha, pct_agua_activa (opcional)
        df_iot:     Serie IoT mensual con columnas fecha, temp_interna, hr_interna (opcional)
        apiario_id: identificador del apiario

    Returns:
        DataFrame con todas las anomalías consolidadas por fecha
    """
    # ── Preparar cada fuente ──────────────────────────────────────────────────
    dfs = []

    # NDVI
    if df_ndvi is not None and not df_ndvi.empty:
        df_n = df_ndvi[["fecha", "ndvi"]].copy()
        if "anomalia" in df_ndvi.columns:
            df_n["anom_ndvi"] = df_ndvi["anomalia"]
        if "estado" in df_ndvi.columns:
            df_n["estado_ndvi"] = df_ndvi["estado"]
        df_n["fecha"] = pd.to_datetime(df_n["fecha"]).dt.to_period("M").dt.to_timestamp()
        dfs.append(df_n)

    # ERA5
    if df_era5 is not None and not df_era5.empty:
        cols_era5 = ["fecha"]
        for c in ["temp_c", "precip_mm", "anom_temp", "anom_precip",
                  "estres_hidrico", "estado_temp", "estado_precip"]:
            if c in df_era5.columns:
                cols_era5.append(c)
        df_e = df_era5[cols_era5].copy()
        df_e["fecha"] = pd.to_datetime(df_e["fecha"]).dt.to_period("M").dt.to_timestamp()
        dfs.append(df_e)

    # Agua
    if df_agua is not None and not df_agua.empty:
        cols_agua = ["fecha", "pct_agua_activa"]
        if "estado_agua" in df_agua.columns:
            cols_agua.append("estado_agua")
        df_a = df_agua[cols_agua].copy()
        df_a["fecha"] = pd.to_datetime(df_a["fecha"]).dt.to_period("M").dt.to_timestamp()
        dfs.append(df_a)

    # IoT
    if df_iot is not None and not df_iot.empty:
        cols_iot = ["fecha"]
        for c in ["temp_interna", "hr_interna", "peso_total_g", "peso_cambio_pct"]:
            if c in df_iot.columns:
                cols_iot.append(c)
        df_i = df_iot[cols_iot].copy()
        df_i["fecha"] = pd.to_datetime(df_i["fecha"]).dt.to_period("M").dt.to_timestamp()
        dfs.append(df_i)

    if not dfs:
        logger.warning("⚠️  Sin datos para calcular anomalías")
        return pd.DataFrame()

    # ── Merge por fecha ───────────────────────────────────────────────────────
    df = dfs[0]
    for df_extra in dfs[1:]:
        df = df.merge(df_extra, on="fecha", how="outer")

    df = df.sort_values("fecha").reset_index(drop=True)
    df["apiario_id"] = apiario_id

    # ── Score de convergencia (doble evidencia) ───────────────────────────────
    df["convergencia_score"] = _calcular_convergencia(df)
    df["alerta_convergente"] = df["convergencia_score"] >= 2

    # ── Clasificación global del mes ──────────────────────────────────────────
    df["estado_mes"] = df.apply(_clasificar_mes, axis=1)

    logger.info(
        f"✅ Anomalías consolidadas: {len(df)} meses | "
        f"alertas convergentes: {df['alerta_convergente'].sum()}"
    )
    return df


def _calcular_convergencia(df: pd.DataFrame) -> pd.Series:
    """
    Calcula el score de convergencia entre fuentes satelitales y biológicas.
    Cada señal anómala suma 1 punto. Score ≥ 2 → alerta convergente.
    """
    score = pd.Series(0, index=df.index)

    # Señal NDVI
    if "anom_ndvi" in df.columns:
        score += (df["anom_ndvi"] < -1.0).astype(int)

    # Señal ERA5 temperatura
    if "anom_temp" in df.columns:
        score += (df["anom_temp"].abs() > 1.5).astype(int)

    # Señal ERA5 precipitación
    if "anom_precip" in df.columns:
        score += (df["anom_precip"] < -1.0).astype(int)

    # Señal agua
    if "pct_agua_activa" in df.columns:
        score += (df["pct_agua_activa"] < 30).astype(int)

    # Señal IoT temperatura (biológica)
    if "temp_interna" in df.columns:
        score += (
            (df["temp_interna"] < 34.0) | (df["temp_interna"] > 37.0)
        ).astype(int)

    # Señal IoT humedad
    if "hr_interna" in df.columns:
        score += (df["hr_interna"] > 75).astype(int)

    return score


def _clasificar_mes(row: pd.Series) -> str:
    """Clasifica el estado general del mes según las señales disponibles."""
    score = row.get("convergencia_score", 0)

    if score == 0:
        return "NORMAL"
    elif score == 1:
        return "ATENCION"
    elif score == 2:
        return "ALERTA"
    else:
        return "CRITICO"


# ── DETECCIÓN DE EVENTOS EXTREMOS ─────────────────────────────────────────────

def detectar_eventos_extremos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifica los eventos más extremos del período para reportes.
    Útil para la sección de hallazgos del dashboard y Taikai.
    """
    eventos = []

    if "ndvi" in df.columns:
        idx_max = df["ndvi"].idxmax()
        idx_min = df["ndvi"].idxmin()
        eventos.append({
            "fecha":     df.loc[idx_max, "fecha"],
            "tipo":      "NDVI_MAXIMO",
            "variable":  "ndvi",
            "valor":     df.loc[idx_max, "ndvi"],
            "descripcion": "Pico máximo de vegetación activa",
        })
        eventos.append({
            "fecha":     df.loc[idx_min, "fecha"],
            "tipo":      "NDVI_MINIMO",
            "variable":  "ndvi",
            "valor":     df.loc[idx_min, "ndvi"],
            "descripcion": "Mínimo de vegetación — mayor riesgo de escasez",
        })

    if "precip_mm" in df.columns:
        idx_min = df["precip_mm"].idxmin()
        eventos.append({
            "fecha":       df.loc[idx_min, "fecha"],
            "tipo":        "PRECIPITACION_MINIMA",
            "variable":    "precip_mm",
            "valor":       df.loc[idx_min, "precip_mm"],
            "descripcion": "Mes más seco del período",
        })

    if "pct_agua_activa" in df.columns:
        idx_min = df["pct_agua_activa"].idxmin()
        eventos.append({
            "fecha":       df.loc[idx_min, "fecha"],
            "tipo":        "AGUA_MINIMA",
            "variable":    "pct_agua_activa",
            "valor":       df.loc[idx_min, "pct_agua_activa"],
            "descripcion": "Menor disponibilidad de agua del período",
        })

    return pd.DataFrame(eventos) if eventos else pd.DataFrame()


def resumen_estadistico(df: pd.DataFrame) -> dict:
    """
    Genera un resumen estadístico del período para reportes.
    """
    resumen = {
        "n_meses":            len(df),
        "meses_normales":     int((df["estado_mes"] == "NORMAL").sum())   if "estado_mes" in df.columns else None,
        "meses_atencion":     int((df["estado_mes"] == "ATENCION").sum()) if "estado_mes" in df.columns else None,
        "meses_alerta":       int((df["estado_mes"] == "ALERTA").sum())   if "estado_mes" in df.columns else None,
        "meses_criticos":     int((df["estado_mes"] == "CRITICO").sum())  if "estado_mes" in df.columns else None,
        "alertas_convergentes": int(df["alerta_convergente"].sum())        if "alerta_convergente" in df.columns else None,
    }

    if "ndvi" in df.columns:
        resumen.update({
            "ndvi_min":   round(df["ndvi"].min(), 3),
            "ndvi_max":   round(df["ndvi"].max(), 3),
            "ndvi_prom":  round(df["ndvi"].mean(), 3),
        })

    if "temp_c" in df.columns:
        resumen["temp_media"] = round(df["temp_c"].mean(), 2)

    if "precip_mm" in df.columns:
        resumen["precip_anual_prom"] = round(df["precip_mm"].mean() * 12, 0)

    return resumen


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_anomalias(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/anomalias.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, date_format="%Y-%m-%d")
    logger.info(f"💾 Anomalías guardadas: {ruta}")
    return ruta


def cargar_anomalias(
    ruta: Union[str, Path] = "data/processed/anomalias.csv",
) -> pd.DataFrame:
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(f"⚠️  No se encontró {ruta}")
        return pd.DataFrame()
    return pd.read_csv(ruta, parse_dates=["fecha"])


# ── DEMO CON DATOS REALES DEL PILOTO ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    print("═" * 60)
    print("  AbejaVerde·EO — anomalias")
    print("  Consolidación de señales satelitales y biológicas")
    print("═" * 60)

    # Datos reales del piloto
    FECHAS = pd.date_range("2024-01", "2025-05", freq="MS")

    NDVI_VALS  = [0.474,0.618,0.584,0.513,0.773,0.817,0.529,0.669,
                  0.698,0.697,0.509,0.701,0.437,0.442,0.554,0.379,0.787]
    TEMP_VALS  = [22.62,22.48,22.19,21.85,21.60,21.55,21.82,22.40,
                  22.45,21.50,21.48,21.50,21.43,21.78,21.52,21.12,21.10]
    PREC_VALS  = [30,130,210,280,380,310,150,210,300,280,230,165,
                  38,42,230,22,405]
    AGUA_VALS  = [11.7,50.6,81.7,105,105,105,58.3,81.7,105,105,
                  89.4,64.2,14.8,16.3,89.4,8.6,105]

    ndvi_media = np.mean(NDVI_VALS)
    ndvi_sigma = np.std(NDVI_VALS)
    temp_media = np.mean(TEMP_VALS)
    temp_sigma = np.std(TEMP_VALS)
    prec_media = np.mean(PREC_VALS)
    prec_sigma = np.std(PREC_VALS)

    df_ndvi = pd.DataFrame({
        "fecha":    FECHAS,
        "ndvi":     NDVI_VALS,
        "anomalia": [(v - ndvi_media) / ndvi_sigma for v in NDVI_VALS],
        "estado":   ["FLORACION_ACTIVA" if v >= 0.60 else
                     "TRANSICION"       if v >= 0.48 else
                     "ESCASEZ" for v in NDVI_VALS],
    })

    df_era5 = pd.DataFrame({
        "fecha":       FECHAS,
        "temp_c":      TEMP_VALS,
        "precip_mm":   PREC_VALS,
        "anom_temp":   [(v - temp_media) / temp_sigma for v in TEMP_VALS],
        "anom_precip": [(v - prec_media) / prec_sigma for v in PREC_VALS],
        "estres_hidrico": [round(1 - min(p, 250) / 250, 2) for p in PREC_VALS],
    })

    df_agua = pd.DataFrame({
        "fecha":           FECHAS,
        "pct_agua_activa": AGUA_VALS,
    })

    # Consolidar anomalías
    df_anom = calcular_anomalias_consolidadas(df_ndvi, df_era5, df_agua)

    # Resumen
    resumen = resumen_estadistico(df_anom)
    print(f"\n📊 Resumen del período (Ene 2024 – May 2025):")
    print(f"   Meses normales     : {resumen['meses_normales']}")
    print(f"   Meses en atención  : {resumen['meses_atencion']}")
    print(f"   Meses en alerta    : {resumen['meses_alerta']}")
    print(f"   Meses críticos     : {resumen['meses_criticos']}")
    print(f"   Alertas convergentes: {resumen['alertas_convergentes']}")
    print(f"   NDVI min/max/prom  : {resumen['ndvi_min']}/{resumen['ndvi_max']}/{resumen['ndvi_prom']}")

    # Vista mensual
    meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    print(f"\n📅 Estado por mes:")
    for _, r in df_anom.iterrows():
        mes  = meses_es[r["fecha"].month]
        año  = r["fecha"].year
        conv = f"⚠️  conv={r['convergencia_score']}" if r["convergencia_score"] >= 2 else ""
        print(f"   {mes} {año}  NDVI={r['ndvi']:.3f}  "
              f"P={r['precip_mm']:.0f}mm  "
              f"Agua={r['pct_agua_activa']:.0f}%  "
              f"[{r['estado_mes']}] {conv}")

    # Eventos extremos
    eventos = detectar_eventos_extremos(df_anom)
    print(f"\n🔍 Eventos extremos del período:")
    for _, e in eventos.iterrows():
        print(f"   {e['tipo']:25s} {e['fecha'].strftime('%b %Y')}  "
              f"valor={e['valor']:.3f}  {e['descripcion']}")

    guardar_anomalias(df_anom)
