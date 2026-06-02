"""
AbejaVerde·EO — Módulo: motor_alertas
========================================
Lógica central de generación de alertas apícolas.

Este módulo orquesta todas las fuentes de datos y tipos de alerta,
aplica la lógica de doble evidencia del plan V2, y produce alertas
accionables en lenguaje natural para el apicultor.

Tipos de alerta soportados (plan V2):
    🍯 ALIMENTACION     — cuándo y cómo alimentar
    ✅ NO_ALIMENTAR      — floración activa, no alimente
    💧 AGUA             — escasez de agua superficial
    👑 VISITA_REINA      — temperatura interna anómala
    📍 REUBICACION      — zona sin floración persistente
    ☀️ OLA_CALOR         — temperatura alta simultánea satelital + colmena
    🔋 BATERIA_BAJA      — sensor sin energía
    ⚠️  CONVERGENCIA     — múltiples señales simultáneas

Principio de doble evidencia:
    Una alerta se activa cuando hay señal convergente de al menos dos fuentes:
    - Satélite (NDVI bajo, ERA5 anómalo, agua escasa)
    - Biológica (IoT temperatura o HR anómalos)
    Una sola fuente → aviso. Dos fuentes → alerta. Tres o más → urgente.

Outputs:
    data/processed/alertas_log.csv   — registro histórico de alertas
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ── MODOS DE OPERACIÓN ───────────────────────────────────────────────────────
#
# El sistema genera alertas en tres frecuencias distintas:
#
#   TIEMPO_REAL  → cada 10-15 min   → solo IoT
#                  Alerta: temp colmena, HR, batería
#                  Acción requerida en < 48h
#
#   SENTINEL     → cada 5 días      → nueva imagen Sentinel-2
#                  Alerta: NDVI cayó, agua cambió
#                  Acción requerida en < 1 semana
#
#   MENSUAL      → día 1 de cada mes → ERA5 + fenología + tendencias
#                  Alerta: tendencia de escasez, reubicación, calendario
#                  Acción requerida en < 1 mes
#
# Las alertas de TIEMPO_REAL son las más críticas para el bienestar
# de la colmena. SENTINEL detecta cambios en el entorno. MENSUAL
# permite planificación estratégica del apiario.

MODO_TIEMPO_REAL = "TIEMPO_REAL"
MODO_SENTINEL    = "SENTINEL"
MODO_MENSUAL     = "MENSUAL"

# Tipos de alerta por modo
ALERTAS_POR_MODO = {
    MODO_TIEMPO_REAL: ["VISITA_REINA", "BATERIA_BAJA", "OLA_CALOR"],
    MODO_SENTINEL:    ["ALIMENTACION", "NO_ALIMENTAR", "AGUA", "OLA_CALOR"],
    MODO_MENSUAL:     ["ALIMENTACION", "REUBICACION", "COSECHA", "PREPARACION"],
}

# ── NIVELES Y PRIORIDADES ─────────────────────────────────────────────────────

NIVELES = {
    "URGENTE": 4,
    "ALTA":    3,
    "MEDIA":   2,
    "INFO":    1,
    "NORMAL":  0,
}

EMOJIS = {
    "ALIMENTACION":   "🍯",
    "NO_ALIMENTAR":   "✅",
    "AGUA":           "💧",
    "VISITA_REINA":   "👑",
    "REUBICACION":    "📍",
    "OLA_CALOR":      "☀️",
    "BATERIA_BAJA":   "🔋",
    "CONVERGENCIA":   "⚠️",
    "COSECHA":        "🫙",
    "PREPARACION":    "🌱",
}


# ── CLASE ALERTA ──────────────────────────────────────────────────────────────

class Alerta:
    """Representa una alerta apícola generada por el sistema."""

    def __init__(
        self,
        tipo:        str,
        nivel:       str,
        mensaje:     str,
        recomendacion: str,
        apiario_id:  str           = "API_SJR_01",
        colmena_id:  Optional[str] = None,
        fecha:       Optional[date] = None,
        fuentes:     Optional[list] = None,
        datos:       Optional[dict] = None,
    ):
        self.tipo          = tipo
        self.nivel         = nivel
        self.prioridad     = NIVELES.get(nivel, 0)
        self.mensaje       = mensaje
        self.recomendacion = recomendacion
        self.apiario_id    = apiario_id
        self.colmena_id    = colmena_id
        self.fecha         = fecha or date.today()
        self.fuentes       = fuentes or []
        self.datos         = datos or {}
        self.emoji         = EMOJIS.get(tipo, "🐝")
        self.timestamp     = datetime.now()

    def __repr__(self):
        return f"Alerta({self.tipo}, {self.nivel}, {self.fecha})"

    def a_dict(self) -> dict:
        return {
            "timestamp":     self.timestamp.isoformat(),
            "fecha":         str(self.fecha),
            "apiario_id":    self.apiario_id,
            "colmena_id":    self.colmena_id or "",
            "tipo":          self.tipo,
            "nivel":         self.nivel,
            "prioridad":     self.prioridad,
            "mensaje":       self.mensaje,
            "recomendacion": self.recomendacion,
            "fuentes":       ", ".join(self.fuentes),
            "emoji":         self.emoji,
        }

    def texto_notificacion(self) -> str:
        """Formato para WhatsApp / app móvil."""
        return (
            f"{self.emoji} *AbejaVerde·EO — {self.nivel}*\n"
            f"{self.mensaje}\n\n"
            f"📋 *Acción recomendada:*\n{self.recomendacion}\n\n"
            f"🗓️  {self.fecha.strftime('%d %b %Y')} | {self.apiario_id}"
        )


# ── GENERADORES DE ALERTAS INDIVIDUALES ──────────────────────────────────────

def alerta_alimentacion(
    ndvi:          float,
    fase_feno:     str,
    precip_mm:     float,
    peso_cambio:   Optional[float] = None,
    apiario_id:    str = "API_SJR_01",
    fecha:         Optional[date] = None,
) -> Optional[Alerta]:
    """
    Genera alerta de alimentación cuando:
    - NDVI bajo + fuera de temporada floral
    - Precipitación en déficit
    - Pérdida de peso (si hay IoT)
    """
    señales  = []
    nivel    = "INFO"

    if ndvi < 0.48:
        señales.append(f"NDVI={ndvi:.3f} (escasez vegetal)")

    if fase_feno in ("FUERA_TEMPORADA", "FLORACION_DECLINANDO"):
        señales.append(f"fase={fase_feno}")

    if precip_mm < 75:
        señales.append(f"precipitación={precip_mm:.0f}mm")

    if peso_cambio is not None and peso_cambio < -3:
        señales.append(f"peso_cambio={peso_cambio:+.1f}%")

    if len(señales) == 0:
        return None
    elif len(señales) == 1:
        nivel = "MEDIA"
    elif len(señales) == 2:
        nivel = "ALTA"
    else:
        nivel = "URGENTE"

    señales_txt = " | ".join(señales)
    mensaje = (
        f"Señales de escasez de néctar detectadas: {señales_txt}. "
        f"Evalúe si sus colmenas necesitan alimentación suplementaria."
    )
    recomendacion = (
        "Visite la colmena y revise las reservas de miel. "
        "Si el peso está por debajo del mínimo (15 kg), inicie "
        "alimentación con jarabe 2:1 (2 partes azúcar, 1 parte agua). "
        "Ofrezca 1-2 litros por colmena cada 2-3 días hasta que mejore el NDVI."
    )

    return Alerta(
        tipo          = "ALIMENTACION",
        nivel         = nivel,
        mensaje       = mensaje,
        recomendacion = recomendacion,
        apiario_id    = apiario_id,
        fecha         = fecha,
        fuentes       = ["Sentinel-2", "ERA5"] + (["IoT"] if peso_cambio else []),
        datos         = {"ndvi": ndvi, "precip_mm": precip_mm, "señales": len(señales)},
    )


def alerta_no_alimentar(
    ndvi:       float,
    fase_feno:  str,
    apiario_id: str = "API_SJR_01",
    fecha:      Optional[date] = None,
) -> Optional[Alerta]:
    """Alerta positiva: floración activa, NO alimente."""
    if ndvi >= 0.65 and fase_feno in ("FLORACION_ACTIVA_CRECIENTE", "FLORACION_ACTIVA"):
        return Alerta(
            tipo          = "NO_ALIMENTAR",
            nivel         = "INFO",
            mensaje       = (
                f"Floración activa detectada. NDVI={ndvi:.3f}. "
                f"Las abejas están recolectando activamente."
            ),
            recomendacion = (
                "NO alimente — interrumpe la recolección natural y puede "
                "contaminar la miel. Verifique que haya espacio suficiente "
                "en las alzas (cuadros < 80% llenos). Si están llenos, agregue alzas."
            ),
            apiario_id = apiario_id,
            fecha      = fecha,
            fuentes    = ["Sentinel-2"],
            datos      = {"ndvi": ndvi, "fase": fase_feno},
        )
    return None


def alerta_agua(
    pct_agua:   float,
    precip_mm:  float,
    n_colmenas: int  = 1,
    apiario_id: str  = "API_SJR_01",
    fecha:      Optional[date] = None,
) -> Optional[Alerta]:
    """Alerta de escasez de agua superficial."""
    señales = []

    if pct_agua < 20:
        señales.append(f"agua={pct_agua:.0f}% del histórico")
    elif pct_agua < 50:
        señales.append(f"agua reducida={pct_agua:.0f}%")

    if precip_mm < 50:
        señales.append(f"precipitación={precip_mm:.0f}mm")

    if not señales:
        return None

    litros = n_colmenas * 1.0
    nivel  = "URGENTE" if (pct_agua < 20 and precip_mm < 50) else \
             "ALTA"    if pct_agua < 20 else "MEDIA"

    return Alerta(
        tipo          = "AGUA",
        nivel         = nivel,
        mensaje       = (
            f"Posible escasez de agua cerca del apiario: "
            f"{' | '.join(señales)}."
        ),
        recomendacion = (
            f"Verifique que cada colmena tenga agua fresca accesible a menos de 500m. "
            f"Sus {n_colmenas} colmenas necesitan {litros:.0f} L/día mínimo. "
            f"Si no hay fuentes naturales activas, instale bebedero artificial "
            f"a menos de 200m del apiario."
        ),
        apiario_id = apiario_id,
        fecha      = fecha,
        fuentes    = ["Water Bodies", "ERA5"],
        datos      = {"pct_agua": pct_agua, "precip_mm": precip_mm},
    )


def alerta_visita_reina(
    temp_colmena: float,
    hr_interna:   Optional[float] = None,
    apiario_id:   str = "API_SJR_01",
    colmena_id:   str = "C01",
    fecha:        Optional[date] = None,
) -> Optional[Alerta]:
    """Alerta de temperatura interna anómala — posible problema de reina."""
    fuera_rango = temp_colmena < 33.0 or temp_colmena > 37.0
    muy_fuera   = temp_colmena < 30.0 or temp_colmena > 40.0

    if not fuera_rango:
        return None

    nivel = "URGENTE" if muy_fuera else "ALTA"
    señal = f"T°={temp_colmena:.1f}°C (óptimo 34.5–35.5°C)"
    if hr_interna and hr_interna > 75:
        señal += f" | HR={hr_interna:.0f}%"

    return Alerta(
        tipo          = "VISITA_REINA",
        nivel         = nivel,
        mensaje       = (
            f"Colmena {colmena_id} no mantiene homeostasis: {señal}. "
            f"Posible problema de reina, colonia pequeña o enfermedad."
        ),
        recomendacion = (
            f"Visite la colmena {colmena_id} en las próximas 24–48 horas. "
            f"Revise: postura de la reina, tamaño de la población, "
            f"presencia de cría uniforme, signos de loque o varroasis. "
            f"Si la reina está ausente, evalúe introducción de reina nueva."
        ),
        apiario_id = apiario_id,
        colmena_id = colmena_id,
        fecha      = fecha,
        fuentes    = ["IoT"],
        datos      = {"temp_colmena": temp_colmena, "hr_interna": hr_interna},
    )


def alerta_reubicacion(
    ndvi:       float,
    fase_feno:  str,
    n_dias_bajo: int = 0,
    apiario_id: str  = "API_SJR_01",
    fecha:      Optional[date] = None,
) -> Optional[Alerta]:
    """Alerta de reubicación cuando la zona lleva mucho tiempo sin floración."""
    if ndvi >= 0.40 or fase_feno not in ("FUERA_TEMPORADA",):
        return None
    if n_dias_bajo < 30:
        return None

    return Alerta(
        tipo          = "REUBICACION",
        nivel         = "ALTA",
        mensaje       = (
            f"Zona de pastoreo agotada por más de {n_dias_bajo} días. "
            f"NDVI={ndvi:.3f} — vegetación muy baja. "
            f"Fuera de temporada floral activa."
        ),
        recomendacion = (
            "Evalúe trasladar el apiario a una zona con mayor NDVI. "
            "En el dashboard encontrará el mapa con las zonas de mayor "
            "actividad vegetal en un radio de 10 km. "
            "Ideal trasladar a zona con NDVI > 0.55 y cerca de fuentes de agua."
        ),
        apiario_id = apiario_id,
        fecha      = fecha,
        fuentes    = ["Sentinel-2"],
        datos      = {"ndvi": ndvi, "dias_bajo": n_dias_bajo},
    )


def alerta_ola_calor(
    tsup_anomalia: float,
    temp_colmena:  Optional[float] = None,
    apiario_id:    str = "API_SJR_01",
    fecha:         Optional[date] = None,
) -> Optional[Alerta]:
    """Alerta de ola de calor cuando ERA5 + IoT confirman temperatura alta."""
    if tsup_anomalia < 1.5:
        return None

    fuentes = ["ERA5"]
    señal   = f"T°superficial anómala (z={tsup_anomalia:+.1f}σ)"

    if temp_colmena and temp_colmena > 36.5:
        señal  += f" | T°colmena={temp_colmena:.1f}°C"
        fuentes.append("IoT")
        nivel   = "URGENTE"
    else:
        nivel   = "ALTA"

    return Alerta(
        tipo          = "OLA_CALOR",
        nivel         = nivel,
        mensaje       = f"Temperatura alta anómala detectada: {señal}.",
        recomendacion = (
            "Garantice sombra y ventilación adecuada en las colmenas. "
            "Asegure acceso a agua fresca en abundancia. "
            "Si la temperatura interna supera 37°C, abra la piquera al máximo "
            "y considere agregar sombra artificial sobre las colmenas."
        ),
        apiario_id = apiario_id,
        fecha      = fecha,
        fuentes    = fuentes,
        datos      = {"tsup_anomalia": tsup_anomalia, "temp_colmena": temp_colmena},
    )


# ── MOTOR PRINCIPAL ───────────────────────────────────────────────────────────

def generar_alertas(
    fecha:           date,
    ndvi:            float,
    fase_feno:       str,
    precip_mm:       float,
    pct_agua:        float,
    tsup_anomalia:   float          = 0.0,
    temp_colmena:    Optional[float] = None,
    hr_interna:      Optional[float] = None,
    peso_cambio:     Optional[float] = None,
    n_dias_ndvi_bajo: int            = 0,
    n_colmenas:      int            = 1,
    apiario_id:      str            = "API_SJR_01",
    colmena_id:      str            = "C01",
    modo:            str            = MODO_SENTINEL,
) -> list[Alerta]:
    """
    Genera todas las alertas aplicables para una fecha y apiario dados.

    Args:
        modo: TIEMPO_REAL (IoT c/15min) | SENTINEL (c/5días) | MENSUAL (c/mes)
              Filtra qué tipos de alerta son relevantes según la frecuencia.

    Aplica la lógica de doble evidencia del plan V2:
        Una sola señal → aviso (INFO/MEDIA)
        Dos señales convergentes → alerta (ALTA)
        Tres o más señales → urgente (URGENTE)

    Returns:
        Lista de alertas ordenadas por prioridad descendente
    """
    tipos_activos = ALERTAS_POR_MODO.get(modo, list(EMOJIS.keys()))
    alertas = []

    # 1. Alerta de alimentación (Sentinel + Mensual)
    if "ALIMENTACION" in tipos_activos:
        a = alerta_alimentacion(
            ndvi, fase_feno, precip_mm, peso_cambio, apiario_id, fecha
        )
        if a:
            alertas.append(a)

    # 2. Alerta positiva: no alimentar (Sentinel)
    if "NO_ALIMENTAR" in tipos_activos:
        a = alerta_no_alimentar(ndvi, fase_feno, apiario_id, fecha)
        if a:
            alertas.append(a)

    # 3. Alerta de agua (Sentinel)
    if "AGUA" in tipos_activos:
        a = alerta_agua(pct_agua, precip_mm, n_colmenas, apiario_id, fecha)
        if a:
            alertas.append(a)

    # 4. Alerta de visita a reina — solo Tiempo Real (IoT)
    if "VISITA_REINA" in tipos_activos and temp_colmena is not None:
        a = alerta_visita_reina(
            temp_colmena, hr_interna, apiario_id, colmena_id, fecha
        )
        if a:
            alertas.append(a)

    # 5. Alerta de reubicación (Mensual)
    if "REUBICACION" in tipos_activos:
        a = alerta_reubicacion(ndvi, fase_feno, n_dias_ndvi_bajo, apiario_id, fecha)
        if a:
            alertas.append(a)

    # 6. Alerta de ola de calor (Sentinel + Tiempo Real)
    if "OLA_CALOR" in tipos_activos:
        a = alerta_ola_calor(tsup_anomalia, temp_colmena, apiario_id, fecha)
        if a:
            alertas.append(a)

    # Ordenar por prioridad descendente
    alertas.sort(key=lambda x: x.prioridad, reverse=True)

    logger.info(
        f"🔔 [{modo}] {len(alertas)} alertas | {fecha} | {apiario_id} | "
        f"max={alertas[0].nivel if alertas else 'N/A'}"
    )
    return alertas


def generar_alertas_serie(
    df_consolidado: pd.DataFrame,
    n_colmenas:     int = 1,
    apiario_id:     str = "API_SJR_01",
) -> pd.DataFrame:
    """
    Genera alertas para toda la serie temporal consolidada.
    df_consolidado: salida de anomalias.calcular_anomalias_consolidadas()

    Returns:
        DataFrame con todas las alertas del período
    """
    todas_alertas = []

    for _, row in df_consolidado.iterrows():
        fecha = pd.Timestamp(row["fecha"]).date()

        alertas = generar_alertas(
            fecha          = fecha,
            ndvi           = row.get("ndvi", 0.5),
            fase_feno      = row.get("estado_ndvi", "DESCONOCIDA"),
            precip_mm      = row.get("precip_mm", 100),
            pct_agua       = row.get("pct_agua_activa", 80),
            tsup_anomalia  = row.get("anom_temp", 0),
            temp_colmena   = row.get("temp_interna"),
            hr_interna     = row.get("hr_interna"),
            peso_cambio    = row.get("peso_cambio_pct"),
            n_colmenas     = n_colmenas,
            apiario_id     = apiario_id,
        )

        for a in alertas:
            todas_alertas.append(a.a_dict())

    df = pd.DataFrame(todas_alertas) if todas_alertas else pd.DataFrame()
    if not df.empty:
        df = df.sort_values(["fecha", "prioridad"], ascending=[True, False])
        df = df.reset_index(drop=True)

    logger.info(f"📋 Serie de alertas: {len(df)} alertas en {len(df_consolidado)} meses")
    return df


# ── RESUMEN DE ALERTAS ────────────────────────────────────────────────────────

def resumen_alertas(df_alertas: pd.DataFrame) -> dict:
    """Resumen estadístico del log de alertas."""
    if df_alertas.empty:
        return {"total": 0}

    return {
        "total":           len(df_alertas),
        "urgentes":        int((df_alertas["nivel"] == "URGENTE").sum()),
        "altas":           int((df_alertas["nivel"] == "ALTA").sum()),
        "medias":          int((df_alertas["nivel"] == "MEDIA").sum()),
        "por_tipo":        df_alertas["tipo"].value_counts().to_dict(),
        "meses_criticos":  df_alertas[
            df_alertas["nivel"].isin(["URGENTE", "ALTA"])
        ]["fecha"].nunique(),
    }


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_log_alertas(
    df:   pd.DataFrame,
    ruta: Union[str, Path] = "data/processed/alertas_log.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 Log de alertas guardado: {ruta} ({len(df)} alertas)")
    return ruta


def cargar_log_alertas(
    ruta: Union[str, Path] = "data/processed/alertas_log.csv",
) -> pd.DataFrame:
    ruta = Path(ruta)
    if not ruta.exists():
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
    print("  AbejaVerde·EO — motor_alertas")
    print("  Apiario San Juan de Rioseco — datos reales piloto")
    print("═" * 60)

    # Escenarios reales del piloto
    escenarios = [
        {
            "nombre":       "Junio 2024 — floración máxima",
            "fecha":        date(2024, 6, 15),
            "ndvi":         0.817,
            "fase_feno":    "FLORACION_ACTIVA_CRECIENTE",
            "precip_mm":    310,
            "pct_agua":     105,
            "tsup_anomalia": -0.3,
            "temp_colmena": 35.1,
            "hr_interna":   52.0,
            "peso_cambio":  +4.5,
        },
        {
            "nombre":       "Enero 2025 — escasez real",
            "fecha":        date(2025, 1, 15),
            "ndvi":         0.437,
            "fase_feno":    "FUERA_TEMPORADA",
            "precip_mm":    38,
            "pct_agua":     14.8,
            "tsup_anomalia": 0.4,
        },
        {
            "nombre":       "Abril 2025 — Fenómeno del Niño",
            "fecha":        date(2025, 4, 10),
            "ndvi":         0.379,
            "fase_feno":    "FUERA_TEMPORADA",
            "precip_mm":    22,
            "pct_agua":     8.6,
            "tsup_anomalia": 1.8,
            "temp_colmena": 33.8,
            "hr_interna":   71.0,
            "peso_cambio":  -6.2,
            "n_dias_ndvi_bajo": 45,
        },
    ]

    for esc in escenarios:
        print(f"\n{'─'*55}")
        print(f"📅 {esc['nombre']}")
        alertas = generar_alertas(
            fecha            = esc["fecha"],
            ndvi             = esc["ndvi"],
            fase_feno        = esc["fase_feno"],
            precip_mm        = esc["precip_mm"],
            pct_agua         = esc["pct_agua"],
            tsup_anomalia    = esc.get("tsup_anomalia", 0),
            temp_colmena     = esc.get("temp_colmena"),
            hr_interna       = esc.get("hr_interna"),
            peso_cambio      = esc.get("peso_cambio"),
            n_dias_ndvi_bajo = esc.get("n_dias_ndvi_bajo", 0),
            n_colmenas       = 10,
        )

        if not alertas:
            print("   ✅ Sin alertas — condiciones normales")
        else:
            for a in alertas:
                print(f"\n   {a.emoji} [{a.nivel}] {a.tipo}")
                print(f"   {a.mensaje[:75]}...")
                print(f"   → {a.recomendacion[:75]}...")

    # Notificación WhatsApp para el peor escenario
    print(f"\n{'═'*55}")
    print("📱 Ejemplo notificación WhatsApp — Abril 2025:")
    print("─" * 55)
    alertas_niño = generar_alertas(
        fecha=date(2025,4,10), ndvi=0.379,
        fase_feno="FUERA_TEMPORADA", precip_mm=22,
        pct_agua=8.6, tsup_anomalia=1.8,
        temp_colmena=33.8, hr_interna=71.0,
        peso_cambio=-6.2, n_dias_ndvi_bajo=45, n_colmenas=10,
    )
    if alertas_niño:
        print(alertas_niño[0].texto_notificacion())
