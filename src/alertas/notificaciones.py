"""
AbejaVerde·EO — notificaciones
Envío de alertas al apicultor por múltiples canales.

Canales soportados:
    WhatsApp           → WhatsApp Business Cloud API de Meta (plantilla aprobada)
    Email              → SMTP (Gmail u otro proveedor)
    Log local          → siempre activo (fallback)

Reglas de envío (Manual Técnico Acelera Lab + Ley 1581 de 2012):
    • Cada apicultor elige su canal: WhatsApp, Correo o Ambos.
    • Solo se envía si el apicultor autorizó el tratamiento de sus datos.
    • Si WhatsApp falla y el canal era solo WhatsApp, se intenta por correo.

Configuración en .env (o en los Secrets de Streamlit Cloud):
    # Correo
    NOTIF_EMAIL_FROM   = alertas@abejaverde.co
    NOTIF_EMAIL_TO     = apicultor@email.com      (destinatario por defecto)
    SMTP_HOST          = smtp.gmail.com
    SMTP_PORT          = 587
    SMTP_USER          = ...
    SMTP_PASS          = ...                       (contraseña de aplicación de Gmail)
    # WhatsApp Cloud API
    WA_TOKEN           = ...                       (token de acceso de Meta)
    WA_PHONE_NUMBER_ID = ...                       (ID del número emisor)
    WA_TEMPLATE        = alerta_semaforo_abejaverde
    WA_LANG            = es
    WA_GRAPH_VERSION   = v23.0
"""
from __future__ import annotations

import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests

from src.alertas.motor_alertas import Alerta

logger = logging.getLogger(__name__)

CANALES_VALIDOS = ("WHATSAPP", "CORREO", "AMBOS")


# ════════════════════════════════════════════════════════════════════════════
#  Utilidades
# ════════════════════════════════════════════════════════════════════════════

def normalizar_telefono(valor) -> str:
    """Devuelve el número en formato internacional sin '+' (ej. 573001234567) o ''."""
    d = re.sub(r"\D", "", str(valor or ""))
    if len(d) == 10 and d.startswith("3"):  # celular colombiano
        d = "57" + d
    return d if 11 <= len(d) <= 15 else ""


def es_email(valor) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", str(valor or "").strip()))


def normalizar_canal(canal, telefono=None, email=None) -> str:
    """WHATSAPP | CORREO | AMBOS | NINGUNO. Sin canal elegido: WhatsApp si hay teléfono."""
    t = str(canal or "").strip().lower()
    if t.startswith("amb"):
        return "AMBOS"
    if t.startswith("what") or t in ("wp", "wa"):
        return "WHATSAPP"
    if t.startswith(("corr", "mail", "email")):
        return "CORREO"
    if normalizar_telefono(telefono):
        return "WHATSAPP"
    if es_email(email):
        return "CORREO"
    return "NINGUNO"


def _limpiar_parametro(texto) -> str:
    """Meta no admite saltos de línea, tabulaciones ni 4+ espacios seguidos en parámetros."""
    t = re.sub(r"[\n\r\t]+", " ", str(texto or ""))
    return re.sub(r" {2,}", " ", t).strip()[:900]


# ════════════════════════════════════════════════════════════════════════════
#  Canal: LOG
# ════════════════════════════════════════════════════════════════════════════

def enviar_por_log(alerta: Alerta) -> bool:
    """Canal siempre disponible — registra la alerta en el log."""
    logger.warning(
        f"ALERTA [{alerta.nivel}] {alerta.tipo} | "
        f"{alerta.fecha} | {alerta.apiario_id} | "
        f"{alerta.mensaje[:80]}"
    )
    return True


# ════════════════════════════════════════════════════════════════════════════
#  Canal: WHATSAPP (WhatsApp Business Cloud API)
# ════════════════════════════════════════════════════════════════════════════

def _whatsapp_post(payload: dict) -> tuple[bool, str]:
    token = os.getenv("WA_TOKEN")
    phone_id = os.getenv("WA_PHONE_NUMBER_ID")
    version = os.getenv("WA_GRAPH_VERSION", "v23.0")
    if not token or not phone_id:
        return False, "WhatsApp no configurado (faltan WA_TOKEN o WA_PHONE_NUMBER_ID)"
    try:
        r = requests.post(
            f"https://graph.facebook.com/{version}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        if 200 <= r.status_code < 300:
            return True, ""
        try:
            detalle = r.json().get("error", {}).get("message", "")
        except ValueError:
            detalle = r.text[:120]
        return False, f"HTTP {r.status_code} {detalle}".strip()
    except requests.RequestException as e:
        return False, str(e)[:180]


def enviar_whatsapp_plantilla(
    telefono: str,
    parametros: list[str],
    plantilla: Optional[str] = None,
    idioma: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Envía una plantilla aprobada de WhatsApp. Fuera de la ventana de 24 h,
    Meta solo permite que el negocio escriba primero con plantillas.

    Plantilla sugerida `alerta_semaforo_abejaverde` (Utilidad, español):
        AbejaVerde·EO – Apiario {{1}} ({{2}}). Semáforo: {{3}}.
        Acción recomendada esta semana: {{4}}
        Si necesita apoyo, comuníquese con su técnico de AbejaVerde.
    """
    numero = normalizar_telefono(telefono)
    if not numero:
        return False, "teléfono no válido"
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": plantilla or os.getenv("WA_TEMPLATE", "alerta_semaforo_abejaverde"),
            "language": {"code": idioma or os.getenv("WA_LANG", "es")},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": _limpiar_parametro(p)} for p in parametros],
            }],
        },
    }
    ok, detalle = _whatsapp_post(payload)
    if ok:
        logger.info(f"📲 WhatsApp enviado a {numero}")
    else:
        logger.error(f"Error enviando WhatsApp a {numero}: {detalle}")
    return ok, detalle


def probar_whatsapp(telefono: str) -> tuple[bool, str]:
    """Envía la plantilla 'hello_world' que Meta trae aprobada (sirve para validar la conexión)."""
    numero = normalizar_telefono(telefono)
    if not numero:
        return False, "teléfono no válido"
    return _whatsapp_post({
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {"name": "hello_world", "language": {"code": "en_US"}},
    })


def enviar_por_whatsapp(alerta: Alerta, telefono: Optional[str] = None) -> bool:
    """Envía una Alerta del motor clásico (alimentación, agua, reina…) por WhatsApp."""
    telefono = telefono or os.getenv("NOTIF_WHATSAPP_TO")
    if not telefono:
        logger.debug("WhatsApp sin destinatario — usando log")
        return False
    ok, _ = enviar_whatsapp_plantilla(
        telefono,
        [
            alerta.apiario_id,
            os.getenv("APIARIO_NOMBRE", "Cundinamarca").replace("_", " "),
            f"{alerta.nivel} – {alerta.tipo.replace('_', ' ').title()}",
            alerta.recomendacion,
        ],
    )
    return ok


# ════════════════════════════════════════════════════════════════════════════
#  Canal: CORREO (SMTP)
# ════════════════════════════════════════════════════════════════════════════

def enviar_correo(
    asunto: str,
    texto: str,
    html: str,
    email_to: Optional[str] = None,
    email_from: Optional[str] = None,
) -> tuple[bool, str]:
    """Envío genérico por SMTP. Devuelve (ok, detalle)."""
    email_to = email_to or os.getenv("NOTIF_EMAIL_TO")
    email_from = email_from or os.getenv("NOTIF_EMAIL_FROM") or os.getenv("SMTP_USER") or "alertas@abejaverde.co"
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not es_email(email_to):
        return False, "correo no válido"
    if not smtp_user or not smtp_pass:
        return False, "correo no configurado (faltan SMTP_USER o SMTP_PASS)"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = f"AbejaVerde·EO <{email_from}>"
        msg["To"] = email_to
        msg.attach(MIMEText(texto, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(email_from, [email_to], msg.as_string())
        logger.info(f"📧 Email enviado a {email_to}")
        return True, ""
    except Exception as e:  # smtplib lanza varias excepciones distintas
        logger.error(f"Error enviando email: {e}")
        return False, str(e)[:180]


def enviar_por_email(
    alerta:    Alerta,
    email_to:  Optional[str] = None,
    email_from: Optional[str] = None,
) -> bool:
    """Envía una Alerta del motor clásico por email via SMTP."""
    asunto = (f"{alerta.emoji} AbejaVerde·EO [{alerta.nivel}]: "
              f"{alerta.tipo} — {alerta.apiario_id}")
    ok, _ = enviar_correo(asunto, alerta.texto_notificacion(), _html_alerta(alerta),
                          email_to, email_from)
    return ok


def _html_alerta(alerta: Alerta) -> str:
    """Genera el HTML del email de alerta."""
    colores = {
        "URGENTE": "#DC2626",
        "ALTA":    "#EA580C",
        "MEDIA":   "#D97706",
        "INFO":    "#16A34A",
        "NORMAL":  "#6B7280",
    }
    color = colores.get(alerta.nivel, "#6B7280")

    return f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #132610; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin:0;">{alerta.emoji} AbejaVerde·EO</h2>
        <p style="margin:4px 0; opacity:0.8;">Sistema de alertas apícolas · {alerta.apiario_id}</p>
    </div>
    <div style="border: 2px solid {color}; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
        <div style="background:{color}; color:white; padding:8px 16px; border-radius:4px; display:inline-block; margin-bottom:16px;">
            <strong>{alerta.nivel}</strong> — {alerta.tipo}
        </div>
        <p style="font-size:16px;">{alerta.mensaje}</p>
        <hr style="border-color:#eee;">
        <h3 style="color:{color};">📋 Acción recomendada:</h3>
        <p>{alerta.recomendacion}</p>
        <hr style="border-color:#eee;">
        <p style="color:#666; font-size:12px;">
            Generado: {alerta.timestamp.strftime('%d/%m/%Y %H:%M')} |
            Fuentes: {', '.join(alerta.fuentes)}
        </p>
    </div>
    </body></html>
    """


def _html_semaforo(r) -> str:
    from src.alertas.semaforo import HEX
    return f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background:#132610; color:white; padding:18px 20px; border-radius:8px 8px 0 0;">
        <h2 style="margin:0;">🐝 AbejaVerde·EO</h2>
        <p style="margin:4px 0; opacity:.85;">Apiario {r.apiario_id} · {r.municipio}</p>
    </div>
    <div style="border:2px solid {HEX[r.semaforo]}; border-top:none; padding:20px; border-radius:0 0 8px 8px;">
        <div style="background:{HEX[r.semaforo]}; color:#1F2A1F; padding:12px 16px; border-radius:8px; font-size:18px;">
            <strong>Semáforo {r.semaforo}</strong> — {r.descripcion}
        </div>
        <h3 style="color:#132610;">📋 Acción recomendada esta semana</h3>
        <p style="font-size:16px;">{r.accion}</p>
        {f'<p style="color:#555; font-size:13px;">🛰️ NDVI Copernicus del entorno: {r.ndvi:.2f}</p>' if r.tiene_ndvi else ''}
        <hr style="border-color:#eee;">
        <p style="color:#777; font-size:12px;">Recibe este mensaje porque autorizó el tratamiento de sus
        datos para alertas apícolas (Ley 1581 de 2012). Para dejar de recibirlas, responda este correo
        con la palabra BAJA.</p>
    </div>
    </body></html>
    """


# ════════════════════════════════════════════════════════════════════════════
#  Envío del SEMÁFORO (bitácora de 3 preguntas) por el canal elegido
# ════════════════════════════════════════════════════════════════════════════

def enviar_semaforo(
    resultado,
    canal: Optional[str] = None,
    telefono: Optional[str] = None,
    email: Optional[str] = None,
    autoriza_datos: bool = False,
) -> dict:
    """
    Envía un `ResultadoSemaforo` (ver src/alertas/semaforo.py) por WhatsApp,
    correo o ambos.

    Returns:
        {"enviado": bool, "canal": str, "detalle": "WhatsApp: OK · Correo: OK"}
    """
    if not autoriza_datos:
        return {"enviado": False, "canal": "NINGUNO",
                "detalle": "No enviado: falta autorización Ley 1581"}

    canal_n = normalizar_canal(canal, telefono, email)
    partes: list[str] = []
    enviado = False

    def _correo() -> tuple[bool, str]:
        return enviar_correo(
            asunto=f"[AbejaVerde·EO] Semáforo {resultado.semaforo} – Apiario "
                   f"{resultado.apiario_id} ({resultado.municipio})",
            texto=resultado.texto_whatsapp().replace("*", ""),
            html=_html_semaforo(resultado),
            email_to=email,
        )

    if canal_n in ("WHATSAPP", "AMBOS"):
        ok, det = enviar_whatsapp_plantilla(
            telefono or "",
            [resultado.apiario_id, resultado.municipio or "Cundinamarca",
             f"{resultado.semaforo} – {resultado.descripcion}", resultado.accion],
        )
        partes.append("WhatsApp: OK" if ok else f"WhatsApp: falló ({det})")
        enviado |= ok
        if not ok and canal_n == "WHATSAPP" and es_email(email):
            ok_c, det_c = _correo()
            partes.append("Correo (respaldo): OK" if ok_c else f"Correo (respaldo): falló ({det_c})")
            enviado |= ok_c

    if canal_n in ("CORREO", "AMBOS"):
        ok, det = _correo()
        partes.append("Correo: OK" if ok else f"Correo: falló ({det})")
        enviado |= ok

    if canal_n == "NINGUNO":
        partes.append("Sin teléfono ni correo válidos")

    return {"enviado": enviado, "canal": canal_n, "detalle": " · ".join(partes)}


# ════════════════════════════════════════════════════════════════════════════
#  Envío de alertas del motor clásico
# ════════════════════════════════════════════════════════════════════════════

def notificar(
    alerta:     Alerta,
    canales:    Optional[list] = None,
    email_to:   Optional[str]  = None,
    telefono:   Optional[str]  = None,
) -> dict:
    """
    Envía la alerta por todos los canales indicados.

    Args:
        alerta:   objeto Alerta a enviar
        canales:  ["log", "email", "whatsapp"] — por defecto ["log"]
        email_to: destinatario email (opcional)
        telefono: celular para WhatsApp (opcional)

    Returns:
        dict con resultado por canal
    """
    canales   = canales or ["log"]
    resultado = {}

    for canal in canales:
        if canal == "log":
            resultado["log"] = enviar_por_log(alerta)
        elif canal == "email":
            resultado["email"] = enviar_por_email(alerta, email_to)
        elif canal == "whatsapp":
            resultado["whatsapp"] = enviar_por_whatsapp(alerta, telefono)
        else:
            logger.debug(f"Canal '{canal}' no implementado aún")
            resultado[canal] = False

    return resultado


def notificar_lista(
    alertas:  list,
    canales:  Optional[list] = None,
    solo_nivel_min: str = "MEDIA",
    email_to: Optional[str] = None,
    telefono: Optional[str] = None,
) -> int:
    """
    Notifica una lista de alertas filtrando por nivel mínimo.

    Returns:
        Número de alertas enviadas
    """
    from src.alertas.motor_alertas import NIVELES
    nivel_min = NIVELES.get(solo_nivel_min, 2)

    enviadas = 0
    for a in alertas:
        if a.prioridad >= nivel_min:
            notificar(a, canales, email_to, telefono)
            enviadas += 1

    logger.info(f"📨 {enviadas}/{len(alertas)} alertas notificadas (nivel ≥ {solo_nivel_min})")
    return enviadas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")

    from src.alertas.motor_alertas import generar_alertas
    from datetime import date

    alertas = generar_alertas(
        fecha=date(2025, 4, 10), ndvi=0.379,
        fase_feno="FUERA_TEMPORADA", precip_mm=22,
        pct_agua=8.6, n_colmenas=10,
    )

    print(f"Alertas generadas: {len(alertas)}")
    for a in alertas:
        resultado = notificar(a, canales=["log"])
        print(f"  {a.emoji} [{a.nivel}] {a.tipo} → log={resultado['log']}")
        print(f"  WhatsApp preview:\n{a.texto_notificacion()[:200]}...\n")
