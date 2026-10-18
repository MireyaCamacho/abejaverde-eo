"""
AbejaVerde·EO — Pruebas del semáforo y del envío por canal.
Los casos de Pacho (ROJO) y Fusagasugá (VERDE) son los de la prueba en vivo
del Manual Técnico Acelera Lab (Proyecto 4).

Ejecutar:  python -m pytest tests/test_semaforo.py -v
"""
from pathlib import Path

import pandas as pd
import pytest

from src.alertas import notificaciones as notif
from src.alertas.semaforo import calcular_semaforo, evaluar_apiario, leer_ndvi

RAIZ = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("ndvi,p1,p2,p3,clima,esperado", [
    ("0. 28 (Floración Muy Baja)", "Alta (8 cuadros llenos)", "Bajas (menos de 2 cuadros)", "Activa", "Sequía / Helada", "ROJO"),
    ("0. 74 (Floración Óptima)", "Media (5 cuadros)", "Medias (4 cuadros)", "Activa", "Templado húmedo", "VERDE"),
    (0.30, "Alta", "Altas", "Activa", "Seco", "NARANJA"),          # cuenta regresiva
    (0.45, "Media", "Bajas", "Activa", "", "NARANJA"),             # floración baja + reservas bajas
    (0.65, "Alta", "Altas", "Activa", "Lluvias intensas", "NARANJA"),
    (0.70, "Media", "Medias", "Detenida", "Templado", "AMARILLO"),  # problema local
    (0.45, "Media", "Medias", "Activa", "", "AMARILLO"),            # floración bajo el óptimo
    (0.30, "Baja", "Bajas", "Detenida", "", "ROJO"),
])
def test_reglas_semaforo(ndvi, p1, p2, p3, clima, esperado):
    assert calcular_semaforo(leer_ndvi(ndvi), p1, p2, p3, clima) == esperado


def test_ndvi_invalido():
    with pytest.raises(ValueError):
        evaluar_apiario("X", "Y", "sin dato", "Alta", "Bajas", "Activa")


def test_normalizacion_contactos():
    assert notif.normalizar_telefono("300 123 4567") == "573001234567"
    assert notif.normalizar_telefono("+57 300 123 4567") == "573001234567"
    assert notif.normalizar_telefono("123") == ""
    assert notif.normalizar_canal("WhatsApp") == "WHATSAPP"
    assert notif.normalizar_canal("", telefono="3001234567") == "WHATSAPP"
    assert notif.normalizar_canal("", email="a@b.co") == "CORREO"
    assert notif.normalizar_canal("Ambos") == "AMBOS"


def test_sin_autorizacion_no_envia(monkeypatch):
    llamado = {"n": 0}
    monkeypatch.setattr(notif, "enviar_whatsapp_plantilla", lambda *a, **k: llamado.update(n=1) or (True, ""))
    r = evaluar_apiario("API-01", "Pacho", 0.28, "Alta", "Bajas", "Activa")
    res = notif.enviar_semaforo(r, "WhatsApp", "3001234567", "a@b.co", autoriza_datos=False)
    assert res["enviado"] is False and llamado["n"] == 0


def test_respaldo_por_correo_si_falla_whatsapp(monkeypatch):
    monkeypatch.setattr(notif, "enviar_whatsapp_plantilla", lambda *a, **k: (False, "HTTP 401"))
    monkeypatch.setattr(notif, "enviar_correo", lambda *a, **k: (True, ""))
    r = evaluar_apiario("API-01", "Pacho", 0.28, "Alta", "Bajas", "Activa")
    res = notif.enviar_semaforo(r, "WhatsApp", "3001234567", "a@b.co", autoriza_datos=True)
    assert res["enviado"] is True
    assert "Correo (respaldo): OK" in res["detalle"]


def test_payload_plantilla_whatsapp(monkeypatch):
    capturado = {}

    class Resp:
        status_code = 200
        def json(self): return {}

    def falso_post(url, headers, json, timeout):
        capturado.update(url=url, json=json, headers=headers)
        return Resp()

    monkeypatch.setenv("WA_TOKEN", "token-prueba")
    monkeypatch.setenv("WA_PHONE_NUMBER_ID", "123456")
    monkeypatch.setattr(notif.requests, "post", falso_post)
    ok, _ = notif.enviar_whatsapp_plantilla("3001234567", ["API-01", "Pacho", "ROJO", "línea 1\nlínea 2"])
    assert ok
    assert capturado["url"].endswith("/123456/messages")
    params = capturado["json"]["template"]["components"][0]["parameters"]
    assert params[3]["text"] == "línea 1 línea 2"          # sin saltos de línea
    assert capturado["json"]["to"] == "573001234567"


def test_plantilla_csv_simulada():
    from src.alertas.enviar_alertas_semanales import procesar_bitacora
    df = pd.read_csv(RAIZ / "mvp_aceleralab/sheets/BD_AbejaVerde_EO_Bitacora_Colmenas.csv",
                     dtype=str, keep_default_na=False)
    out = procesar_bitacora(df, simular=True, usar_gemini=False)
    assert list(out["Semaforo_IA"]) == ["ROJO", "VERDE", "NARANJA", "AMARILLO"]
