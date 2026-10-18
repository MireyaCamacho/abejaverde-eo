"""
AbejaVerde·EO — Envío semanal de alertas desde la bitácora
============================================================
Versión en Python del motor de Google Apps Script del MVP Acelera Lab.
Lee la bitácora (`Bitacora_Colmenas`, exportada como CSV desde Google Sheets
o AppSheet), calcula el semáforo por reglas, pide a Gemini la redacción de
la acción (opcional) y envía la alerta por WhatsApp y/o correo.

Columnas esperadas (las 11 del Manual Técnico + 5 de la v2):
    ID_Apiario, Municipio, Coordenadas_GPS, Email_Apicultor,
    NDVI_Satelite_Copernicus, Clima_Territorio, P1_Fuerza_Poblacion,
    P2_Reservas_Miel_Polen, P3_Postura_Reina, Semaforo_IA,
    Accion_Recomendada_IA, Telefono_WhatsApp, Canal_Preferido,
    Autoriza_Datos_Ley1581, Fecha_Ultima_Alerta, Estado_Envio

Uso:
    # Solo calcular (no envía nada) — ideal para probar
    python -m src.alertas.enviar_alertas_semanales mvp_aceleralab/sheets/BD_AbejaVerde_EO_Bitacora_Colmenas.csv --simular

    # Calcular y enviar
    python -m src.alertas.enviar_alertas_semanales bitacora.csv --salida bitacora_resultado.csv
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from src.alertas.semaforo import ACCION_POR_DEFECTO, evaluar_apiario
from src.alertas.notificaciones import enviar_semaforo

logger = logging.getLogger(__name__)

COLUMNAS_V2 = ["Telefono_WhatsApp", "Canal_Preferido", "Autoriza_Datos_Ley1581",
               "Fecha_Ultima_Alerta", "Estado_Envio"]


def redactar_accion_gemini(r, modelo: str = "gemini-2.5-flash") -> str:
    """Pide a Gemini la acción recomendada. El color ya viene decidido por las reglas."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return ACCION_POR_DEFECTO[r.semaforo]
    prompt = (
        f"Actúa según la Skill abejaverde-riesgo-apicola. El semáforo YA está decidido: {r.semaforo}.\n"
        f"Datos: municipio {r.municipio}; NDVI Copernicus {r.ndvi}; clima \"{r.clima}\"; "
        f"población {r.respuestas['P1']}; reservas de miel y polen {r.respuestas['P2']}; "
        f"postura de la reina {r.respuestas['P3']}.\n"
        "Redacta UNA acción práctica para el apicultor esta semana, en español sencillo de "
        "Colombia, máximo 45 palabras, con dosis o manejo concreto. Sin saltos de línea. "
        'Devuelve JSON estricto: {"accion_recomendada": "..."}'
    )
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
            params={"key": api_key},
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}},
            timeout=30,
        )
        resp.raise_for_status()
        texto = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        accion = str(json.loads(texto).get("accion_recomendada", "")).strip()
        palabras = accion.split()
        if len(palabras) > 45:
            accion = " ".join(palabras[:45]) + "…"
        return accion or ACCION_POR_DEFECTO[r.semaforo]
    except Exception as e:  # red, cuota o JSON inválido: la alerta sale igual
        logger.warning(f"Gemini no respondió ({e}); se usa la acción por defecto")
        return ACCION_POR_DEFECTO[r.semaforo]


def procesar_bitacora(df: pd.DataFrame, simular: bool = False, usar_gemini: bool = True) -> pd.DataFrame:
    df = df.copy()
    for col in COLUMNAS_V2 + ["Semaforo_IA", "Accion_Recomendada_IA"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype("object")

    for i, fila in df.iterrows():
        if not str(fila.get("ID_Apiario", "")).strip() or str(fila.get("ID_Apiario")) == "nan":
            continue
        try:
            r = evaluar_apiario(
                fila["ID_Apiario"], fila.get("Municipio", ""), fila.get("NDVI_Satelite_Copernicus"),
                fila.get("P1_Fuerza_Poblacion"), fila.get("P2_Reservas_Miel_Polen"),
                fila.get("P3_Postura_Reina"), fila.get("Clima_Territorio", ""),
            )
        except ValueError:
            df.at[i, "Estado_Envio"] = "Sin dato NDVI válido: no se evaluó"
            continue

        if usar_gemini:
            r.accion = redactar_accion_gemini(r)
        df.at[i, "Semaforo_IA"] = r.semaforo
        df.at[i, "Accion_Recomendada_IA"] = r.accion

        if simular:
            df.at[i, "Estado_Envio"] = "Simulación: no enviado"
            continue

        autoriza = str(fila.get("Autoriza_Datos_Ley1581", "")).strip().upper() == "SI"
        res = enviar_semaforo(
            r,
            canal=fila.get("Canal_Preferido"),
            telefono=str(fila.get("Telefono_WhatsApp", "") or ""),
            email=str(fila.get("Email_Apicultor", "") or ""),
            autoriza_datos=autoriza,
        )
        df.at[i, "Estado_Envio"] = res["detalle"]
        if res["enviado"]:
            df.at[i, "Fecha_Ultima_Alerta"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    ap = argparse.ArgumentParser(description="AbejaVerde·EO — envío semanal de alertas")
    ap.add_argument("csv", help="Bitácora exportada de Google Sheets (CSV)")
    ap.add_argument("--salida", help="CSV de salida (por defecto <entrada>_resultado.csv)")
    ap.add_argument("--simular", action="store_true", help="Calcula el semáforo sin enviar nada")
    ap.add_argument("--sin-gemini", action="store_true", help="No llama a Gemini (usa acciones por defecto)")
    args = ap.parse_args()

    entrada = Path(args.csv)
    df = pd.read_csv(entrada, dtype=str, keep_default_na=False)
    out = procesar_bitacora(df, simular=args.simular, usar_gemini=not args.sin_gemini)
    salida = Path(args.salida) if args.salida else entrada.with_name(entrada.stem + "_resultado.csv")
    out.to_csv(salida, index=False, encoding="utf-8")

    for _, f in out.iterrows():
        print(f"{f['ID_Apiario']:>8} | {f['Municipio']:<20} | {f['Semaforo_IA']:<8} | {f['Estado_Envio']}")
    print(f"\nResultado guardado en {salida}")


if __name__ == "__main__":
    main()
