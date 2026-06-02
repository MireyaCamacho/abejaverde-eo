"""
AbejaVerde·EO — Módulo: land_phenology
========================================
Índice fenológico y calendario floral para el apiario piloto.

Dos estrategias complementarias:
    1. CLMS LSP global (Copernicus Land Monitoring Service)
       → SOS, POS, EOS, AMPL directamente desde el satélite
       → Resolución 300m, disponible vía openEO CDSE

    2. Derivado desde serie NDVI Sentinel-2 (fallback)
       → Calcula SOS, POS, EOS a partir de los valores NDVI ya obtenidos
       → Más preciso para el territorio específico del apiario
       → No requiere dataset adicional

En la práctica, para San Juan de Rioseco la estrategia 2 es más precisa
porque usa resolución 10m (Sentinel-2) vs 300m (LSP global).

Métricas LSP:
    SOS  — Start of Season:   inicio de floración
    POS  — Peak of Season:    pico de floración (máximo NDVI)
    EOS  — End of Season:     fin de floración
    LOS  — Length of Season:  duración total (EOS - SOS en días)
    AMPL — Amplitude:         intensidad de la floración (NDVI_max - NDVI_min)

Outputs:
    data/reference/floraciones_sjr.csv   — calendario floral del territorio
    data/processed/fenologia_series.csv  — serie fenológica con fase actual
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── UMBRALES FENOLÓGICOS ──────────────────────────────────────────────────────
# Calibrados con 17 meses de datos reales del apiario piloto

NDVI_SOS      = 0.55    # NDVI creciente que supera este umbral → inicio temporada
NDVI_EOS      = 0.55    # NDVI decreciente que cae por debajo → fin temporada
NDVI_PICO_MIN = 0.65    # NDVI mínimo para que el período sea "floración activa"

# Ventana mínima para un período de floración válido
MIN_MESES_FLORACION = 2

# Meses del año en español
MESES_ES = {
    1: "Enero",    2: "Febrero",  3: "Marzo",
    4: "Abril",    5: "Mayo",     6: "Junio",
    7: "Julio",    8: "Agosto",   9: "Septiembre",
    10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


# ── ESTRATEGIA 1: CLMS LSP GLOBAL ────────────────────────────────────────────

def obtener_lsp_clms(
    lat:          float,
    lon:          float,
    año:          int,
    radio_km:     float = 3.0,
    client=None,
) -> Optional[dict]:
    """
    Intenta obtener el índice fenológico LSP del CLMS via openEO.

    Colección: COPERNICUS_LAND_PHENOLOGY (resolución 300m, anual)
    Variables: SOS, POS, EOS, LOS, AMPL

    Returns:
        dict con {sos, pos, eos, los, ampl} como objetos date y float,
        o None si no está disponible para la zona/año.
    """
    try:
        from src.ingesta.copernicus_api import CDSEClient, bbox_desde_coordenadas
        from shapely.geometry import mapping, box as shapely_box

        client = client or CDSEClient()
        bbox   = bbox_desde_coordenadas(lat, lon, radio_km)

        conn = client._conectar_openeo()
        colecciones_disponibles = [
            c["id"] for c in conn.list_collections()
            if "PHENOLOGY" in c["id"].upper() or "LSP" in c["id"].upper()
        ]

        if not colecciones_disponibles:
            logger.info("ℹ️  LSP CLMS no disponible via openEO — usando derivado NDVI")
            return None

        logger.info(f"🌿 Obteniendo LSP CLMS: {colecciones_disponibles[0]}")
        bbox_dict = {
            "west": bbox[0], "south": bbox[1],
            "east": bbox[2], "north": bbox[3],
            "crs":  "EPSG:4326",
        }
        cubo = conn.load_collection(
            colecciones_disponibles[0],
            spatial_extent  = bbox_dict,
            temporal_extent = [f"{año}-01-01", f"{año}-12-31"],
        )
        poligono  = mapping(shapely_box(*bbox))
        resultado = cubo.aggregate_spatial(
            geometries = poligono, reducer = "mean"
        ).execute()

        return _parsear_lsp_clms(resultado, año)

    except Exception as e:
        logger.debug(f"LSP CLMS no disponible: {e}")
        return None


def _parsear_lsp_clms(resultado: dict, año: int) -> Optional[dict]:
    """Parsea la respuesta openEO del LSP CLMS."""
    try:
        valores = list(resultado.values())
        if not valores:
            return None
        v = valores[0]
        while isinstance(v, (list, tuple)):
            v = v[0]
        # El LSP entrega día del año (DOY) para SOS, POS, EOS
        # y valor 0-1 para AMPL
        return {
            "sos":  _doy_a_fecha(int(v[0]), año) if len(v) > 0 else None,
            "pos":  _doy_a_fecha(int(v[1]), año) if len(v) > 1 else None,
            "eos":  _doy_a_fecha(int(v[2]), año) if len(v) > 2 else None,
            "ampl": round(float(v[3]), 3)         if len(v) > 3 else None,
        }
    except Exception:
        return None


def _doy_a_fecha(doy: int, año: int) -> date:
    """Convierte día del año (DOY) a objeto date."""
    return date(año, 1, 1) + timedelta(days=doy - 1)


# ── ESTRATEGIA 2: DERIVADO DESDE NDVI SENTINEL-2 ────────────────────────────

def derivar_fenologia_ndvi(
    df_ndvi: pd.DataFrame,
    umbral_sos: float = NDVI_SOS,
    umbral_eos: float = NDVI_EOS,
) -> list[dict]:
    """
    Deriva los eventos fenológicos (SOS, POS, EOS) directamente
    desde la serie NDVI Sentinel-2.

    Algoritmo:
    1. Detectar cruce ascendente del umbral → SOS
    2. Detectar máximo local entre SOS y próximo cruce descendente → POS
    3. Detectar cruce descendente del umbral → EOS
    4. Calcular AMPL = NDVI_POS - NDVI_min_season

    Args:
        df_ndvi:    DataFrame con columnas fecha, ndvi
        umbral_sos: umbral de cruce para inicio de temporada
        umbral_eos: umbral de cruce para fin de temporada

    Returns:
        Lista de temporadas con {año, sos, pos, eos, los, ampl, ndvi_pico}
    """
    if df_ndvi.empty:
        return []

    df = df_ndvi.sort_values("fecha").copy()
    df = df.reset_index(drop=True)

    temporadas = []
    en_temporada = False
    sos_idx      = None

    for i in range(1, len(df)):
        ndvi_prev = df.loc[i - 1, "ndvi"]
        ndvi_curr = df.loc[i,     "ndvi"]
        fecha     = df.loc[i,     "fecha"]

        # SOS — cruce ascendente del umbral
        if not en_temporada and ndvi_prev < umbral_sos <= ndvi_curr:
            en_temporada = True
            sos_idx      = i

        # EOS — cruce descendente del umbral
        elif en_temporada and ndvi_prev >= umbral_eos > ndvi_curr:
            eos_idx = i

            # Extraer la temporada
            segmento = df.iloc[sos_idx:eos_idx + 1]

            if len(segmento) < MIN_MESES_FLORACION:
                en_temporada = False
                continue

            pos_idx   = segmento["ndvi"].idxmax()
            ndvi_pico = segmento.loc[pos_idx, "ndvi"]

            if ndvi_pico < NDVI_PICO_MIN:
                en_temporada = False
                continue

            sos_fecha = df.loc[sos_idx, "fecha"]
            pos_fecha = df.loc[pos_idx, "fecha"]
            eos_fecha = df.loc[eos_idx, "fecha"]

            ndvi_min_season = segmento["ndvi"].min()
            ampl = round(ndvi_pico - ndvi_min_season, 3)
            los  = (eos_fecha - sos_fecha).days

            temporadas.append({
                "año":       sos_fecha.year,
                "sos":       sos_fecha.date() if hasattr(sos_fecha, "date") else sos_fecha,
                "pos":       pos_fecha.date() if hasattr(pos_fecha, "date") else pos_fecha,
                "eos":       eos_fecha.date() if hasattr(eos_fecha, "date") else eos_fecha,
                "los_dias":  los,
                "ampl":      ampl,
                "ndvi_pico": round(ndvi_pico, 3),
                "fuente":    "Sentinel-2 NDVI derivado",
            })
            en_temporada = False

    logger.info(f"🌿 {len(temporadas)} temporadas fenológicas detectadas")
    return temporadas


def fase_actual(
    fecha_hoy:   date,
    temporadas:  list[dict],
) -> dict:
    """
    Determina la fase fenológica actual del territorio.

    Returns:
        dict con: fase, dias_para_sos, dias_para_pos, dias_para_eos,
                  temporada_actual (si aplica)
    """
    # Buscar la temporada activa o más próxima
    for t in sorted(temporadas, key=lambda x: abs((x["sos"] - fecha_hoy).days)):
        sos = t["sos"] if isinstance(t["sos"], date) else t["sos"].date()
        pos = t["pos"] if isinstance(t["pos"], date) else t["pos"].date()
        eos = t["eos"] if isinstance(t["eos"], date) else t["eos"].date()

        if fecha_hoy < sos:
            dias = (sos - fecha_hoy).days
            if dias <= 90:   # próxima temporada en menos de 3 meses
                return {
                    "fase":             "PRE_TEMPORADA",
                    "descripcion":      f"Próxima floración en ~{dias} días",
                    "dias_para_sos":    dias,
                    "dias_para_pos":    (pos - fecha_hoy).days,
                    "dias_para_eos":    (eos - fecha_hoy).days,
                    "temporada":        t,
                }

        elif sos <= fecha_hoy <= pos:
            return {
                "fase":          "FLORACION_ACTIVA",
                "descripcion":   "Floración activa — máxima oferta de néctar",
                "dias_para_pos": (pos - fecha_hoy).days,
                "dias_para_eos": (eos - fecha_hoy).days,
                "temporada":     t,
            }

        elif pos < fecha_hoy <= eos:
            return {
                "fase":          "FLORACION_DECLINANDO",
                "descripcion":   "Floración declinando — prepare para escasez",
                "dias_para_eos": (eos - fecha_hoy).days,
                "temporada":     t,
            }

    return {
        "fase":        "FUERA_TEMPORADA",
        "descripcion": "Fuera de temporada floral — monitoree alimentación",
        "temporada":   None,
    }


# ── CALENDARIO FLORAL ─────────────────────────────────────────────────────────

def construir_calendario_floral(
    temporadas: list[dict],
    nombre_apiario: str = "Apiario AbejaVerde·EO",
) -> pd.DataFrame:
    """
    Construye el calendario floral del territorio a partir de
    las temporadas detectadas.

    Identifica el patrón bimodal típico de Cundinamarca:
        Temporada 1 (principal):  mayo–agosto
        Temporada 2 (secundaria): octubre–diciembre

    Returns:
        DataFrame con el calendario y recomendaciones por mes
    """
    if not temporadas:
        return pd.DataFrame()

    # Construir vista mensual de actividad floral
    meses_activos = set()
    for t in temporadas:
        sos = pd.Timestamp(t["sos"])
        eos = pd.Timestamp(t["eos"])
        cursor = sos
        while cursor <= eos:
            meses_activos.add(cursor.month)
            cursor += pd.DateOffset(months=1)

    calendario = []
    for mes in range(1, 13):
        activo = mes in meses_activos

        # Promedio de NDVI en ese mes sobre todas las temporadas
        ndvi_picos = [t["ndvi_pico"] for t in temporadas
                      if pd.Timestamp(t["sos"]).month <= mes <= pd.Timestamp(t["eos"]).month]
        ndvi_prom = round(np.mean(ndvi_picos), 3) if ndvi_picos else None

        calendario.append({
            "mes":                mes,
            "nombre_mes":         MESES_ES[mes],
            "floración_activa":   activo,
            "ndvi_promedio":      ndvi_prom,
            "recomendacion":      _recomendacion_mes(mes, activo),
        })

    df = pd.DataFrame(calendario)
    logger.info(
        f"📅 Calendario floral construido — {MESES_ES[mes]} | "
        f"{df['floración_activa'].sum()} meses activos"
    )
    return df


def _recomendacion_mes(mes: int, activo: bool) -> str:
    """Recomendación apícola por mes según actividad floral."""
    if activo:
        if mes in [5, 6]:
            return "Floración alta. No alimente. Prepare alzas. Monitoree enjambrazón."
        elif mes in [7, 8]:
            return "Floración activa. Revise alzas. Cosecha si están llenas (>80%)."
        elif mes in [10, 11, 12]:
            return "Segunda temporada. Monitoree peso. Prepare invernada si aplica."
        else:
            return "Floración activa. Monitoreo rutinario."
    else:
        if mes in [1, 2]:
            return "Temporada seca. Alimente si el peso baja. Revise reservas."
        elif mes in [3, 4]:
            return "Inicio de temporada próxima. Revise colonia. Trate varroasis."
        elif mes == 9:
            return "Transición. Monitoree peso. Prepare para segunda temporada."
        else:
            return "Fuera de temporada. Mantenga alimentación suplementaria."


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_fenologia(
    temporadas: list[dict],
    ruta: Union[str, Path] = "data/processed/fenologia_series.csv",
) -> Path:
    """Guarda las temporadas detectadas en CSV."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(temporadas).to_csv(ruta, index=False)
    logger.info(f"💾 Fenología guardada: {ruta}")
    return ruta


def guardar_calendario(
    df: pd.DataFrame,
    ruta: Union[str, Path] = "data/reference/floraciones_sjr.csv",
) -> Path:
    """Guarda el calendario floral en CSV."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 Calendario floral guardado: {ruta}")
    return ruta


def cargar_calendario(
    ruta: Union[str, Path] = "data/reference/floraciones_sjr.csv",
) -> pd.DataFrame:
    """Carga el calendario floral desde CSV."""
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(f"⚠️  No se encontró calendario en {ruta}")
        return pd.DataFrame()
    return pd.read_csv(ruta)


# ── PIPELINE COMPLETO ─────────────────────────────────────────────────────────

def pipeline_fenologia(
    df_ndvi:    pd.DataFrame,
    lat:        float,
    lon:        float,
    guardar:    bool = True,
    client=None,
) -> tuple[list[dict], pd.DataFrame]:
    """
    Pipeline completo: intenta LSP CLMS → fallback a NDVI derivado → calendario.

    Returns:
        (temporadas, df_calendario)
    """
    temporadas = []

    # Intentar LSP CLMS para cada año disponible
    if not df_ndvi.empty and client is not None:
        años = df_ndvi["año"].unique() if "año" in df_ndvi.columns else []
        for año in sorted(años):
            lsp = obtener_lsp_clms(lat, lon, int(año), client=client)
            if lsp:
                lsp["año"]    = int(año)
                lsp["fuente"] = "CLMS LSP global"
                temporadas.append(lsp)

    # Fallback: derivar desde NDVI
    if not temporadas and not df_ndvi.empty:
        logger.info("🔄 Derivando fenología desde NDVI Sentinel-2...")
        temporadas = derivar_fenologia_ndvi(df_ndvi)

    # Construir calendario
    calendario = construir_calendario_floral(temporadas)

    if guardar and temporadas:
        guardar_fenologia(temporadas)
    if guardar and not calendario.empty:
        guardar_calendario(calendario)

    return temporadas, calendario


# ── DEMO CON DATOS REALES DEL PILOTO ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    # Datos reales del piloto
    DATOS_REALES = [
        {"fecha":"2024-01","ndvi":0.474},{"fecha":"2024-02","ndvi":0.618},
        {"fecha":"2024-03","ndvi":0.584},{"fecha":"2024-04","ndvi":0.513},
        {"fecha":"2024-05","ndvi":0.773},{"fecha":"2024-06","ndvi":0.817},
        {"fecha":"2024-07","ndvi":0.529},{"fecha":"2024-08","ndvi":0.669},
        {"fecha":"2024-09","ndvi":0.698},{"fecha":"2024-10","ndvi":0.697},
        {"fecha":"2024-11","ndvi":0.509},{"fecha":"2024-12","ndvi":0.701},
        {"fecha":"2025-01","ndvi":0.437},{"fecha":"2025-02","ndvi":0.442},
        {"fecha":"2025-03","ndvi":0.554},{"fecha":"2025-04","ndvi":0.379},
        {"fecha":"2025-05","ndvi":0.787},
    ]

    print("═" * 60)
    print("  AbejaVerde·EO — land_phenology")
    print("  Apiario San Juan de Rioseco — datos reales piloto")
    print("═" * 60)

    df = pd.DataFrame(DATOS_REALES)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["año"]   = df["fecha"].dt.year
    df["mes"]   = df["fecha"].dt.month

    # Derivar fenología
    temporadas = derivar_fenologia_ndvi(df)

    print(f"\n🌸 Temporadas fenológicas detectadas: {len(temporadas)}")
    for t in temporadas:
        sos_str = t["sos"].strftime("%b %Y") if hasattr(t["sos"], "strftime") else str(t["sos"])
        pos_str = t["pos"].strftime("%b %Y") if hasattr(t["pos"], "strftime") else str(t["pos"])
        eos_str = t["eos"].strftime("%b %Y") if hasattr(t["eos"], "strftime") else str(t["eos"])
        print(f"   SOS: {sos_str}  POS: {pos_str}  EOS: {eos_str}  "
              f"NDVI pico: {t['ndvi_pico']}  AMPL: {t['ampl']}  "
              f"LOS: {t['los_dias']} días")

    # Calendario floral
    calendario = construir_calendario_floral(temporadas)
    print(f"\n📅 Calendario floral — San Juan de Rioseco:")
    for _, r in calendario.iterrows():
        estado = "🌿 ACTIVA" if r["floración_activa"] else "   -----"
        ndvi   = f"NDVI~{r['ndvi_promedio']}" if r["ndvi_promedio"] else ""
        print(f"   {r['nombre_mes']:12s} {estado}  {ndvi}")

    # Fase actual
    hoy = date.today()
    fase = fase_actual(hoy, temporadas)
    print(f"\n📍 Fase actual ({hoy}):")
    print(f"   {fase['fase']}")
    print(f"   {fase['descripcion']}")
    if fase.get("temporada"):
        t = fase["temporada"]
        print(f"   Temporada: SOS {t['sos']} → EOS {t['eos']}")
