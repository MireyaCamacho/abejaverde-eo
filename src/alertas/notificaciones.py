"""
AbejaVerde·EO — notificaciones
Envío de alertas al apicultor por múltiples canales.

Canales soportados:
    App propia (push)  → via API FastAPI → app móvil
    Email              → via SMTP o SendGrid
    WhatsApp           → via Twilio o Meta Cloud API (futuro)
    Log local          → siempre activo (fallback)

Configuración en .env:
    NOTIF_EMAIL_FROM   = alertas@abejaverde.co
    NOTIF_EMAIL_TO     = apicultor@email.com
    SMTP_HOST          = smtp.gmail.com
    SMTP_PORT          = 587
    SMTP_USER          = ...
    SMTP_PASS          = ...
"""
from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional, Union

from src.alertas.motor_alertas import Alerta

logger = logging.getLogger(__name__)


def enviar_por_log(alerta: Alerta) -> bool:
    """Canal siempre disponible — registra la alerta en el log."""
    logger.warning(
        f"ALERTA [{alerta.nivel}] {alerta.tipo} | "
        f"{alerta.fecha} | {alerta.apiario_id} | "
        f"{alerta.mensaje[:80]}"
    )
    return True


def enviar_por_email(
    alerta:    Alerta,
    email_to:  Optional[str] = None,
    email_from: Optional[str] = None,
) -> bool:
    """
    Envía la alerta por email via SMTP.
    Configurar credenciales en .env
    """
    email_to   = email_to   or os.getenv("NOTIF_EMAIL_TO")
    email_from = email_from or os.getenv("NOTIF_EMAIL_FROM", "alertas@abejaverde.co")
    smtp_host  = os.getenv("SMTP_HOST",  "smtp.gmail.com")
    smtp_port  = int(os.getenv("SMTP_PORT", "587"))
    smtp_user  = os.getenv("SMTP_USER")
    smtp_pass  = os.getenv("SMTP_PASS")

    if not email_to or not smtp_user:
        logger.debug("Email no configurado — usando log")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = (
            f"{alerta.emoji} AbejaVerde·EO [{alerta.nivel}]: "
            f"{alerta.tipo} — {alerta.apiario_id}"
        )
        msg["From"] = email_from
        msg["To"]   = email_to

        cuerpo_txt = alerta.texto_notificacion()
        cuerpo_html = _html_alerta(alerta)

        msg.attach(MIMEText(cuerpo_txt,  "plain",  "utf-8"))
        msg.attach(MIMEText(cuerpo_html, "html",   "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(email_from, email_to, msg.as_string())

        logger.info(f"📧 Email enviado a {email_to}: {alerta.tipo} [{alerta.nivel}]")
        return True

    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return False


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


def notificar(
    alerta:     Alerta,
    canales:    Optional[list] = None,
    email_to:   Optional[str]  = None,
) -> dict:
    """
    Envía la alerta por todos los canales configurados.

    Args:
        alerta:   objeto Alerta a enviar
        canales:  ["log", "email", "push"] — por defecto ["log"]
        email_to: destinatario email (opcional)

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
        else:
            logger.debug(f"Canal '{canal}' no implementado aún")
            resultado[canal] = False

    return resultado


def notificar_lista(
    alertas:  list,
    canales:  Optional[list] = None,
    solo_nivel_min: str = "MEDIA",
    email_to: Optional[str] = None,
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
            notificar(a, canales, email_to)
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
