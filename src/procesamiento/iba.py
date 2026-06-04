"""
AbejaVerde·EO — Módulo: iba
=============================
IBA — Índice de Bioindicación Apícola
AbejaVerde·EO — sistema de alertas apícolas con inteligencia satelital

0 = Sin riesgo | 100 = Riesgo máximo

El IBA captura lo que ningún satélite puede ver:
las observaciones directas del apicultor en campo.

Variables:
    1. Entrada de polen    — actividad de forrajeo (peso 50%)
    2. Disponibilidad agua — fuentes cercanas al apiario (peso 25%)
    3. Población colmena   — cantidad de abejas y marcos con cría (peso 25%)

Pesos calibrables — use el simulador para encontrar el modelo
más parsimonioso para su territorio.

Escala:
    0-25  Bajo
    26-50 Moderado
    51-75 Alto
    76-100 Crítico

Integración con ITA:
    ITA alto + IBA bajo  → estrés ambiental, colmena aún aguanta
    ITA bajo + IBA alto  → problema interno, no explicado por satélite
    ITA alto + IBA alto  → crisis confirmada por dos fuentes independientes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Optional, Union

import pandas as pd

logger = logging.getLogger(__name__)

# ── PESOS POR DEFECTO (propuesta Arelys Camacho) ─────────────────────────────
PESO_POLEN_DEFAULT  = 0.50
PESO_AGUA_DEFAULT   = 0.25
PESO_POB_DEFAULT    = 0.25

# ── ESCALAS DE OBSERVACIÓN ────────────────────────────────────────────────────

class EntradaPolen(IntEnum):
    """Observación de entrada de abejas con polen en la piquera."""
    ALTA     = 0    # abundante — sin riesgo
    MODERADA = 25
    BAJA     = 50
    MUY_BAJA = 75
    NULA     = 100  # cero abejas entrando con polen


class DisponibilidadAgua(IntEnum):
    """Estado de las fuentes de agua cercanas al apiario (< 500m)."""
    ADECUADA = 0    # fuentes activas y accesibles
    LIMITADA = 50   # nivel bajo o acceso difícil
    AUSENTE  = 100  # sin agua disponible


class PoblacionColmena(IntEnum):
    """Estimación visual de la población en la colmena."""
    BASTANTE  = 0    # colonia muy fuerte
    ALTA      = 25
    MODERADA  = 50
    BAJA      = 75
    MUY_BAJA  = 100


# Mapeo de texto a valor para facilidad de uso
MAPA_TEXTO_POLEN = {
    "alta": EntradaPolen.ALTA, "abundante": EntradaPolen.ALTA,
    "moderada": EntradaPolen.MODERADA, "media": EntradaPolen.MODERADA,
    "baja": EntradaPolen.BAJA,
    "muy baja": EntradaPolen.MUY_BAJA, "muy_baja": EntradaPolen.MUY_BAJA,
    "nula": EntradaPolen.NULA, "cero": EntradaPolen.NULA, "sin": EntradaPolen.NULA,
}

MAPA_TEXTO_AGUA = {
    "adecuada": DisponibilidadAgua.ADECUADA, "buena": DisponibilidadAgua.ADECUADA,
    "normal": DisponibilidadAgua.ADECUADA,
    "limitada": DisponibilidadAgua.LIMITADA, "baja": DisponibilidadAgua.LIMITADA,
    "ausente": DisponibilidadAgua.AUSENTE, "seca": DisponibilidadAgua.AUSENTE,
    "sin": DisponibilidadAgua.AUSENTE,
}

MAPA_TEXTO_POB = {
    "bastante": PoblacionColmena.BASTANTE, "muy alta": PoblacionColmena.BASTANTE,
    "alta": PoblacionColmena.ALTA,
    "moderada": PoblacionColmena.MODERADA, "media": PoblacionColmena.MODERADA,
    "baja": PoblacionColmena.BAJA,
    "muy baja": PoblacionColmena.MUY_BAJA, "muy_baja": PoblacionColmena.MUY_BAJA,
}


# ── CLASE RESULTADO ───────────────────────────────────────────────────────────

@dataclass
class ResultadoIBA:
    """Resultado del cálculo del IBA."""
    iba:            float
    nivel:          str
    r_polen:        int
    r_agua:         int
    r_poblacion:    int
    peso_polen:     float
    peso_agua:      float
    peso_poblacion: float
    notas:          str = ""
    interpretacion: str = field(default="")
    colmena_id:     str = "C01"

    def __post_init__(self):
        if not self.interpretacion:
            self.interpretacion = _interpretar_iba(
                self.iba, self.r_polen, self.r_agua, self.r_poblacion
            )

    @property
    def es_critico(self) -> bool:
        return self.iba > 75

    def a_dict(self) -> dict:
        return {
            "iba":            round(self.iba, 1),
            "nivel":          self.nivel,
            "r_polen":        self.r_polen,
            "r_agua":         self.r_agua,
            "r_poblacion":    self.r_poblacion,
            "interpretacion": self.interpretacion,
            "colmena_id":     self.colmena_id,
        }


def _nivel_iba(iba: float) -> str:
    if iba <= 25: return "Bajo"
    if iba <= 50: return "Moderado"
    if iba <= 75: return "Alto"
    return "Crítico"


def _interpretar_iba(iba: float, r_polen: int, r_agua: int, r_pob: int) -> str:
    if iba <= 25:
        return "La colmena muestra indicadores biológicos saludables. Monitoreo rutinario."
    drivers = []
    if r_polen >= 75: drivers.append("entrada de polen muy baja o nula")
    if r_agua  >= 50: drivers.append("agua limitada o ausente")
    if r_pob   >= 75: drivers.append("población baja")
    if iba <= 50:
        txt = " y ".join(drivers) if drivers else "señales de estrés moderado"
        return f"Riesgo moderado — {txt}. Planifique visita y evalúe intervención."
    if iba <= 75:
        txt = " y ".join(drivers) if drivers else "múltiples señales de estrés"
        return f"Riesgo alto — {txt}. Visite la colmena esta semana."
    txt = " y ".join(drivers) if drivers else "múltiples variables críticas"
    return f"CRÍTICO — {txt}. Intervención urgente necesaria."


# ── FUNCIÓN PRINCIPAL ─────────────────────────────────────────────────────────

def calcular_iba(
    entrada_polen:   Union[int, str, EntradaPolen],
    agua:            Union[int, str, DisponibilidadAgua],
    poblacion:       Union[int, str, PoblacionColmena],
    peso_polen:      float = PESO_POLEN_DEFAULT,
    peso_agua:       float = PESO_AGUA_DEFAULT,
    peso_poblacion:  float = PESO_POB_DEFAULT,
    colmena_id:      str   = "C01",
    notas:           str   = "",
) -> ResultadoIBA:
    """
    Calcula el IBA — Índice de Bioindicación Apícola.

    Args:
        entrada_polen:  valor o texto ("alta", "moderada", "baja", "muy baja", "nula")
        agua:           valor o texto ("adecuada", "limitada", "ausente")
        poblacion:      valor o texto ("bastante", "alta", "moderada", "baja", "muy baja")
        peso_*:         pesos (deben sumar 1.0)
        colmena_id:     identificador de la colmena
        notas:          observaciones libres del apicultor

    Returns:
        ResultadoIBA con el score y la interpretación
    """
    # Convertir texto a valor si es necesario
    r_polen = _resolver_valor(entrada_polen, MAPA_TEXTO_POLEN, EntradaPolen.MODERADA)
    r_agua  = _resolver_valor(agua,          MAPA_TEXTO_AGUA,  DisponibilidadAgua.ADECUADA)
    r_pob   = _resolver_valor(poblacion,     MAPA_TEXTO_POB,   PoblacionColmena.MODERADA)

    # Validar pesos
    suma = peso_polen + peso_agua + peso_poblacion
    if abs(suma - 1.0) > 0.01:
        logger.warning(f"Pesos IBA no suman 1.0 ({suma:.2f}) — normalizando")
        peso_polen     /= suma
        peso_agua      /= suma
        peso_poblacion /= suma

    iba = (r_polen * peso_polen) + (r_agua * peso_agua) + (r_pob * peso_poblacion)
    iba = round(min(100, max(0, iba)), 1)

    return ResultadoIBA(
        iba=iba, nivel=_nivel_iba(iba),
        r_polen=int(r_polen), r_agua=int(r_agua), r_poblacion=int(r_pob),
        peso_polen=peso_polen, peso_agua=peso_agua, peso_poblacion=peso_poblacion,
        colmena_id=colmena_id, notas=notas,
    )


def _resolver_valor(valor, mapa: dict, defecto):
    """Convierte texto o enum a valor entero."""
    if isinstance(valor, str):
        return int(mapa.get(valor.lower(), defecto))
    if isinstance(valor, (int, float)):
        return int(valor)
    return int(valor)


# ── COMPARACIÓN ITA vs IBA ────────────────────────────────────────────────────

def comparar_ita_iba(
    resultado_ita,
    resultado_iba: ResultadoIBA,
) -> dict:
    """
    Compara el ITA (satelital) con el IBA (campo) y genera la
    interpretación combinada para el apicultor.

    Casos:
        ITA > IBA + 20 → el paisaje está peor que la colmena (alerta preventiva)
        IBA > ITA + 20 → la colmena está peor de lo que el satélite ve (revisar)
        Ambos altos    → crisis confirmada por dos fuentes
        Ambos bajos    → condiciones favorables
    """
    ita = resultado_ita.ita if hasattr(resultado_ita, 'ita') else float(resultado_ita)
    iba = resultado_iba.iba
    diff = ita - iba

    if ita <= 25 and iba <= 25:
        estado    = "FAVORABLE"
        accion    = "Sin acción urgente. Monitoreo rutinario."
        alerta    = False

    elif diff > 20:
        estado    = "ALERTA_PREVENTIVA"
        accion    = (
            f"El paisaje muestra más estrés (ITA={ita:.0f}) que la colmena (IBA={iba:.0f}). "
            f"La colmena todavía aguanta, pero el riesgo ambiental puede impactar pronto. "
            f"Planifique visita en los próximos 5 días."
        )
        alerta    = True

    elif diff < -20:
        estado    = "PROBLEMA_INTERNO"
        accion    = (
            f"La colmena muestra más estrés (IBA={iba:.0f}) que el entorno satelital (ITA={ita:.0f}). "
            f"Posible problema interno: revisar reina, varroa, o fuente de contaminación local. "
            f"El satélite no explica este nivel de estrés."
        )
        alerta    = True

    elif ita > 50 and iba > 50:
        estado    = "CRISIS_CONFIRMADA"
        accion    = (
            f"Ambos índices elevados: ITA={ita:.0f}, IBA={iba:.0f}. "
            f"Crisis confirmada por satélite y por observación en campo. "
            f"Intervención urgente: alimente, asegure agua, visite hoy."
        )
        alerta    = True

    else:
        estado    = "ATENCION"
        accion    = (
            f"ITA={ita:.0f} ({resultado_ita.nivel}), IBA={iba:.0f} ({resultado_iba.nivel}). "
            f"Monitoree con mayor frecuencia."
        )
        alerta    = ita > 33 or iba > 33

    return {
        "ita":      ita,
        "iba":      iba,
        "estado":   estado,
        "accion":   accion,
        "alerta":   alerta,
        "diferencia": round(diff, 1),
    }


# ── PERSISTENCIA ──────────────────────────────────────────────────────────────

def guardar_observaciones_iba(
    observaciones: list[dict],
    ruta: Union[str, Path] = "data/processed/observaciones_iba.csv",
) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(observaciones)
    if ruta.exists():
        df_prev = pd.read_csv(ruta)
        df = pd.concat([df_prev, df], ignore_index=True)
    df.to_csv(ruta, index=False)
    logger.info(f"💾 Observaciones IBA guardadas: {ruta}")
    return ruta


# ── DEMO ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")

    print("═" * 60)
    print("  AbejaVerde·EO — IBA (Índice de Bioindicación Apícola)")
    print("  AbejaVerde·EO · San Juan de Rioseco")
    print("═" * 60)

    # Escenarios reales del apiario
    escenarios = [
        ("Junio 2024 — floración activa",  "alta",     "adecuada", "bastante"),
        ("Enero 2025 — escasez",           "baja",     "limitada", "moderada"),
        ("Abril 2025 — Fenómeno del Niño", "muy baja", "ausente",  "baja"),
        ("Mayo 2026 — situación actual",   "moderada", "limitada", "alta"),
        ("Dic 2025 — peor mes histórico",  "nula",     "ausente",  "baja"),
    ]

    print(f"\n{'Escenario':35s} {'Polen':7s} {'Agua':7s} {'Pob':5s} {'IBA':5s} {'Nivel':10s}")
    print("-" * 75)

    for nombre, polen, agua, pob in escenarios:
        r = calcular_iba(polonia=polen, agua=agua, poblacion=pob) \
            if False else calcular_iba(
                entrada_polen=polen, agua=agua, poblacion=pob
            )
        print(f"{nombre:35s} {r.r_polen:6d}  {r.r_agua:6d}  {r.r_poblacion:4d}  "
              f"{r.iba:5.1f}  {r.nivel:10s}")

    # Comparación ITA vs IBA — Abril 2025
    print("\n📊 Comparación ITA vs IBA — Abril 2025 (Fenómeno del Niño):")
    from src.procesamiento.ita import calcular_ita, _linea_base_sjr_default
    lb   = _linea_base_sjr_default()
    r_ita = calcular_ita(0.379, lb[4]["ndvi_media"], 0.178, lb[4]["ndmi_media"], 1.8)
    r_iba = calcular_iba("muy baja", "ausente", "baja")
    comp  = comparar_ita_iba(r_ita, r_iba)
    print(f"   ITA: {comp['ita']:.0f} ({r_ita.nivel})")
    print(f"   IBA: {comp['iba']:.0f} ({r_iba.nivel})")
    print(f"   Estado: {comp['estado']}")
    print(f"   → {comp['accion']}")

    # Simulación de pesos alternativos
    print("\n🔬 Simulación de pesos — ¿cambia el resultado con 40-30-30?")
    r2 = calcular_iba("muy baja", "ausente", "baja",
                      peso_polen=0.40, peso_agua=0.30, peso_poblacion=0.30)
    print(f"   Pesos 50-25-25: IBA = {calcular_iba('muy baja','ausente','baja').iba}")
    print(f"   Pesos 40-30-30: IBA = {r2.iba}")
    print(f"   Diferencia: {abs(calcular_iba('muy baja','ausente','baja').iba - r2.iba):.1f} puntos")
    print("   (diferencia pequeña = modelo parsimonioso y robusto)")
