"""
AbejaVerde·EO — App del Apicultor
===================================
Aplicación simple para apicultores — alertas en lenguaje natural.

Diferencia con dashboard.py:
    dashboard.py      → técnico, para jueces y administradores
    app_apicultor.py  → simple, para el apicultor en campo

Para correr:
    streamlit run app/app_apicultor.py --server.port 8502

Despliegue:
    Streamlit Cloud → app/app_apicultor.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
import streamlit as st
from datetime import date, datetime

st.set_page_config(
    page_title = "AbejaVerde — Mi Apiario",
    page_icon  = "🐝",
    layout     = "centered",
)

# ── CSS MÓVIL ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main { max-width: 480px; margin: 0 auto; }
    .semaforo-verde  { background:#EAF3DE; color:#3B6D11; border-radius:50%;
                       width:110px; height:110px; display:flex; align-items:center;
                       justify-content:center; font-size:2.2rem; font-weight:500;
                       margin:0 auto 8px; }
    .semaforo-amarillo { background:#FAEEDA; color:#633806; border-radius:50%;
                         width:110px; height:110px; display:flex; align-items:center;
                         justify-content:center; font-size:2.2rem; font-weight:500;
                         margin:0 auto 8px; }
    .semaforo-rojo   { background:#FCEBEB; color:#A32D2D; border-radius:50%;
                       width:110px; height:110px; display:flex; align-items:center;
                       justify-content:center; font-size:2.2rem; font-weight:500;
                       margin:0 auto 8px; }
    .alerta-box      { padding:14px 16px; border-radius:12px; margin-bottom:10px; }
    .sensor-val      { font-size:1.4rem; font-weight:500; }
</style>
""", unsafe_allow_html=True)


# ── DATOS ─────────────────────────────────────────────────────────────────────

@st.cache_data
def cargar_datos_iot():
    """Carga datos IoT reales si existen, o usa demo."""
    ruta_pesos   = ROOT / "lecturas_pesos.csv"
    ruta_estado  = ROOT / "lecturas_estado.csv"
    ruta_exterior = ROOT / "lecturas_exterior.csv"

    if ruta_pesos.exists() and ruta_estado.exists():
        df_pesos    = pd.read_csv(ruta_pesos,    parse_dates=["timestamp"])
        df_estado   = pd.read_csv(ruta_estado,   parse_dates=["timestamp"])
        df_exterior = pd.read_csv(ruta_exterior, parse_dates=["timestamp"]) \
                      if ruta_exterior.exists() else pd.DataFrame()

        ultima_p = df_pesos.iloc[-1]
        ultima_e = df_estado.iloc[-1]
        ultima_x = df_exterior.iloc[-1] if not df_exterior.empty else None

        return {
            "real":           True,
            "timestamp":      ultima_p["timestamp"],
            "temp_interior":  round(float(ultima_p["temperatura"]), 1),
            "hum_interior":   round(float(ultima_p["humedad"]), 1),
            "temp_exterior":  round(float(ultima_x["temp_exterior_C"]), 1) if ultima_x is not None else None,
            "hum_exterior":   round(float(ultima_x["hum_exterior_pct"]), 1) if ultima_x is not None else None,
            "bateria_v":      round(float(ultima_x["campo_4"]) if ultima_x is not None
                                    else float(ultima_e.get("campo5", 2900)) / 1000, 2),
            "celdas_activas": sum(1 for c in ["c1","c11","c12","c13"]
                                  if c in ultima_p and float(ultima_p[c]) > 100),
            "n_lecturas":     len(df_pesos),
        }
    else:
        return {
            "real":           False,
            "timestamp":      datetime.now(),
            "temp_interior":  22.2,
            "hum_interior":   66.3,
            "temp_exterior":  22.4,
            "hum_exterior":   65.8,
            "bateria_v":      2.61,
            "celdas_activas": 4,
            "n_lecturas":     0,
        }


@st.cache_data
def cargar_datos_satelitales():
    """Datos reales Copernicus del piloto."""
    return {
        "ndvi_ultimo":    0.787,
        "ndvi_mes":       "Mayo 2025",
        "ndvi_estado":    "Floración activa",
        "precip_mm":      22.0,
        "precip_estado":  "Bajo",
        "temp_era5":      21.1,
        "agua_pct":       8.6,
        "agua_estado":    "Escasa",
        "ira_score":      37.0,
        "ira_nivel":      "MEDIO",
    }


def calcular_ira_color(score):
    if score > 66: return "rojo",    "Riesgo alto",    "⚠️ Atención urgente"
    if score > 33: return "amarillo","Riesgo moderado","Revise esta semana"
    return             "verde",      "Condiciones OK", "Sin acción urgente"


# ── GENERAR ALERTAS EN LENGUAJE NATURAL ──────────────────────────────────────

def generar_alertas_lenguaje_natural(sat, iot):
    """
    Transforma los datos en alertas en español simple para el apicultor.
    Sin siglas, sin decimales innecesarios, con acción concreta.
    """
    alertas = []

    # ── Alimentación ─────────────────────────────────────────────────────────
    if sat["ndvi_ultimo"] < 0.52 and sat["precip_mm"] < 75:
        alertas.append({
            "tipo":  "alimentacion",
            "icono": "🍯",
            "titulo": "Considere alimentar sus colmenas",
            "texto": (
                f"La vegetación melífera bajó y ha llovido poco ({sat['precip_mm']:.0f}mm). "
                f"Revise las reservas de miel. Si el peso de la colmena bajó más del 5% "
                f"esta semana, alimente con jarabe de azúcar (2 partes azúcar, 1 parte agua)."
            ),
            "nivel": "media",
        })
    elif sat["ndvi_ultimo"] >= 0.65:
        alertas.append({
            "tipo":  "no_alimentar",
            "icono": "✅",
            "titulo": "Hay floración activa — no alimente",
            "texto": (
                f"El satélite ve vegetación activa en el radio de vuelo de sus abejas "
                f"(índice {sat['ndvi_ultimo']:.2f}). Sus abejas están recolectando. "
                f"Si alimenta ahora puede contaminar la miel."
            ),
            "nivel": "buena",
        })

    # ── Agua ──────────────────────────────────────────────────────────────────
    if sat["agua_pct"] < 30 or sat["precip_mm"] < 50:
        alertas.append({
            "tipo":  "agua",
            "icono": "💧",
            "titulo": "Verifique que haya agua cerca",
            "texto": (
                f"Ha llovido muy poco ({sat['precip_mm']:.0f}mm) y los cuerpos de agua "
                f"en la zona están bajos. Sus abejas necesitan al menos 1 litro de agua "
                f"fresca por colmena por día. Si no hay fuentes naturales cerca, "
                f"instale un bebedero a menos de 200 metros."
            ),
            "nivel": "alerta",
        })

    # ── Temperatura colmena ───────────────────────────────────────────────────
    temp = iot.get("temp_interior", 22)
    if temp < 33 or temp > 37:
        alertas.append({
            "tipo":  "temperatura",
            "icono": "🌡️",
            "titulo": "Temperatura interna inusual",
            "texto": (
                f"El sensor interior registra {temp}°C. "
                f"Una colmena sana mantiene entre 34.5 y 35.5°C en la zona de cría. "
                f"Visite la colmena y revise si la reina está activa y si la población es suficiente."
            ),
            "nivel": "alerta",
        })

    # ── Batería ───────────────────────────────────────────────────────────────
    bat = iot.get("bateria_v", 3.7)
    if bat < 3.3:
        alertas.append({
            "tipo":  "bateria",
            "icono": "🔋",
            "titulo": "Batería del sensor baja",
            "texto": (
                f"El sensor está al {bat:.1f}V. Si baja de 3.0V dejará de enviar datos. "
                f"En su próxima visita revise el panel solar o recargue la batería."
            ),
            "nivel": "info",
        })

    if not alertas:
        alertas.append({
            "tipo":  "ok",
            "icono": "🌿",
            "titulo": "Todo en orden",
            "texto": "No hay alertas activas. Continue con el monitoreo rutinario.",
            "nivel": "buena",
        })

    return alertas


COLORES_ALERTA = {
    "alerta": ("#FCEBEB", "#A32D2D", "#F7C1C1"),
    "media":  ("#FAEEDA", "#633806", "#FAC775"),
    "info":   ("#E6F1FB", "#042C53", "#B5D4F4"),
    "buena":  ("#EAF3DE", "#173404", "#C0DD97"),
}


# ── RESPUESTAS DEL ASESOR IA ──────────────────────────────────────────────────

CONOCIMIENTO_APIARIO = """
Eres la asesora de AbejaVerde·EO para el Apiario en San Juan de Rioseco, Cundinamarca.
Datos reales del apiario (Copernicus + IoT):
- NDVI mayo 2025: 0.787 (floración activa, el más alto en meses)
- NDVI abril 2025: 0.379 (mínimo histórico — Fenómeno del Niño)
- Precipitación reciente: 22mm (muy baja)
- Temperatura ERA5: 21.1°C
- Agua superficial: 8.6% del nivel normal
- IRA Score: 37/100 (riesgo moderado)
- Temperatura interior nodo: 22.2°C (sin abejas — colmena en calibración)
- Patrón del territorio: pico de floración en junio (NDVI 0.817 en jun 2024)
- Meses de escasez histórica: enero y abril

Responde en español colombiano, lenguaje simple, con recomendaciones concretas.
Máximo 3 párrafos cortos. Usa términos apícolas pero explícalos.
"""

RESPUESTAS_RAPIDAS = {
    "alimentar": (
        "Dado que mayo tuvo buena floración (0.787), sus colmenas probablemente entraron junio "
        "con reservas. Sin embargo, ha llovido muy poco últimamente (22mm) y el agua superficial "
        "está baja.\n\n"
        "**Mi recomendación:** revise el peso de sus colmenas en la próxima visita. "
        "Si perdieron más del 5% en las últimas 2 semanas, empiece a alimentar con jarabe 1:1 "
        "(1 kilo azúcar en 1 litro de agua tibia). Ofrezca 1 litro por colmena cada 3 días.\n\n"
        "Si el peso está estable o subiendo, no alimente — las abejas siguen trabajando."
    ),
    "enjambrar": (
        "El riesgo de enjambrazón es moderado-alto en este momento. Mayo fue un mes excelente "
        "de floración (NDVI 0.787) y eso hace que las colonias crezcan rápido.\n\n"
        "**Señales de alerta:** si ve celdas reales (parecen cacahuetes colgando en los bordes "
        "del panal), la colonia está preparando enjambre. Si los cuadros del centro están más "
        "del 80% llenos, agregue un alza ya.\n\n"
        "La ventana crítica es ahora — si junio sigue el patrón de 2024 (NDVI 0.817), "
        "va a ser el mes de mayor actividad del año."
    ),
    "cosechar": (
        "El mejor momento para cosechar en San Juan de Rioseco, basado en los datos satelitales "
        "de 2024, es entre la segunda quincena de junio y la primera de julio — cuando el NDVI "
        "empieza a bajar desde su pico.\n\n"
        "**Regla práctica:** coseche cuando los cuadros del alza estén más del 80% operculados "
        "(sellados con cera blanca). Si cosechar miel verde fermenta y pierde calidad.\n\n"
        "No espere a que el NDVI baje demasiado — cuando baja es señal de que las abejas "
        "ya están consumiendo las reservas."
    ),
    "agua": (
        "Con solo 22mm de lluvia y el agua superficial al 8.6% del nivel normal, "
        "el agua es la prioridad número uno ahora mismo.\n\n"
        "Sus abejas necesitan 1 litro de agua fresca por colmena por día. "
        "Si tiene 10 colmenas, eso es 10 litros diarios. "
        "El bebedero debe estar a menos de 200 metros — las abejas gastan energía "
        "buscando agua lejana y eso reduce la recolección de néctar.\n\n"
        "Use un recipiente con piedras o flotadores para que las abejas puedan posarse "
        "sin ahogarse. Cambie el agua cada 2 días para evitar mosquitos."
    ),
}


# ── INTERFAZ PRINCIPAL ────────────────────────────────────────────────────────

iot = cargar_datos_iot()
sat = cargar_datos_satelitales()
alertas = generar_alertas_lenguaje_natural(sat, iot)
color_ira, nivel_ira, desc_ira = calcular_ira_color(sat["ira_score"])

# Header
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("## 🐝 Mi Apiario")
    st.markdown(f"San Juan de Rioseco · *{datetime.now().strftime('%d %b %Y, %H:%M')}*")
with col_h2:
    if iot["real"]:
        st.markdown('<span style="background:#EAF3DE;color:#3B6D11;padding:4px 8px;'
                    'border-radius:6px;font-size:11px;font-weight:500;">● En vivo</span>',
                    unsafe_allow_html=True)

st.divider()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["🏠 Inicio", "📷 Mis Fotos", "📡 Sensores", "💬 Asesora IA"])

# ── TAB 1: INICIO ─────────────────────────────────────────────────────────────
with tab1:

    # Semáforo IRA
    col_s1, col_s2, col_s3 = st.columns([1, 2, 1])
    with col_s2:
        st.markdown(
            f'<div class="semaforo-{color_ira}">{sat["ira_score"]:.0f}</div>'
            f'<div style="text-align:center; font-weight:500; font-size:1.1rem;">{nivel_ira}</div>'
            f'<div style="text-align:center; color:#666; font-size:0.9rem; margin-bottom:16px;">{desc_ira}</div>',
            unsafe_allow_html=True,
        )

    # Alertas en lenguaje natural
    st.markdown("**Alertas de hoy**")
    for a in alertas:
        bg, txt, brd = COLORES_ALERTA.get(a["nivel"], COLORES_ALERTA["info"])
        st.markdown(
            f'<div class="alerta-box" style="background:{bg};border-left:4px solid {brd};">'
            f'<div style="font-size:1.1rem;">{a["icono"]} <strong style="color:{txt};">'
            f'{a["titulo"]}</strong></div>'
            f'<div style="font-size:0.9rem;color:{txt};margin-top:6px;line-height:1.6;">'
            f'{a["texto"]}</div></div>',
            unsafe_allow_html=True,
        )

    # Resumen rápido
    st.divider()
    st.markdown("**Resumen del apiario**")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Temperatura", f"{iot['temp_interior']:.1f}°C", "Interior")
    with c2:
        st.metric("Humedad", f"{iot['hum_interior']:.0f}%", "Interior")
    with c3:
        bat_delta = "OK" if iot["bateria_v"] > 3.3 else "Baja"
        st.metric("Batería", f"{iot['bateria_v']:.2f}V", bat_delta)


# ── TAB 2: FOTOS ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("**Suba una foto de su entorno** — la IA extrae variables para mejorar las alertas")
    st.caption("El apicultor es el puente entre el satélite y el sensor. Sus fotos capturan lo que ninguna tecnología puede ver remotamente.")

    tipo_foto = st.radio(
        "¿Qué tipo de foto va a subir?",
        ["🌸 Floración", "💧 Agua", "🐝 Colmena", "🏔️ Paisaje"],
        horizontal=True,
    )
    tipo_map  = {"🌸 Floración": "flora", "💧 Agua": "agua",
                 "🐝 Colmena": "colmena", "🏔️ Paisaje": "paisaje"}
    tipo_clave = tipo_map[tipo_foto]

    foto_subida = st.file_uploader(
        "Suba la foto desde su teléfono o galería",
        type=["jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed",
    )

    if foto_subida:
        st.image(foto_subida, use_column_width=True)

        if st.button("🔍 Analizar foto", type="primary"):
            with st.spinner("Analizando con IA..."):
                import tempfile, os
                try:
                    from src.ingesta.foto_parser import analizar_foto_sin_api
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".jpg"
                    ) as tmp:
                        tmp.write(foto_subida.read())
                        ruta_tmp = tmp.name

                    resultado = analizar_foto_sin_api(
                        ruta_tmp, tipo=tipo_clave,
                        municipio=muni_sel,
                        guardar=True,
                    )
                    os.unlink(ruta_tmp)

                    st.success("✅ Análisis completado")
                    st.divider()

                    col_v1, col_v2 = st.columns(2)
                    with col_v1:
                        if tipo_clave == "flora":
                            st.metric("Floración", resultado.get("estado_floracion","?").upper())
                            st.metric("Valor melífero", resultado.get("valor_melifero","?").upper())
                            st.metric("NDVI proxy", resultado.get("ndvi_proxy","?"))
                        elif tipo_clave == "agua":
                            st.metric("Nivel del agua", resultado.get("nivel_estimado","?").upper())
                            st.metric("Acceso abejas", resultado.get("accesibilidad","?"))
                        elif tipo_clave == "colmena":
                            st.metric("Actividad piquera", resultado.get("actividad_piquera","?").upper())
                            st.metric("Estado", resultado.get("estado","?"))
                        else:
                            st.metric("Cobertura vegetal", f"{resultado.get('cobertura_vegetal_pct','?')}%")
                            st.metric("NDVI proxy", resultado.get("ndvi_proxy","?"))
                    with col_v2:
                        st.markdown("**Impacto en el IRA:**")
                        st.info(resultado.get("impacto_ira",""))

                    st.markdown("**Recomendación:**")
                    st.success(resultado.get("recomendacion",""))

                    st.markdown("**Señales detectadas:**")
                    señal = resultado.get("senales", resultado.get("senales_estres",""))
                    st.write(señal)

                except Exception as e:
                    st.error(f"Error al analizar: {e}")

    else:
        st.markdown("""
        <div style="border:1.5px dashed #C0DD97; border-radius:10px; padding:24px;
             text-align:center; background:#F7FAF3;">
            <div style="font-size:2rem; margin-bottom:8px">📷</div>
            <div style="font-size:14px; font-weight:500; color:#132610;">
                Toque aquí para subir una foto</div>
            <div style="font-size:12px; color:#888780; margin-top:4px;">
                JPG, PNG · Desde la cámara o galería del teléfono</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # Historial de observaciones guardadas
    ruta_obs = ROOT / "data" / "processed" / "observaciones_campo.csv"
    if ruta_obs.exists():
        st.markdown("**Fotos recientes del apiario:**")
        df_obs = pd.read_csv(ruta_obs, on_bad_lines="skip")
        if not df_obs.empty:
            for _, row in df_obs.tail(5).iloc[::-1].iterrows():
                icono = {"flora":"🌸","agua":"💧","colmena":"🐝","paisaje":"🏔️"}.get(
                    row.get("tipo_foto",""), "📷")
                rec   = str(row.get("recomendacion",""))[:60]
                fecha = str(row.get("timestamp",""))[:10]
                st.markdown(
                    f'<div style="padding:8px 0;border-bottom:.5px solid #E5E2D9;'
                    f'font-size:13px;">'
                    f'{icono} <b>{row.get("tipo_foto","foto").upper()}</b> · {fecha}'
                    f'<br><span style="color:#5F5E5A;font-size:12px;">{rec}...</span></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.caption("Las fotos analizadas aparecerán aquí como historial.")


# ── TAB 3: SENSORES ───────────────────────────────────────────────────────────
with tab3:

    if iot["real"]:
        st.success(f"✅ Datos reales del nodo IoT — {iot['timestamp'].strftime('%d %b %Y, %H:%M')}")
    else:
        st.warning("⚠️ Datos de demostración — conecte el nodo para ver datos reales")

    col_i, col_e = st.columns(2)

    with col_i:
        st.markdown("**Interior colmena**")
        st.metric("Temperatura", f"{iot['temp_interior']:.1f}°C")
        st.metric("Humedad", f"{iot['hum_interior']:.0f}%")
        st.metric("Celdas activas", f"{iot['celdas_activas']} de 22")

    with col_e:
        st.markdown("**Exterior**")
        if iot.get("temp_exterior"):
            st.metric("Temperatura", f"{iot['temp_exterior']:.1f}°C")
            st.metric("Humedad", f"{iot['hum_exterior']:.0f}%")
        st.metric("Batería LiPo", f"{iot['bateria_v']:.2f}V")

    st.divider()
    st.markdown("**Datos satelitales Copernicus**")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("NDVI", f"{sat['ndvi_ultimo']:.3f}", sat["ndvi_estado"])
        st.metric("Temperatura ERA5", f"{sat['temp_era5']:.1f}°C")
    with col_s2:
        st.metric("Precipitación", f"{sat['precip_mm']:.0f} mm", sat["precip_estado"])
        st.metric("Agua superficial", f"{sat['agua_pct']:.0f}%", sat["agua_estado"])

    st.caption("Fuente: Sentinel-2, ERA5 / Copernicus Data Space Ecosystem · openEO")


# ── TAB 4: ASESORA IA ─────────────────────────────────────────────────────────
with tab4:

    st.markdown(
        "**Asesora AbejaVerde** — pregúntele sobre su apiario en lenguaje natural. "
        "Usa los datos reales de Copernicus e IoT para responder."
    )

    # Preguntas frecuentes
    st.markdown("**Preguntas frecuentes:**")
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        if st.button("🍯 ¿Debo alimentar esta semana?"):
            st.session_state["respuesta_ia"] = RESPUESTAS_RAPIDAS["alimentar"]
        if st.button("💧 ¿Cómo manejo el agua?"):
            st.session_state["respuesta_ia"] = RESPUESTAS_RAPIDAS["agua"]
    with col_q2:
        if st.button("🐝 ¿Hay riesgo de enjambrazón?"):
            st.session_state["respuesta_ia"] = RESPUESTAS_RAPIDAS["enjambrar"]
        if st.button("🫙 ¿Cuándo cosechar?"):
            st.session_state["respuesta_ia"] = RESPUESTAS_RAPIDAS["cosechar"]

    # Chat libre
    pregunta_libre = st.text_input("O escriba su pregunta:", placeholder="Ej: ¿Por qué bajó el peso en abril?")

    if pregunta_libre:
        try:
            import anthropic
            cliente = anthropic.Anthropic()
            with st.spinner("Consultando con la asesora..."):
                resp = cliente.messages.create(
                    model      = "claude-opus-4-6",
                    max_tokens = 400,
                    system     = CONOCIMIENTO_APIARIO,
                    messages   = [{"role": "user", "content": pregunta_libre}],
                )
                st.session_state["respuesta_ia"] = resp.content[0].text
        except Exception:
            # Fallback sin API
            st.session_state["respuesta_ia"] = (
                "Para responder preguntas personalizadas en producción, "
                "el sistema usa la API de Claude con el contexto real de su apiario. "
                "Use los botones de arriba para las preguntas más frecuentes."
            )

    if "respuesta_ia" in st.session_state:
        st.divider()
        st.markdown("**Asesora AbejaVerde:**")
        st.markdown(st.session_state["respuesta_ia"])
        if st.button("Limpiar"):
            del st.session_state["respuesta_ia"]

    st.divider()
    st.caption(
        "Las respuestas se basan en datos reales de Copernicus (Sentinel-2, ERA5) "
        "y el IoT del apiario piloto. No reemplazan la visita física a la colmena."
    )
