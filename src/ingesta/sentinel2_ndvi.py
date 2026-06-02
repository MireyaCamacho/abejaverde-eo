"""
AbejaVerde·EO — Módulo: sentinel2_ndvi
=======================================
Cálculo de serie temporal NDVI/EVI desde Sentinel-2 L2A
y construcción de línea base histórica.

Flujo:
    1. Usar CDSEClient.calcular_ndvi_openeo() para obtener valores crudos
    2. Resamplear a promedios mensuales
    3. Calcular EVI opcional (requiere banda B02 azul)
    4. Construir línea base histórica (media + σ por mes del año)
    5. Calcular anomalías estandarizadas
    6. Exportar ndvi_series.csv y linea_base_ndvi.csv

Outputs:
    data/processed/ndvi_series.csv
    data/reference/linea_base/linea_base_ndvi.csv

Uso:
    from src.ingesta.sentinel2_ndvi import calcular_ndvi_serie, construir_linea_base
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

from src.ingesta.copernicus_api import (
    CDSEClient,
    bbox_desde_coordenadas,
    resamplear_mensual,
)

logger = logging.getLogger(__name__)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

# Rango considerado válido para NDVI en zona apícola de Cundinamarca
NDVI_MIN_VALIDO =  0.10
NDVI_MAX_VALIDO =  0.95

# Período de referencia para línea base histórica
LINEA_BASE_INICIO = "2022-01-01"
LINEA_BASE_FIN    = "2024-12-31"

# Umbrales de alerta (calibrados con datos reales del piloto)
NDVI_FLORACION_ACTIVA  = 0.60   # ≥ este valor → floración probable
NDVI_ESCASEZ           = 0.48   # < este valor → escasez probable
NDVI_CRISIS            = 0.35   # < este valor → estrés severo


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────────────────

def calcular_ndvi_serie(
    lat:           float,
    lon:           float,
    fecha_inicio:  str,
    fecha_fin:     str,
    radio_km:      float = 3.0,
    max_nubosidad: float = 40.0,
    client:        Optional[CDSEClient] = None,
) -> pd.DataFrame:
    """
    Calcula la serie temporal NDVI mensual para un apiario.

    Args:
        lat, lon:       coordenadas del apiario
        fecha_inicio:   "YYYY-MM-DD"
        fecha_fin:      "YYYY-MM-DD"
        radio_km:       radio de análisis (radio de vuelo de las abejas)
        max_nubosidad:  % máximo de nubosidad para filtrar imágenes
        client:         CDSEClient existente (crea uno nuevo si None)

    Returns:
        DataFrame con columnas: fecha, ndvi, año, mes
    """
    client = client or CDSEClient()
    bbox   = bbox_desde_coordenadas(lat, lon, radio_km)

    logger.info(
        f"🛰  Calculando NDVI | {lat}°N {lon}°O | "
        f"radio {radio_km} km | {fecha_inicio} → {fecha_fin}"
    )

    # Obtener valores crudos via openEO
    registros_crudos = client.calcular_ndvi_openeo(
        bbox          = bbox,
        fecha_inicio  = fecha_inicio,
        fecha_fin     = fecha_fin,
        max_nubosidad = max_nubosidad,
    )

    if not registros_crudos:
        logger.warning("⚠️  Sin datos NDVI — verifica credenciales y conexión")
        return pd.DataFrame(columns=["fecha", "ndvi", "año", "mes"])

    # Resamplear a mensual
    registros_mensuales = resamplear_mensual(registros_crudos, "ndvi")

    # Construir DataFrame
    df = pd.DataFrame(registros_mensuales)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["año"]   = df["fecha"].dt.year
    df["mes"]   = df["fecha"].dt.month

    # Filtrar valores fuera de rango
    df = df[
        (df["ndvi"] >= NDVI_MIN_VALIDO) &
        (df["ndvi"] <= NDVI_MAX_VALIDO)
    ].reset_index(drop=True)

    # Clasificar estado fenológico básico
    df["estado"] = df["ndvi"].apply(_clasificar_estado_ndvi)

    logger.info(
        f"✅ NDVI calculado — {len(df)} meses | "
        f"min={df['ndvi'].min():.3f} | max={df['ndvi'].max():.3f} | "
        f"prom={df['ndvi'].mean():.3f}"
    )
    return df


def _clasificar_estado_ndvi(ndvi: float) -> str:
    """Clasifica el NDVI en estado apícola."""
    if ndvi >= NDVI_FLORACION_ACTIVA:
        return "FLORACION_ACTIVA"
    elif ndvi >= NDVI_ESCASEZ:
        return "TRANSICION"
    elif ndvi >= NDVI_CRISIS:
        return "ESCASEZ"
    else:
        return "CRISIS"


# ── LÍNEA BASE HISTÓRICA ──────────────────────────────────────────────────────

def construir_linea_base(
    df_ndvi:        pd.DataFrame,
    periodo_inicio: int = 2022,
    periodo_fin:    int = 2024,
) -> pd.DataFrame:
    """
    Construye la línea base histórica mensual (media + σ) a partir
    de la serie NDVI.

    La línea base se calcula por mes del año (1-12) sobre el período
    de referencia. Se usa para detectar anomalías en tiempo real.

    Args:
        df_ndvi:        DataFrame con columnas fecha, ndvi, año, mes
        periodo_inicio: año de inicio del período de referencia
        periodo_fin:    año de fin (inclusive)

    Returns:
        DataFrame con: mes, ndvi_media, ndvi_sigma, n_observaciones
    """
    df_ref = df_ndvi[
        (df_ndvi["año"] >= periodo_inicio) &
        (df_ndvi["año"] <= periodo_fin)
    ].copy()

    if df_ref.empty:
        logger.warning(
            f"⚠️  Sin datos para línea base {periodo_inicio}–{periodo_fin}. "
            f"Usando todos los datos disponibles."
        )
        df_ref = df_ndvi.copy()

    linea_base = (
        df_ref
        .groupby("mes")["ndvi"]
        .agg(
            ndvi_media = "mean",
            ndvi_sigma = "std",
            n          = "count",
        )
        .reset_index()
    )

    # Sigma mínima para evitar división por cero
    linea_base["ndvi_sigma"] = linea_base["ndvi_sigma"].fillna(0.05).clip(lower=0.03)

    logger.info(
        f"📊 Línea base construida | "
        f"{periodo_inicio}–{periodo_fin} | "
        f"{len(df_ref)} observaciones"
    )
    return linea_base


def calcular_anomalias(
    df_ndvi:     pd.DataFrame,
    linea_base:  pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula anomalías estandarizadas respecto a la línea base.

    anomalia = (ndvi_actual - ndvi_media_mes) / sigma_mes

    Valores positivos: NDVI por encima del promedio histórico
    Valores negativos: NDVI por debajo (déficit, posible escasez)

    Returns:
        df_ndvi con columnas adicionales: ndvi_media_hist, ndvi_sigma_hist, anomalia
    """
    df = df_ndvi.merge(
        linea_base[["mes", "ndvi_media", "ndvi_sigma"]],
        on  = "mes",
        how = "left",
    )
    df.rename(columns={
        "ndvi_media": "ndvi_media_hist",
        "ndvi_sigma": "ndvi_sigma_hist",
    }, inplace=True)

    df["anomalia"] = (
        (df["ndvi"] - df["ndvi_media_hist"]) / df["ndvi_sigma_hist"]
    ).round(3)

    # Clasificar la anomalía
    df["anomalia_nivel"] = df["anomalia"].apply(_clasificar_anomalia)

    return df


def _clasificar_anomalia(z: float) -> str:
    """Clasifica la anomalía estandarizada en niveles de riesgo."""
    if z >= 1.0:
        return "MUY_ALTO"      # floración excepcional
    elif z >= 0.3:
        return "ALTO"          # por encima del promedio
    elif z >= -0.3:
        return "NORMAL"
    elif z >= -1.0:
        return "BAJO"          # déficit moderado
    else:
        return "MUY_BAJO"      # déficit severo — alerta


# ── DETECCIÓN DE PERÍODOS ─────────────────────────────────────────────────────

def detectar_periodos_floracion(df_ndvi: pd.DataFrame) -> pd.DataFrame:
    """
    Identifica los períodos de floración activa y escasez en la serie.

    Returns:
        DataFrame con: fecha_inicio, fecha_fin, tipo, ndvi_max/min, duracion_dias
    """
    if df_ndvi.empty:
        return pd.DataFrame()

    df = df_ndvi.sort_values("fecha").copy()
    periodos = []
    en_floracion = False
    en_escasez   = False
    inicio_periodo = None
    ndvi_extremo   = None

    for _, row in df.iterrows():
        ndvi  = row["ndvi"]
        fecha = row["fecha"]

        # Detectar floración activa
        if ndvi >= NDVI_FLORACION_ACTIVA and not en_floracion:
            en_floracion   = True
            inicio_periodo = fecha
            ndvi_extremo   = ndvi
        elif ndvi >= NDVI_FLORACION_ACTIVA and en_floracion:
            ndvi_extremo = max(ndvi_extremo, ndvi)
        elif ndvi < NDVI_FLORACION_ACTIVA and en_floracion:
            periodos.append({
                "tipo":          "FLORACION",
                "fecha_inicio":  inicio_periodo,
                "fecha_fin":     fecha,
                "ndvi_pico":     round(ndvi_extremo, 3),
                "duracion_meses": (fecha.year - inicio_periodo.year) * 12
                                  + fecha.month - inicio_periodo.month,
            })
            en_floracion = False

        # Detectar escasez
        if ndvi < NDVI_ESCASEZ and not en_escasez:
            en_escasez     = True
            inicio_periodo = fecha
            ndvi_extremo   = ndvi
        elif ndvi < NDVI_ESCASEZ and en_escasez:
            ndvi_extremo = min(ndvi_extremo, ndvi)
        elif ndvi >= NDVI_ESCASEZ and en_escasez:
            periodos.append({
                "tipo":          "ESCASEZ",
                "fecha_inicio":  inicio_periodo,
                "fecha_fin":     fecha,
                "ndvi_min":      round(ndvi_extremo, 3),
                "duracion_meses": (fecha.year - inicio_periodo.year) * 12
                                  + fecha.month - inicio_periodo.month,
            })
            en_escasez = False

    return pd.DataFrame(periodos) if periodos else pd.DataFrame()


def mes_pico_floracion(df_ndvi: pd.DataFrame) -> dict:
    """
    Identifica el mes de mayor y menor actividad vegetal histórica.
    Útil para calibrar el calendario floral del territorio.
    """
    if df_ndvi.empty:
        return {}

    por_mes = df_ndvi.groupby("mes")["ndvi"].mean()

    return {
        "mes_max_ndvi":    int(por_mes.idxmax()),
        "ndvi_max_prom":   round(por_mes.max(), 3),
        "mes_min_ndvi":    int(por_mes.idxmin()),
        "ndvi_min_prom":   round(por_mes.min(), 3),
        "amplitud_anual":  round(por_mes.max() - por_mes.min(), 3),
    }


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_ndvi(
    df:         pd.DataFrame,
    ruta:       Union[str, Path] = "data/processed/ndvi_series.csv",
) -> Path:
    """Guarda la serie NDVI en CSV."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, date_format="%Y-%m-%d")
    logger.info(f"💾 NDVI guardado: {ruta}")
    return ruta


def guardar_linea_base(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/reference/linea_base/linea_base_ndvi.csv",
) -> Path:
    """Guarda la línea base en CSV."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 Línea base NDVI guardada: {ruta}")
    return ruta


def cargar_ndvi(
    ruta: Union[str, Path] = "data/processed/ndvi_series.csv",
) -> pd.DataFrame:
    """Carga la serie NDVI desde CSV."""
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(f"⚠️  No se encontró {ruta}")
        return pd.DataFrame()
    df = pd.read_csv(ruta, parse_dates=["fecha"])
    logger.info(f"📂 NDVI cargado: {len(df)} registros desde {ruta}")
    return df


def cargar_linea_base(
    ruta: Union[str, Path] = "data/reference/linea_base/linea_base_ndvi.csv",
) -> pd.DataFrame:
    """Carga la línea base desde CSV."""
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(f"⚠️  No se encontró línea base en {ruta}")
        return pd.DataFrame()
    return pd.read_csv(ruta)


# ── PIPELINE COMPLETO ─────────────────────────────────────────────────────────

def pipeline_ndvi(
    lat:              float,
    lon:              float,
    fecha_inicio:     str,
    fecha_fin:        str,
    radio_km:         float = 3.0,
    guardar:          bool  = True,
    client:           Optional[CDSEClient] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Pipeline completo: descarga → mensual → línea base → anomalías → guarda.

    Returns:
        (df_ndvi_con_anomalias, df_linea_base)
    """
    # 1. Calcular serie NDVI
    df_ndvi = calcular_ndvi_serie(
        lat          = lat,
        lon          = lon,
        fecha_inicio = fecha_inicio,
        fecha_fin    = fecha_fin,
        radio_km     = radio_km,
        client       = client,
    )

    if df_ndvi.empty:
        return df_ndvi, pd.DataFrame()

    # 2. Construir línea base histórica
    linea_base = construir_linea_base(df_ndvi)

    # 3. Calcular anomalías
    df_ndvi = calcular_anomalias(df_ndvi, linea_base)

    # 4. Detectar períodos
    periodos = detectar_periodos_floracion(df_ndvi)
    patron   = mes_pico_floracion(df_ndvi)

    logger.info(f"🌸 Patrón del territorio: {patron}")
    if not periodos.empty:
        floraciones = periodos[periodos["tipo"] == "FLORACION"]
        escaseces   = periodos[periodos["tipo"] == "ESCASEZ"]
        logger.info(
            f"   {len(floraciones)} períodos de floración detectados | "
            f"{len(escaseces)} períodos de escasez"
        )

    # 5. Persistir
    if guardar:
        guardar_ndvi(df_ndvi)
        guardar_linea_base(linea_base)

    return df_ndvi, linea_base


# ── DEMO CON DATOS REALES DEL PILOTO ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    # Datos reales del piloto — 17 meses procesados con openEO
    DATOS_REALES = [
        {"fecha": "2024-01", "ndvi": 0.474},
        {"fecha": "2024-02", "ndvi": 0.618},
        {"fecha": "2024-03", "ndvi": 0.584},
        {"fecha": "2024-04", "ndvi": 0.513},
        {"fecha": "2024-05", "ndvi": 0.773},
        {"fecha": "2024-06", "ndvi": 0.817},
        {"fecha": "2024-07", "ndvi": 0.529},
        {"fecha": "2024-08", "ndvi": 0.669},
        {"fecha": "2024-09", "ndvi": 0.698},
        {"fecha": "2024-10", "ndvi": 0.697},
        {"fecha": "2024-11", "ndvi": 0.509},
        {"fecha": "2024-12", "ndvi": 0.701},
        {"fecha": "2025-01", "ndvi": 0.437},
        {"fecha": "2025-02", "ndvi": 0.442},
        {"fecha": "2025-03", "ndvi": 0.554},
        {"fecha": "2025-04", "ndvi": 0.379},
        {"fecha": "2025-05", "ndvi": 0.787},
    ]

    print("═" * 60)
    print("  AbejaVerde·EO — sentinel2_ndvi")
    print("  Apiario San Juan de Rioseco — datos reales piloto")
    print("═" * 60)

    # Construir DataFrame desde datos reales
    df = pd.DataFrame(DATOS_REALES)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["año"]   = df["fecha"].dt.year
    df["mes"]   = df["fecha"].dt.month
    df["estado"] = df["ndvi"].apply(_clasificar_estado_ndvi)

    # Línea base con los mismos datos (piloto único)
    linea_base = construir_linea_base(df, 2024, 2024)
    df_con_anomalias = calcular_anomalias(df, linea_base)

    print(f"\n📊 Serie NDVI real — {len(df)} meses")
    print(f"   Min : {df['ndvi'].min():.3f}  ({df.loc[df['ndvi'].idxmin(),'fecha'].strftime('%b %Y')})")
    print(f"   Max : {df['ndvi'].max():.3f}  ({df.loc[df['ndvi'].idxmax(),'fecha'].strftime('%b %Y')})")
    print(f"   Prom: {df['ndvi'].mean():.3f}")

    # Patrón del territorio
    patron = mes_pico_floracion(df)
    meses_es = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",
                6:"Junio",7:"Julio",8:"Agosto",9:"Septiembre",
                10:"Octubre",11:"Noviembre",12:"Diciembre"}
    print(f"\n🌸 Patrón del territorio:")
    print(f"   Mes de mayor floración : {meses_es[patron['mes_max_ndvi']]} (NDVI prom. {patron['ndvi_max_prom']})")
    print(f"   Mes de mayor escasez   : {meses_es[patron['mes_min_ndvi']]} (NDVI prom. {patron['ndvi_min_prom']})")
    print(f"   Amplitud anual         : {patron['amplitud_anual']}")

    # Períodos detectados
    periodos = detectar_periodos_floracion(df)
    if not periodos.empty:
        print(f"\n🔍 Períodos detectados:")
        for _, p in periodos.iterrows():
            if p["tipo"] == "FLORACION":
                print(f"   🌿 Floración  {p['fecha_inicio'].strftime('%b %Y')} → "
                      f"{p['fecha_fin'].strftime('%b %Y')}  "
                      f"pico NDVI {p.get('ndvi_pico','N/A')}")
            else:
                print(f"   ⚠️  Escasez    {p['fecha_inicio'].strftime('%b %Y')} → "
                      f"{p['fecha_fin'].strftime('%b %Y')}  "
                      f"min NDVI {p.get('ndvi_min','N/A')}")

    # Top anomalías
    print(f"\n📉 Anomalías más significativas:")
    top = df_con_anomalias.nsmallest(3, "anomalia")[["fecha","ndvi","anomalia","anomalia_nivel"]]
    for _, row in top.iterrows():
        print(f"   {row['fecha'].strftime('%b %Y')}  NDVI={row['ndvi']:.3f}  "
              f"z={row['anomalia']:+.2f}  [{row['anomalia_nivel']}]")
