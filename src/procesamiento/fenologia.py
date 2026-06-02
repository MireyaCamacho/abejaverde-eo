"""
AbejaVerde·EO — Módulo: fenologia
=====================================
Procesamiento e interpretación del ciclo fenológico para el sistema de alertas.

Este módulo (src/procesamiento/) trabaja con los datos ya ingestados por
src/ingesta/land_phenology.py y los transforma en insumos concretos para:
    - El componente f_fenologia del IRA
    - Las alertas de alimentación y cosecha
    - El calendario de manejo personalizado

Diferencia con land_phenology.py (ingesta):
    land_phenology.py  → descarga datos y detecta SOS/POS/EOS desde NDVI
    fenologia.py       → interpreta esos datos, detecta anomalías
                         y genera recomendaciones accionables

Outputs:
    data/processed/fenologia_series.csv  — ciclos anuales con estado
    data/reference/floraciones_sjr.csv   — calendario floral actualizado
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── CONSTANTES ────────────────────────────────────────────────────────────────

MESES_ES = {
    1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
    7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre",
}

# Duración media de la temporada floral en San Juan de Rioseco
# Derivada de los 17 meses de datos reales del piloto
DURACION_TEMPORADA_MEDIA_DIAS = 75
DURACION_TEMPORADA_SIGMA_DIAS = 15

# Días de anticipación para cada tipo de alerta
DIAS_ANTICIPACION_ALIMENTACION = 14   # alertar 2 semanas antes del fin de temporada
DIAS_ANTICIPACION_COSECHA      = 7    # alertar 1 semana antes del pico


# ── ANÁLISIS DE TEMPORADAS ────────────────────────────────────────────────────

def analizar_temporada(temporada: dict) -> dict:
    """
    Analiza una temporada individual y la enriquece con métricas derivadas.

    Args:
        temporada: dict con {sos, pos, eos, ampl, ndvi_pico, año}

    Returns:
        temporada enriquecida con: duracion_dias, intensidad, anomalia_duracion
    """
    t = dict(temporada)

    sos = pd.Timestamp(t["sos"])
    pos = pd.Timestamp(t["pos"])
    eos = pd.Timestamp(t["eos"])

    t["duracion_dias"]    = (eos - sos).days
    t["dias_hasta_pico"]  = (pos - sos).days
    t["dias_desde_pico"]  = (eos - pos).days
    t["mes_sos"]          = sos.month
    t["mes_pos"]          = pos.month
    t["mes_eos"]          = eos.month

    # Anomalía de duración vs. media histórica
    t["anomalia_duracion"] = round(
        (t["duracion_dias"] - DURACION_TEMPORADA_MEDIA_DIAS)
        / DURACION_TEMPORADA_SIGMA_DIAS, 2
    )

    # Clasificar intensidad según AMPL y NDVI pico
    ampl = t.get("ampl", 0) or 0
    ndvi = t.get("ndvi_pico", 0) or 0

    if ndvi >= 0.75 and ampl >= 0.25:
        t["intensidad"] = "ALTA"
    elif ndvi >= 0.60 and ampl >= 0.15:
        t["intensidad"] = "MEDIA"
    else:
        t["intensidad"] = "BAJA"

    return t


def comparar_temporadas(temporadas: list[dict]) -> pd.DataFrame:
    """
    Compara las temporadas detectadas entre sí para identificar patrones
    y anomalías interanuales.

    Detecta:
        - ¿La temporada llegó tarde/temprano vs. el histórico?
        - ¿Es más larga/corta que el promedio?
        - ¿Es más intensa/débil?

    Returns:
        DataFrame con temporadas enriquecidas y comparativas
    """
    if not temporadas:
        return pd.DataFrame()

    analizadas = [analizar_temporada(t) for t in temporadas]
    df         = pd.DataFrame(analizadas)

    # Estadísticos históricos de la serie
    if len(df) > 1:
        media_mes_sos  = df["mes_sos"].mean()
        media_duracion = df["duracion_dias"].mean()
        media_ndvi     = df["ndvi_pico"].mean() if "ndvi_pico" in df.columns else None

        df["retraso_inicio_dias"] = (
            (df["mes_sos"] - media_mes_sos) * 30
        ).round(0)

        df["vs_duracion_historica"] = df["duracion_dias"].apply(
            lambda d: "MAS_LARGA" if d > media_duracion + 15
            else "MAS_CORTA"  if d < media_duracion - 15
            else "NORMAL"
        )

        if media_ndvi:
            df["vs_intensidad_historica"] = df["ndvi_pico"].apply(
                lambda n: "MAS_INTENSA" if n > media_ndvi + 0.05
                else "MENOS_INTENSA" if n < media_ndvi - 0.05
                else "NORMAL"
            )

    logger.info(f"🌿 {len(df)} temporadas analizadas y comparadas")
    return df


# ── POSICIÓN EN EL CICLO ──────────────────────────────────────────────────────

def posicion_en_ciclo(
    fecha_hoy:   date,
    temporadas:  list[dict],
) -> dict:
    """
    Determina la posición actual dentro del ciclo fenológico y calcula
    los días hasta los próximos eventos clave.

    Returns:
        dict con: fase, dias_para_sos, dias_para_pos, dias_para_eos,
                  alertas_fenologicas, recomendacion_manejo
    """
    if not temporadas:
        return {
            "fase":               "DESCONOCIDA",
            "descripcion":        "Sin datos fenológicos disponibles",
            "alertas_fenologicas": [],
        }

    # Encontrar temporada activa o más próxima
    hoy     = pd.Timestamp(fecha_hoy)
    alertas = []

    # Ordenar temporadas por proximidad a hoy
    def distancia_a_hoy(t):
        sos = pd.Timestamp(t["sos"])
        eos = pd.Timestamp(t["eos"])
        if sos <= hoy <= eos:
            return 0   # estamos dentro
        return min(abs((sos - hoy).days), abs((eos - hoy).days))

    temporadas_ord = sorted(temporadas, key=distancia_a_hoy)
    t_proxima      = temporadas_ord[0]

    sos = pd.Timestamp(t_proxima["sos"])
    pos = pd.Timestamp(t_proxima["pos"])
    eos = pd.Timestamp(t_proxima["eos"])

    dias_sos = (sos - hoy).days
    dias_pos = (pos - hoy).days
    dias_eos = (eos - hoy).days

    # Determinar fase
    if hoy < sos:
        if dias_sos <= 30:
            fase        = "PRE_TEMPORADA_CERCANA"
            descripcion = f"Floración en ~{dias_sos} días ({sos.strftime('%d %b')}). Prepare la colmena."
            alertas.append({
                "tipo":    "PREPARACION",
                "urgencia": "MEDIA",
                "mensaje": f"La temporada floral comienza en {dias_sos} días. "
                           f"Revise la colmena, trate varroasis si es necesario y prepare alzas.",
            })
        else:
            fase        = "PRE_TEMPORADA"
            descripcion = f"Próxima floración en ~{dias_sos} días ({MESES_ES[sos.month]})."

    elif sos <= hoy <= pos:
        fase        = "FLORACION_ACTIVA_CRECIENTE"
        descripcion = f"Floración activa y creciendo. Pico en ~{dias_pos} días ({pos.strftime('%d %b')})."
        alertas.append({
            "tipo":    "NO_ALIMENTAR",
            "urgencia": "INFO",
            "mensaje": "Floración activa. NO alimente. Las abejas están recolectando. "
                       "Verifique que haya espacio suficiente en las alzas.",
        })
        if dias_pos <= DIAS_ANTICIPACION_COSECHA:
            alertas.append({
                "tipo":    "COSECHA_PROXIMA",
                "urgencia": "MEDIA",
                "mensaje": f"El pico de floración es en {dias_pos} días. "
                           f"Revise si los cuadros están al {'>'}80% para cosechar.",
            })

    elif pos < hoy <= eos:
        fase        = "FLORACION_ACTIVA_DECLINANDO"
        descripcion = f"Floración declinando. Fin de temporada en ~{dias_eos} días ({eos.strftime('%d %b')})."
        if dias_eos <= DIAS_ANTICIPACION_ALIMENTACION:
            alertas.append({
                "tipo":    "PREPARAR_ALIMENTACION",
                "urgencia": "ALTA",
                "mensaje": f"La temporada floral termina en {dias_eos} días. "
                           f"Prepare alimentación suplementaria para después del {eos.strftime('%d %b')}.",
            })

    else:
        fase        = "FUERA_TEMPORADA"
        descripcion = "Fuera de temporada floral. Monitoree reservas y considere alimentar."
        alertas.append({
            "tipo":    "ALIMENTACION",
            "urgencia": "ALTA",
            "mensaje": "Temporada floral terminada. Evalúe las reservas de la colmena. "
                       "Si el peso está por debajo del promedio, inicie alimentación suplementaria.",
        })

    resultado = {
        "fase":               fase,
        "descripcion":        descripcion,
        "dias_para_sos":      dias_sos,
        "dias_para_pos":      dias_pos,
        "dias_para_eos":      dias_eos,
        "temporada":          t_proxima,
        "alertas_fenologicas": alertas,
    }

    # Recomendación de manejo según la fase
    resultado["recomendacion_manejo"] = _recomendacion_manejo(fase, dias_eos)

    return resultado


def _recomendacion_manejo(fase: str, dias_eos: int) -> str:
    """Genera recomendación de manejo específica según la fase fenológica."""
    recomendaciones = {
        "PRE_TEMPORADA_CERCANA": (
            "Semana previa a la floración: revise la colmena, "
            "verifique que la reina esté en postura, "
            "trate varroasis si el nivel es alto y prepare alzas vacías."
        ),
        "PRE_TEMPORADA": (
            "Fuera de temporada: mantenga el monitoreo semanal. "
            "Alimente si el peso baja más del 5% en 7 días."
        ),
        "FLORACION_ACTIVA_CRECIENTE": (
            "Floración en crecimiento: NO alimente. "
            "Verifique que hay espacio para almacenar néctar. "
            "Si los cuadros están al 80%, agregue alzas."
        ),
        "FLORACION_ACTIVA_DECLINANDO": (
            f"Floración terminando en {dias_eos} días: "
            "realice la cosecha si los cuadros están maduros (>80% operculados). "
            "Prepare la alimentación post-cosecha."
        ),
        "FUERA_TEMPORADA": (
            "Sin floración activa: evalúe las reservas. "
            "Peso por colmena < 15 kg → alimente con jarabe 2:1. "
            "Revise signos de varroasis y enfermedades."
        ),
    }
    return recomendaciones.get(fase, "Monitoreo rutinario recomendado.")


# ── SCORE FENOLÓGICO PARA EL IRA ─────────────────────────────────────────────

def calcular_score_fenologico(
    fecha_hoy:   date,
    temporadas:  list[dict],
    ndvi_anomalia: float = 0.0,
) -> float:
    """
    Calcula el score de riesgo fenológico para el componente f_fenologia del IRA.
    Riesgo 0-1: 0 = sin riesgo (floración activa), 1 = máximo riesgo.

    Este score ya está implementado en src/procesamiento/ira.py (f_fenologia),
    pero aquí se expone como función standalone para pruebas y visualización.
    """
    posicion = posicion_en_ciclo(fecha_hoy, temporadas)
    fase     = posicion["fase"]

    scores_base = {
        "FLORACION_ACTIVA_CRECIENTE":  0.0,
        "FLORACION_ACTIVA_DECLINANDO": 0.2,
        "PRE_TEMPORADA_CERCANA":       0.3,
        "PRE_TEMPORADA":               0.4,
        "FUERA_TEMPORADA":             0.7,
        "DESCONOCIDA":                 0.5,
    }

    score_base = scores_base.get(fase, 0.5)

    # Penalización si el NDVI también está bajo
    penal_ndvi = max(0.0, min(0.2, -ndvi_anomalia * 0.1))

    return round(min(1.0, score_base + penal_ndvi), 3)


# ── CALENDARIO DE MANEJO PERSONALIZADO ───────────────────────────────────────

def generar_calendario_manejo(
    temporadas:   list[dict],
    año_objetivo: int,
    n_colmenas:   int = 1,
) -> pd.DataFrame:
    """
    Genera un calendario mensual de manejo apícola personalizado
    basado en el patrón fenológico detectado para el territorio.

    Returns:
        DataFrame con: mes, nombre_mes, actividad_principal, prioridad, detalle
    """
    if not temporadas:
        return pd.DataFrame()

    # Inferir patrón del territorio desde las temporadas detectadas
    meses_floracion  = set()
    meses_pico       = set()
    meses_post_eos   = set()

    for t in temporadas:
        sos = pd.Timestamp(t["sos"])
        pos = pd.Timestamp(t["pos"])
        eos = pd.Timestamp(t["eos"])

        cursor = sos
        while cursor <= pos:
            meses_floracion.add(cursor.month)
            cursor += pd.DateOffset(months=1)

        meses_pico.add(pos.month)

        # Mes siguiente al EOS = preparar alimentación
        mes_post = (eos + pd.DateOffset(months=1)).month
        meses_post_eos.add(mes_post)

    calendario = []
    for mes in range(1, 13):
        if mes in meses_pico:
            actividad  = "COSECHA"
            prioridad  = "ALTA"
            detalle    = (
                f"Mes de pico floral. Revise si los cuadros están al 80% operculados. "
                f"Cosechue si están maduros. No alimente."
            )
        elif mes in meses_floracion:
            actividad  = "MONITOREO_FLORACION"
            prioridad  = "MEDIA"
            detalle    = (
                f"Floración activa. Revise semanalmente. "
                f"Asegure espacio en alzas. No alimente."
            )
        elif mes in meses_post_eos:
            actividad  = "ALIMENTACION_POST_COSECHA"
            prioridad  = "ALTA"
            detalle    = (
                f"Fin de temporada floral. Evalúe reservas. "
                f"Alimente si el peso baja del mínimo (15 kg por colmena). "
                f"Trate varroasis."
            )
        else:
            actividad  = "MANTENIMIENTO"
            prioridad  = "NORMAL"
            detalle    = (
                f"Fuera de temporada principal. Monitoreo quincenal. "
                f"Verifique temperatura, humedad y peso. "
                f"Alimente si es necesario."
            )

        calendario.append({
            "mes":               mes,
            "nombre_mes":        MESES_ES[mes],
            "año":               año_objetivo,
            "actividad_principal": actividad,
            "prioridad":         prioridad,
            "detalle":           detalle,
            "floración_activa":  mes in meses_floracion,
        })

    df = pd.DataFrame(calendario)
    logger.info(
        f"📅 Calendario de manejo {año_objetivo} generado — "
        f"{n_colmenas} colmenas | "
        f"{df['floración_activa'].sum()} meses de floración activa"
    )
    return df


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_fenologia_procesada(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/fenologia_series.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 Fenología procesada guardada: {ruta}")
    return ruta


def guardar_calendario_manejo(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/reference/calendario_manejo.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 Calendario de manejo guardado: {ruta}")
    return ruta


# ── DEMO CON DATOS REALES DEL PILOTO ─────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level   = logging.INFO,
        format  = "%(asctime)s %(levelname)s %(message)s",
        datefmt = "%H:%M:%S",
    )

    from datetime import date

    print("═" * 60)
    print("  AbejaVerde·EO — fenologia (procesamiento)")
    print("  Apiario San Juan de Rioseco — datos reales piloto")
    print("═" * 60)

    # Temporadas reales detectadas por land_phenology.py
    TEMPORADAS_REALES = [
        {
            "año":       2024,
            "sos":       date(2024, 2, 1),
            "pos":       date(2024, 6, 1),
            "eos":       date(2024, 7, 1),
            "ndvi_pico": 0.817,
            "ampl":      0.288,
            "los_dias":  150,
            "fuente":    "Sentinel-2 NDVI derivado",
        },
        {
            "año":       2024,
            "sos":       date(2024, 8, 1),
            "pos":       date(2024, 10, 1),
            "eos":       date(2024, 11, 1),
            "ndvi_pico": 0.698,
            "ampl":      0.169,
            "los_dias":  92,
            "fuente":    "Sentinel-2 NDVI derivado",
        },
        {
            "año":       2024,
            "sos":       date(2024, 12, 1),
            "pos":       date(2025, 5, 1),
            "eos":       date(2025, 5, 31),
            "ndvi_pico": 0.787,
            "ampl":      0.350,
            "los_dias":  181,
            "fuente":    "Sentinel-2 NDVI derivado",
        },
    ]

    # Comparar temporadas
    df_temporadas = comparar_temporadas(TEMPORADAS_REALES)
    print(f"\n🌸 Análisis de temporadas detectadas:")
    for _, t in df_temporadas.iterrows():
        print(f"   {MESES_ES[t['mes_sos']]}→{MESES_ES[t['mes_eos']]} {t['año']}  "
              f"NDVI pico={t['ndvi_pico']:.3f}  "
              f"Duración={t['duracion_dias']}d  "
              f"Intensidad={t['intensidad']}")

    # Posición actual en el ciclo
    hoy = date.today()
    posicion = posicion_en_ciclo(hoy, TEMPORADAS_REALES)
    print(f"\n📍 Posición actual ({hoy}):")
    print(f"   Fase: {posicion['fase']}")
    print(f"   {posicion['descripcion']}")
    print(f"   Manejo: {posicion['recomendacion_manejo'][:80]}...")

    if posicion["alertas_fenologicas"]:
        print(f"\n⚠️  Alertas fenológicas:")
        for a in posicion["alertas_fenologicas"]:
            print(f"   [{a['urgencia']}] {a['tipo']}: {a['mensaje'][:70]}...")

    # Score fenológico para el IRA
    score = calcular_score_fenologico(hoy, TEMPORADAS_REALES)
    print(f"\n🧠 Score f_fenologia para IRA: {score} (0=sin riesgo, 1=máximo)")

    # Calendario de manejo 2025
    calendario = generar_calendario_manejo(TEMPORADAS_REALES, 2025, n_colmenas=10)
    print(f"\n📅 Calendario de manejo 2025:")
    for _, r in calendario.iterrows():
        flag = "🌿" if r["floración_activa"] else "  "
        print(f"   {flag} {r['nombre_mes']:12s}  [{r['prioridad']:6s}]  {r['actividad_principal']}")

    guardar_fenologia_procesada(df_temporadas)
    guardar_calendario_manejo(calendario)
