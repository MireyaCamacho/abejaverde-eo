"""
AbejaVerde·EO — Módulo: era5_land
===================================
Descarga y procesamiento de ERA5-Land desde Copernicus Climate Data Store.
Cubre temperatura, precipitación y evapotranspiración para el apiario piloto.

Flujo:
    1. CDSClient.descargar_era5() → NetCDF en data/raw/copernicus/era5_land/
    2. Leer variables de temperatura (t2m) y precipitación (tp)
    3. Construir serie mensual con unidades apícolas (°C, mm/mes)
    4. Construir línea base histórica (media + σ por mes del año)
    5. Calcular anomalías estandarizadas
    6. Exportar era5_series.csv y linea_base_era5.csv

Outputs:
    data/processed/era5_series.csv
    data/reference/linea_base/linea_base_era5.csv

Variables ERA5 usadas:
    t2m  — temperatura a 2 metros (K → °C)
    tp   — precipitación total  (m → mm/mes)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

from src.ingesta.copernicus_api import CDSClient, bbox_desde_coordenadas

logger = logging.getLogger(__name__)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

# Umbrales apícolas para temperatura ambiente (San Juan de Rioseco ~900m)
TEMP_OPTIMA_MIN  = 20.0   # °C — temperatura mínima favorable
TEMP_OPTIMA_MAX  = 26.0   # °C — temperatura máxima favorable
TEMP_FRIO        = 15.0   # °C — por debajo → actividad reducida
TEMP_CALOR       = 32.0   # °C — por encima → estrés calórico

# Umbrales de precipitación mensual (mm/mes)
PRECIP_ALTA      = 250.0  # mm — temporada lluviosa activa
PRECIP_MODERADA  = 100.0  # mm — transición
PRECIP_DEFICIT   = 50.0   # mm — déficit hídrico
PRECIP_SEQUIA    = 20.0   # mm — sequía

LINEA_BASE_INICIO = 2022
LINEA_BASE_FIN    = 2024


# ── DESCARGA Y LECTURA ────────────────────────────────────────────────────────

def descargar_era5(
    lat:          float,
    lon:          float,
    años:         list[int],
    meses:        Optional[list[int]] = None,
    radio_km:     float = 3.0,
    directorio:   Union[str, Path] = "data/raw/copernicus/era5_land",
    client:       Optional[CDSClient] = None,
) -> Path:
    """
    Descarga ERA5-Land mensual para el área del apiario.

    Args:
        lat, lon:     coordenadas del apiario
        años:         lista de años a descargar
        meses:        lista de meses (1-12). None = todos
        radio_km:     radio de análisis
        directorio:   carpeta destino
        client:       CDSClient existente

    Returns:
        Ruta al NetCDF extraído
    """
    client = client or CDSClient()
    meses  = meses or list(range(1, 13))
    bbox   = bbox_desde_coordenadas(lat, lon, radio_km)

    logger.info(
        f"🌧  Descargando ERA5 | {lat}°N {lon}°O | "
        f"años {min(años)}–{max(años)} | meses {meses}"
    )

    return client.descargar_era5(
        bbox       = bbox,
        años       = años,
        meses      = meses,
        directorio = directorio,
        variables  = ["2m_temperature", "total_precipitation"],
    )


def leer_era5(
    ruta_nc:   Union[str, Path],
    fecha_fin: Optional[str] = None,
) -> pd.DataFrame:
    """
    Lee el NetCDF ERA5 y retorna DataFrame con temperatura y precipitación.

    Args:
        ruta_nc:   ruta al archivo NetCDF
        fecha_fin: filtrar hasta esta fecha "YYYY-MM" (opcional)

    Returns:
        DataFrame con: fecha, año, mes, temp_c, precip_mm, estado_temp, estado_precip
    """
    import datetime as dt

    try:
        import netCDF4 as nc_lib
    except ImportError:
        raise ImportError("Instala netCDF4: pip install netCDF4")

    ruta_nc = Path(ruta_nc)
    if not ruta_nc.exists():
        raise FileNotFoundError(f"No se encontró {ruta_nc}")

    ds      = nc_lib.Dataset(str(ruta_nc))
    tiempos = ds["valid_time"][:]

    registros = []
    for i, t in enumerate(tiempos):
        fecha = dt.datetime.utcfromtimestamp(int(t))
        rec   = {
            "fecha": pd.Timestamp(fecha.year, fecha.month, 1),
            "año":   fecha.year,
            "mes":   fecha.month,
        }

        if "t2m" in ds.variables:
            valores_temp = np.array(ds["t2m"][i])
            rec["temp_c"] = round(float(valores_temp.mean()) - 273.15, 2)

        if "tp" in ds.variables:
            valores_prec = np.array(ds["tp"][i])
            # ERA5 entrega m/s × 30 días × 86400 s/día × 1000 mm/m
            # Para monthly means: valor ya es el promedio del mes
            rec["precip_mm"] = round(float(valores_prec.mean()) * 1000 * 30, 1)

        registros.append(rec)

    ds.close()

    df = pd.DataFrame(registros)

    # Filtrar por fecha_fin si se especifica
    if fecha_fin:
        df = df[df["fecha"] <= pd.Timestamp(fecha_fin)]

    # Clasificar estados apícolas
    if "temp_c" in df.columns:
        df["estado_temp"] = df["temp_c"].apply(_clasificar_estado_temp)

    if "precip_mm" in df.columns:
        df["estado_precip"] = df["precip_mm"].apply(_clasificar_estado_precip)

    df = df.sort_values("fecha").reset_index(drop=True)

    logger.info(
        f"✅ ERA5 leído — {len(df)} meses | "
        f"T° {df['temp_c'].min():.1f}–{df['temp_c'].max():.1f}°C | "
        f"Precip {df['precip_mm'].min():.0f}–{df['precip_mm'].max():.0f} mm"
        if "temp_c" in df.columns and "precip_mm" in df.columns
        else f"✅ ERA5 leído — {len(df)} meses"
    )
    return df


def _clasificar_estado_temp(temp: float) -> str:
    """Estado apícola según temperatura ambiente."""
    if temp < TEMP_FRIO:
        return "FRIO"
    elif temp <= TEMP_OPTIMA_MIN:
        return "FRESCO"
    elif temp <= TEMP_OPTIMA_MAX:
        return "OPTIMA"
    elif temp <= TEMP_CALOR:
        return "CALIDO"
    else:
        return "ESTRES_CALORICO"


def _clasificar_estado_precip(precip: float) -> str:
    """Estado hídrico según precipitación mensual."""
    if precip >= PRECIP_ALTA:
        return "LLUVIA_ALTA"
    elif precip >= PRECIP_MODERADA:
        return "LLUVIA_MODERADA"
    elif precip >= PRECIP_DEFICIT:
        return "DEFICIT_LEVE"
    elif precip >= PRECIP_SEQUIA:
        return "DEFICIT_SEVERO"
    else:
        return "SEQUIA"


# ── LÍNEA BASE HISTÓRICA ──────────────────────────────────────────────────────

def construir_linea_base(
    df:             pd.DataFrame,
    periodo_inicio: int = LINEA_BASE_INICIO,
    periodo_fin:    int = LINEA_BASE_FIN,
) -> pd.DataFrame:
    """
    Construye la línea base climática mensual (media + σ) para cada
    mes del año. Usada para calcular anomalías de temperatura y precipitación.

    Returns:
        DataFrame con: mes, temp_media, temp_sigma, precip_media, precip_sigma, n
    """
    df_ref = df[
        (df["año"] >= periodo_inicio) &
        (df["año"] <= periodo_fin)
    ].copy()

    if df_ref.empty:
        logger.warning("⚠️  Sin datos para línea base — usando todos los disponibles")
        df_ref = df.copy()

    agg_dict = {"n": ("temp_c", "count")}

    if "temp_c" in df_ref.columns:
        agg_dict.update({
            "temp_media":  ("temp_c", "mean"),
            "temp_sigma":  ("temp_c", "std"),
        })
    if "precip_mm" in df_ref.columns:
        agg_dict.update({
            "precip_media": ("precip_mm", "mean"),
            "precip_sigma": ("precip_mm", "std"),
        })

    linea_base = (
        df_ref
        .groupby("mes")
        .agg(**agg_dict)
        .reset_index()
    )

    # Sigma mínima
    for col in ["temp_sigma", "precip_sigma"]:
        if col in linea_base.columns:
            linea_base[col] = linea_base[col].fillna(0.5).clip(lower=0.2)

    logger.info(
        f"📊 Línea base ERA5 construida | "
        f"{periodo_inicio}–{periodo_fin} | {len(df_ref)} observaciones"
    )
    return linea_base


def calcular_anomalias(
    df:          pd.DataFrame,
    linea_base:  pd.DataFrame,
) -> pd.DataFrame:
    """
    Calcula anomalías estandarizadas de temperatura y precipitación.

    anomalia_T    = (T_actual - T_media_mes)    / sigma_T_mes
    anomalia_P    = (P_actual - P_media_mes)    / sigma_P_mes

    Valores positivos temperatura: más caliente de lo normal
    Valores negativos precipitación: déficit respecto al histórico
    """
    df = df.merge(linea_base, on="mes", how="left")

    if "temp_c" in df.columns and "temp_media" in df.columns:
        df["anom_temp"] = (
            (df["temp_c"] - df["temp_media"]) / df["temp_sigma"]
        ).round(3)

    if "precip_mm" in df.columns and "precip_media" in df.columns:
        df["anom_precip"] = (
            (df["precip_mm"] - df["precip_media"]) / df["precip_sigma"]
        ).round(3)

    return df


# ── ÍNDICES DERIVADOS ─────────────────────────────────────────────────────────

def calcular_indice_estres_hidrico(df: pd.DataFrame) -> pd.DataFrame:
    """
    Índice simple de estrés hídrico para abejas:
    combina déficit de precipitación y temperatura alta.

    estres_hidrico = 0 (sin estrés) a 1 (máximo estrés)
    """
    if "precip_mm" not in df.columns or "temp_c" not in df.columns:
        return df

    # Normalizar precipitación (0 = mucha lluvia, 1 = sequía)
    p_norm = 1.0 - (df["precip_mm"].clip(0, PRECIP_ALTA) / PRECIP_ALTA)

    # Normalizar temperatura (0 = fresca, 1 = caliente)
    t_norm = ((df["temp_c"] - TEMP_OPTIMA_MIN) / (TEMP_CALOR - TEMP_OPTIMA_MIN)).clip(0, 1)

    df["estres_hidrico"] = ((0.6 * p_norm + 0.4 * t_norm)).round(3)
    return df


def patron_climatico(df: pd.DataFrame) -> dict:
    """
    Caracteriza el patrón climático anual del territorio.
    Útil para calibrar umbrales del IRA.
    """
    if df.empty:
        return {}

    por_mes = df.groupby("mes").agg({
        "temp_c":    "mean",
        "precip_mm": "mean",
    })

    return {
        "temp_media_anual":     round(df["temp_c"].mean(), 2),
        "temp_max_mes":         int(por_mes["temp_c"].idxmax()),
        "temp_min_mes":         int(por_mes["temp_c"].idxmin()),
        "precip_total_anual":   round(df["precip_mm"].sum(), 0),
        "mes_mas_lluvioso":     int(por_mes["precip_mm"].idxmax()),
        "mes_mas_seco":         int(por_mes["precip_mm"].idxmin()),
        "meses_lluvia_alta":    int((por_mes["precip_mm"] >= PRECIP_ALTA).sum()),
        "meses_deficit":        int((por_mes["precip_mm"] < PRECIP_DEFICIT).sum()),
    }


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_era5(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/era5_series.csv",
) -> Path:
    """Guarda la serie ERA5 en CSV."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, date_format="%Y-%m-%d")
    logger.info(f"💾 ERA5 guardado: {ruta}")
    return ruta


def guardar_linea_base(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/reference/linea_base/linea_base_era5.csv",
) -> Path:
    """Guarda la línea base ERA5 en CSV."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 Línea base ERA5 guardada: {ruta}")
    return ruta


def cargar_era5(
    ruta: Union[str, Path] = "data/processed/era5_series.csv",
) -> pd.DataFrame:
    """Carga la serie ERA5 desde CSV."""
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(f"⚠️  No se encontró {ruta}")
        return pd.DataFrame()
    df = pd.read_csv(ruta, parse_dates=["fecha"])
    logger.info(f"📂 ERA5 cargado: {len(df)} registros")
    return df


# ── PIPELINE COMPLETO ─────────────────────────────────────────────────────────

def pipeline_era5(
    lat:          float,
    lon:          float,
    años:         list[int],
    radio_km:     float = 3.0,
    guardar:      bool  = True,
    client:       Optional[CDSClient] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Pipeline completo: descarga → lectura → línea base → anomalías → guarda.

    Returns:
        (df_era5_con_anomalias, df_linea_base)
    """
    # 1. Descargar
    ruta_nc = descargar_era5(
        lat      = lat,
        lon      = lon,
        años     = años,
        radio_km = radio_km,
        client   = client,
    )

    # 2. Leer
    df = leer_era5(ruta_nc)
    if df.empty:
        return df, pd.DataFrame()

    # 3. Línea base
    linea_base = construir_linea_base(df)

    # 4. Anomalías + estrés hídrico
    df = calcular_anomalias(df, linea_base)
    df = calcular_indice_estres_hidrico(df)

    # 5. Patrón
    patron = patron_climatico(df)
    logger.info(f"🌤  Patrón climático: {patron}")

    # 6. Guardar
    if guardar:
        guardar_era5(df)
        guardar_linea_base(linea_base)

    return df, linea_base


# ── DEMO CON DATOS REALES DEL PILOTO ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    # Datos reales ERA5 del piloto — procesados con openEO/CDS
    DATOS_REALES = [
        {"fecha":"2024-01","temp_c":22.62,"precip_mm": 30.0},
        {"fecha":"2024-02","temp_c":22.48,"precip_mm":130.0},
        {"fecha":"2024-03","temp_c":22.19,"precip_mm":210.0},
        {"fecha":"2024-04","temp_c":21.85,"precip_mm":280.0},
        {"fecha":"2024-05","temp_c":21.60,"precip_mm":380.0},
        {"fecha":"2024-06","temp_c":21.55,"precip_mm":310.0},
        {"fecha":"2024-07","temp_c":21.82,"precip_mm":150.0},
        {"fecha":"2024-08","temp_c":22.40,"precip_mm":210.0},
        {"fecha":"2024-09","temp_c":22.45,"precip_mm":300.0},
        {"fecha":"2024-10","temp_c":21.50,"precip_mm":280.0},
        {"fecha":"2024-11","temp_c":21.48,"precip_mm":230.0},
        {"fecha":"2024-12","temp_c":21.50,"precip_mm":165.0},
        {"fecha":"2025-01","temp_c":21.43,"precip_mm": 38.0},
        {"fecha":"2025-02","temp_c":21.78,"precip_mm": 42.0},
        {"fecha":"2025-03","temp_c":21.52,"precip_mm":230.0},
        {"fecha":"2025-04","temp_c":21.12,"precip_mm": 22.0},
        {"fecha":"2025-05","temp_c":21.10,"precip_mm":405.0},
    ]

    print("═" * 60)
    print("  AbejaVerde·EO — era5_land")
    print("  Apiario San Juan de Rioseco — datos reales piloto")
    print("═" * 60)

    df = pd.DataFrame(DATOS_REALES)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["año"]   = df["fecha"].dt.year
    df["mes"]   = df["fecha"].dt.month
    df["estado_temp"]   = df["temp_c"].apply(_clasificar_estado_temp)
    df["estado_precip"] = df["precip_mm"].apply(_clasificar_estado_precip)
    df = calcular_indice_estres_hidrico(df)

    linea_base = construir_linea_base(df, 2024, 2024)
    df         = calcular_anomalias(df, linea_base)

    meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}

    patron = patron_climatico(df)
    print(f"\n🌤  Patrón climático del territorio:")
    print(f"   Temperatura media anual  : {patron['temp_media_anual']}°C")
    print(f"   Mes más lluvioso         : {meses_es[patron['mes_mas_lluvioso']]}")
    print(f"   Mes más seco             : {meses_es[patron['mes_mas_seco']]}")
    print(f"   Precipitación anual total: {patron['precip_total_anual']:.0f} mm")
    print(f"   Meses con lluvia alta    : {patron['meses_lluvia_alta']}")
    print(f"   Meses con déficit        : {patron['meses_deficit']}")

    print(f"\n📉 Períodos de mayor estrés hídrico (precip + temp):")
    top_estres = df.nlargest(3, "estres_hidrico")[
        ["fecha","temp_c","precip_mm","estres_hidrico","estado_precip"]
    ]
    for _, r in top_estres.iterrows():
        print(f"   {r['fecha'].strftime('%b %Y')}  "
              f"T°={r['temp_c']:.1f}°C  "
              f"P={r['precip_mm']:.0f}mm  "
              f"estrés={r['estres_hidrico']:.2f}  "
              f"[{r['estado_precip']}]")

    print(f"\n🌧  Serie completa:")
    for _, r in df.iterrows():
        bar = "█" * int(r["precip_mm"] / 30)
        print(f"   {r['fecha'].strftime('%b %Y')}  "
              f"T°{r['temp_c']:.1f}°C  "
              f"{r['precip_mm']:5.0f}mm {bar}")
