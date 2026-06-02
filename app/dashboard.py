"""
AbejaVerde·EO — Dashboard principal Streamlit
Ejecutar con: streamlit run app/dashboard.py
"""
import streamlit as st

st.set_page_config(
    page_title="AbejaVerde·EO",
    page_icon="🐝",
    layout="wide",
)

st.title("🐝 AbejaVerde·EO")
st.caption("Sistema híbrido de alertas tempranas ecosistémicas | San Juan de Rioseco, Cundinamarca")
st.info("Pipeline de datos en construcción — Semana 1")
