"""
AbejaVerde·EO — Módulo: linea_base
=====================================
Construcción, actualización y gestión de la línea base histórica consolidada.

La línea base es la "memoria" del sistema: los promedios y desviaciones
estándar históricas de cada variable, por mes del año, para el territorio
específico del apiario piloto.

Sin línea base no hay anomalías. Sin anomalías no hay IRA. Sin IRA no hay alertas.

Período de referencia: 2022–2024 (cuando hay datos suficientes)
    Para el piloto de San Juan de Rioseco, usamos 2024 como base inicial
    y actualizamos conforme se acumulan más datos.

Estructura de la línea base (por mes del año 1-12):
    ndvi_media, ndvi_sigma
    temp_media, temp_sigma
    precip_media, precip_sigma
    agua_media, agua_sigma
    tcolmena_media, tcolmena_sigma   (cuando hay IoT)
    hr_media, hr_sigma               (cuando hay IoT)

Outputs:
    data/reference/linea_base/linea_base_consolidada.csv
    data/reference/linea_base/metadatos_linea_base.json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────

DIRECTORIO_BASE   = Path("data/reference/linea_base")
ARCHIVO_LB        = DIRECTORIO_BASE / "linea_base_consolidada.csv"
ARCHIVO_META      = DIRECTORIO_BASE / "metadatos_linea_base.json"

# Mínimo de observaciones por mes para considerar la línea base confiable
MIN_OBSERVACIONES = 2

VARIABLES_LB = [
    "ndvi", "temp_c", "precip_mm", "pct_agua_activa",
    "temp_interna", "hr_interna",
]


# ── CONSTRUCCIÓN ──────────────────────────────────────────────────────────────

def construir_linea_base_consolidada(
    df_ndvi:   Optional[pd.DataFrame] = None,
    df_era5:   Optional[pd.DataFrame] = None,
    df_agua:   Optional[pd.DataFrame] = None,
    df_iot:    Optional[pd.DataFrame] = None,
    periodo_inicio: int = 2022,
    periodo_fin:    int = 2024,
    apiario_id:     str = "API_SJR_01",
) -> pd.DataFrame:
    """
    Construye la línea base histórica consolidada cruzando todas las fuentes.

    Para cada mes del año (1-12) calcula:
        media y desviación estándar de cada variable disponible
        número de observaciones (para medir confiabilidad)

    Args:
        df_ndvi:        Serie NDVI mensual
        df_era5:        Serie ERA5 mensual
        df_agua:        Serie agua mensual
        df_iot:         Serie IoT mensual
        periodo_inicio: año de inicio del período de referencia
        periodo_fin:    año de fin del período de referencia

    Returns:
        DataFrame con 12 filas (una por mes) y columnas media/sigma de cada variable
    """
    # Inicializar tabla base con 12 meses
    lb = pd.DataFrame({"mes": range(1, 13)})

    # ── NDVI ──────────────────────────────────────────────────────────────────
    lb = _agregar_variable(lb, df_ndvi,  "fecha", "ndvi",
                           periodo_inicio, periodo_fin)

    # ── ERA5 temperatura y precipitación ─────────────────────────────────────
    lb = _agregar_variable(lb, df_era5,  "fecha", "temp_c",
                           periodo_inicio, periodo_fin)
    lb = _agregar_variable(lb, df_era5,  "fecha", "precip_mm",
                           periodo_inicio, periodo_fin)

    # ── Agua ──────────────────────────────────────────────────────────────────
    lb = _agregar_variable(lb, df_agua,  "fecha", "pct_agua_activa",
                           periodo_inicio, periodo_fin)

    # ── IoT ───────────────────────────────────────────────────────────────────
    if df_iot is not None and not df_iot.empty:
        col_ts = "fecha" if "fecha" in df_iot.columns else "timestamp"
        lb = _agregar_variable(lb, df_iot, col_ts, "temp_interna",
                               periodo_inicio, periodo_fin)
        lb = _agregar_variable(lb, df_iot, col_ts, "hr_interna",
                               periodo_inicio, periodo_fin)

    lb["apiario_id"]       = apiario_id
    lb["periodo_inicio"]   = periodo_inicio
    lb["periodo_fin"]      = periodo_fin
    lb["actualizado"]      = datetime.now().strftime("%Y-%m-%d")

    n_vars = sum(1 for c in lb.columns if c.endswith("_media"))
    logger.info(
        f"📊 Línea base consolidada: {n_vars} variables | "
        f"período {periodo_inicio}–{periodo_fin} | {apiario_id}"
    )
    return lb


def _agregar_variable(
    lb:             pd.DataFrame,
    df_fuente:      Optional[pd.DataFrame],
    col_fecha:      str,
    col_variable:   str,
    periodo_inicio: int,
    periodo_fin:    int,
) -> pd.DataFrame:
    """
    Agrega la media y sigma de una variable a la tabla de línea base.
    Si la variable no está disponible, agrega columnas con NaN.
    """
    col_media = f"{col_variable}_media"
    col_sigma = f"{col_variable}_sigma"
    col_n     = f"{col_variable}_n"

    if df_fuente is None or df_fuente.empty or col_variable not in df_fuente.columns:
        lb[col_media] = np.nan
        lb[col_sigma] = np.nan
        lb[col_n]     = 0
        return lb

    df = df_fuente.copy()
    df[col_fecha] = pd.to_datetime(df[col_fecha])
    df["año"]     = df[col_fecha].dt.year
    df["mes"]     = df[col_fecha].dt.month

    # Filtrar por período de referencia
    df_ref = df[
        (df["año"] >= periodo_inicio) & (df["año"] <= periodo_fin)
    ]

    if df_ref.empty:
        df_ref = df   # usar todos los datos si no hay del período

    stats = (
        df_ref
        .groupby("mes")[col_variable]
        .agg(
            **{
                col_media: "mean",
                col_sigma: "std",
                col_n:     "count",
            }
        )
        .reset_index()
    )

    # Sigma mínima para evitar división por cero
    sigma_min = {"ndvi": 0.03, "temp_c": 0.2, "precip_mm": 10.0,
                 "pct_agua_activa": 2.0, "temp_interna": 0.2, "hr_interna": 2.0}
    stats[col_sigma] = stats[col_sigma].fillna(
        sigma_min.get(col_variable, 1.0)
    ).clip(lower=sigma_min.get(col_variable, 0.1))

    lb = lb.merge(stats, on="mes", how="left")
    return lb


# ── ACTUALIZACIÓN ─────────────────────────────────────────────────────────────

def actualizar_linea_base(
    lb_existente:   pd.DataFrame,
    nuevos_datos:   dict[str, pd.DataFrame],
    año_nuevo:      int,
    peso_nuevo:     float = 0.3,
) -> pd.DataFrame:
    """
    Actualiza la línea base incorporando nuevos datos con promedio ponderado.

    Permite que la línea base evolucione gradualmente con nuevas observaciones
    sin borrar el histórico anterior.

    Args:
        lb_existente:  línea base actual
        nuevos_datos:  dict {"ndvi": df, "era5": df, ...} con datos nuevos
        año_nuevo:     año de los datos nuevos
        peso_nuevo:    peso de los nuevos datos vs. histórico (0.3 = 30%)

    Returns:
        Línea base actualizada
    """
    lb_nueva = construir_linea_base_consolidada(
        df_ndvi  = nuevos_datos.get("ndvi"),
        df_era5  = nuevos_datos.get("era5"),
        df_agua  = nuevos_datos.get("agua"),
        df_iot   = nuevos_datos.get("iot"),
        periodo_inicio = año_nuevo,
        periodo_fin    = año_nuevo,
    )

    lb_act = lb_existente.copy()
    peso_hist = 1.0 - peso_nuevo

    cols_media = [c for c in lb_existente.columns if c.endswith("_media")]
    for col in cols_media:
        if col in lb_nueva.columns:
            lb_act[col] = (
                lb_existente[col].fillna(0) * peso_hist
                + lb_nueva[col].fillna(lb_existente[col]) * peso_nuevo
            ).round(4)

    lb_act["actualizado"] = datetime.now().strftime("%Y-%m-%d")
    lb_act["periodo_fin"] = año_nuevo

    logger.info(
        f"🔄 Línea base actualizada con datos {año_nuevo} "
        f"(peso histórico={peso_hist:.0%}, nuevo={peso_nuevo:.0%})"
    )
    return lb_act


# ── VALIDACIÓN ────────────────────────────────────────────────────────────────

def validar_linea_base(lb: pd.DataFrame) -> dict:
    """
    Valida la calidad de la línea base y reporta qué variables
    tienen suficientes datos.

    Returns:
        dict con: variables_completas, variables_parciales,
                  variables_faltantes, confiabilidad_pct
    """
    completas  = []
    parciales  = []
    faltantes  = []

    for var in VARIABLES_LB:
        col_media = f"{var}_media"
        col_n     = f"{var}_n"

        if col_media not in lb.columns:
            faltantes.append(var)
            continue

        nulos = lb[col_media].isna().sum()
        if nulos == 0:
            n_min = lb[col_n].min() if col_n in lb.columns else MIN_OBSERVACIONES
            if n_min >= MIN_OBSERVACIONES:
                completas.append(var)
            else:
                parciales.append(var)
        elif nulos < 6:   # menos de 6 meses sin dato
            parciales.append(var)
        else:
            faltantes.append(var)

    total        = len(VARIABLES_LB)
    confiabilidad = round(len(completas) / total * 100, 0)

    resultado = {
        "variables_completas": completas,
        "variables_parciales": parciales,
        "variables_faltantes": faltantes,
        "confiabilidad_pct":   confiabilidad,
        # Con 1 año de datos (piloto) las variables son "parciales" pero usables
        "lista_para_ira":      len(completas) >= 3 or len(parciales) >= 3,
        "nota":                "Parciales = datos disponibles pero < 2 años de historial" if parciales else "",
    }

    logger.info(
        f"✅ Línea base validada: {len(completas)} completas | "
        f"{len(parciales)} parciales | {len(faltantes)} faltantes | "
        f"confiabilidad {confiabilidad:.0f}%"
    )
    return resultado


# ── OBTENER VALORES PARA IRA ──────────────────────────────────────────────────

def obtener_referencia_mes(
    lb:  pd.DataFrame,
    mes: int,
) -> dict:
    """
    Extrae los valores de referencia histórica para un mes específico.
    Retorna el dict que el IRA necesita para calcular anomalías.

    Args:
        lb:   línea base consolidada
        mes:  mes del año (1-12)

    Returns:
        dict con: ndvi_media, ndvi_sigma, temp_media, temp_sigma, etc.
    """
    fila = lb[lb["mes"] == mes]
    if fila.empty:
        logger.warning(f"⚠️  No hay línea base para el mes {mes}")
        return {}

    fila = fila.iloc[0]
    referencia = {}

    for var in VARIABLES_LB:
        col_media = f"{var}_media"
        col_sigma = f"{var}_sigma"
        if col_media in fila.index and not pd.isna(fila[col_media]):
            referencia[f"{var}_media"] = round(float(fila[col_media]), 4)
            referencia[f"{var}_sigma"] = round(float(fila.get(col_sigma, 0.1)), 4)

    return referencia


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_linea_base(
    lb:   pd.DataFrame,
    meta: Optional[dict] = None,
    ruta: Union[str, Path] = ARCHIVO_LB,
) -> Path:
    """Guarda la línea base consolidada en CSV y metadatos en JSON."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    lb.to_csv(ruta, index=False)
    logger.info(f"💾 Línea base consolidada guardada: {ruta}")

    if meta:
        ruta_meta = ruta.parent / "metadatos_linea_base.json"
        with open(ruta_meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Metadatos guardados: {ruta_meta}")

    return ruta


def cargar_linea_base(
    ruta: Union[str, Path] = ARCHIVO_LB,
) -> pd.DataFrame:
    """Carga la línea base desde CSV."""
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(f"⚠️  No se encontró línea base en {ruta}")
        return pd.DataFrame()
    df = pd.read_csv(ruta)
    logger.info(f"📂 Línea base cargada: {ruta}")
    return df


def existe_linea_base(
    ruta: Union[str, Path] = ARCHIVO_LB,
) -> bool:
    return Path(ruta).exists()


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
    print("  AbejaVerde·EO — linea_base")
    print("  Línea base consolidada — datos reales piloto")
    print("═" * 60)

    FECHAS = pd.date_range("2024-01", "2025-05", freq="MS")

    df_ndvi = pd.DataFrame({
        "fecha": FECHAS,
        "ndvi":  [0.474,0.618,0.584,0.513,0.773,0.817,0.529,0.669,
                  0.698,0.697,0.509,0.701,0.437,0.442,0.554,0.379,0.787],
    })

    df_era5 = pd.DataFrame({
        "fecha":     FECHAS,
        "temp_c":    [22.62,22.48,22.19,21.85,21.60,21.55,21.82,22.40,
                      22.45,21.50,21.48,21.50,21.43,21.78,21.52,21.12,21.10],
        "precip_mm": [30,130,210,280,380,310,150,210,300,280,230,165,
                      38,42,230,22,405],
    })

    df_agua = pd.DataFrame({
        "fecha":           FECHAS,
        "pct_agua_activa": [11.7,50.6,81.7,105,105,105,58.3,81.7,105,105,
                            89.4,64.2,14.8,16.3,89.4,8.6,105],
    })

    # Construir línea base
    lb = construir_linea_base_consolidada(
        df_ndvi  = df_ndvi,
        df_era5  = df_era5,
        df_agua  = df_agua,
        periodo_inicio = 2024,
        periodo_fin    = 2024,
    )

    # Validar
    validacion = validar_linea_base(lb)
    print(f"\n✅ Validación:")
    print(f"   Variables completas : {validacion['variables_completas']}")
    print(f"   Variables parciales : {validacion['variables_parciales']}")
    print(f"   Variables faltantes : {validacion['variables_faltantes']}")
    print(f"   Confiabilidad       : {validacion['confiabilidad_pct']:.0f}%")
    print(f"   Lista para IRA      : {validacion['lista_para_ira']}")

    # Vista mensual
    print(f"\n📊 Línea base por mes:")
    print(f"   {'Mes':5s}  {'NDVI':12s}  {'Temp':12s}  {'Precip':12s}  {'Agua':12s}")
    for _, r in lb.iterrows():
        mes = MESES_ES.get(int(r["mes"]), "?")
        ndvi = f"{r.get('ndvi_media',np.nan):.3f}±{r.get('ndvi_sigma',np.nan):.3f}" \
               if not pd.isna(r.get("ndvi_media",np.nan)) else "   N/D  "
        temp = f"{r.get('temp_c_media',np.nan):.1f}±{r.get('temp_c_sigma',np.nan):.1f}°" \
               if not pd.isna(r.get("temp_c_media",np.nan)) else "   N/D  "
        prec = f"{r.get('precip_mm_media',np.nan):.0f}±{r.get('precip_mm_sigma',np.nan):.0f}mm" \
               if not pd.isna(r.get("precip_mm_media",np.nan)) else "   N/D  "
        agua = f"{r.get('pct_agua_activa_media',np.nan):.0f}±{r.get('pct_agua_activa_sigma',np.nan):.0f}%" \
               if not pd.isna(r.get("pct_agua_activa_media",np.nan)) else "  N/D  "
        print(f"   {mes:5s}  {ndvi:12s}  {temp:12s}  {prec:12s}  {agua:12s}")

    # Ejemplo: obtener referencia para enero (mes más crítico)
    ref_enero = obtener_referencia_mes(lb, 1)
    print(f"\n🔍 Referencia para Enero (mes más crítico):")
    for k, v in ref_enero.items():
        print(f"   {k}: {v}")

    # Guardar
    meta = {
        "apiario_id":      "API_SJR_01",
        "nombre":          "Apiario AbejaVerde·EO — San Juan de Rioseco",
        "coordenadas":     {"lat": 4.875, "lon": -74.635},
        "periodo_inicio":  2024,
        "periodo_fin":     2024,
        "n_meses":         int(len(df_ndvi)),
        "variables":       validacion["variables_completas"],
        "generado":        datetime.now().isoformat(),
        "fuentes":         ["Sentinel-2 openEO/CDSE", "ERA5 CDS", "Estimación agua"],
    }
    guardar_linea_base(lb, meta)
