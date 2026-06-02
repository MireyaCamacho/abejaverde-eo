"""
AbejaVerde·EO — alerta_reubicacion
Wrapper especializado para alerta de reubicación del apiario.
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from src.alertas.motor_alertas import alerta_reubicacion, Alerta


CRITERIOS_REUBICACION = {
    "ndvi_min":         0.40,   # NDVI por debajo de esto en zona actual
    "ndvi_destino_min": 0.55,   # NDVI mínimo en zona de destino
    "dias_min":         30,     # días continuos con NDVI bajo
    "radio_busqueda_km": 10,    # radio para buscar zonas mejores
}


def evaluar_reubicacion(
    ndvi_actual:    float,
    fase_feno:      str,
    n_dias_bajo:    int,
    ndvi_maximo_zona: Optional[float] = None,
    apiario_id:     str  = "API_SJR_01",
    fecha:          Optional[date] = None,
) -> dict:
    """
    Evaluación completa de necesidad de reubicación del apiario.
    """
    alerta = alerta_reubicacion(
        ndvi_actual, fase_feno, n_dias_bajo, apiario_id, fecha
    )

    resultado = {
        "recomienda_reubicar": alerta is not None,
        "ndvi_actual":         ndvi_actual,
        "dias_zona_agotada":   n_dias_bajo,
    }

    if alerta:
        resultado.update({
            "nivel":            alerta.nivel,
            "mensaje":          alerta.mensaje,
            "criterios":        CRITERIOS_REUBICACION,
            "pasos_reubicacion": [
                "Identificar zonas con NDVI > 0.55 en radio de 10 km (ver mapa en dashboard)",
                "Verificar acceso a agua en la zona de destino (< 500m)",
                "Revisar que la zona de destino no tenga cultivos con agroquímicos recientes",
                "Planificar traslado nocturno (abejas en la colmena) con mínimo 3 km de distancia",
                "Mantener 2 semanas de seguimiento IoT post-traslado para confirmar adaptación",
            ],
        })

    return resultado


if __name__ == "__main__":
    resultado = evaluar_reubicacion(
        ndvi_actual=0.379, fase_feno="FUERA_TEMPORADA", n_dias_bajo=45
    )
    print("Abril 2025 — Evaluación reubicación:")
    for k, v in resultado.items():
        if k != "pasos_reubicacion":
            print(f"  {k}: {v}")
    if resultado.get("pasos_reubicacion"):
        print("  pasos:")
        for i, p in enumerate(resultado["pasos_reubicacion"], 1):
            print(f"    {i}. {p}")
