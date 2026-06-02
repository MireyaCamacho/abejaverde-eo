"""
AbejaVerde·EO — alerta_alimentacion
Wrapper especializado para la alerta de alimentación.
Importa la lógica central desde motor_alertas.
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from src.alertas.motor_alertas import alerta_alimentacion, Alerta


def evaluar_necesidad_alimentacion(
    ndvi:         float,
    fase_feno:    str,
    precip_mm:    float,
    peso_cambio:  Optional[float] = None,
    umbral_ndvi:  float = 0.52,
    apiario_id:   str   = "API_SJR_01",
    fecha:        Optional[date] = None,
) -> dict:
    """
    Evalúa si la colmena necesita alimentación y qué tipo.

    Returns:
        dict con: necesita_alimentar, tipo_alimento, cantidad_litros,
                  frecuencia_dias, justificacion
    """
    alerta = alerta_alimentacion(
        ndvi, fase_feno, precip_mm, peso_cambio, apiario_id, fecha
    )

    if alerta is None:
        return {
            "necesita_alimentar": False,
            "justificacion":      "Condiciones favorables — sin necesidad de alimentar.",
        }

    # Tipo de alimento según la temporada
    if fase_feno in ("FUERA_TEMPORADA",):
        tipo     = "jarabe 2:1 (estimulante)"
        cantidad = 1.5   # litros por colmena
        frecuencia = 3   # cada 3 días
    elif alerta.nivel in ("URGENTE", "ALTA"):
        tipo     = "jarabe 1:1 (hidratante)"
        cantidad = 2.0
        frecuencia = 2
    else:
        tipo     = "jarabe 1:1 o candy"
        cantidad = 1.0
        frecuencia = 5

    return {
        "necesita_alimentar": True,
        "nivel_urgencia":     alerta.nivel,
        "tipo_alimento":      tipo,
        "cantidad_litros":    cantidad,
        "frecuencia_dias":    frecuencia,
        "justificacion":      alerta.mensaje,
        "instruccion":        (
            f"Ofrezca {cantidad}L de {tipo} por colmena cada {frecuencia} días. "
            f"Revise que el alimentador no tenga hongos. "
            f"Continúe hasta que el NDVI supere 0.55."
        ),
    }


if __name__ == "__main__":
    # Escenario: Enero 2025
    resultado = evaluar_necesidad_alimentacion(
        ndvi=0.437, fase_feno="FUERA_TEMPORADA",
        precip_mm=38, peso_cambio=-4.2,
    )
    print("Enero 2025 — Evaluación de alimentación:")
    for k, v in resultado.items():
        print(f"  {k}: {v}")
