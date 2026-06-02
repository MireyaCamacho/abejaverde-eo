"""
AbejaVerde·EO — Módulo: water_bodies
======================================
Disponibilidad de agua superficial en el radio del apiario.

Las abejas necesitan mínimo 1 litro de agua por colmena por día.
Sin agua accesible en un radio de 500m, la colonia sufre estrés
y pierde eficiencia de polinización.

Dos fuentes complementarias (plan V2):

    JRC Global Surface Water (JRC GSW)
        Presencia histórica de agua (1984–2021), resolución 30m
        Fuente: Google Earth Engine / JRC
        Uso: mapear qué cuerpos de agua EXISTEN en el territorio

    CLMS Water Bodies
        Estado actual de cuerpos de agua, actualización cada 10 días
        Resolución 300m, Copernicus Land Monitoring Service
        Uso: verificar si esos cuerpos están ACTIVOS hoy

Estrategia:
    Si CLMS Water Bodies disponible → usar estado actual
    Si solo JRC disponible → usar presencia histórica como proxy
    Si ninguno → estimar desde precipitación ERA5

Outputs:
    data/processed/agua_superficial.csv
    data/reference/cuerpos_agua_500m.geojson
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

RADIO_AGUA_KM     = 0.5    # 500m — radio de acceso de las abejas al agua
AGUA_MIN_COLMENA  = 1.0    # litros/colmena/día
AGUA_OPTIMA_PCT   = 80.0   # % de cuerpos históricos que deben estar activos
AGUA_ALERTA_PCT   = 50.0   # % por debajo → alerta amarilla
AGUA_CRITICA_PCT  = 20.0   # % por debajo → alerta roja


# ── JRC GLOBAL SURFACE WATER ─────────────────────────────────────────────────

def obtener_jrc_gsw(
    lat:      float,
    lon:      float,
    radio_km: float = RADIO_AGUA_KM,
    client=None,
) -> Optional[dict]:
    """
    Obtiene la presencia histórica de agua del JRC Global Surface Water.
    Calcula el % del área que tiene agua en al menos 3 meses por año.

    Returns:
        dict con {pct_agua_historica, area_km2, fuente} o None
    """
    try:
        from src.ingesta.copernicus_api import CDSEClient, bbox_desde_coordenadas
        from shapely.geometry import mapping, box as shapely_box

        client = client or CDSEClient()
        bbox   = bbox_desde_coordenadas(lat, lon, radio_km)

        conn = client._conectar_openeo()

        # Buscar colección JRC en openEO
        colecciones = [
            c["id"] for c in conn.list_collections()
            if "JRC" in c["id"].upper() or "WATER" in c["id"].upper()
            or "GSW"  in c["id"].upper()
        ]

        if not colecciones:
            logger.info("ℹ️  JRC GSW no disponible via openEO — usando estimación ERA5")
            return None

        logger.info(f"💧 Obteniendo JRC GSW: {colecciones[0]}")
        bbox_dict = {
            "west": bbox[0], "south": bbox[1],
            "east": bbox[2], "north": bbox[3],
            "crs":  "EPSG:4326",
        }
        cubo = conn.load_collection(
            colecciones[0],
            spatial_extent = bbox_dict,
        )
        poligono  = mapping(shapely_box(*bbox))
        resultado = cubo.aggregate_spatial(
            geometries = poligono, reducer = "mean"
        ).execute()

        if resultado:
            vals = list(resultado.values())
            if vals:
                v = vals[0]
                while isinstance(v, (list, tuple)):
                    v = v[0]
                pct = round(float(v) * 100, 2)
                logger.info(f"✅ JRC GSW: {pct}% del área con presencia histórica de agua")
                return {
                    "pct_agua_historica": pct,
                    "fuente":             colecciones[0],
                }

    except Exception as e:
        logger.debug(f"JRC GSW no disponible: {e}")

    return None


def obtener_water_bodies_clms(
    lat:          float,
    lon:          float,
    fecha_inicio: str,
    fecha_fin:    str,
    radio_km:     float = RADIO_AGUA_KM,
    client=None,
) -> Optional[list[dict]]:
    """
    Obtiene el estado actual de cuerpos de agua del CLMS Water Bodies.
    Actualización cada 10 días, resolución 300m.

    Returns:
        Lista de {fecha, pct_agua_activa} o None
    """
    try:
        from src.ingesta.copernicus_api import CDSEClient, bbox_desde_coordenadas
        from shapely.geometry import mapping, box as shapely_box

        client = client or CDSEClient()
        bbox   = bbox_desde_coordenadas(lat, lon, radio_km)

        conn = client._conectar_openeo()

        colecciones = [
            c["id"] for c in conn.list_collections()
            if "WATER_BODIES" in c["id"].upper()
            or "WATER-BODIES" in c["id"].upper()
            or ("CLMS" in c["id"].upper() and "WATER" in c["id"].upper())
        ]

        if not colecciones:
            logger.info("ℹ️  CLMS Water Bodies no disponible — usando estimación")
            return None

        logger.info(f"💧 Obteniendo CLMS Water Bodies: {colecciones[0]}")
        bbox_dict = {
            "west": bbox[0], "south": bbox[1],
            "east": bbox[2], "north": bbox[3],
            "crs": "EPSG:4326",
        }
        cubo = conn.load_collection(
            colecciones[0],
            spatial_extent  = bbox_dict,
            temporal_extent = [fecha_inicio, fecha_fin],
        )
        from src.ingesta.copernicus_api import resamplear_mensual
        poligono  = mapping(shapely_box(*bbox))
        resultado = cubo.aggregate_spatial(
            geometries = poligono, reducer = "mean"
        ).execute()

        registros = []
        for fecha_str, valores in resultado.items():
            try:
                val = valores
                while isinstance(val, (list, tuple)):
                    val = val[0]
                registros.append({
                    "fecha":           fecha_str[:10],
                    "pct_agua_activa": round(float(val) * 100, 2),
                })
            except Exception:
                continue

        logger.info(f"✅ Water Bodies: {len(registros)} registros")
        return registros

    except Exception as e:
        logger.debug(f"CLMS Water Bodies no disponible: {e}")
        return None


# ── ESTIMACIÓN DESDE ERA5 ─────────────────────────────────────────────────────

def estimar_agua_desde_era5(
    df_era5:          pd.DataFrame,
    pct_historico:    float = 70.0,
    precip_umbral:    float = 100.0,
) -> pd.DataFrame:
    """
    Estima la disponibilidad de agua superficial a partir de ERA5.

    Cuando no hay datos directos de cuerpos de agua, la precipitación
    acumulada es el mejor proxy disponible.

    Lógica:
        precipitación alta → cuerpos de agua activos → agua disponible
        precipitación baja → cuerpos de agua reducidos → alerta

    Args:
        df_era5:          DataFrame con columnas fecha, precip_mm
        pct_historico:    % de disponibilidad histórica normal (baseline)
        precip_umbral:    precipitación mensual considerada "normal" (mm)

    Returns:
        DataFrame con columnas: fecha, pct_agua_activa, estado_agua, fuente
    """
    if df_era5.empty or "precip_mm" not in df_era5.columns:
        return pd.DataFrame()

    df = df_era5[["fecha", "precip_mm"]].copy()

    # Normalizar precipitación respecto al umbral
    df["pct_agua_activa"] = (
        (df["precip_mm"] / precip_umbral).clip(0, 1.5) * pct_historico
    ).round(2)

    df["estado_agua"] = df["pct_agua_activa"].apply(_clasificar_estado_agua)
    df["fuente"]      = "Estimado desde ERA5 (precipitación)"

    logger.info(
        f"💧 Agua estimada desde ERA5 — {len(df)} meses | "
        f"min={df['pct_agua_activa'].min():.1f}% | "
        f"max={df['pct_agua_activa'].max():.1f}%"
    )
    return df[["fecha", "pct_agua_activa", "estado_agua", "fuente"]]


def _clasificar_estado_agua(pct: float) -> str:
    """Clasifica la disponibilidad de agua para las abejas."""
    if pct >= AGUA_OPTIMA_PCT:
        return "NORMAL"
    elif pct >= AGUA_ALERTA_PCT:
        return "REDUCIDA"
    elif pct >= AGUA_CRITICA_PCT:
        return "ESCASA"
    else:
        return "CRITICA"


# ── LÍNEA BASE ────────────────────────────────────────────────────────────────

def construir_linea_base_agua(
    df_agua:        pd.DataFrame,
    periodo_inicio: int = 2022,
    periodo_fin:    int = 2024,
) -> pd.DataFrame:
    """
    Construye la línea base histórica de disponibilidad de agua por mes.

    Returns:
        DataFrame con: mes, agua_media, agua_sigma
    """
    if "fecha" not in df_agua.columns:
        return pd.DataFrame()

    df = df_agua.copy()
    df["mes"] = pd.to_datetime(df["fecha"]).dt.month
    df["año"] = pd.to_datetime(df["fecha"]).dt.year

    df_ref = df[
        (df["año"] >= periodo_inicio) &
        (df["año"] <= periodo_fin)
    ]

    if df_ref.empty:
        df_ref = df

    linea_base = (
        df_ref
        .groupby("mes")["pct_agua_activa"]
        .agg(
            agua_media = "mean",
            agua_sigma = "std",
        )
        .reset_index()
    )
    linea_base["agua_sigma"] = linea_base["agua_sigma"].fillna(5.0).clip(lower=2.0)
    return linea_base


def calcular_anomalia_agua(
    df_agua:     pd.DataFrame,
    linea_base:  pd.DataFrame,
) -> pd.DataFrame:
    """Calcula anomalía estandarizada de disponibilidad de agua."""
    df = df_agua.copy()
    df["mes"] = pd.to_datetime(df["fecha"]).dt.month
    df = df.merge(linea_base, on="mes", how="left")
    df["anom_agua"] = (
        (df["pct_agua_activa"] - df["agua_media"]) / df["agua_sigma"]
    ).round(3)
    return df


# ── ALERTA DE AGUA ────────────────────────────────────────────────────────────

def generar_alerta_agua(
    pct_agua_activa: float,
    n_colmenas:      int = 1,
) -> dict:
    """
    Genera la alerta de agua para el apicultor.

    Args:
        pct_agua_activa: % de cuerpos de agua activos vs. histórico
        n_colmenas:      número de colmenas en el apiario

    Returns:
        dict con nivel, mensaje y recomendación
    """
    litros_dia = n_colmenas * AGUA_MIN_COLMENA

    if pct_agua_activa >= AGUA_OPTIMA_PCT:
        return {
            "nivel":         "NORMAL",
            "color":         "verde",
            "mensaje":       "Disponibilidad de agua normal en su zona.",
            "recomendacion": "Sin acción necesaria. Monitoreo rutinario.",
        }
    elif pct_agua_activa >= AGUA_ALERTA_PCT:
        return {
            "nivel":         "REDUCIDA",
            "color":         "amarillo",
            "mensaje":       "Nivel de agua en la zona disminuyendo.",
            "recomendacion": (
                f"Revise las fuentes de agua cercanas esta semana. "
                f"Sus {n_colmenas} colmenas necesitan al menos "
                f"{litros_dia:.0f} litros de agua fresca por día."
            ),
        }
    elif pct_agua_activa >= AGUA_CRITICA_PCT:
        return {
            "nivel":         "ESCASA",
            "color":         "naranja",
            "mensaje":       "Posible escasez de agua cerca del apiario.",
            "recomendacion": (
                f"Verifique que cada colmena tenga acceso a agua fresca. "
                f"Si no hay fuentes naturales activas, instale bebedero "
                f"artificial a menos de 200m del apiario. "
                f"Necesita {litros_dia:.0f} litros/día para "
                f"{n_colmenas} colmenas."
            ),
        }
    else:
        return {
            "nivel":         "CRITICA",
            "color":         "rojo",
            "mensaje":       "Sequía severa — escasez crítica de agua.",
            "recomendacion": (
                f"URGENTE: instale bebedero artificial de inmediato. "
                f"La falta de agua puede matar colonias en 48–72 horas "
                f"en condiciones de calor. Necesita mínimo "
                f"{litros_dia:.0f} litros/día para {n_colmenas} colmenas."
            ),
        }


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_agua(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/agua_superficial.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 Agua guardada: {ruta}")
    return ruta


def cargar_agua(
    ruta: Union[str, Path] = "data/processed/agua_superficial.csv",
) -> pd.DataFrame:
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(f"⚠️  No se encontró {ruta}")
        return pd.DataFrame()
    return pd.read_csv(ruta, parse_dates=["fecha"])


# ── PIPELINE COMPLETO ─────────────────────────────────────────────────────────

def pipeline_agua(
    lat:          float,
    lon:          float,
    fecha_inicio: str,
    fecha_fin:    str,
    df_era5:      Optional[pd.DataFrame] = None,
    guardar:      bool = True,
    client=None,
) -> pd.DataFrame:
    """
    Pipeline completo: intenta CLMS → JRC → estimación ERA5.
    Siempre retorna un DataFrame con disponibilidad de agua.
    """
    # 1. Intentar CLMS Water Bodies
    registros = obtener_water_bodies_clms(
        lat, lon, fecha_inicio, fecha_fin, client=client
    )
    if registros:
        df = pd.DataFrame(registros)
        df["fecha"]       = pd.to_datetime(df["fecha"])
        df["estado_agua"] = df["pct_agua_activa"].apply(_clasificar_estado_agua)
        df["fuente"]      = "CLMS Water Bodies"

        if guardar:
            guardar_agua(df)
        return df

    # 2. Estimación desde ERA5
    if df_era5 is not None and not df_era5.empty:
        logger.info("🔄 Estimando agua desde ERA5...")
        df = estimar_agua_desde_era5(df_era5)
        if not df.empty:
            df["fecha"] = pd.to_datetime(df["fecha"])
            if guardar:
                guardar_agua(df)
            return df

    logger.warning("⚠️  Sin datos de agua disponibles")
    return pd.DataFrame()


# ── DEMO CON DATOS REALES DEL PILOTO ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    # Datos ERA5 reales del piloto como fuente de estimación
    ERA5_REALES = [
        {"fecha":"2024-01","precip_mm": 30.0},
        {"fecha":"2024-02","precip_mm":130.0},
        {"fecha":"2024-03","precip_mm":210.0},
        {"fecha":"2024-04","precip_mm":280.0},
        {"fecha":"2024-05","precip_mm":380.0},
        {"fecha":"2024-06","precip_mm":310.0},
        {"fecha":"2024-07","precip_mm":150.0},
        {"fecha":"2024-08","precip_mm":210.0},
        {"fecha":"2024-09","precip_mm":300.0},
        {"fecha":"2024-10","precip_mm":280.0},
        {"fecha":"2024-11","precip_mm":230.0},
        {"fecha":"2024-12","precip_mm":165.0},
        {"fecha":"2025-01","precip_mm": 38.0},
        {"fecha":"2025-02","precip_mm": 42.0},
        {"fecha":"2025-03","precip_mm":230.0},
        {"fecha":"2025-04","precip_mm": 22.0},
        {"fecha":"2025-05","precip_mm":405.0},
    ]

    print("═" * 60)
    print("  AbejaVerde·EO — water_bodies")
    print("  Apiario San Juan de Rioseco — datos reales piloto")
    print("═" * 60)

    df_era5 = pd.DataFrame(ERA5_REALES)
    df_agua = estimar_agua_desde_era5(df_era5, precip_umbral=180.0)
    df_agua["fecha"] = pd.to_datetime(df_agua["fecha"])

    print(f"\n💧 Disponibilidad de agua estimada desde ERA5:")
    meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    for _, r in df_agua.iterrows():
        pct  = r["pct_agua_activa"]
        bar  = "█" * int(pct / 5)
        mes  = meses_es[r["fecha"].month]
        año  = r["fecha"].year
        print(f"   {mes} {año}  {pct:5.1f}%  {bar:20s}  [{r['estado_agua']}]")

    # Meses críticos
    criticos = df_agua[df_agua["estado_agua"].isin(["ESCASA", "CRITICA"])]
    print(f"\n⚠️  Meses con escasez de agua: {len(criticos)}")
    for _, r in criticos.iterrows():
        alerta = generar_alerta_agua(r["pct_agua_activa"], n_colmenas=10)
        print(f"   {r['fecha'].strftime('%b %Y')}  {r['pct_agua_activa']:.1f}%")
        print(f"   → {alerta['recomendacion'][:80]}...")

    # Alerta de agua para hoy (peor mes real: abril 2025 con 22mm)
    print(f"\n🚨 Ejemplo alerta — Abril 2025 (22mm precip, peor mes real):")
    alerta = generar_alerta_agua(pct_agua_activa=12.2, n_colmenas=10)
    print(f"   Nivel: {alerta['nivel']} ({alerta['color']})")
    print(f"   {alerta['mensaje']}")
    print(f"   {alerta['recomendacion']}")
