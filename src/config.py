"""
AbejaVerde·EO — Configuración central del proyecto
Todas las constantes, coordenadas y umbrales en un solo lugar.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Apiario piloto ────────────────────────────────────────────────────────────
APIARIO = {
    "nombre": os.getenv("APIARIO_NOMBRE", "San_Juan_de_Rioseco_Piloto"),
    "lat": float(os.getenv("APIARIO_LAT", 4.875)),
    "lon": float(os.getenv("APIARIO_LON", -74.635)),
    "municipio": "San Juan de Rioseco",
    "departamento": "Cundinamarca",
    "pais": "Colombia",
}

# ─── Radios de análisis ────────────────────────────────────────────────────────
RADIO_AGUA_M = int(os.getenv("RADIO_AGUA_M", 500))          # Para alerta de agua
RADIO_NDVI_M = 1000                                          # Para cálculo NDVI
RADIO_REUBICACION_KM = int(os.getenv("RADIO_REUBICACION_KM", 10))

# ─── Credenciales Copernicus ───────────────────────────────────────────────────
CDSE_USERNAME = os.getenv("CDSE_USERNAME", "")
CDSE_PASSWORD = os.getenv("CDSE_PASSWORD", "")
CDS_API_KEY   = os.getenv("CDS_API_KEY", "")

# ─── Período histórico de referencia ──────────────────────────────────────────
PERIODO_LINEA_BASE = {
    "inicio": "2022-01-01",
    "fin":    "2024-12-31",
}

# ─── Umbrales biológicos de la colmena ────────────────────────────────────────
COLMENA = {
    "temp_optima_min":  34.5,   # °C — mínimo homeostasis
    "temp_optima_max":  35.5,   # °C — máximo homeostasis
    "temp_alerta_baja": 34.0,   # °C — alerta visita reina
    "temp_alerta_alta": 37.0,   # °C — alerta crítica
    "hr_optima_min":    40.0,   # % — mínimo humedad relativa interna
    "hr_optima_max":    65.0,   # % — máximo humedad relativa interna
    "hr_alerta_alta":   75.0,   # % — alerta humedad elevada
    "agua_litros_dia":  1.0,    # L/colmena/día — necesidad mínima de agua
}

# ─── Umbrales NDVI ────────────────────────────────────────────────────────────
NDVI = {
    "floración_activa":     0.45,   # NDVI > 0.45 → floración buena
    "floración_baja":       0.30,   # NDVI < 0.30 → zona sin floración
    "caida_alerta_pct":    -0.15,   # Caída > 15% vs histórico → alerta
    "caida_reubicacion_pct": -0.20, # Caída > 20% → evaluar traslado
    "dias_alerta_reubicacion": 10,  # Días sostenidos bajo umbral para alertar
}

# ─── Umbrales de precipitación ────────────────────────────────────────────────
PRECIPITACION = {
    "deficit_alerta_pct":     -0.20,  # Déficit > 20% vs histórico → alerta
    "deficit_agua_pct":       -0.40,  # Déficit > 40% → alerta de agua
    "ventana_dias":            15,    # Días de acumulación para cálculo
}

# ─── Umbrales de agua superficial ─────────────────────────────────────────────
AGUA = {
    "cobertura_alerta_pct":   0.50,   # < 50% del histórico → alerta roja
    "cobertura_monitoreo_pct": 0.80,  # < 80% del histórico → alerta amarilla
}

# ─── Pesos del IRA ────────────────────────────────────────────────────────────
IRA_PESOS = {
    "ndvi":       0.25,
    "fenologia":  0.15,
    "tsup":       0.20,
    "tcolmena":   0.20,
    "hr":         0.08,
    "precip":     0.07,
    "agua":       0.05,
}

# ─── Clasificación de riesgo IRA ──────────────────────────────────────────────
IRA_UMBRALES = {
    "bajo":  (0,  33),   # 🟢
    "medio": (34, 66),   # 🟡
    "alto":  (67, 100),  # 🔴
}
