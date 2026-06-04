"""
AbejaVerde·EO — Módulo: ita
=============================
Índice de Alerta Temprana Apícola (ITA)
Propuesto por Arelys Camacho — apicultora piloto San Juan de Rioseco

0 = Sin riesgo | 100 = Riesgo máximo

El ITA estima el nivel de riesgo para un apiario utilizando
exclusivamente datos de Observación de la Tierra (Copernicus).
Integra tres variables que afectan directamente la disponibilidad
de recursos para las abejas:

    Variable 1: NDVI  — estado de la vegetación (Sentinel-2)
    Variable 2: NDMI  — humedad de la vegetación (Sentinel-2)
    Variable 3: LST   — temperatura superficial (Sentinel-3 / ERA5)

La lógica NO usa valores absolutos sino variaciones respecto
a las condiciones normales del territorio (anomalías).
Esto permite detectar estrés antes de que sea visible en las colmenas.

Pesos (calibrados con 29 meses de datos reales SJR):
    NDVI = 35% | NDMI = 35% | LST = 30%

Escala:
    0-25  Bajo
    26-50 Moderado
    51-75 Alto
    76-100 Crítico
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── PESOS POR DEFECTO ─────────────────────────────────────────────────────────
PESO_NDVI_DEFAULT = 0.35
PESO_NDMI_DEFAULT = 0.35
PESO_LST_DEFAULT  = 0.30

# ── TABLAS DE RIESGO ──────────────────────────────────────────────────────────

def riesgo_ndvi(ndvi_historico: float, ndvi_actual: float) -> int:
    """
    Calcula el riesgo NDVI según disminución porcentual respecto al histórico.

    Tabla (Arelys Camacho, 2026):
        < 5%  → 0
        5-10% → 25
        10-20%→ 50
        20-30%→ 75
        > 30% → 100
    """
    if ndvi_historico <= 0:
        return 0
    disminucion = ((ndvi_historico - ndvi_actual) / ndvi_historico) * 100
    disminucion = max(0, disminucion)

    if disminucion < 5:   return 0
    if disminucion < 10:  return 25
    if disminucion < 20:  return 50
    if disminucion < 30:  return 75
    return 100


def riesgo_ndmi(ndmi_historico: float, ndmi_actual: float) -> int:
    """
    Calcula el riesgo NDMI según disminución porcentual respecto al histórico.
    Misma tabla que NDVI — estrés hídrico en la vegetación.
    """
    if ndmi_historico <= 0:
        return 0
    disminucion = ((ndmi_historico - ndmi_actual) / abs(ndmi_historico)) * 100
    disminucion = max(0, disminucion)

    if disminucion < 5:   return 0
    if disminucion < 10:  return 25
    if disminucion < 20:  return 50
    if disminucion < 30:  return 75
    return 100


def riesgo_lst(incremento_c: float) -> int:
    """
    Calcula el riesgo LST según incremento de temperatura respecto al histórico.

    Tabla (Arelys Camacho, 2026):
        < 0.5°C  → 0
        0.5-1°C  → 25
        1-2°C    → 50
        2-3°C    → 75
        > 3°C    → 100
    """
    inc = abs(incremento_c)  # tanto calor como frío extremo son riesgo
    if inc < 0.5: return 0
    if inc < 1.0: return 25
    if inc < 2.0: return 50
    if inc < 3.0: return 75
    return 100


# ── CLASE RESULTADO ───────────────────────────────────────────────────────────

@dataclass
class ResultadoITA:
    """Resultado del cálculo del ITA."""
    ita:            float
    nivel:          str
    r_ndvi:         int
    r_ndmi:         int
    r_lst:          int
    ndvi_actual:    float
    ndmi_actual:    float
    lst_incremento: float
    peso_ndvi:      float
    peso_ndmi:      float
    peso_lst:       float
    interpretacion: str = field(default="")

    def __post_init__(self):
        if not self.interpretacion:
            self.interpretacion = _interpretar_ita(
                self.ita, self.r_ndvi, self.r_ndmi, self.r_lst
            )

    @property
    def es_critico(self) -> bool:
        return self.ita > 75

    @property
    def necesita_visita(self) -> bool:
        return self.ita > 50

    def a_dict(self) -> dict:
        return {
            "ita":            round(self.ita, 1),
            "nivel":          self.nivel,
            "r_ndvi":         self.r_ndvi,
            "r_ndmi":         self.r_ndmi,
            "r_lst":          self.r_lst,
            "ndvi_actual":    self.ndvi_actual,
            "ndmi_actual":    self.ndmi_actual,
            "lst_incremento": self.lst_incremento,
            "interpretacion": self.interpretacion,
        }


def _nivel_ita(ita: float) -> str:
    if ita <= 25: return "Bajo"
    if ita <= 50: return "Moderado"
    if ita <= 75: return "Alto"
    return "Crítico"


def _interpretar_ita(ita: float, r_ndvi: int, r_ndmi: int, r_lst: int) -> str:
    """Genera interpretación en lenguaje natural."""
    if ita <= 25:
        return "El entorno del apiario muestra condiciones favorables. Sin señales de estrés ecosistémico."
    if ita <= 50:
        drivers = []
        if r_ndvi >= 50: drivers.append("vegetación con señales de estrés")
        if r_ndmi >= 50: drivers.append("humedad vegetal reducida")
        if r_lst   >= 50: drivers.append("temperatura inusual")
        txt = ", ".join(drivers) if drivers else "condiciones variables"
        return f"Riesgo moderado — {txt}. Planifique visita al apiario esta semana."
    if ita <= 75:
        return (
            "Condiciones de estrés ambiental detectadas. El entorno puede afectar "
            "la disponibilidad de néctar y agua. Visite el apiario y evalúe si "
            "necesita alimentación suplementaria o bebedero."
        )
    return (
        "ALERTA CRÍTICA — El entorno del apiario muestra estrés severo. "
        "Visite la colmena lo antes posible. Evalúe alimentación urgente "
        "y verifique disponibilidad de agua."
    )


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────────────────

def calcular_ita(
    ndvi_actual:    float,
    ndvi_historico: float,
    ndmi_actual:    float,
    ndmi_historico: float,
    lst_incremento: float,
    peso_ndvi:      float = PESO_NDVI_DEFAULT,
    peso_ndmi:      float = PESO_NDMI_DEFAULT,
    peso_lst:       float = PESO_LST_DEFAULT,
) -> ResultadoITA:
    """
    Calcula el Índice de Alerta Temprana Apícola (ITA).

    Args:
        ndvi_actual:     NDVI del mes actual (Sentinel-2)
        ndvi_historico:  NDVI promedio histórico del mismo mes
        ndmi_actual:     NDMI del mes actual (Sentinel-2)
        ndmi_historico:  NDMI promedio histórico del mismo mes
        lst_incremento:  Anomalía de temperatura superficial en °C
        peso_ndvi/ndmi/lst: pesos (deben sumar 1.0)

    Returns:
        ResultadoITA con el score y la interpretación
    """
    # Validar pesos
    suma = peso_ndvi + peso_ndmi + peso_lst
    if abs(suma - 1.0) > 0.01:
        logger.warning(f"Pesos no suman 1.0 ({suma:.2f}) — normalizando")
        peso_ndvi /= suma
        peso_ndmi /= suma
        peso_lst  /= suma

    r_ndvi = riesgo_ndvi(ndvi_historico, ndvi_actual)
    r_ndmi = riesgo_ndmi(ndmi_historico, ndmi_actual)
    r_lst  = riesgo_lst(lst_incremento)

    ita = (r_ndvi * peso_ndvi) + (r_ndmi * peso_ndmi) + (r_lst * peso_lst)
    ita = round(min(100, max(0, ita)), 1)

    return ResultadoITA(
        ita=ita, nivel=_nivel_ita(ita),
        r_ndvi=r_ndvi, r_ndmi=r_ndmi, r_lst=r_lst,
        ndvi_actual=ndvi_actual, ndmi_actual=ndmi_actual,
        lst_incremento=lst_incremento,
        peso_ndvi=peso_ndvi, peso_ndmi=peso_ndmi, peso_lst=peso_lst,
    )


def calcular_ita_serie(
    df:             pd.DataFrame,
    linea_base:     Optional[dict] = None,
    peso_ndvi:      float = PESO_NDVI_DEFAULT,
    peso_ndmi:      float = PESO_NDMI_DEFAULT,
    peso_lst:       float = PESO_LST_DEFAULT,
) -> pd.DataFrame:
    """
    Calcula el ITA para una serie temporal completa.

    Args:
        df:          DataFrame con columnas: fecha, ndvi, ndmi (opcional), anom_temp
        linea_base:  dict con ndvi_media por mes {1: 0.5, 2: 0.6, ...}
        peso_*:      pesos de cada variable

    Returns:
        df con columnas adicionales: ita, nivel_ita, r_ndvi, r_ndmi, r_lst
    """
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["mes"]   = df["fecha"].dt.month

    # Línea base por defecto — datos reales piloto SJR
    if linea_base is None:
        linea_base = _linea_base_sjr_default()

    resultados = []
    for _, row in df.iterrows():
        mes          = int(row["mes"])
        ndvi_hist    = linea_base.get(mes, {}).get("ndvi_media", 0.595)
        ndmi_hist    = linea_base.get(mes, {}).get("ndmi_media", 0.28)
        ndvi_actual  = float(row.get("ndvi", ndvi_hist))
        ndmi_actual  = float(row.get("ndmi", ndmi_hist))
        lst_inc      = float(row.get("anom_temp", row.get("lst_incremento", 0)))

        r = calcular_ita(
            ndvi_actual, ndvi_hist, ndmi_actual, ndmi_hist, lst_inc,
            peso_ndvi, peso_ndmi, peso_lst,
        )
        resultados.append(r.a_dict())

    df_r = pd.DataFrame(resultados)
    df   = pd.concat([df.reset_index(drop=True), df_r], axis=1)
    return df


def _linea_base_sjr_default() -> dict:
    """
    Línea base histórica de San Juan de Rioseco (29 meses reales 2024-2026).
    NDVI promedio por mes. NDMI estimado a partir del NDVI.
    """
    ndvi_por_mes = {
        1: 0.456, 2: 0.614, 3: 0.569, 4: 0.446,
        5: 0.742, 6: 0.817, 7: 0.529, 8: 0.701,
        9: 0.675, 10: 0.694, 11: 0.579, 12: 0.507,
    }
    return {
        mes: {
            "ndvi_media": ndvi,
            "ndmi_media": round(ndvi * 0.47, 3),  # NDMI ≈ 0.47 × NDVI (calibrado SJR)
        }
        for mes, ndvi in ndvi_por_mes.items()
    }


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_ita(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/ita_serie.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, date_format="%Y-%m-%d")
    logger.info(f"💾 ITA guardado: {ruta}")
    return ruta


# ── DEMO CON DATOS REALES SJR ─────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")

    print("═" * 55)
    print("  AbejaVerde·EO — ITA (Índice de Alerta Temprana Apícola)")
    print("  Propuesto por Arelys Camacho · San Juan de Rioseco")
    print("═" * 55)

    # Datos reales 29 meses SJR
    DATOS = [
        ("2024-01", 0.474, 0.0),  ("2024-02", 0.618, -0.1),
        ("2024-05", 0.773, -0.2), ("2024-06", 0.817, -0.3),
        ("2025-01", 0.437, 0.4),  ("2025-04", 0.379, 1.8),
        ("2025-05", 0.787, -0.1), ("2025-12", 0.313, 0.6),
        ("2026-01", 0.319, 0.5),  ("2026-02", 0.782, -0.2),
        ("2026-05", 0.667, 0.1),
    ]

    lb = _linea_base_sjr_default()
    print(f"\n{'Mes':12s} {'NDVI':6s} {'r_NDVI':7s} {'r_NDMI':7s} {'r_LST':6s} {'ITA':5s} {'Nivel':10s}")
    print("-" * 60)

    for fecha_str, ndvi, lst_inc in DATOS:
        mes   = int(fecha_str.split("-")[1])
        ndvi_h = lb[mes]["ndvi_media"]
        ndmi_h = lb[mes]["ndmi_media"]
        ndmi   = ndvi * 0.47

        r = calcular_ita(ndvi, ndvi_h, ndmi, ndmi_h, lst_inc)
        alert = " ⚠️" if r.es_critico else " 👁" if r.necesita_visita else ""
        print(f"{fecha_str:12s} {ndvi:.3f}  {r.r_ndvi:6d}  {r.r_ndmi:6d}  "
              f"{r.r_lst:5d}  {r.ita:5.1f}  {r.nivel:10s}{alert}")

    print("\n💡 Caso más crítico: Dic 2025 — ITA calculado:")
    r_critico = calcular_ita(0.313, 0.507, 0.147, 0.238, 0.6)
    print(f"   ITA = {r_critico.ita} — {r_critico.nivel}")
    print(f"   {r_critico.interpretacion}")
