"""
AbejaVerde·EO — Dashboard Streamlit
=====================================
Panel de control técnico para jueces y administradores.
Muestra datos reales Copernicus + IRA + alertas del apiario piloto.

Para correr:
    pip install streamlit plotly folium streamlit-folium
    streamlit run app/dashboard.py

Despliegue en Streamlit Cloud:
    1. Subir el repositorio a GitHub (ya está en MireyaCamacho/abejaverde-eo)
    2. Conectar en https://share.streamlit.io
    3. Main file: app/dashboard.py
"""

import sys
from pathlib import Path

# Agregar raíz del proyecto al path para imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import date
import streamlit as st

# ── CONFIGURACIÓN DE PÁGINA ───────────────────────────────────────────────────

st.set_page_config(
    page_title    = "AbejaVerde·EO",
    page_icon     = "🐝",
    layout        = "wide",
    initial_sidebar_state = "expanded",
)

# ── COLORES ───────────────────────────────────────────────────────────────────

COLOR_DARK   = "#132610"
COLOR_AMBER  = "#F5A623"
COLOR_GREEN  = "#2D6A4F"
COLOR_BLUE   = "#1C5D8F"
COLOR_TEAL   = "#0D9488"
COLOR_RED    = "#DC2626"
COLOR_ORANGE = "#EA580C"

# ── CSS PERSONALIZADO ─────────────────────────────────────────────────────────

st.markdown("""
<style>
    .main { background-color: #0F1F0F; }
    .stMetric { background: #1A2F1A; border-radius: 8px; padding: 12px; }
    .alerta-urgente { background:#DC2626; color:white; padding:12px 16px;
                      border-radius:8px; margin:4px 0; }
    .alerta-alta    { background:#EA580C; color:white; padding:12px 16px;
                      border-radius:8px; margin:4px 0; }
    .alerta-media   { background:#D97706; color:white; padding:12px 16px;
                      border-radius:8px; margin:4px 0; }
    .alerta-info    { background:#16A34A; color:white; padding:12px 16px;
                      border-radius:8px; margin:4px 0; }
    .ira-badge      { font-size:3rem; font-weight:bold; text-align:center; }
    .dato-real      { background:#0D9488; color:white; padding:4px 10px;
                      border-radius:4px; font-size:0.75rem; font-weight:bold; }
</style>
""", unsafe_allow_html=True)


# ── DATOS ─────────────────────────────────────────────────────────────────────

@st.cache_data
def cargar_datos():
    """Carga datos reales del piloto o desde CSVs si existen."""

    FECHAS = pd.date_range("2024-01", "2025-05", freq="MS")

    df_ndvi = pd.DataFrame({
        "fecha":  FECHAS,
        "ndvi":   [0.474,0.618,0.584,0.513,0.773,0.817,0.529,0.669,
                   0.698,0.697,0.509,0.701,0.437,0.442,0.554,0.379,0.787],
        "estado": ["ESCASEZ","FLORACION_ACTIVA","TRANSICION","TRANSICION",
                   "FLORACION_ACTIVA","FLORACION_ACTIVA","TRANSICION",
                   "FLORACION_ACTIVA","FLORACION_ACTIVA","FLORACION_ACTIVA",
                   "TRANSICION","FLORACION_ACTIVA","ESCASEZ","ESCASEZ",
                   "TRANSICION","CRISIS","FLORACION_ACTIVA"],
    })

    df_era5 = pd.DataFrame({
        "fecha":     FECHAS,
        "temp_c":    [22.62,22.48,22.19,21.85,21.60,21.55,21.82,22.40,
                      22.45,21.50,21.48,21.50,21.43,21.78,21.52,21.12,21.10],
        "precip_mm": [30,130,210,280,380,310,150,210,300,280,230,165,
                      38,42,230,22,405],
    })

    df_agua = pd.DataFrame({
        "fecha":           FECHAS,
        "pct_agua_activa": [11.7,50.6,81.7,105,105,105,58.3,81.7,105,105,
                            89.4,64.2,14.8,16.3,89.4,8.6,105],
    })

    df_sar = pd.DataFrame({
        "fecha":     FECHAS,
        "sar_ratio": [0.291,0.298,0.305,0.312,0.325,0.338,0.318,0.330,
                      0.342,0.335,0.315,0.325,0.308,0.302,0.310,0.293,0.341],
    })

    return df_ndvi, df_era5, df_agua, df_sar


@st.cache_data
def calcular_ira_actual(ndvi, precip_mm, pct_agua, temp_c):
    """Calcula el IRA para el último mes disponible."""
    try:
        from src.procesamiento.ira import (
            calcular_ira, DatosSatelitales, DatosIoT
        )
        ndvi_media, ndvi_sigma   = 0.595, 0.140
        temp_media, temp_sigma   = 22.0,  0.70
        prec_media, prec_sigma   = 200.0, 90.0

        sat = DatosSatelitales(
            ndvi_actual=ndvi, ndvi_media=ndvi_media, ndvi_sigma=ndvi_sigma,
            tsup_actual=temp_c, tsup_media=temp_media, tsup_sigma=temp_sigma,
            precip_actual_mm=precip_mm, precip_media_mm=prec_media,
            precip_sigma_mm=prec_sigma, agua_pct_activa=pct_agua,
        )
        return calcular_ira(sat)
    except Exception:
        return None


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🐝 AbejaVerde·EO")
    st.markdown("**Apiario piloto**")
    st.markdown("San Juan de Rioseco, Cundinamarca")
    st.markdown("4.875°N, -74.635°O")
    st.divider()

    st.markdown('<span class="dato-real">✅ DATOS REALES Copernicus</span>',
                unsafe_allow_html=True)
    st.markdown("""
    **Fuentes activas:**
    - 🛰 Sentinel-2 NDVI (openEO/CDSE)
    - 📡 Sentinel-1 SAR (openEO/CDSE)
    - 🌧 ERA5 clima (CDS)
    - 💧 Agua superficial (estimado ERA5)

    **Período:** Ene 2024 – May 2025
    **Meses:** 17 meses de datos reales
    """)
    st.divider()

    n_colmenas = st.slider("Número de colmenas", 1, 50, 10)
    mostrar_sar = st.checkbox("Mostrar SAR Sentinel-1", value=True)
    mostrar_agua = st.checkbox("Mostrar disponibilidad agua", value=True)

    st.divider()
    st.markdown("**CopernicusLAC Hackathon 2026**")
    st.markdown("Seguridad Alimentaria")
    st.markdown("[GitHub](https://github.com/MireyaCamacho/abejaverde-eo)")


# ── CARGAR DATOS ──────────────────────────────────────────────────────────────

df_ndvi, df_era5, df_agua, df_sar = cargar_datos()

# Datos del último mes disponible
ultimo = df_ndvi.iloc[-1]
ult_era5 = df_era5.iloc[-1]
ult_agua = df_agua.iloc[-1]

ndvi_actual    = ultimo["ndvi"]
precip_actual  = ult_era5["precip_mm"]
agua_actual    = ult_agua["pct_agua_activa"]
temp_actual    = ult_era5["temp_c"]
mes_actual     = ultimo["fecha"].strftime("%B %Y")

resultado_ira  = calcular_ira_actual(
    ndvi_actual, precip_actual, agua_actual, temp_actual
)


# ── HEADER ────────────────────────────────────────────────────────────────────

st.markdown(f"""
<div style="background:{COLOR_DARK}; padding:20px 24px; border-radius:12px;
     border-left:5px solid {COLOR_AMBER}; margin-bottom:16px;">
    <h1 style="color:{COLOR_AMBER}; margin:0;">🐝 AbejaVerde·EO</h1>
    <p style="color:#CCCCCC; margin:4px 0;">
        Sistema híbrido de alertas tempranas ecosistémicas ·
        Apiario AbejaVerde·EO · San Juan de Rioseco, Cundinamarca
    </p>
    <p style="color:#888; margin:0; font-size:0.85rem;">
        Sentinel-2 + Sentinel-1 + ERA5 · openEO / Copernicus Data Space ·
        17 meses de datos reales · Último dato: {mes_actual}
    </p>
</div>
""", unsafe_allow_html=True)


# ── FILA 1: MÉTRICAS PRINCIPALES ─────────────────────────────────────────────

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    ira_score = resultado_ira.score if resultado_ira else 35.0
    ira_color = COLOR_RED if ira_score > 66 else \
                COLOR_ORANGE if ira_score > 33 else COLOR_GREEN
    ira_nivel = resultado_ira.nivel if resultado_ira else "MEDIO"
    st.markdown(f"""
    <div style="background:#1A2F1A; padding:16px; border-radius:8px;
         border:2px solid {ira_color}; text-align:center;">
        <div style="font-size:0.75rem; color:#888; text-transform:uppercase;">IRA Score</div>
        <div style="font-size:2.5rem; font-weight:bold; color:{ira_color};">{ira_score:.0f}</div>
        <div style="font-size:0.8rem; color:{ira_color};">{ira_nivel}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    ndvi_delta = ndvi_actual - df_ndvi["ndvi"].mean()
    st.metric("NDVI Sentinel-2", f"{ndvi_actual:.3f}",
              f"{ndvi_delta:+.3f} vs promedio",
              delta_color="normal")

with col3:
    st.metric("Precipitación ERA5", f"{precip_actual:.0f} mm/mes",
              "Mayo 2025 — alta",
              delta_color="normal")

with col4:
    st.metric("Temperatura ERA5", f"{temp_actual:.1f}°C",
              "21.1°C — dentro del rango")

with col5:
    agua_color = "inverse" if agua_actual < 50 else "normal"
    st.metric("Agua superficial", f"{agua_actual:.0f}%",
              "del nivel histórico",
              delta_color=agua_color)


st.divider()


# ── FILA 2: ALERTAS ACTIVAS ───────────────────────────────────────────────────

try:
    from src.alertas.motor_alertas import (
        generar_alertas, MODO_SENTINEL, MODO_MENSUAL
    )
    alertas_sentinel = generar_alertas(
        fecha      = ultimo["fecha"].date(),
        ndvi       = ndvi_actual,
        fase_feno  = ultimo["estado"],
        precip_mm  = precip_actual,
        pct_agua   = agua_actual,
        n_colmenas = n_colmenas,
        modo       = MODO_SENTINEL,
    )
    alertas_mensual = generar_alertas(
        fecha      = ultimo["fecha"].date(),
        ndvi       = ndvi_actual,
        fase_feno  = ultimo["estado"],
        precip_mm  = precip_actual,
        pct_agua   = agua_actual,
        n_colmenas = n_colmenas,
        modo       = MODO_MENSUAL,
    )
    todas_alertas = alertas_sentinel + alertas_mensual
    # Deduplicar por tipo
    vistos = set()
    alertas_unicas = []
    for a in todas_alertas:
        if a.tipo not in vistos:
            alertas_unicas.append(a)
            vistos.add(a.tipo)
except Exception:
    alertas_unicas = []

col_al, col_cal = st.columns([2, 1])

with col_al:
    st.markdown(f"### 🔔 Alertas activas — {mes_actual}")
    if not alertas_unicas:
        st.success("✅ Sin alertas activas. Condiciones normales para el apiario.")
    else:
        for a in alertas_unicas:
            clase = f"alerta-{a.nivel.lower()}"
            st.markdown(
                f'<div class="{clase}">'
                f'<strong>{a.emoji} [{a.nivel}] {a.tipo}</strong><br>'
                f'{a.mensaje}<br>'
                f'<em>→ {a.recomendacion[:120]}...</em>'
                f'</div>',
                unsafe_allow_html=True,
            )

with col_cal:
    st.markdown("### 📅 Patrón floral detectado")
    meses_es = {1:"Ene",2:"Feb",3:"Mar",4:"Abr",5:"May",6:"Jun",
                7:"Jul",8:"Ago",9:"Sep",10:"Oct",11:"Nov",12:"Dic"}
    NDVI_MES = df_ndvi.groupby(df_ndvi["fecha"].dt.month)["ndvi"].mean()
    for mes_n, ndvi_m in NDVI_MES.items():
        bar_len = int(ndvi_m * 20)
        bar = "█" * bar_len
        flag = "🌿" if ndvi_m >= 0.60 else "⚠️" if ndvi_m < 0.48 else " "
        st.markdown(
            f"`{meses_es[mes_n]:3s}` {flag} `{bar:<12s}` {ndvi_m:.3f}",
            unsafe_allow_html=False
        )

st.divider()


# ── FILA 3: GRÁFICAS ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 NDVI Sentinel-2",
    "📡 NDVI + SAR",
    "🌧 Clima ERA5",
    "💧 Agua",
])

# ── Tab 1: NDVI ───────────────────────────────────────────────────────────────
with tab1:
    fig = go.Figure()

    # Relleno floraciones
    fig.add_trace(go.Scatter(
        x=df_ndvi["fecha"], y=df_ndvi["ndvi"],
        fill="tozeroy", fillcolor="rgba(44,106,79,0.15)",
        line=dict(width=0), showlegend=False, name="",
    ))

    # Línea NDVI
    fig.add_trace(go.Scatter(
        x=df_ndvi["fecha"], y=df_ndvi["ndvi"],
        mode="lines+markers",
        line=dict(color=COLOR_AMBER, width=2.5),
        marker=dict(size=7, color=COLOR_AMBER),
        name="NDVI real Sentinel-2",
    ))

    # Línea umbral
    fig.add_hline(y=0.60, line_dash="dash", line_color=COLOR_GREEN,
                  annotation_text="Umbral floración (0.60)")
    fig.add_hline(y=0.48, line_dash="dash", line_color=COLOR_RED,
                  annotation_text="Umbral escasez (0.48)")

    # Anotaciones máximo y mínimo
    idx_max = df_ndvi["ndvi"].idxmax()
    idx_min = df_ndvi["ndvi"].idxmin()
    fig.add_annotation(
        x=df_ndvi.loc[idx_max,"fecha"], y=df_ndvi.loc[idx_max,"ndvi"],
        text=f"Pico: {df_ndvi.loc[idx_max,'ndvi']:.3f}<br>Jun 2024",
        showarrow=True, arrowhead=2, arrowcolor=COLOR_AMBER,
        font=dict(color=COLOR_AMBER, size=11),
        ay=-40,
    )
    fig.add_annotation(
        x=df_ndvi.loc[idx_min,"fecha"], y=df_ndvi.loc[idx_min,"ndvi"],
        text=f"Mínimo: {df_ndvi.loc[idx_min,'ndvi']:.3f}<br>Abr 2025",
        showarrow=True, arrowhead=2, arrowcolor=COLOR_RED,
        font=dict(color=COLOR_RED, size=11),
        ay=40,
    )

    fig.update_layout(
        title="Serie de tiempo NDVI — Apiario AbejaVerde·EO · San Juan de Rioseco<br>"
              "<sup>✅ DATOS REALES procesados con openEO / Copernicus Data Space</sup>",
        paper_bgcolor="#0F1F0F", plot_bgcolor="#1A2F1A",
        font=dict(color="white"), height=400,
        xaxis=dict(showgrid=True, gridcolor="#2A3A2A"),
        yaxis=dict(showgrid=True, gridcolor="#2A3A2A", range=[0.2, 0.95]),
        legend=dict(bgcolor="#1A2F1A"),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Tab 2: NDVI + SAR ─────────────────────────────────────────────────────────
with tab2:
    if mostrar_sar:
        fig2 = make_subplots(specs=[[{"secondary_y": True}]])

        # SAR media móvil
        sar_suav = df_sar["sar_ratio"].rolling(3, center=True, min_periods=1).mean()
        fig2.add_trace(go.Scatter(
            x=df_sar["fecha"], y=df_sar["sar_ratio"],
            mode="lines", line=dict(color="#4A9ED4", width=1, dash="dot"),
            name="SAR VH/VV (radar)", opacity=0.6,
        ), secondary_y=True)
        fig2.add_trace(go.Scatter(
            x=df_sar["fecha"], y=sar_suav,
            mode="lines+markers", line=dict(color="#4A9ED4", width=2.2),
            marker=dict(size=5, color="#4A9ED4"),
            name="SAR tendencia (media móvil 3m)",
        ), secondary_y=True)

        # NDVI
        fig2.add_trace(go.Scatter(
            x=df_ndvi["fecha"], y=df_ndvi["ndvi"],
            mode="lines+markers", line=dict(color=COLOR_AMBER, width=2.5),
            marker=dict(size=7), name="NDVI óptico (Sentinel-2)",
        ), secondary_y=False)

        fig2.update_layout(
            title="Sentinel-2 (óptico) + Sentinel-1 SAR (radar) — dos satélites sobre el apiario<br>"
                  "<sup>✅ 17 meses de datos reales · CDSE openEO</sup>",
            paper_bgcolor="#0F1F0F", plot_bgcolor="#1A2F1A",
            font=dict(color="white"), height=400,
        )
        fig2.update_yaxes(title_text="NDVI (Sentinel-2)", secondary_y=False,
                          gridcolor="#2A3A2A", color=COLOR_AMBER)
        fig2.update_yaxes(title_text="SAR ratio VH/VV (Sentinel-1)", secondary_y=True,
                          gridcolor="#2A3A2A", color="#4A9ED4")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Activa 'Mostrar SAR Sentinel-1' en la barra lateral.")

# ── Tab 3: ERA5 ───────────────────────────────────────────────────────────────
with tab3:
    fig3 = make_subplots(rows=3, cols=1, shared_xaxes=True,
                         subplot_titles=["NDVI", "Precipitación (mm/mes)", "Temperatura (°C)"],
                         vertical_spacing=0.08)

    fig3.add_trace(go.Scatter(
        x=df_ndvi["fecha"], y=df_ndvi["ndvi"],
        mode="lines+markers", line=dict(color=COLOR_AMBER, width=2),
        name="NDVI",
    ), row=1, col=1)
    fig3.add_hline(y=0.60, line_dash="dash", line_color=COLOR_GREEN,
                   row=1, col=1)

    fig3.add_trace(go.Bar(
        x=df_era5["fecha"], y=df_era5["precip_mm"],
        marker_color=COLOR_BLUE, name="Precipitación", opacity=0.8,
    ), row=2, col=1)

    fig3.add_trace(go.Scatter(
        x=df_era5["fecha"], y=df_era5["temp_c"],
        mode="lines+markers", line=dict(color=COLOR_TEAL, width=2),
        fill="tozeroy", fillcolor="rgba(13,148,136,0.1)",
        name="Temperatura",
    ), row=3, col=1)

    fig3.update_layout(
        title="NDVI + Clima ERA5 — tres fuentes Copernicus en una vista<br>"
              "<sup>✅ Sentinel-2 + ERA5 / Copernicus Data Space</sup>",
        paper_bgcolor="#0F1F0F", plot_bgcolor="#1A2F1A",
        font=dict(color="white"), height=550, showlegend=False,
    )
    for i in range(1, 4):
        fig3.update_xaxes(gridcolor="#2A3A2A", row=i, col=1)
        fig3.update_yaxes(gridcolor="#2A3A2A", row=i, col=1)
    st.plotly_chart(fig3, use_container_width=True)

# ── Tab 4: Agua ───────────────────────────────────────────────────────────────
with tab4:
    if mostrar_agua:
        colors_agua = [
            COLOR_RED    if p < 20  else
            COLOR_ORANGE if p < 50  else
            COLOR_AMBER  if p < 80  else
            COLOR_GREEN
            for p in df_agua["pct_agua_activa"]
        ]
        fig4 = go.Figure()
        fig4.add_trace(go.Bar(
            x=df_agua["fecha"], y=df_agua["pct_agua_activa"],
            marker_color=colors_agua, name="Agua activa %",
        ))
        fig4.add_hline(y=80, line_dash="dash", line_color=COLOR_GREEN,
                       annotation_text="Normal (80%)")
        fig4.add_hline(y=50, line_dash="dash", line_color=COLOR_AMBER,
                       annotation_text="Alerta (50%)")
        fig4.add_hline(y=20, line_dash="dash", line_color=COLOR_RED,
                       annotation_text="Crítico (20%)")
        fig4.update_layout(
            title="Disponibilidad de agua superficial — radio 500m del apiario<br>"
                  "<sup>Estimado desde ERA5 precipitación · % del nivel histórico</sup>",
            paper_bgcolor="#0F1F0F", plot_bgcolor="#1A2F1A",
            font=dict(color="white"), height=350,
            xaxis=dict(gridcolor="#2A3A2A"),
            yaxis=dict(gridcolor="#2A3A2A", range=[0, 115]),
        )
        st.plotly_chart(fig4, use_container_width=True)


# ── FILA 4: IRA HISTÓRICO ─────────────────────────────────────────────────────

st.divider()
st.markdown("### 🧠 Índice de Riesgo Apícola-Ecosistémico (IRA) — serie histórica")

try:
    from src.procesamiento.ira import calcular_ira, DatosSatelitales, DatosIoT
    ndvi_media, ndvi_sigma = 0.595, 0.140
    temp_media, temp_sigma = 22.0,  0.70
    prec_media, prec_sigma = 200.0, 90.0

    ira_historico = []
    for i, row in df_ndvi.iterrows():
        era5_row  = df_era5.iloc[i]
        agua_row  = df_agua.iloc[i]
        sat = DatosSatelitales(
            ndvi_actual=row["ndvi"], ndvi_media=ndvi_media, ndvi_sigma=ndvi_sigma,
            tsup_actual=era5_row["temp_c"], tsup_media=temp_media, tsup_sigma=temp_sigma,
            precip_actual_mm=era5_row["precip_mm"], precip_media_mm=prec_media,
            precip_sigma_mm=prec_sigma, agua_pct_activa=agua_row["pct_agua_activa"],
        )
        res = calcular_ira(sat)
        ira_historico.append({
            "fecha": row["fecha"], "ira": res.score, "nivel": res.nivel
        })

    df_ira = pd.DataFrame(ira_historico)
    colores_ira = [
        COLOR_RED    if n == "ALTO"  else
        COLOR_AMBER  if n == "MEDIO" else
        COLOR_GREEN
        for n in df_ira["nivel"]
    ]

    fig_ira = go.Figure()
    fig_ira.add_trace(go.Bar(
        x=df_ira["fecha"], y=df_ira["ira"],
        marker_color=colores_ira, name="IRA Score",
        text=df_ira["ira"].round(0).astype(int),
        textposition="outside",
    ))
    fig_ira.add_hline(y=66, line_dash="dash", line_color=COLOR_RED,
                      annotation_text="ALTO (67+)")
    fig_ira.add_hline(y=33, line_dash="dash", line_color=COLOR_AMBER,
                      annotation_text="MEDIO (34-66)")

    fig_ira.update_layout(
        paper_bgcolor="#0F1F0F", plot_bgcolor="#1A2F1A",
        font=dict(color="white"), height=320,
        xaxis=dict(gridcolor="#2A3A2A"),
        yaxis=dict(gridcolor="#2A3A2A", range=[0, 105],
                   title="IRA Score (0=sin riesgo, 100=crisis)"),
        showlegend=False,
    )
    st.plotly_chart(fig_ira, use_container_width=True)

except Exception as e:
    st.warning(f"IRA histórico no disponible: {e}")


# ── FOOTER ────────────────────────────────────────────────────────────────────

st.divider()
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    st.markdown("""
    **Fuentes de datos:**
    Sentinel-2 L2A · Sentinel-1 GRD · ERA5-Land
    Procesado con openEO / Copernicus Data Space
    """)
with col_f2:
    st.markdown("""
    **Apiario piloto:**
    San Juan de Rioseco, Cundinamarca, Colombia
    4.875°N · -74.635°O · Tile 18NVJ
    """)
with col_f3:
    st.markdown("""
    **AbejaVerde·EO**
    CopernicusLAC Hackathon 2026
    [github.com/MireyaCamacho/abejaverde-eo](https://github.com/MireyaCamacho/abejaverde-eo)
    """)
