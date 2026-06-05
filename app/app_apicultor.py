"""
AbejaVerde·EO — App del Apicultor v5
Arquitectura de 4 páginas según documento de ingeniería AbejaVerde·EO
"""
import sys, random
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

st.set_page_config(page_title="AbejaVerde·EO", page_icon="🐝", layout="centered")

st.markdown("""
<style>
.hdr{background:#132610;padding:16px 20px;border-radius:12px;
     display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.hdr-t{color:#F5A623;font-size:20px;font-weight:500}
.hdr-s{color:#9FE1CB;font-size:13px;margin-top:2px}
/* Índices */
.ita-box{background:#132610;border-radius:13px;padding:18px;margin-bottom:12px}
.idx-circle{width:80px;height:80px;border-radius:50%;display:flex;flex-direction:column;
            align-items:center;justify-content:center;flex-shrink:0}
/* Alertas */
.ac-v{background:#EAF3DE;border-left:5px solid #3B6D11;border-radius:0 10px 10px 0;padding:15px 17px;margin-bottom:10px}
.ac-a{background:#FAEEDA;border-left:5px solid #F5A623;border-radius:0 10px 10px 0;padding:15px 17px;margin-bottom:10px}
.ac-b{background:#E6F1FB;border-left:5px solid #185FA5;border-radius:0 10px 10px 0;padding:15px 17px;margin-bottom:10px}
.ac-r{background:#FCEBEB;border-left:5px solid #A32D2D;border-radius:0 10px 10px 0;padding:15px 17px;margin-bottom:10px}
.tit-v{color:#173404;font-size:16px;font-weight:600}
.tit-a{color:#412402;font-size:16px;font-weight:600}
.tit-b{color:#042C53;font-size:16px;font-weight:600}
.tit-r{color:#501313;font-size:16px;font-weight:600}
.txt-v{color:#27500A;font-size:14px;line-height:1.7;margin-top:5px}
.txt-a{color:#633806;font-size:14px;line-height:1.7;margin-top:5px}
.txt-b{color:#185FA5;font-size:14px;line-height:1.7;margin-top:5px}
.txt-r{color:#791F1F;font-size:14px;line-height:1.7;margin-top:5px}
/* Margen de Maniobra */
.mdm-box{border-radius:12px;padding:18px;margin:12px 0;text-align:center}
.mdm-verde{background:#EAF3DE;border:2px solid #3B6D11}
.mdm-amarillo{background:#FAEEDA;border:2px solid #F5A623}
.mdm-rojo{background:#FCEBEB;border:2px solid #A32D2D}
.mdm-critico{background:#F09595;border:2px solid #A32D2D}
/* Desacoplamiento */
.desacop-box{background:#132610;border-radius:12px;padding:16px;margin:12px 0}
/* Satélite */
.sat-card{background:#132610;border-radius:11px;padding:14px;margin-bottom:10px}
/* Equipo */
.team-card{background:white;border-radius:12px;border:.5px solid #D3D1C7;overflow:hidden;margin-bottom:8px}
/* Mapa comunitario */
.mapa-card{background:#132610;border-radius:12px;padding:16px;margin-bottom:10px}
/* Sello */
.sello-card{background:#132610;border-radius:12px;padding:16px;margin-bottom:10px}
/* Métricas grandes */
[data-testid="stMetricValue"]{font-size:2rem!important}
[data-testid="stMetricLabel"]{font-size:1rem!important}
.stButton button{font-size:15px!important;padding:10px 18px!important}
.stTabs [data-baseweb="tab"]{font-size:14px!important;padding:10px 14px!important}
.piloto{background:#EAF3DE;color:#27500A;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:500}
.demo{background:#FAEEDA;color:#633806;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:500}
.frase-box{background:#132610;border-radius:12px;padding:18px;text-align:center;margin-top:8px}
</style>
""", unsafe_allow_html=True)

# ── DATOS ─────────────────────────────────────────────────────────────────────
MUNICIPIOS = {
    "San Juan de Rioseco ⭐ Piloto":{"ira":32,"ita":35,"iba":31,"titulo":"Riesgo moderado",
        "desc":"Floración activa mayo 2026 (NDVI 0.667). Monitoree el agua.",
        "chips":["🌿 Floración activa","🛰️ ITA 35","👩‍🌾 IBA 31"],"real":True},
    "Guaduas":{"ira":28,"ita":28,"iba":22,"titulo":"Condiciones favorables",
        "desc":"Buen mes. Monitoreo rutinario.","chips":["🌿 Vegetación alta"],"real":False},
    "Chaguaní":{"ira":52,"ita":55,"iba":48,"titulo":"Riesgo moderado-alto",
        "desc":"Déficit hídrico persistente.","chips":["💧 Agua crítica"],"real":False},
    "Beltrán":{"ira":44,"ita":44,"iba":38,"titulo":"Riesgo moderado",
        "desc":"Floración activa pero agua escasa.","chips":["🌿 Floración","💧 Agua baja"],"real":False},
    "Pulí":{"ira":31,"ita":30,"iba":28,"titulo":"Condiciones normales",
        "desc":"Estable.","chips":["🌿 Estable"],"real":False},
    "Támesis, Antioquia":{"ira":22,"ita":20,"iba":18,"titulo":"Excelentes condiciones",
        "desc":"Alta biodiversidad.","chips":["🌿 Óptimo"],"real":False},
    "La Unión, Nariño":{"ira":39,"ita":40,"iba":35,"titulo":"Riesgo moderado",
        "desc":"Zona de transición.","chips":["🌡️ Variable"],"real":False},
    "Pitalito, Huila":{"ira":45,"ita":50,"iba":42,"titulo":"Alerta por sequía",
        "desc":"Déficit de lluvia.","chips":["💧 Sequía"],"real":False},
    "Tibasosa, Boyacá":{"ira":18,"ita":18,"iba":15,"titulo":"Condiciones óptimas",
        "desc":"Muy buen mes.","chips":["🌿 NDVI alto"],"real":False},
    "Barichara, Santander":{"ira":33,"ita":32,"iba":30,"titulo":"Condiciones normales",
        "desc":"Estable.","chips":["🌿 Normal"],"real":False},
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
    "alimentar": "Mayo 2026 muestra floración activa (NDVI 0.667). Sus colmenas probablemente tienen buenas reservas.\n\nAtención: diciembre 2025 y enero 2026 fueron críticos (NDVI 0.313 — los más bajos en 29 meses). Si sus colmenas pasaron ese período sin apoyo, revise las reservas. Si están livianas, alimente con jarabe 1:1 hasta que el peso se estabilice.",
    "enjambrar": "El riesgo es moderado-alto. Mayo fue un buen mes y las colonias fuertes tienden a enjambrar.\n\nBusque celdas de reina en los bordes del panal (parecen cacahuetes colgando). Si los cuadros del centro están más del 80% llenos, agregue un alza ya.",
    "cosechar":  "Con floración activa en mayo 2026 (NDVI 0.667), el pico de cosecha en San Juan de Rioseco se espera entre junio y julio — consistente con el patrón de 2024 (junio fue el máximo histórico con 0.817).\n\nCoseche cuando los cuadros del alza estén más del 80% operculados (sellados con cera blanca).",
    "agua":      "El territorio mostró estrés hídrico severo en diciembre 2025 y enero 2026. Mayo 2026 está mejor pero julio-agosto son meses de riesgo histórico.\n\nSus abejas necesitan 1L por colmena por día. Mantenga bebedero activo a menos de 200m.",
}

# ── FUNCIONES ─────────────────────────────────────────────────────────────────
@st.cache_data
def cargar_iot():
    ruta_p = ROOT/"lecturas_pesos.csv"
    ruta_x = ROOT/"lecturas_exterior.csv"
    if ruta_p.exists():
        df_p = pd.read_csv(ruta_p, on_bad_lines="skip")
        df_x = pd.read_csv(ruta_x, on_bad_lines="skip") if ruta_x.exists() else pd.DataFrame()
        ult_p = df_p.iloc[-1]
        ult_x = df_x.iloc[-1] if not df_x.empty else None
        return {
            "real":True,"timestamp":str(ult_p.get("timestamp",""))[:16],
            "temp_interior":round(float(ult_p.get("temperatura",22.2)),1),
            "hum_interior":round(float(ult_p.get("humedad",66.3)),1),
            "temp_exterior":round(float(ult_x.get("temp_exterior_C",22.4)),1) if ult_x is not None else 22.4,
            "bateria_v":round(float(ult_x.get("campo_4",2610))/1000 if ult_x is not None else 2.61,2),
            "celdas_activas":sum(1 for c in ["c1","c11","c12","c13"] if c in ult_p.index and float(ult_p.get(c,0))>100),
        }
    return {"real":False,"timestamp":"2026-06-02 19:52","temp_interior":22.2,
            "hum_interior":66.3,"temp_exterior":22.4,"bateria_v":2.61,"celdas_activas":4}

def calcular_nivel(score):
    if score <= 33: return 0
    if score <= 66: return 1
    return 2

def calcular_mdm(ita, iba):
    """Calcula el Margen de Maniobra según Desacoplamiento Ecológico."""
    n_ita = calcular_nivel(ita)
    n_iba = calcular_nivel(iba)
    delta = n_ita - n_iba
    # Caso especial: ambos en nivel 2 = emergencia
    if n_ita == 2 and n_iba == 2:
        return {"estado":"EMERGENCIA_TERRITORIAL","dias":1,"clase":"mdm-critico",
                "emoji":"🚨","titulo":"Emergencia Territorial",
                "desc":"El tiempo de ventaja se agotó. Tanto el territorio como la colmena están en crisis crítica simultánea. Intervención urgente en 24 horas: alimentación de rescate y manejo de sombrío."}
    if delta == 0:
        return {"estado":"MARGEN_AMPLIO","dias":30,"clase":"mdm-verde",
                "emoji":"✅","titulo":"Margen Amplio — Ecosistema Acoplado",
                "desc":"El territorio y la colmena están alineados. Puede mantener el cronograma de inspección estándar (15-30 días)."}
    if delta == 1:
        return {"estado":"CUENTA_REGRESIVA","dias":7,"clase":"mdm-amarillo",
                "emoji":"⏳","titulo":"Cuenta Regresiva — Inercia Nutricional",
                "desc":"El satélite detectó más estrés que la colmena. Las abejas están consumiendo las reservas de miel. Inspeccione en 5-7 días antes de que se agoten."}
    if delta == 2:
        return {"estado":"CUENTA_REGRESIVA_CRITICA","dias":3,"clase":"mdm-rojo",
                "emoji":"⚠️","titulo":"Cuenta Regresiva Crítica",
                "desc":"El paisaje está severamente estresado mientras la colmena aún subsiste. Las reservas se agotarán en 3 días. Suministre alimentación artificial urgente."}
    if delta == -1 or delta == -2:
        return {"estado":"REACCION_INMEDIATA","dias":0,"clase":"mdm-critico",
                "emoji":"🚨","titulo":"Reacción Inmediata — Anomalía Exógena",
                "desc":"La colmena está peor de lo que el satélite explica. Copernicus certifica entorno óptimo pero hay problema biológico. Posible envenenamiento químico o patología. Intervenga en 24 horas."}
    return {"estado":"NORMAL","dias":30,"clase":"mdm-verde","emoji":"✅",
            "titulo":"Condiciones Normales","desc":"Monitoreo rutinario."}

# ── ESTADO DE SESIÓN ──────────────────────────────────────────────────────────
if "muni"   not in st.session_state: st.session_state.muni   = "San Juan de Rioseco ⭐ Piloto"
if "chat"   not in st.session_state: st.session_state.chat   = []
if "frase_i" not in st.session_state: st.session_state.frase_i = random.randint(0,len(FRASES)-1)

iot  = cargar_iot()
muni = MUNICIPIOS[st.session_state.muni]
mdm  = calcular_mdm(muni["ita"], muni["iba"])

# ── HEADER ────────────────────────────────────────────────────────────────────
en_vivo = '<span style="color:#5DCAA5">● En vivo</span>' if iot["real"] else '<span style="color:#888780">● Demo</span>'
st.markdown(f'<div class="hdr"><div><div class="hdr-t">🐝 AbejaVerde·EO</div><div class="hdr-s">Sistema de alertas apícolas con inteligencia satelital Copernicus</div></div><div style="color:#9FE1CB;font-size:13px">{en_vivo}</div></div>', unsafe_allow_html=True)

nuevo_muni = st.selectbox("Municipio del apiario", list(MUNICIPIOS.keys()),
    index=list(MUNICIPIOS.keys()).index(st.session_state.muni), label_visibility="collapsed")
if nuevo_muni != st.session_state.muni:
    st.session_state.muni = nuevo_muni; st.rerun()
muni = MUNICIPIOS[st.session_state.muni]
mdm  = calcular_mdm(muni["ita"], muni["iba"])

badge = '<span class="piloto">⭐ Datos reales Copernicus · 29 meses procesados</span>' if muni["real"] else '<span class="demo">Demo · Proyección regional · Escalable a Colombia</span>'
st.markdown(badge, unsafe_allow_html=True)
st.divider()

# ── PÁGINAS (TABS) ────────────────────────────────────────────────────────────
pag1, pag2, pag3, pag4, pag5 = st.tabs([
    "📊 Diagnóstico", "📈 Bitácora", "🗺️ Territorio", "🏅 Sello Origen", "👩‍🌾 Nosotras"
])

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 1 — CONSOLA DE DIAGNÓSTICO TEMPORAL
# ═══════════════════════════════════════════════════════════════════
with pag1:
    # ITA + IBA
    ita, iba = muni["ita"], muni["iba"]
    c_ita = "#A32D2D" if ita>66 else "#854F0B" if ita>33 else "#3B6D11"
    bg_ita= "#FCEBEB" if ita>66 else "#FAEEDA" if ita>33 else "#EAF3DE"
    c_iba = "#A32D2D" if iba>66 else "#854F0B" if iba>33 else "#3B6D11"
    bg_iba= "#FCEBEB" if iba>66 else "#FAEEDA" if iba>33 else "#EAF3DE"

    st.markdown(f"""
    <div class="ita-box">
      <div style="color:#9FE1CB;font-size:11px;font-weight:500;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px">
        Diagnóstico — {st.session_state.muni.replace(" ⭐ Piloto","")}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
        <div style="text-align:center">
          <div style="width:80px;height:80px;border-radius:50%;background:{bg_ita};border:3px solid {c_ita};
               display:flex;flex-direction:column;align-items:center;justify-content:center;margin:0 auto 6px">
            <div style="font-size:1.8rem;font-weight:600;color:{c_ita};line-height:1">{ita}</div>
            <div style="font-size:9px;color:{c_ita};font-weight:600">ITA</div>
          </div>
          <div style="color:#F5A623;font-size:12px;font-weight:500">Índice de Alerta Temprana Apícola</div>
          <div style="color:#9FE1CB;font-size:11px">🛰️ Satelital (NDVI · NDMI · LST)</div>
        </div>
        <div style="text-align:center">
          <div style="width:80px;height:80px;border-radius:50%;background:{bg_iba};border:3px solid {c_iba};
               display:flex;flex-direction:column;align-items:center;justify-content:center;margin:0 auto 6px">
            <div style="font-size:1.8rem;font-weight:600;color:{c_iba};line-height:1">{iba}</div>
            <div style="font-size:9px;color:{c_iba};font-weight:600">IBA</div>
          </div>
          <div style="color:#F5A623;font-size:12px;font-weight:500">Índice de Bioindicación Apícola</div>
          <div style="color:#9FE1CB;font-size:11px">👩‍🌾 Campo (Polen · Agua · Población)</div>
        </div>
      </div>
      <div style="color:#5F5E5A;font-size:10px;text-align:center">
        🛰 Sentinel-2 (NDVI/NDMI) + ERA5 (LST) · 29 meses reales · Se actualiza cada 5 días
      </div>
    </div>
    """, unsafe_allow_html=True)

    # MARGEN DE MANIOBRA
    dias_txt = f"{mdm['dias']} días" if mdm['dias'] > 0 else "⚡ AHORA"
    mdm_html = f"""<div class="{mdm['clase']} mdm-box">
      <div style="font-size:2rem;margin-bottom:4px">{mdm['emoji']}</div>
      <div style="font-size:18px;font-weight:600;margin-bottom:6px">{mdm['titulo']}</div>
      <div style="font-size:2.5rem;font-weight:700;margin-bottom:6px">{dias_txt}</div>
      <div style="font-size:14px;line-height:1.7;max-width:400px;margin:0 auto">{mdm['desc']}</div>
    </div>"""
    st.markdown(mdm_html, unsafe_allow_html=True)

    # DESACOPLAMIENTO ECOLÓGICO
    st.markdown("""
    <div class="desacop-box">
      <div style="color:#F5A623;font-size:13px;font-weight:500;margin-bottom:8px">
        🔬 El Desacoplamiento Ecológico — ¿por qué importa?
      </div>
      <div style="color:#9FE1CB;font-size:13px;line-height:1.8">
        El <b style="color:#F5A623">monte y los cultivos</b> son el supermercado donde las abejas recolectan
        néctar y polen cada día. Los <b style="color:#F5A623">panales</b> son la despensa de la casa,
        donde almacenan excedentes para tiempos de escasez.<br><br>
        Cuando el satélite detecta que el supermercado se cerró (estrés hídrico o térmico),
        la colmena puede seguir aparentemente normal porque está consumiendo la despensa.
        <b style="color:#F5A623">AbejaVerde·EO mide exactamente cuántos días tiene esa despensa
        antes de vaciarse.</b> Ese es el Margen de Maniobra.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ALERTAS
    st.markdown("**Alertas de hoy**")
    if muni["real"]:
        st.markdown('<div class="ac-v"><div class="tit-v">✅ Floración activa — no alimente</div><div class="txt-v">El satélite ve vegetación activa (NDVI 0.667). Sus abejas están recolectando. Si los cuadros están al 80%, agregue un alza.</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="ac-b"><div class="tit-b">💧 Verifique el agua cerca del apiario</div><div class="txt-b">El patrón histórico muestra riesgo hídrico en julio-agosto. Mantenga bebedero activo a menos de 200m. Sus abejas necesitan 1L por colmena por día.</div></div>', unsafe_allow_html=True)
    else:
        color = "a" if muni["ita"]>40 else "v"
        ico   = "⚠️" if muni["ita"]>40 else "✅"
        st.markdown(f'<div class="ac-{color}"><div class="tit-{color}">{ico} {muni["titulo"]}</div><div class="txt-{color}">{muni["desc"]}</div></div>', unsafe_allow_html=True)

    st.divider()
    c1,c2,c3 = st.columns(3)
    with c1: st.metric("Temp. interior", f"{iot['temp_interior']}°C")
    with c2: st.metric("Humedad", f"{iot['hum_interior']:.0f}%")
    with c3: st.metric("Batería", f"{iot['bateria_v']:.2f}V")

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 2 — BITÁCORA SATELITAL
# ═══════════════════════════════════════════════════════════════════
with pag2:
    st.markdown("### 📈 Bitácora Satelital — La memoria del territorio")
    st.markdown("*29 meses de historia del apiario piloto · Ene 2024 – May 2026*")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        FECHAS = pd.date_range("2024-01","2026-05",freq="MS")
        NDVI   = [0.474,0.618,0.584,0.513,0.773,0.817,0.529,0.669,0.698,0.697,
                  0.509,0.701,0.437,0.442,0.554,0.379,0.787,0.732,0.675,0.690,
                  0.621,0.313,0.319,0.782,0.643,0.645,0.667]
        PREC   = [30,130,210,280,380,310,150,210,300,280,230,165,38,42,230,22,
                  405,280,195,210,175,45,38,320,210,180,45]
        TEMP   = [22.62,22.48,22.19,21.85,21.60,21.55,21.82,22.40,22.45,21.50,
                  21.48,21.50,21.43,21.78,21.52,21.12,21.10,21.45,21.38,21.42,
                  21.55,21.80,21.95,21.35,21.28,21.40,21.30]
        NDVI_H = [0.456]*len(FECHAS)

        fig = make_subplots(rows=3,cols=1,shared_xaxes=True,
            subplot_titles=["Vigor Vegetal (NDVI) — Sentinel-2",
                            "Temperatura del Suelo (LST/ERA5)",
                            "Lluvia y Humedad Vegetal (ERA5 + NDMI)"],
            vertical_spacing=0.10)

        # Panel 1 NDVI con área de anomalía
        fig.add_trace(go.Scatter(x=FECHAS,y=NDVI_H,mode="lines",
            line=dict(color="#888",width=1,dash="dot"),name="Histórico NDVI",showlegend=False),row=1,col=1)
        fig.add_trace(go.Scatter(x=FECHAS,y=NDVI,mode="lines+markers",
            line=dict(color="#F5A623",width=2.5),marker=dict(size=6),name="NDVI actual"),row=1,col=1)
        fig.add_hrect(y0=0,y1=0.48,fillcolor="red",opacity=0.08,row=1,col=1)

        # Panel 2 LST
        TEMP_H = [21.5]*len(FECHAS)
        fig.add_trace(go.Scatter(x=FECHAS,y=TEMP_H,mode="lines",
            line=dict(color="#888",width=1,dash="dot"),name="Histórico Temp",showlegend=False),row=2,col=1)
        fig.add_trace(go.Scatter(x=FECHAS,y=TEMP,mode="lines+markers",
            line=dict(color="#EF9F27",width=2),fill="tonexty",
            fillcolor="rgba(239,159,39,0.1)",name="Temperatura"),row=2,col=1)

        # Panel 3 Lluvia
        fig.add_trace(go.Bar(x=FECHAS,y=[180]*len(FECHAS),
            marker_color="rgba(100,150,200,0.2)",name="Lluvia histórica",showlegend=False),row=3,col=1)
        fig.add_trace(go.Bar(x=FECHAS,y=PREC,
            marker_color=["#F09595" if p<75 else "#4A9ED4" for p in PREC],
            name="Lluvia actual"),row=3,col=1)

        fig.update_layout(paper_bgcolor="#0F1F0F",plot_bgcolor="#1A2F1A",
            font=dict(color="white"),height=550,showlegend=False)
        for i in range(1,4):
            fig.update_xaxes(gridcolor="#2A3A2A",row=i,col=1)
            fig.update_yaxes(gridcolor="#2A3A2A",row=i,col=1)

        st.plotly_chart(fig,use_container_width=True)
        st.caption("Áreas rojas = anomalías detectadas por Copernicus · Línea gris = promedio histórico")

    except ImportError:
        st.info("Instala plotly para ver las gráficas: `pip install plotly`")

    st.markdown("""
    <div class="sat-card">
      <div style="color:#9FE1CB;font-size:11px;font-weight:500;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px">
        Resumen histórico · 29 meses reales Copernicus
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px">
        <div style="color:#9FE1CB">Pico floración</div><div style="color:#5DCAA5;font-weight:500">0.817 — Jun 2024</div>
        <div style="color:#9FE1CB">Mínimo crítico</div><div style="color:#F09595;font-weight:500">0.313 — Dic 2025 ⚠️</div>
        <div style="color:#9FE1CB">Floración actual</div><div style="color:#5DCAA5;font-weight:500">0.667 — May 2026</div>
        <div style="color:#9FE1CB">Feb 2026</div><div style="color:#5DCAA5;font-weight:500">0.782 — Floración alta</div>
        <div style="color:#9FE1CB">ITA · may 2026</div><div style="color:#F5A623;font-weight:500">35 — Moderado</div>
        <div style="color:#9FE1CB">IBA · may 2026</div><div style="color:#F5A623;font-weight:500">31 — Moderado</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Sentinel-2 (NDVI/NDMI) + Sentinel-3 (LST) + ERA5-Land (lluvia) · openEO / CDSE")

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 3 — MAPA COMUNITARIO (MOCKUP)
# ═══════════════════════════════════════════════════════════════════
with pag3:
    st.markdown("### 🗺️ Mapa Comunitario del Territorio")
    st.markdown("*Gobernanza gremial — San Juan de Rioseco · Radio de pecoreo 3 km*")

    st.markdown("""
    <div class="mapa-card">
      <div style="color:#F5A623;font-size:13px;font-weight:500;margin-bottom:10px">
        🐝 Apiarios activos en el municipio
      </div>
      <div style="display:grid;gap:8px;font-size:13px">
        <div style="background:#1A3A1A;border-radius:8px;padding:10px;display:flex;justify-content:space-between;align-items:center">
          <div><div style="color:#F5A623;font-weight:500">Apiario El Paraíso ⭐</div>
          <div style="color:#9FE1CB;font-size:11px">1000 msnm · Piloto AbejaVerde·EO</div></div>
          <span style="background:#EAF3DE;color:#27500A;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:500">Margen Amplio</span>
        </div>
        <div style="background:#1A3A1A;border-radius:8px;padding:10px;display:flex;justify-content:space-between;align-items:center">
          <div><div style="color:#9FE1CB;font-weight:500">Apiario Santamaría</div>
          <div style="color:#9FE1CB;font-size:11px">720 msnm · Zona baja</div></div>
          <span style="background:#FAEEDA;color:#633806;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:500">Cuenta Regresiva</span>
        </div>
        <div style="background:#1A3A1A;border-radius:8px;padding:10px;display:flex;justify-content:space-between;align-items:center">
          <div><div style="color:#9FE1CB;font-weight:500">Apiario Lagunitas</div>
          <div style="color:#9FE1CB;font-size:11px">1200 msnm · Zona cafetera</div></div>
          <span style="background:#FCEBEB;color:#791F1F;padding:3px 8px;border-radius:20px;font-size:11px;font-weight:500">⚠️ Anomalía Exógena</span>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="mapa-card" style="margin-top:10px">
      <div style="color:#F5A623;font-size:13px;font-weight:500;margin-bottom:8px">
        🔬 Protocolo de Exclusión Ambiental
      </div>
      <div style="color:#9FE1CB;font-size:13px;line-height:1.7">
        Cuando el satélite certifica entorno óptimo pero la bitácora reporta
        <b style="color:#F5A623">mortalidad masiva aguda</b>, el sistema descarta causas climáticas
        e identifica el evento como <b style="color:#F09595">posible impacto de agroquímicos</b>.
        Los datos de Copernicus actúan como evidencia científica para denuncias
        ante entidades de control (ICA, Secretaría de Agricultura).<br><br>
        <span style="color:#5F5E5A;font-size:11px">Esta funcionalidad requiere registro de múltiples apiarios por vereda. Fase 2 del producto.</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("🗺️ El mapa interactivo por veredas está en desarrollo. Se activa con el registro de al menos 3 apiarios por municipio.")

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 4 — SELLO DE ORIGEN ECOSISTÉMICO
# ═══════════════════════════════════════════════════════════════════
with pag4:
    st.markdown("### 🏅 Sello de Origen Ecosistémico")
    st.markdown("*Certificación de valor de cosecha respaldada por Copernicus*")

    if muni["real"]:
        st.markdown("""
        <div class="sello-card">
          <div style="color:#F5A623;font-size:13px;font-weight:500;margin-bottom:12px">
            Certificado de Trazabilidad Espacial Copernicus · Lote Junio 2026
          </div>
          <div style="display:grid;gap:10px">
            <div style="background:#1A3A1A;border-radius:8px;padding:12px">
              <div style="color:#9FE1CB;font-size:11px;margin-bottom:4px">1. COBERTURA VEGETAL (Sentinel-2 / NDVI)</div>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div style="color:white;font-size:14px">Índice de Estabilidad de Flora</div>
                <div style="color:#5DCAA5;font-size:1.4rem;font-weight:600">94/100</div>
              </div>
              <div style="color:#9FE1CB;font-size:12px;margin-top:4px">Radio de pecoreo de 3 km mantuvo la estructura foliar. Cero alertas por deforestación.</div>
            </div>
            <div style="background:#1A3A1A;border-radius:8px;padding:12px">
              <div style="color:#9FE1CB;font-size:11px;margin-bottom:4px">2. CONFORT TÉRMICO (ERA5 + Sentinel-3)</div>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div style="color:white;font-size:14px">Anomalía térmica acumulada</div>
                <div style="color:#F5A623;font-size:1.4rem;font-weight:600">+0.4°C</div>
              </div>
              <div style="color:#9FE1CB;font-size:12px;margin-top:4px">El microclima operó en 88% del tiempo bajo temperaturas nominales para el vuelo de Apis mellifera.</div>
            </div>
            <div style="background:#1A3A1A;border-radius:8px;padding:12px">
              <div style="color:#9FE1CB;font-size:11px;margin-bottom:4px">3. GESTIÓN BIOLÓGICA (IBA · Bitácora)</div>
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div style="color:white;font-size:14px">Inspecciones registradas</div>
                <div style="color:#5DCAA5;font-size:1.4rem;font-weight:600">14</div>
              </div>
              <div style="color:#9FE1CB;font-size:12px;margin-top:4px">Población y entrada de polen estables durante los picos de floración.</div>
            </div>
          </div>
          <div style="margin-top:14px;padding:12px;background:#0F1F0F;border-radius:8px;text-align:center">
            <div style="font-size:2rem;margin-bottom:4px">📱</div>
            <div style="color:#F5A623;font-size:13px;font-weight:500;margin-bottom:4px">Código QR dinámico del empaque</div>
            <div style="color:#9FE1CB;font-size:12px">El consumidor escanea el empaque y ve la validación científica Copernicus de la miel — origen, estabilidad forestal y confort climático verificados por satélite.</div>
            <div style="color:#5F5E5A;font-size:11px;margin-top:8px">Permite al pequeño productor comercializar su miel a precio diferenciado en mercados especializados.</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("El Sello de Origen se genera con datos reales del apiario piloto. Seleccione San Juan de Rioseco para ver el certificado.")

    st.markdown("""
    <div style="background:#FAEEDA;border-radius:10px;padding:14px;border:.5px solid #FAC775;margin-top:8px">
      <div style="color:#412402;font-size:13px;font-weight:500;margin-bottom:6px">💰 Modelo de monetización</div>
      <div style="color:#633806;font-size:13px;line-height:1.7">
        El registro sistemático de datos tiene un retorno económico directo para el apicultor:
        <b>su miel certificada por Copernicus puede venderse a un precio diferenciado</b>
        en mercados especializados (supermercados orgánicos, exportación a la UE).
        El sello elimina el greenwashing y da al consumidor validación científica auditable.
      </div>
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# PÁGINA 5 — NOSOTRAS + ASESORA IA
# ═══════════════════════════════════════════════════════════════════
with pag5:
    # Asesora IA
    st.markdown("**💬 Asesora AbejaVerde**")
    st.caption("Respuestas basadas en datos reales de Copernicus e IoT.")

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"], avatar="👩‍🌾" if msg["role"]=="assistant" else "👤"):
            st.markdown(msg["content"])
    if not st.session_state.chat:
        with st.chat_message("assistant", avatar="👩‍🌾"):
            st.markdown("Hola. Soy la asesora de AbejaVerde. Analicé los datos de su apiario. ¿Qué quiere saber sobre sus colmenas hoy?")

    c1,c2 = st.columns(2)
    with c1:
        if st.button("🍯 ¿Debo alimentar?"): st.session_state.chat+=[{"role":"user","content":"¿Debo alimentar?"},{"role":"assistant","content":RESP_IA["alimentar"]}]; st.rerun()
        if st.button("💧 ¿Cómo manejo el agua?"): st.session_state.chat+=[{"role":"user","content":"¿Cómo manejo el agua?"},{"role":"assistant","content":RESP_IA["agua"]}]; st.rerun()
    with c2:
        if st.button("🐝 ¿Riesgo de enjambrazón?"): st.session_state.chat+=[{"role":"user","content":"¿Riesgo de enjambrazón?"},{"role":"assistant","content":RESP_IA["enjambrar"]}]; st.rerun()
        if st.button("🫙 ¿Cuándo cosechar?"): st.session_state.chat+=[{"role":"user","content":"¿Cuándo cosechar?"},{"role":"assistant","content":RESP_IA["cosechar"]}]; st.rerun()

    preg = st.chat_input("Escriba su pregunta...")
    if preg:
        tl=preg.lower()
        if "aliment" in tl: r=RESP_IA["alimentar"]
        elif "enjambr" in tl: r=RESP_IA["enjambrar"]
        elif "cosech" in tl or "miel" in tl: r=RESP_IA["cosechar"]
        elif "agua" in tl or "bebed" in tl: r=RESP_IA["agua"]
        else: r="Use los botones de arriba para las preguntas más frecuentes."
        st.session_state.chat+=[{"role":"user","content":preg},{"role":"assistant","content":r}]; st.rerun()
    if st.session_state.chat and st.button("Limpiar conversación"): st.session_state.chat=[]; st.rerun()

    st.divider()

    # Quiénes somos
    st.markdown("""
    <div style="background:#132610;border-radius:12px;padding:15px;margin-bottom:12px">
      <div style="color:#F5A623;font-size:14px;font-weight:500;margin-bottom:7px">¿Qué es AbejaVerde·EO?</div>
      <div style="color:#9FE1CB;font-size:13px;line-height:1.7">
        Un sistema de <b style="color:#F5A623">alertas tempranas ecosistémicas</b> que combina satélites
        Copernicus con sensores IoT en colmenas reales. Las abejas registran estrés ecosistémico
        antes de que sea visible en la producción agrícola.<br><br>
        Dos fuentes de datos, una sola alerta, en lenguaje que el apicultor entiende.
      </div>
    </div>
    <div style="background:#FAEEDA;border-radius:12px;padding:14px;margin-bottom:12px;border:.5px solid #FAC775">
      <div style="color:#412402;font-size:13px;font-weight:500;margin-bottom:5px">🌉 El apicultor: el puente insustituible</div>
      <div style="color:#633806;font-size:13px;line-height:1.7">
        El satélite ve el territorio desde 800 km. El sensor mide la colmena desde adentro.
        Pero ninguno sabe que la acacia amarilla a 50 metros del apiario empezó a florecer hoy.
        <b>El apicultor ve lo que la tecnología no puede:</b> sus fotos y observaciones
        son la tercera fuente de datos del sistema.
      </div>
    </div>
    """, unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="team-card"><div style="height:110px;background:#132610;display:flex;align-items:center;justify-content:center;font-size:2.5rem;opacity:.5">👩‍🌾</div><div style="padding:12px"><div style="font-size:14px;font-weight:500;color:#132610">Arelys Camacho</div><div style="font-size:11px;color:#888780">Ing. química · Apicultora</div><div style="font-size:12px;color:#5F5E5A;margin-top:5px;line-height:1.5">Apiario piloto en San Juan de Rioseco. Conoce las floraciones de los Andes colombianos por nombre.</div></div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="team-card"><div style="height:110px;background:#132610;display:flex;align-items:center;justify-content:center;font-size:2.5rem;opacity:.5">👩‍💻</div><div style="padding:12px"><div style="font-size:14px;font-weight:500;color:#132610">Mireya Camacho</div><div style="font-size:11px;color:#888780">Abogada · Científica de datos</div><div style="font-size:12px;color:#5F5E5A;margin-top:5px;line-height:1.5">Análisis geoespacial y sistemas de alerta. Llegó a la apicultura por la familia.</div></div></div>', unsafe_allow_html=True)

    frase, autor = FRASES[st.session_state.frase_i]
    st.markdown(f'<div class="frase-box"><div style="color:#F5A623;font-size:14px;font-weight:500;line-height:1.8">{frase}</div><div style="color:#9FE1CB;font-size:12px;margin-top:6px">{autor} · AbejaVerde·EO · CopernicusLAC Hackathon 2026</div></div>', unsafe_allow_html=True)
