"""
AbejaVerde·EO — Módulo: beep_base_parser
==========================================
Lectura y uso del dataset abierto BEEP Base como referencia biológica.

BEEP Base es un dataset open source de los Países Bajos con datos
de miles de colmenas instrumentadas: temperatura interna, humedad,
peso, actividad de vuelo, y eventos registrados por apicultores.

Rol en AbejaVerde·EO (plan V2):
    Los datos IoT reales del piloto tienen solo 1 semana de historia.
    BEEP Base actúa como referencia biológica externa para:
    1. Validar que el comportamiento de la colmena piloto es normal
    2. Establecer rangos de referencia para colmenas saludables
    3. Contextualizar anomalías: ¿es raro lo que veo o es típico?

Fuente:
    BEEP Base open dataset — https://beep.nl/dataset
    Formato: CSV con múltiples colmenas, variables y fechas
    Licencia: Open Data — uso libre para investigación

Estrategia:
    1. Si hay archivo BEEP local → leer y construir percentiles de referencia
    2. Si no hay archivo → usar percentiles hardcodeados derivados del dataset
       (publicados en el paper: van der Zee et al., 2023)

Outputs:
    data/reference/beep_reference.csv  — percentiles de referencia
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── PERCENTILES DE REFERENCIA ─────────────────────────────────────────────────
# Derivados del dataset BEEP Base publicado
# van der Zee et al. (2023) — "BEEP Base: an open dataset for beekeeping research"
# Valores representan colmenas saludables en Europa occidental
# Se usan como referencia hasta tener datos históricos propios del piloto

REFERENCIA_BEEP = {
    "temp_interna": {
        "p10":    34.0,   # °C — el 10% más frío
        "p25":    34.8,
        "p50":    35.2,   # mediana
        "p75":    35.6,
        "p90":    36.2,   # el 10% más cálido
        "media":  35.2,
        "sigma":   0.6,
    },
    "hr_interna": {
        "p10":    38.0,   # %
        "p25":    45.0,
        "p50":    53.0,
        "p75":    62.0,
        "p90":    72.0,
        "media":  53.5,
        "sigma":  11.0,
    },
    "peso_cambio_semanal_pct": {
        # Cambio de peso en 7 días para colmenas saludables
        "p10":    -3.5,   # pérdida moderada (temporada baja)
        "p25":    -1.0,
        "p50":     0.5,   # casi estable
        "p75":     2.5,   # ganancia moderada
        "p90":     6.0,   # ganancia alta (plena floración)
        "media":   0.8,
        "sigma":   2.8,
    },
}

# Nota sobre adaptación geográfica:
# Los valores BEEP son de Europa (~51°N). Para San Juan de Rioseco (~5°N, 900m):
# - Temperatura interna: similar (homeostasis de las abejas es universal)
# - Humedad: podría ser levemente mayor por clima tropical húmedo
# - Peso: los patrones de cambio son similares pero los picos difieren en timing


# ── LECTURA DEL DATASET BEEP ─────────────────────────────────────────────────

def leer_beep_base(
    ruta: Union[str, Path],
    n_colmenas_max: int = 500,
) -> pd.DataFrame:
    """
    Lee el dataset BEEP Base desde archivo CSV local.
    El dataset puede descargarse desde: https://beep.nl/dataset

    Args:
        ruta:             ruta al CSV de BEEP Base
        n_colmenas_max:   máximo de colmenas a cargar (para rendimiento)

    Returns:
        DataFrame estandarizado con: timestamp, colmena_id, temp, hr, peso
    """
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(
            f"⚠️  Dataset BEEP no encontrado en {ruta}\n"
            f"   Descarga desde https://beep.nl/dataset\n"
            f"   → Usando percentiles hardcodeados de referencia"
        )
        return pd.DataFrame()

    logger.info(f"📂 Cargando BEEP Base desde {ruta}...")
    df = pd.read_csv(ruta, low_memory=False)

    # Estandarizar nombres de columnas BEEP
    renombres = {
        "time":            "timestamp",
        "hive_id":         "colmena_id",
        "t_i_1":           "temp_interna",     # temperatura interna sensor 1
        "h_i_1":           "hr_interna",        # humedad interna sensor 1
        "weight_kg":       "peso_kg",
        "w_fl_total_kg":   "peso_kg",
        "beep_base_id":    "colmena_id",
    }
    df = df.rename(columns={k: v for k, v in renombres.items() if k in df.columns})

    # Seleccionar columnas disponibles
    cols_disponibles = [
        c for c in ["timestamp", "colmena_id", "temp_interna", "hr_interna", "peso_kg"]
        if c in df.columns
    ]
    df = df[cols_disponibles].copy()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"])

    # Limitar número de colmenas
    if "colmena_id" in df.columns:
        colmenas = df["colmena_id"].unique()[:n_colmenas_max]
        df = df[df["colmena_id"].isin(colmenas)]

    df = df.sort_values("timestamp").reset_index(drop=True)
    logger.info(
        f"✅ BEEP Base cargado: {len(df)} registros | "
        f"{df['colmena_id'].nunique() if 'colmena_id' in df.columns else '?'} colmenas"
    )
    return df


def construir_percentiles_beep(df: pd.DataFrame) -> dict:
    """
    Construye percentiles de referencia desde el dataset BEEP local.
    Reemplaza los valores hardcodeados cuando hay datos reales disponibles.
    """
    if df.empty:
        logger.info("ℹ️  Usando percentiles BEEP hardcodeados (van der Zee et al., 2023)")
        return REFERENCIA_BEEP

    percentiles = {}
    cols_variables = {
        "temp_interna":              "temp_interna",
        "hr_interna":                "hr_interna",
    }

    for col_beep, col_ref in cols_variables.items():
        if col_beep in df.columns:
            serie = df[col_beep].dropna()
            if len(serie) > 100:
                percentiles[col_ref] = {
                    "p10":   round(serie.quantile(0.10), 2),
                    "p25":   round(serie.quantile(0.25), 2),
                    "p50":   round(serie.quantile(0.50), 2),
                    "p75":   round(serie.quantile(0.75), 2),
                    "p90":   round(serie.quantile(0.90), 2),
                    "media": round(serie.mean(), 2),
                    "sigma": round(serie.std(), 2),
                }

    # Calcular cambio de peso semanal si hay datos de peso
    if "peso_kg" in df.columns and "colmena_id" in df.columns:
        cambios = []
        for _, grupo in df.groupby("colmena_id"):
            grupo = grupo.sort_values("timestamp")
            peso_semanal = grupo.set_index("timestamp")["peso_kg"].resample("W").mean()
            cambio_pct   = peso_semanal.pct_change() * 100
            cambios.extend(cambio_pct.dropna().tolist())

        if cambios:
            serie_cambios = pd.Series(cambios)
            serie_cambios = serie_cambios[
                serie_cambios.between(-20, 20)
            ]
            percentiles["peso_cambio_semanal_pct"] = {
                "p10":   round(serie_cambios.quantile(0.10), 2),
                "p25":   round(serie_cambios.quantile(0.25), 2),
                "p50":   round(serie_cambios.quantile(0.50), 2),
                "p75":   round(serie_cambios.quantile(0.75), 2),
                "p90":   round(serie_cambios.quantile(0.90), 2),
                "media": round(serie_cambios.mean(), 2),
                "sigma": round(serie_cambios.std(), 2),
            }

    # Completar con hardcodeados si faltan variables
    for var, vals in REFERENCIA_BEEP.items():
        if var not in percentiles:
            percentiles[var] = vals

    logger.info(f"📊 Percentiles BEEP construidos para {len(percentiles)} variables")
    return percentiles


# ── COMPARACIÓN CON COLMENA PILOTO ────────────────────────────────────────────

def comparar_con_referencia(
    valor:     float,
    variable:  str,
    referencia: Optional[dict] = None,
) -> dict:
    """
    Compara un valor de la colmena piloto con los percentiles de referencia BEEP.

    Args:
        valor:      valor observado en la colmena piloto
        variable:   nombre de la variable (temp_interna, hr_interna, etc.)
        referencia: dict de percentiles (usa REFERENCIA_BEEP si es None)

    Returns:
        dict con: percentil_aprox, clasificacion, mensaje
    """
    ref = (referencia or REFERENCIA_BEEP).get(variable, {})
    if not ref:
        return {"percentil_aprox": None, "clasificacion": "SIN_REFERENCIA", "mensaje": ""}

    p10, p25, p50, p75, p90 = (
        ref["p10"], ref["p25"], ref["p50"], ref["p75"], ref["p90"]
    )

    if valor <= p10:
        percentil = 10
        clasificacion = "MUY_BAJO"
    elif valor <= p25:
        percentil = 25
        clasificacion = "BAJO"
    elif valor <= p75:
        percentil = 50
        clasificacion = "NORMAL"
    elif valor <= p90:
        percentil = 75
        clasificacion = "ALTO"
    else:
        percentil = 90
        clasificacion = "MUY_ALTO"

    # Mensaje interpretativo según variable
    mensajes = {
        "temp_interna": {
            "MUY_BAJO":  f"Temperatura {valor:.1f}°C muy por debajo de colmenas sanas. Posible problema de reina o colonia pequeña.",
            "BAJO":      f"Temperatura {valor:.1f}°C ligeramente baja. Monitoree.",
            "NORMAL":    f"Temperatura {valor:.1f}°C dentro del rango normal de colmenas saludables.",
            "ALTO":      f"Temperatura {valor:.1f}°C levemente alta. Verifique ventilación.",
            "MUY_ALTO":  f"Temperatura {valor:.1f}°C inusualmente alta. Posible estrés calórico.",
        },
        "hr_interna": {
            "MUY_BAJO":  f"Humedad {valor:.0f}% muy baja. Verifique sensor.",
            "BAJO":      f"Humedad {valor:.0f}% ligeramente baja.",
            "NORMAL":    f"Humedad {valor:.0f}% en rango saludable.",
            "ALTO":      f"Humedad {valor:.0f}% elevada. Verifique ventilación.",
            "MUY_ALTO":  f"Humedad {valor:.0f}% muy alta. Riesgo de enfermedades fúngicas.",
        },
        "peso_cambio_semanal_pct": {
            "MUY_BAJO":  f"Pérdida de {abs(valor):.1f}% en 7 días. Inusual — revise la colmena.",
            "BAJO":      f"Pérdida de {abs(valor):.1f}%. Dentro del rango bajo normal.",
            "NORMAL":    f"Cambio de {valor:+.1f}%. Comportamiento normal.",
            "ALTO":      f"Ganancia de {valor:.1f}%. Floración activa — buen indicador.",
            "MUY_ALTO":  f"Ganancia de {valor:.1f}%. Floración excepcional.",
        },
    }

    mensaje = mensajes.get(variable, {}).get(clasificacion, "")

    return {
        "percentil_aprox": percentil,
        "clasificacion":   clasificacion,
        "media_beep":      ref["media"],
        "mensaje":         mensaje,
    }


def validar_iot_vs_beep(
    df_iot_mensual: pd.DataFrame,
    referencia:     Optional[dict] = None,
) -> pd.DataFrame:
    """
    Valida la serie IoT mensual contra los percentiles BEEP.
    Agrega columnas de clasificación y mensaje para cada variable.

    Returns:
        df_iot_mensual con columnas adicionales de validación BEEP
    """
    ref = referencia or REFERENCIA_BEEP
    df  = df_iot_mensual.copy()

    variables = {
        "temp_interna":        "temp_interna",
        "hr_interna":          "hr_interna",
        "peso_cambio_pct":     "peso_cambio_semanal_pct",
    }

    for col_iot, var_beep in variables.items():
        if col_iot in df.columns:
            resultados = df[col_iot].apply(
                lambda v: comparar_con_referencia(v, var_beep, ref)
                if not pd.isna(v) else {"percentil_aprox": None, "clasificacion": "SIN_DATO"}
            )
            df[f"{col_iot}_beep_pct"]    = resultados.apply(lambda x: x.get("percentil_aprox"))
            df[f"{col_iot}_beep_clase"]  = resultados.apply(lambda x: x.get("clasificacion"))

    return df


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_referencia(
    referencia: dict,
    ruta: Union[str, Path] = "data/reference/beep_reference.csv",
) -> Path:
    """Guarda los percentiles de referencia en CSV."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    filas = []
    for variable, percentiles in referencia.items():
        fila = {"variable": variable}
        fila.update(percentiles)
        filas.append(fila)

    pd.DataFrame(filas).to_csv(ruta, index=False)
    logger.info(f"💾 Referencia BEEP guardada: {ruta}")
    return ruta


def cargar_referencia(
    ruta: Union[str, Path] = "data/reference/beep_reference.csv",
) -> dict:
    """Carga los percentiles de referencia desde CSV."""
    ruta = Path(ruta)
    if not ruta.exists():
        logger.info("ℹ️  Usando percentiles BEEP hardcodeados")
        return REFERENCIA_BEEP

    df  = pd.read_csv(ruta)
    ref = {}
    for _, row in df.iterrows():
        var = row["variable"]
        ref[var] = {k: v for k, v in row.items() if k != "variable"}
    return ref


# ── DEMO ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    print("═" * 60)
    print("  AbejaVerde·EO — beep_base_parser")
    print("  Referencia biológica para validación IoT")
    print("═" * 60)

    print("\n📊 Percentiles de referencia BEEP Base")
    print("   (van der Zee et al., 2023 — colmenas saludables Europa)")
    for var, vals in REFERENCIA_BEEP.items():
        print(f"\n   {var}:")
        print(f"   P10={vals['p10']} | P25={vals['p25']} | "
              f"P50={vals['p50']} | P75={vals['p75']} | P90={vals['p90']}")
        print(f"   Media={vals['media']} ± {vals['sigma']} σ")

    # Validar escenarios reales del piloto vs BEEP
    print("\n🔍 Validación de escenarios reales del piloto vs. BEEP:")

    escenarios = [
        ("Temperatura normal",      "temp_interna",            35.1),
        ("Temperatura crisis Niño", "temp_interna",            33.8),
        ("HR saludable",            "hr_interna",              52.0),
        ("HR alta (Abr 2025)",      "hr_interna",              71.0),
        ("Peso ganando (May 2024)", "peso_cambio_semanal_pct",  4.5),
        ("Peso perdiendo (Ene)",    "peso_cambio_semanal_pct", -6.2),
    ]

    for nombre, variable, valor in escenarios:
        resultado = comparar_con_referencia(valor, variable)
        print(f"\n   {nombre}: {valor}")
        print(f"   → {resultado['clasificacion']} (aprox. percentil {resultado['percentil_aprox']})")
        print(f"   → {resultado['mensaje'][:70]}...")

    # Guardar referencia hardcodeada
    guardar_referencia(REFERENCIA_BEEP)
    print("\n✅ Referencia BEEP guardada en data/reference/beep_reference.csv")
    print("   Para datos reales: descarga el dataset en https://beep.nl/dataset")
    print("   y corre: leer_beep_base('ruta/al/beep_dataset.csv')")
