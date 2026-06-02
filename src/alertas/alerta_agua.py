"""
AbejaVerde·EO — alerta_agua
Wrapper especializado para la alerta de agua.
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from src.alertas.motor_alertas import alerta_agua, Alerta
from src.procesamiento.agua_disponibilidad import recomendar_bebedero


def evaluar_agua_completo(
    pct_agua:    float,
    precip_mm:   float,
    n_colmenas:  int  = 1,
    apiario_id:  str  = "API_SJR_01",
    fecha:       Optional[date] = None,
) -> dict:
    """
    Evaluación completa de agua: alerta + recomendación de bebedero.
    """
    alerta = alerta_agua(pct_agua, precip_mm, n_colmenas, apiario_id, fecha)
    bebedero = recomendar_bebedero(pct_agua, n_colmenas)

    if alerta is None:
        return {
            "hay_alerta":       False,
            "necesita_bebedero": False,
            "estado":           "NORMAL",
            "mensaje":          "Agua suficiente en la zona.",
        }

    return {
        "hay_alerta":           True,
        "nivel":                alerta.nivel,
        "mensaje":              alerta.mensaje,
        "necesita_bebedero":    bebedero["necesita_bebedero"],
        "urgencia_bebedero":    bebedero.get("urgencia"),
        "capacidad_litros":     bebedero.get("capacidad_litros"),
        "distancia_max_m":      bebedero.get("distancia_max_m"),
        "recomendacion":        bebedero["recomendacion"],
    }


if __name__ == "__main__":
    resultado = evaluar_agua_completo(pct_agua=8.6, precip_mm=22, n_colmenas=10)
    print("Abril 2025 — Evaluación de agua:")
    for k, v in resultado.items():
        print(f"  {k}: {v}")
