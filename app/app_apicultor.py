"""
AbejaVerde·EO — App del Apicultor v4 (completa)
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from datetime import datetime
import random

st.set_page_config(page_title="AbejaVerde — Mi Apiario", page_icon="🐝", layout="centered")

st.markdown("""
<style>
/* BASE — letra grande para apicultores mayores */
html, body, [class*="css"] { font-size: 17px !important; }
.hdr{background:#132610;padding:18px 20px;border-radius:12px;
     display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.hdr-t{color:#F5A623;font-size:22px;font-weight:500}
.hdr-s{color:#9FE1CB;font-size:14px;margin-top:3px}
.ira-box{background:#132610;border-radius:14px;padding:20px;margin-bottom:16px}
.ac-v{background:#EAF3DE;border-left:5px solid #3B6D11;border-radius:0 10px 10px 0;padding:16px 18px;margin-bottom:11px}
.ac-a{background:#FAEEDA;border-left:5px solid #F5A623;border-radius:0 10px 10px 0;padding:16px 18px;margin-bottom:11px}
.ac-b{background:#E6F1FB;border-left:5px solid #185FA5;border-radius:0 10px 10px 0;padding:16px 18px;margin-bottom:11px}
.tit-v{color:#173404;font-size:17px;font-weight:600}
.tit-a{color:#412402;font-size:17px;font-weight:600}
.tit-b{color:#042C53;font-size:17px;font-weight:600}
.txt-v{color:#27500A;font-size:15px;line-height:1.7;margin-top:5px}
.txt-a{color:#633806;font-size:15px;line-height:1.7;margin-top:5px}
.txt-b{color:#185FA5;font-size:15px;line-height:1.7;margin-top:5px}
.sat-card{background:#132610;border-radius:11px;padding:16px;margin-bottom:12px}
.mision-box{background:#132610;border-radius:12px;padding:16px;margin-bottom:14px}
.puente-box{background:#FAEEDA;border-radius:12px;padding:16px;margin-bottom:14px;border:.5px solid #FAC775}
.frase-box{background:#132610;border-radius:12px;padding:18px;text-align:center;margin-top:10px}
.team-card{background:white;border-radius:12px;border:.5px solid #D3D1C7;overflow:hidden;margin-bottom:10px}
.piloto{background:#EAF3DE;color:#27500A;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:500}
.demo{background:#FAEEDA;color:#633806;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:500}
/* Métricas más grandes */
[data-testid="stMetricValue"] { font-size: 2.2rem !important; }
[data-testid="stMetricLabel"] { font-size: 1rem !important; }
/* Selectbox más grande */
.stSelectbox select { font-size: 16px !important; }
/* Botones más grandes */
.stButton button { font-size: 16px !important; padding: 12px 20px !important; }
/* Tabs más grandes */
.stTabs [data-baseweb="tab"] { font-size: 15px !important; padding: 10px 16px !important; }
/* Chat input más grande */
.stChatInput textarea { font-size: 16px !important; }
</style>
""", unsafe_allow_html=True)

MUNICIPIOS = {
    "San Juan de Rioseco ⭐ Piloto":{"ira":32,"titulo":"Riesgo moderado","desc":"Floración activa mayo 2026 (NDVI 0.667). ITA=35, IBA=31. Prepárese para la cosecha.","chips":["🌿 Floración activa","🛰️ ITA 35","👩‍🌾 IBA 31"],"real":True},
    "Guaduas":{"ira":28,"titulo":"Condiciones favorables","desc":"Buen mes. Monitoreo rutinario.","chips":["🌿 Vegetación alta"],"real":False},
    "Chaguaní":{"ira":52,"titulo":"Riesgo moderado-alto","desc":"Déficit hídrico persistente.","chips":["💧 Agua crítica","🌡️ Calor alto"],"real":False},
    "Beltrán":{"ira":44,"titulo":"Riesgo moderado","desc":"Floración activa pero agua escasa.","chips":["🌿 Floración","💧 Agua baja"],"real":False},
    "Pulí":{"ira":31,"titulo":"Condiciones normales","desc":"Estable. Sin alertas urgentes.","chips":["🌿 Estable"],"real":False},
    "Támesis, Antioquia":{"ira":22,"titulo":"Excelentes condiciones","desc":"Alta biodiversidad. Floración activa.","chips":["🌿 Óptimo"],"real":False},
    "La Unión, Nariño":{"ira":39,"titulo":"Riesgo moderado","desc":"Zona de transición.","chips":["🌡️ Variable"],"real":False},
    "Pitalito, Huila":{"ira":45,"titulo":"Alerta por sequía","desc":"Déficit de lluvia significativo.","chips":["💧 Sequía"],"real":False},
    "Tibasosa, Boyacá":{"ira":18,"titulo":"Condiciones óptimas","desc":"Muy buen mes. Prepare la cosecha.","chips":["🌿 NDVI alto"],"real":False},
    "Barichara, Santander":{"ira":33,"titulo":"Condiciones normales","desc":"Estable.","chips":["🌿 Normal"],"real":False},
}

FRASES = [
    ("\"Las abejas polinizan el 75% de los cultivos que alimentan al mundo.<br>Proteger una colmena es proteger la mesa de una familia.\"","— AbejaVerde·EO"),
    ("\"El satélite ve el territorio desde 800 km. El sensor mide la colmena desde adentro.<br>El apicultor ve lo que ninguna tecnología puede: el presente.\"","— AbejaVerde·EO"),
    ("\"Una colmena saludable no es solo miel. Es polinización de cultivos,<br>biodiversidad activa y resiliencia frente al cambio climático.\"","— AbejaVerde·EO"),
    ("\"Sin abejas no hay polinización, sin polinización no hay frutas,<br>sin frutas no hay seguridad alimentaria.\"","— PNUMA"),
    ("\"La apicultura de precisión no es para grandes empresas.<br>Es para los 163.215 apicultores que cuidan el ecosistema que nos alimenta.\"","— AbejaVerde·EO"),
    ("\"El conocimiento del apicultor, los datos del satélite y la respuesta de la colmena<br>— tres verdades que juntas protegen el alimento de Latinoamérica.\"","— AbejaVerde·EO"),
]

RESP_IA = {
    "alimentar":"Mayo 2026 muestra floración activa (NDVI 0.667). Sus colmenas probablemente tienen buenas reservas.\n\nAtención: diciembre 2025 y enero 2026 fueron críticos (NDVI 0.313 y 0.319 — los más bajos en 29 meses). Si sus colmenas pasaron ese período sin apoyo, revise las reservas. Si están livianas, alimente con jarabe 1:1 hasta que el peso se estabilice.",
    "enjambrar":"El riesgo es moderado-alto. Mayo fue tan bueno que las colonias crecieron rápido.\n\nBusque celdas de reina en los bordes del panal (parecen cacahuetes colgando). Si los cuadros del centro están más del 80% llenos, agregue un alza ya.",
    "cosechar":"Con floración activa en mayo 2026 (NDVI 0.667), el pico de cosecha en San Juan de Rioseco se espera entre junio y julio 2026 — consistente con el patrón de 2024 cuando junio fue el máximo histórico (0.817).\n\nCoseche cuando los cuadros del alza estén más del 80% operculados (sellados con cera blanca). No espere demasiado — cuando el NDVI baje en julio-agosto las abejas empiezan a consumir las reservas.",
    "agua":"El territorio mostró estrés hídrico severo en diciembre 2025 y enero 2026 (NDVI más bajos de los 29 meses). Mayo 2026 está mejor pero el patrón histórico muestra que julio-agosto son meses de riesgo.\n\nSus abejas necesitan 1L por colmena por día. Mantenga bebedero activo a menos de 200m. En los meses de julio-agosto esté atento — el sistema le avisará con 5 días de anticipación cuando el NDVI caiga.",
}

@st.cache_data
def cargar_iot():
    ruta_p = ROOT / "lecturas_pesos.csv"
    ruta_x = ROOT / "lecturas_exterior.csv"
    if ruta_p.exists():
        df_p = pd.read_csv(ruta_p, on_bad_lines="skip")
        df_x = pd.read_csv(ruta_x, on_bad_lines="skip") if ruta_x.exists() else pd.DataFrame()
        ult_p = df_p.iloc[-1]
        ult_x = df_x.iloc[-1] if not df_x.empty else None
        return {
            "real": True,
            "timestamp": str(ult_p.get("timestamp",""))[:16],
            "temp_interior": round(float(ult_p.get("temperatura", 22.2)), 1),
            "hum_interior":  round(float(ult_p.get("humedad", 66.3)), 1),
            "temp_exterior": round(float(ult_x.get("temp_exterior_C", 22.4)), 1) if ult_x is not None else 22.4,
            "bateria_v":     round(float(ult_x.get("campo_4", 2610)) / 1000 if ult_x is not None else 2.61, 2),
            "celdas_activas": sum(1 for c in ["c1","c11","c12","c13"] if c in ult_p.index and float(ult_p.get(c,0))>100),
        }
    return {"real":False,"timestamp":"2026-06-02 19:52","temp_interior":22.2,"hum_interior":66.3,"temp_exterior":22.4,"bateria_v":2.61,"celdas_activas":4}

if "muni"     not in st.session_state: st.session_state.muni     = "San Juan de Rioseco ⭐ Piloto"
if "chat"     not in st.session_state: st.session_state.chat     = []
if "frase_i"  not in st.session_state: st.session_state.frase_i  = random.randint(0, len(FRASES)-1)

iot  = cargar_iot()
muni = MUNICIPIOS[st.session_state.muni]

# Header
en_vivo = '<span style="color:#5DCAA5">● En vivo</span>' if iot["real"] else '<span style="color:#888780">● Demo</span>'
st.markdown(f'<div class="hdr"><div><div class="hdr-t">🐝 AbejaVerde·EO</div><div class="hdr-s">Alertas apícolas con inteligencia satelital</div></div><div style="color:#9FE1CB;font-size:12px">{en_vivo}</div></div>', unsafe_allow_html=True)

# Municipio
nuevo_muni = st.selectbox("Municipio", list(MUNICIPIOS.keys()), index=list(MUNICIPIOS.keys()).index(st.session_state.muni), label_visibility="collapsed")
if nuevo_muni != st.session_state.muni:
    st.session_state.muni = nuevo_muni
    st.rerun()
muni = MUNICIPIOS[st.session_state.muni]
badge = '<span class="piloto">⭐ Datos reales Copernicus · 29 meses procesados</span>' if muni["real"] else '<span class="demo">Demo · Proyección regional</span>'
st.markdown(badge, unsafe_allow_html=True)
st.divider()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Mi Apiario","📷 Mis Fotos","📡 Sensores","💬 Asesora IA","👩‍🌾 Nosotras"])

# ─── TAB 1 ───────────────────────────────────────────────────────────────────
with tab1:
    s = muni["ira"]
    c = "#A32D2D" if s>66 else "#854F0B" if s>33 else "#3B6D11"
    bg= "#FCEBEB" if s>66 else "#FAEEDA" if s>33 else "#EAF3DE"
    chips_html = "".join(f'<span style="background:#1A3A1A;color:#9FE1CB;padding:2px 7px;border-radius:20px;font-size:10px;margin-right:4px">{ch}</span>' for ch in muni["chips"])
    st.markdown(f'<div class="ira-box"><div style="display:flex;align-items:center;gap:18px"><div style="width:90px;height:90px;border-radius:50%;background:{bg};border:4px solid {c};display:flex;flex-direction:column;align-items:center;justify-content:center;flex-shrink:0"><div style="font-size:2.2rem;font-weight:600;color:{c};line-height:1">{s}</div><div style="font-size:11px;color:{c};font-weight:600">IRA</div></div><div><div style="color:#F5A623;font-size:18px;font-weight:600;margin-bottom:4px">{muni["titulo"]}</div><div style="color:#9FE1CB;font-size:14px;line-height:1.5;margin-bottom:7px">{muni["desc"]}</div>{chips_html}<div style="color:#5F5E5A;font-size:11px;margin-top:8px">🛰 Calculado con datos Sentinel-2 mayo 2026 · 29 meses de historia · Se actualiza cada 5 días</div></div></div></div>', unsafe_allow_html=True)

    st.markdown("**Alertas de hoy**")
    if muni["real"]:
        st.markdown('<div class="ac-v"><div class="tit-v">✅ Floración activa — no alimente</div><div class="txt-v">El satélite ve vegetación muy activa (NDVI 0.79). Sus abejas están recolectando. Si los cuadros están llenos al 80%, agregue un alza.</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="ac-b"><div class="tit-b">💧 Verifique el agua cerca del apiario</div><div class="txt-b">Solo 22mm de lluvia y el agua está al mínimo. Sus abejas necesitan 1L por colmena por día. Instale bebedero a menos de 200m.</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="ac-a"><div class="tit-a">☀️ Temperatura alta en el territorio</div><div class="txt-a">ERA5 registró temperatura inusual. Garantice sombra y agua. Si la colmena supera 37°C las larvas pueden morir.</div></div>', unsafe_allow_html=True)
    else:
        color_cls = "a" if muni["ira"]>40 else "v"
        ico = "⚠️" if muni["ira"]>40 else "✅"
        st.markdown(f'<div class="ac-{color_cls}"><div class="tit-{color_cls}">{ico} {muni["titulo"]}</div><div class="txt-{color_cls}">{muni["desc"]}</div></div>', unsafe_allow_html=True)

    st.divider()
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Temp. interior", f"{iot['temp_interior']}°C")
    with c2: st.metric("Humedad", f"{iot['hum_interior']:.0f}%")
    with c3: st.metric("Batería", f"{iot['bateria_v']:.2f}V")

# ─── TAB 2 FOTOS ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("**Suba una foto de su entorno**")
    st.caption("Sus fotos son la tercera fuente de datos del sistema — capturan lo que el satélite y el sensor no pueden ver.")
    tipo = st.radio("Tipo", ["🌸 Floración","💧 Agua","🐝 Colmena","🏔️ Paisaje"], horizontal=True, label_visibility="collapsed")
    tmap = {"🌸 Floración":"flora","💧 Agua":"agua","🐝 Colmena":"colmena","🏔️ Paisaje":"paisaje"}
    foto = st.file_uploader("Foto", type=["jpg","jpeg","png","webp"], label_visibility="collapsed")
    if foto:
        st.image(foto, use_column_width=True)
        if st.button("🔍 Analizar foto", type="primary"):
            with st.spinner("Analizando..."):
                import tempfile, os
                try:
                    from src.ingesta.foto_parser import analizar_foto_sin_api
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(foto.read())
                        ruta_tmp = tmp.name
                    res = analizar_foto_sin_api(ruta_tmp, tipo=tmap[tipo])
                    os.unlink(ruta_tmp)
                    st.success("✅ Análisis completado")
                    ca, cb = st.columns(2)
                    with ca:
                        t = tmap[tipo]
                        if t=="flora":
                            st.metric("Floración", str(res.get("estado_floracion","?")).upper())
                            st.metric("Valor melífero", str(res.get("valor_melifero","?")).upper())
                            st.metric("NDVI proxy", res.get("ndvi_proxy","?"))
                        elif t=="agua":
                            st.metric("Nivel", str(res.get("nivel_estimado","?")).upper())
                        elif t=="colmena":
                            st.metric("Actividad", str(res.get("actividad_piquera","?")).upper())
                        else:
                            st.metric("Cobertura", f"{res.get('cobertura_vegetal_pct',80)}%")
                            st.metric("NDVI proxy", res.get("ndvi_proxy","?"))
                    with cb:
                        st.info(res.get("impacto_ira",""))
                    st.success(res.get("recomendacion",""))
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.markdown('<div style="border:1.5px dashed #C0DD97;border-radius:10px;padding:24px;text-align:center;background:#F7FAF3"><div style="font-size:2rem;margin-bottom:8px">📷</div><div style="font-size:14px;font-weight:500;color:#132610">Toque aquí para subir una foto</div><div style="font-size:12px;color:#888780;margin-top:4px">JPG, PNG · Desde la cámara o galería</div></div>', unsafe_allow_html=True)

    ruta_obs = ROOT/"data"/"processed"/"observaciones_campo.csv"
    if ruta_obs.exists():
        df_obs = pd.read_csv(ruta_obs, on_bad_lines="skip")
        if not df_obs.empty:
            st.divider()
            st.markdown("**Fotos recientes:**")
            for _, r in df_obs.tail(5).iloc[::-1].iterrows():
                ico2 = {"flora":"🌸","agua":"💧","colmena":"🐝","paisaje":"🏔️"}.get(str(r.get("tipo_foto","")),"📷")
                rec  = str(r.get("recomendacion",""))[:70]
                ts   = str(r.get("timestamp",""))[:10]
                st.markdown(f'<div style="padding:7px 0;border-bottom:.5px solid #E5E2D9;font-size:13px">{ico2} <b>{str(r.get("tipo_foto","")).upper()}</b> · {ts}<br><span style="color:#5F5E5A;font-size:12px">{rec}...</span></div>', unsafe_allow_html=True)

# ─── TAB 3 SENSORES ──────────────────────────────────────────────────────────
with tab3:
    if iot["real"]:
        st.success(f"✅ Datos reales del nodo IoT — {iot['timestamp']}")
    else:
        st.warning("⚠️ Datos de demostración — conecte el nodo para ver datos reales")
    c1,c2 = st.columns(2)
    with c1:
        st.markdown("**Interior colmena**")
        st.metric("Temperatura", f"{iot['temp_interior']:.1f}°C")
        st.metric("Humedad", f"{iot['hum_interior']:.0f}%")
        st.metric("Celdas activas", f"{iot['celdas_activas']} de 22")
    with c2:
        st.markdown("**Exterior**")
        st.metric("Temperatura", f"{iot['temp_exterior']:.1f}°C")
        st.metric("Batería LiPo", f"{iot['bateria_v']:.2f}V")
    st.divider()
    st.markdown("**Datos satelitales Copernicus**")
    st.markdown('''<div class="sat-card">
      <div style="color:#9FE1CB;font-size:10px;font-weight:500;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px">
        29 meses reales · openEO / CDSE · San Juan de Rioseco · Ene 2024 – May 2026
      </div>
      <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:.5px solid #1A3A1A;font-size:13px">
        <span style="color:#9FE1CB">NDVI mayo 2026</span><span style="color:#5DCAA5;font-weight:500">0.667 — Floración activa</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:.5px solid #1A3A1A;font-size:13px">
        <span style="color:#9FE1CB">Pico histórico</span><span style="color:#5DCAA5;font-weight:500">0.817 — Jun 2024</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:.5px solid #1A3A1A;font-size:13px">
        <span style="color:#F09595">Mínimo histórico</span><span style="color:#F09595;font-weight:500">0.313 — Dic 2025 ⚠️</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:.5px solid #1A3A1A;font-size:13px">
        <span style="color:#9FE1CB">Feb 2026</span><span style="color:#5DCAA5;font-weight:500">0.782 — Floración alta</span>
      </div>
      <div style="margin-top:10px;padding-top:8px;border-top:.5px solid #2A3A2A">
        <div style="color:#F5A623;font-size:11px;font-weight:500;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px">
          Índices Arelys Camacho (mayo 2026)
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <div style="background:#1A3A1A;border-radius:8px;padding:8px;text-align:center">
            <div style="color:#F5A623;font-size:1.3rem;font-weight:500">35</div>
            <div style="color:#9FE1CB;font-size:10px">ITA — Satélite</div>
            <div style="color:#EF9F27;font-size:10px">Moderado</div>
          </div>
          <div style="background:#1A3A1A;border-radius:8px;padding:8px;text-align:center">
            <div style="color:#F5A623;font-size:1.3rem;font-weight:500">31</div>
            <div style="color:#9FE1CB;font-size:10px">IBA — Campo</div>
            <div style="color:#EF9F27;font-size:10px">Moderado</div>
          </div>
        </div>
        <div style="color:#9FE1CB;font-size:11px;margin-top:7px;line-height:1.5">
          ITA y IBA convergentes — condiciones similares en satélite y campo.
          Floración activa reduce el riesgo. Monitoree el agua.
        </div>
      </div>
    </div>''', unsafe_allow_html=True)
    st.caption("Sentinel-2 (NDVI/NDMI) + ERA5 (LST) · ITA/IBA propuesto por Arelys Camacho · openEO / CDSE")

# ─── TAB 4 ASESORA ───────────────────────────────────────────────────────────
with tab4:
    st.markdown("**Asesora AbejaVerde** — pregúntele sobre su apiario")
    st.caption("Respuestas basadas en datos reales de Copernicus e IoT.")
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"], avatar="👩‍🌾" if msg["role"]=="assistant" else "👤"):
            st.markdown(msg["content"])
    if not st.session_state.chat:
        with st.chat_message("assistant", avatar="👩‍🌾"):
            st.markdown("Hola. Soy la asesora de AbejaVerde. Analicé los datos de su apiario. ¿Qué quiere saber sobre sus colmenas hoy?")
    c1,c2 = st.columns(2)
    with c1:
        if st.button("🍯 ¿Debo alimentar?"):
            st.session_state.chat += [{"role":"user","content":"¿Debo alimentar esta semana?"},{"role":"assistant","content":RESP_IA["alimentar"]}]; st.rerun()
        if st.button("💧 ¿Cómo manejo el agua?"):
            st.session_state.chat += [{"role":"user","content":"¿Cómo manejo el agua?"},{"role":"assistant","content":RESP_IA["agua"]}]; st.rerun()
    with c2:
        if st.button("🐝 ¿Riesgo de enjambrazón?"):
            st.session_state.chat += [{"role":"user","content":"¿Hay riesgo de enjambrazón?"},{"role":"assistant","content":RESP_IA["enjambrar"]}]; st.rerun()
        if st.button("🫙 ¿Cuándo cosechar?"):
            st.session_state.chat += [{"role":"user","content":"¿Cuándo cosechar?"},{"role":"assistant","content":RESP_IA["cosechar"]}]; st.rerun()
    preg = st.chat_input("Escriba su pregunta...")
    if preg:
        tl = preg.lower()
        if   "aliment" in tl: r = RESP_IA["alimentar"]
        elif "enjambr" in tl: r = RESP_IA["enjambrar"]
        elif "cosech"  in tl or "miel" in tl: r = RESP_IA["cosechar"]
        elif "agua"    in tl or "bebed" in tl: r = RESP_IA["agua"]
        else: r = "Use los botones de arriba para las preguntas más frecuentes, o amplíe su pregunta con más contexto."
        st.session_state.chat += [{"role":"user","content":preg},{"role":"assistant","content":r}]; st.rerun()
    if st.session_state.chat and st.button("Limpiar"):
        st.session_state.chat = []; st.rerun()

# ─── TAB 5 NOSOTRAS ──────────────────────────────────────────────────────────
with tab5:
    st.markdown('<div class="mision-box"><div style="color:#F5A623;font-size:14px;font-weight:500;margin-bottom:7px">¿Qué es AbejaVerde·EO?</div><div style="color:#9FE1CB;font-size:12px;line-height:1.7">Un sistema de <b style="color:#F5A623">alertas tempranas ecosistémicas</b> que combina satélites Copernicus con sensores IoT en colmenas reales. Las abejas registran estrés ecosistémico antes de que sea visible en la producción agrícola.<br><br>Dos fuentes de datos, una sola alerta, en lenguaje que el apicultor entiende.</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="puente-box"><div style="color:#412402;font-size:13px;font-weight:500;margin-bottom:5px">🌉 El apicultor: el puente insustituible</div><div style="color:#633806;font-size:12px;line-height:1.7">El satélite ve el territorio desde 800 km. El sensor mide la colmena desde adentro. Pero ninguno sabe que la acacia amarilla a 50 metros del apiario empezó a florecer hoy, o que la quebrada bajó esta semana. <b>El apicultor ve lo que la tecnología no puede:</b> sus fotos y observaciones son la tercera fuente de datos del sistema — la más cercana, la más oportuna, la más humana.</div></div>', unsafe_allow_html=True)
    st.markdown("**El equipo**")
    c1,c2 = st.columns(2)
    with c1: st.markdown('<div class="team-card"><div style="height:110px;background:#132610;display:flex;align-items:center;justify-content:center;font-size:2.5rem;opacity:.5">👩‍🌾</div><div style="padding:12px"><div style="font-size:13px;font-weight:500;color:#132610">Arelys Camacho</div><div style="font-size:11px;color:#888780">Ing. química · Apicultora</div><div style="font-size:11px;color:#5F5E5A;margin-top:5px;line-height:1.5">Apiario piloto en San Juan de Rioseco. Conoce las floraciones de los Andes colombianos por nombre. Es los ojos y las manos del sistema en campo.</div></div></div>', unsafe_allow_html=True)
    with c2: st.markdown('<div class="team-card"><div style="height:110px;background:#132610;display:flex;align-items:center;justify-content:center;font-size:2.5rem;opacity:.5">👩‍💻</div><div style="padding:12px"><div style="font-size:13px;font-weight:500;color:#132610">Mireya Camacho</div><div style="font-size:11px;color:#888780">Abogada · Científica de datos</div><div style="font-size:11px;color:#5F5E5A;margin-top:5px;line-height:1.5">Análisis geoespacial y sistemas de alerta. Llegó a la apicultura por la familia — y por eso entiende el problema desde adentro.</div></div></div>', unsafe_allow_html=True)
    st.divider()
    frase, autor = FRASES[st.session_state.frase_i]
    st.markdown(f'<div class="frase-box"><div style="color:#F5A623;font-size:13px;font-weight:500;line-height:1.8">{frase}</div><div style="color:#9FE1CB;font-size:11px;margin-top:6px">{autor} · AbejaVerde·EO · CopernicusLAC Hackathon 2026</div></div>', unsafe_allow_html=True)
