"""
AbejaVerde·EO — Módulo: iot_parser
=====================================
Lectura, validación y estandarización de datos IoT de la colmena inteligente.

Hardware del piloto:
    Nodo:    Heltec WiFi LoRa 32 V3 (ESP32-S3 + SX1262)
    Sensores: 10 celdas de carga HX711 (una por cuadro/marco)
              Temperatura + humedad interna
    Radio:   LoRa 915 MHz → gateway LILYGO LoRa32
    Envío:   cada 10–15 minutos

Formato de datos esperado (JSON del gateway):
    {
      "ts":        "2025-05-29T14:30:00Z",
      "colmena_id": "C01",
      "cuadros": [
        {"id": 1, "peso_g": 2340.5},
        {"id": 2, "peso_g": 2180.0},
        ...
      ],
      "temp_interna": 35.2,
      "hr_interna":   52.1,
      "bateria_pct":  87.0
    }

También acepta CSV plano exportado desde el gateway.

Outputs:
    data/processed/iot_clean.csv         — serie limpia lista para el IRA
    data/processed/iot_anomalias.csv     — alertas biológicas detectadas
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── RANGOS VÁLIDOS ────────────────────────────────────────────────────────────

TEMP_COLMENA_MIN   = 20.0    # °C — por debajo: sensor desconectado o colonia muerta
TEMP_COLMENA_MAX   = 45.0    # °C — por encima: valor inválido
TEMP_CRIA_OPTIMA   = (34.5, 35.5)   # °C — homeostasis zona de cría
TEMP_CRIA_ALERTA   = (33.0, 37.0)   # °C — fuera de este rango → revisar
TEMP_CRIA_CRITICA  = (30.0, 40.0)   # °C — riesgo de muerte de cría

HR_MIN             =  20.0   # % — por debajo: sensor inválido
HR_MAX             = 100.0   # %
HR_OPTIMA          = (40.0, 65.0)   # % — rango saludable

PESO_MIN_G         =  100.0  # g — cuadro vacío mínimo
PESO_MAX_G         = 8000.0  # g — cuadro lleno máximo
BATERIA_ALERTA_PCT =  20.0   # % — notificar batería baja

# Pérdida de peso alarmante en 7 días
PERDIDA_PESO_7D_ALERTA_PCT   = -5.0   # %
PERDIDA_PESO_7D_CRITICA_PCT  = -10.0  # %


# ── LECTURA DE DATOS ─────────────────────────────────────────────────────────

def leer_json_gateway(
    ruta: Union[str, Path],
) -> pd.DataFrame:
    """
    Lee el archivo JSON exportado por el gateway LoRa.
    Acepta tanto un solo registro como una lista de registros.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró {ruta}")

    with open(ruta, "r", encoding="utf-8") as f:
        datos = json.load(f)

    if isinstance(datos, dict):
        datos = [datos]

    registros = []
    for d in datos:
        rec = _parsear_registro_json(d)
        if rec:
            registros.append(rec)

    if not registros:
        logger.warning("⚠️  No se encontraron registros válidos en el JSON")
        return pd.DataFrame()

    df = pd.DataFrame(registros)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    logger.info(f"📡 JSON gateway leído: {len(df)} registros")
    return df


def _parsear_registro_json(d: dict) -> Optional[dict]:
    """Parsea un registro JSON del gateway a formato estándar."""
    try:
        rec = {
            "timestamp":    d.get("ts", d.get("timestamp", "")),
            "colmena_id":   d.get("colmena_id", d.get("id", "C01")),
            "temp_interna": float(d.get("temp_interna", d.get("temp", np.nan))),
            "hr_interna":   float(d.get("hr_interna",   d.get("hr",   np.nan))),
            "bateria_pct":  float(d.get("bateria_pct",  d.get("bat",  np.nan))),
        }

        # Peso total y por cuadro
        cuadros = d.get("cuadros", [])
        if cuadros:
            pesos = [c.get("peso_g", c.get("peso", np.nan)) for c in cuadros]
            rec["peso_total_g"]  = round(sum(p for p in pesos if not np.isnan(p)), 1)
            rec["n_cuadros"]     = len(cuadros)
            for i, c in enumerate(cuadros):
                rec[f"peso_cuadro_{i+1}_g"] = float(c.get("peso_g", c.get("peso", np.nan)))
        else:
            rec["peso_total_g"]  = float(d.get("peso_total_g", d.get("peso", np.nan)))
            rec["n_cuadros"]     = 0

        return rec
    except Exception as e:
        logger.debug(f"Error parseando registro: {e}")
        return None


def leer_csv_gateway(
    ruta:        Union[str, Path],
    sep:         str = ",",
    col_ts:      str = "timestamp",
    col_temp:    str = "temp_interna",
    col_hr:      str = "hr_interna",
    col_peso:    str = "peso_total_g",
    col_bateria: str = "bateria_pct",
) -> pd.DataFrame:
    """
    Lee un CSV exportado desde el gateway o desde el IDE Serial Monitor.
    Flexible en nombres de columnas.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró {ruta}")

    df = pd.read_csv(ruta, sep=sep)

    # Renombrar columnas al formato estándar
    renombres = {
        col_ts:      "timestamp",
        col_temp:    "temp_interna",
        col_hr:      "hr_interna",
        col_peso:    "peso_total_g",
        col_bateria: "bateria_pct",
    }
    df = df.rename(columns={k: v for k, v in renombres.items() if k in df.columns})

    if "timestamp" not in df.columns:
        # Intentar encontrar la columna de tiempo
        candidatos = [c for c in df.columns
                      if any(k in c.lower() for k in ["time","fecha","ts","date"])]
        if candidatos:
            df = df.rename(columns={candidatos[0]: "timestamp"})

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    logger.info(f"📡 CSV gateway leído: {len(df)} registros")
    return df


# ── VALIDACIÓN Y LIMPIEZA ─────────────────────────────────────────────────────

def validar_limpiar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Valida rangos físicos y elimina lecturas inválidas.
    Imputa valores faltantes con interpolación lineal.
    """
    df = df.copy()
    n_inicial = len(df)

    # Temperatura interna
    if "temp_interna" in df.columns:
        invalidos = (df["temp_interna"] < TEMP_COLMENA_MIN) | \
                    (df["temp_interna"] > TEMP_COLMENA_MAX)
        df.loc[invalidos, "temp_interna"] = np.nan
        logger.debug(f"   Temp inválida: {invalidos.sum()} registros")

    # Humedad relativa
    if "hr_interna" in df.columns:
        invalidos = (df["hr_interna"] < HR_MIN) | (df["hr_interna"] > HR_MAX)
        df.loc[invalidos, "hr_interna"] = np.nan

    # Peso por cuadro
    cols_peso = [c for c in df.columns if "peso_cuadro" in c]
    for col in cols_peso:
        invalidos = (df[col] < PESO_MIN_G) | (df[col] > PESO_MAX_G)
        df.loc[invalidos, col] = np.nan

    # Peso total
    if "peso_total_g" in df.columns:
        invalidos = (df["peso_total_g"] < PESO_MIN_G * 5) | \
                    (df["peso_total_g"] > PESO_MAX_G * 12)
        df.loc[invalidos, "peso_total_g"] = np.nan

    # Interpolación lineal para valores faltantes (máx 3 periodos seguidos)
    cols_numericas = df.select_dtypes(include=[np.number]).columns
    df[cols_numericas] = df[cols_numericas].interpolate(
        method="linear", limit=3, limit_direction="both"
    )

    n_eliminados = n_inicial - df.dropna(subset=["temp_interna"]).shape[0]
    logger.info(
        f"✅ Validación IoT: {n_inicial} registros → "
        f"{len(df)} válidos | {n_eliminados} imputados"
    )
    return df


# ── RESAMPLEO Y AGREGACIÓN ────────────────────────────────────────────────────

def resamplear_horario(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega lecturas cada 10-15 min a promedios horarios."""
    df = df.set_index("timestamp")
    cols = df.select_dtypes(include=[np.number]).columns
    df_hora = df[cols].resample("h").mean().round(3)
    df_hora = df_hora.reset_index()
    logger.info(f"⏱️  Resampleado a horario: {len(df_hora)} horas")
    return df_hora


def resamplear_diario(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega lecturas a estadísticas diarias."""
    df = df.set_index("timestamp")
    cols_num = df.select_dtypes(include=[np.number]).columns

    agg = {}
    for col in cols_num:
        if "temp" in col:
            agg[col] = ["mean", "min", "max"]
        elif "hr" in col:
            agg[col] = ["mean", "max"]
        elif "peso" in col:
            agg[col] = ["mean", "min", "max"]
        else:
            agg[col] = "mean"

    df_dia = df[cols_num].resample("D").agg(agg)
    df_dia.columns = ["_".join(c).strip() if isinstance(c, tuple) else c
                      for c in df_dia.columns]
    df_dia = df_dia.reset_index()
    logger.info(f"📅 Resampleado a diario: {len(df_dia)} días")
    return df_dia


def resamplear_mensual_iot(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega datos IoT a promedios mensuales para alimentar el IRA.
    Calcula también el cambio de peso relativo mes a mes.
    """
    df = df.copy()
    df["mes"] = df["timestamp"].dt.to_period("M")

    agg = {}
    if "temp_interna" in df.columns:
        agg["temp_interna"] = "mean"
    if "hr_interna" in df.columns:
        agg["hr_interna"] = "mean"
    if "peso_total_g" in df.columns:
        agg["peso_total_g"] = "mean"
    if "bateria_pct" in df.columns:
        agg["bateria_pct"] = "min"   # registrar la batería más baja del mes

    df_mes = df.groupby("mes").agg(agg).reset_index()
    df_mes["fecha"] = df_mes["mes"].dt.to_timestamp()

    # Cambio de peso mes a mes (%)
    if "peso_total_g" in df_mes.columns:
        df_mes["peso_cambio_pct"] = (
            df_mes["peso_total_g"].pct_change() * 100
        ).round(2)

    df_mes = df_mes.drop(columns=["mes"])
    df_mes = df_mes.round(3)
    logger.info(f"📊 IoT mensual: {len(df_mes)} meses")
    return df_mes


# ── DETECCIÓN DE ANOMALÍAS BIOLÓGICAS ─────────────────────────────────────────

def detectar_anomalias_biologicas(
    df:         pd.DataFrame,
    colmena_id: str = "C01",
) -> list[dict]:
    """
    Detecta eventos biológicos anómalos en la serie IoT.

    Detecta:
        - Temperatura fuera de homeostasis sostenida (problema de reina)
        - Pérdida de peso severa (enjambrazón, robo, escasez)
        - Humedad alta sostenida (enfermedades fúngicas)
        - Batería baja

    Returns:
        Lista de eventos anómalos con timestamp, tipo y severidad
    """
    anomalias = []

    if df.empty:
        return anomalias

    df = df.sort_values("timestamp").reset_index(drop=True)

    # ── Temperatura fuera de homeostasis ──────────────────────────────────────
    if "temp_interna" in df.columns:
        t_min, t_max   = TEMP_CRIA_ALERTA
        t_crit_min, t_crit_max = TEMP_CRIA_CRITICA

        for i in range(len(df) - 1):
            t_curr = df.loc[i, "temp_interna"]
            t_next = df.loc[i + 1, "temp_interna"]
            ts     = df.loc[i, "timestamp"]

            if pd.isna(t_curr) or pd.isna(t_next):
                continue

            if t_curr < t_crit_min or t_curr > t_crit_max:
                anomalias.append({
                    "timestamp":  ts,
                    "colmena_id": colmena_id,
                    "tipo":       "TEMP_CRITICA",
                    "severidad":  "ALTA",
                    "valor":      t_curr,
                    "mensaje":    (
                        f"Temperatura crítica: {t_curr:.1f}°C. "
                        f"Visite la colmena en las próximas 24h. "
                        f"Revise reina, población y signos de enfermedad."
                    ),
                })
            elif t_curr < t_min or t_curr > t_max:
                anomalias.append({
                    "timestamp":  ts,
                    "colmena_id": colmena_id,
                    "tipo":       "TEMP_ANORMAL",
                    "severidad":  "MEDIA",
                    "valor":      t_curr,
                    "mensaje":    (
                        f"Temperatura anormal: {t_curr:.1f}°C "
                        f"(óptimo 34.5–35.5°C). Monitoree."
                    ),
                })

    # ── Pérdida de peso severa ────────────────────────────────────────────────
    if "peso_total_g" in df.columns:
        df_dia = df.set_index("timestamp")["peso_total_g"].resample("D").mean()

        for i in range(7, len(df_dia)):
            peso_hace_7d = df_dia.iloc[i - 7]
            peso_hoy     = df_dia.iloc[i]

            if pd.isna(peso_hace_7d) or pd.isna(peso_hoy) or peso_hace_7d <= 0:
                continue

            cambio_pct = (peso_hoy - peso_hace_7d) / peso_hace_7d * 100

            if cambio_pct <= PERDIDA_PESO_7D_CRITICA_PCT:
                anomalias.append({
                    "timestamp":  df_dia.index[i],
                    "colmena_id": colmena_id,
                    "tipo":       "PERDIDA_PESO_SEVERA",
                    "severidad":  "ALTA",
                    "valor":      round(cambio_pct, 1),
                    "mensaje":    (
                        f"Pérdida de peso severa: {cambio_pct:.1f}% en 7 días. "
                        f"Posible enjambrazón, robo o escasez aguda. "
                        f"Revise la colmena hoy."
                    ),
                })
            elif cambio_pct <= PERDIDA_PESO_7D_ALERTA_PCT:
                anomalias.append({
                    "timestamp":  df_dia.index[i],
                    "colmena_id": colmena_id,
                    "tipo":       "PERDIDA_PESO_MODERADA",
                    "severidad":  "MEDIA",
                    "valor":      round(cambio_pct, 1),
                    "mensaje":    (
                        f"Pérdida de peso moderada: {cambio_pct:.1f}% en 7 días. "
                        f"Monitoree y considere alimentación suplementaria."
                    ),
                })

    # ── Humedad alta sostenida ────────────────────────────────────────────────
    if "hr_interna" in df.columns:
        hr_alta = df["hr_interna"] > 75.0
        if hr_alta.sum() >= 3:
            anomalias.append({
                "timestamp":  df.loc[hr_alta.idxmax(), "timestamp"],
                "colmena_id": colmena_id,
                "tipo":       "HR_ALTA_SOSTENIDA",
                "severidad":  "MEDIA",
                "valor":      df.loc[hr_alta, "hr_interna"].mean(),
                "mensaje":    (
                    f"Humedad interna alta sostenida "
                    f"(media {df.loc[hr_alta,'hr_interna'].mean():.1f}%). "
                    f"Verifique ventilación y revise signos de nosemosis."
                ),
            })

    # ── Batería baja ──────────────────────────────────────────────────────────
    if "bateria_pct" in df.columns:
        bat_baja = df["bateria_pct"] < BATERIA_ALERTA_PCT
        if bat_baja.any():
            anomalias.append({
                "timestamp":  df.loc[bat_baja.idxmax(), "timestamp"],
                "colmena_id": colmena_id,
                "tipo":       "BATERIA_BAJA",
                "severidad":  "INFO",
                "valor":      df.loc[bat_baja, "bateria_pct"].min(),
                "mensaje":    (
                    f"Batería del sensor al "
                    f"{df.loc[bat_baja,'bateria_pct'].min():.0f}%. "
                    f"Revise panel solar o recargue en la próxima visita."
                ),
            })

    logger.info(f"🔍 {len(anomalias)} anomalías biológicas detectadas")
    return anomalias


# ── RESUMEN PARA EL IRA ───────────────────────────────────────────────────────

def resumen_para_ira(df_mensual: pd.DataFrame) -> list[dict]:
    """
    Prepara los datos IoT en el formato que espera calcular_ira() del IRA.

    Returns:
        Lista de dicts con: fecha, tcolmena, hr_interna, peso_cambio_pct
    """
    registros = []
    for _, row in df_mensual.iterrows():
        registros.append({
            "fecha":           row.get("fecha"),
            "tcolmena":        row.get("temp_interna"),
            "hr_interna":      row.get("hr_interna"),
            "peso_cambio_pct": row.get("peso_cambio_pct"),
        })
    return registros


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_iot_limpio(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/iot_clean.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 IoT guardado: {ruta}")
    return ruta


def guardar_anomalias_iot(
    anomalias: list[dict],
    ruta:      Union[str, Path] = "data/processed/iot_anomalias.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(anomalias).to_csv(ruta, index=False)
    logger.info(f"💾 Anomalías IoT guardadas: {ruta}")
    return ruta


def cargar_iot(
    ruta: Union[str, Path] = "data/processed/iot_clean.csv",
) -> pd.DataFrame:
    ruta = Path(ruta)
    if not ruta.exists():
        logger.warning(f"⚠️  No se encontró {ruta}")
        return pd.DataFrame()
    return pd.read_csv(ruta, parse_dates=["timestamp"])


# ── DEMO CON DATOS SIMULADOS DEL PILOTO ──────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    import datetime as dt

    print("═" * 60)
    print("  AbejaVerde·EO — iot_parser")
    print("  Colmena piloto C01 — San Juan de Rioseco")
    print("═" * 60)

    # Generar datos de prueba (1 semana, cada 15 min)
    rng        = np.random.default_rng(42)
    inicio     = dt.datetime(2025, 5, 1, 6, 0, 0)
    n          = 7 * 24 * 4   # 7 días × 24h × 4 lecturas/hora

    timestamps = [inicio + dt.timedelta(minutes=15 * i) for i in range(n)]

    # Simular temperatura con homeostasis normal y un evento de hipotermia
    temp_base = 35.0 + rng.normal(0, 0.3, n)
    temp_base[200:220] = 33.2   # evento anómalo: hipotermia

    # Simular peso total con tendencia creciente (floración activa mayo)
    peso_base = 18000 + np.linspace(0, 800, n) + rng.normal(0, 50, n)

    datos_demo = pd.DataFrame({
        "timestamp":    timestamps,
        "colmena_id":   "C01",
        "temp_interna": temp_base.round(2),
        "hr_interna":   (52 + rng.normal(0, 3, n)).clip(40, 75).round(1),
        "peso_total_g": peso_base.round(0),
        "bateria_pct":  (88 - np.linspace(0, 5, n) + rng.normal(0, 1, n)).clip(0, 100).round(1),
    })

    # Validar y limpiar
    df_limpio = validar_limpiar(datos_demo)

    # Resamplear
    df_horario = resamplear_horario(df_limpio)
    df_mensual = resamplear_mensual_iot(df_limpio)

    print(f"\n📡 Datos IoT — Colmena C01 (1 semana simulada):")
    print(f"   Lecturas totales    : {len(datos_demo)}")
    print(f"   Temperatura media   : {df_limpio['temp_interna'].mean():.2f}°C")
    print(f"   HR media            : {df_limpio['hr_interna'].mean():.1f}%")
    print(f"   Peso inicial        : {df_limpio['peso_total_g'].iloc[0]:.0f}g")
    print(f"   Peso final          : {df_limpio['peso_total_g'].iloc[-1]:.0f}g")
    peso_cambio = (df_limpio['peso_total_g'].iloc[-1] - df_limpio['peso_total_g'].iloc[0]) \
                  / df_limpio['peso_total_g'].iloc[0] * 100
    print(f"   Cambio peso 7 días  : {peso_cambio:+.1f}% ({'ganando' if peso_cambio > 0 else 'perdiendo'})")

    # Detectar anomalías
    anomalias = detectar_anomalias_biologicas(df_limpio, "C01")
    print(f"\n🔍 Anomalías detectadas: {len(anomalias)}")
    for a in anomalias[:3]:
        ts = a["timestamp"]
        ts_str = ts.strftime("%d %b %H:%M") if hasattr(ts, "strftime") else str(ts)
        print(f"   [{a['severidad']:5s}] {ts_str}  {a['tipo']}")
        print(f"          {a['mensaje'][:70]}...")

    # Resumen para IRA
    ira_data = resumen_para_ira(df_mensual)
    print(f"\n🧠 Datos para IRA:")
    for r in ira_data:
        print(f"   {str(r.get('fecha',''))[:7]}  "
              f"T°{r.get('tcolmena',0):.1f}  "
              f"HR{r.get('hr_interna',0):.0f}%  "
              f"Δpeso{r.get('peso_cambio_pct',0) or 0:+.1f}%")
