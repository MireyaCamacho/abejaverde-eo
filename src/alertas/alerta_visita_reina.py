"""
AbejaVerde·EO — alerta_visita_reina
Wrapper especializado para alertas de salud de la colmena (IoT).
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from src.alertas.motor_alertas import alerta_visita_reina, Alerta


CHECKLIST_VISITA = [
    "Buscar la reina o confirmar presencia de huevos frescos (<3 días)",
    "Evaluar patrón de postura: ¿es uniforme o tiene huecos?",
    "Contar marcos de cría: ¿hay al menos 4-6 marcos con cría?",
    "Verificar presencia de cría sana (larvas brillantes en C, no oscuras)",
    "Revisar nivel de varroasis: contar ácaros en 100 abejas",
    "Evaluar reservas de miel y polen (mínimo 2 marcos de cada uno)",
    "Observar comportamiento: ¿abejas agresivas, aleteo excesivo, olor inusual?",
]


def evaluar_salud_colmena(
    temp_colmena:  float,
    hr_interna:    Optional[float] = None,
    horas_anormal: int = 1,
    colmena_id:    str = "C01",
    apiario_id:    str = "API_SJR_01",
    fecha:         Optional[date] = None,
) -> dict:
    """
    Evaluación completa de salud de la colmena basada en IoT.
    """
    alerta = alerta_visita_reina(
        temp_colmena, hr_interna, apiario_id, colmena_id, fecha
    )

    optima = 34.5 <= temp_colmena <= 35.5
    estado = "OPTIMA" if optima else \
             "BAJA"   if temp_colmena < 34.5 else "ALTA"

    resultado = {
        "colmena_id":    colmena_id,
        "temp_colmena":  temp_colmena,
        "estado_temp":   estado,
        "hr_interna":    hr_interna,
        "hay_alerta":    alerta is not None,
    }

    if alerta:
        resultado.update({
            "nivel":        alerta.nivel,
            "mensaje":      alerta.mensaje,
            "checklist":    CHECKLIST_VISITA,
            "horas_max_espera": 24 if alerta.nivel == "URGENTE" else 48,
        })
    else:
        resultado["mensaje"] = f"Temperatura {temp_colmena:.1f}°C dentro del rango normal."

    return resultado


if __name__ == "__main__":
    resultado = evaluar_salud_colmena(temp_colmena=33.8, hr_interna=71.0)
    print("Evaluación salud colmena — T°33.8°C:")
    for k, v in resultado.items():
        if k != "checklist":
            print(f"  {k}: {v}")
    if resultado.get("checklist"):
        print("  checklist:")
        for item in resultado["checklist"]:
            print(f"    ☐ {item}")
