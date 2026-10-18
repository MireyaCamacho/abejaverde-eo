# 🐝 AbejaVerde·EO

**Sistema híbrido de alertas tempranas ecosistémicas con datos Copernicus y bioindicación apícola real**

> Caso piloto: San Juan de Rioseco, Cundinamarca — Colombia  
> CopernicusLAC Hackathon 2026 | Track: Resiliencia de Pequeños Agricultores

---

## ¿Qué hace?

AbejaVerde·EO combina datos satelitales de Copernicus con datos reales de una colmena inteligente IoT para generar alertas tempranas que le dicen al apicultor:

| Alerta | Pregunta que responde |
|---|---|
| 🍯 Alimentación | ¿Debo alimentar mis abejas hoy? |
| 💧 Agua | ¿Hay agua suficiente cerca de la colmena? |
| 👑 Visita - Reina | ¿Debo revisar la reina urgentemente? |
| 📍 Reubicación | ¿Debo trasladar el apiario a otra zona? |
| ☀️ Ola de calor | ¿Hay estrés térmico territorial activo? |

---

## Arquitectura

```
Copernicus (Sentinel-2, ERA5, LSP, Water Bodies)
    +
IDEAM (estaciones locales Cundinamarca)
    +
Colmena IoT (temperatura y humedad reales)
    +
BEEP Base (referencia biológica colmenas)
          ↓
    IRA — Índice de Riesgo Apícola-Ecosistémico (0–100)
          ↓
    Dashboard Streamlit  +  App Móvil (FastAPI + PWA)
```

---

## 🏁 MVP Acelera Lab — semáforo de 4 colores y alertas por WhatsApp o correo

Finalista de **Acelera Lab** (Gobernación de Cundinamarca · OEI). El MVP cruza el NDVI de
Copernicus con una bitácora de 3 preguntas del apicultor (población, reservas de miel y
polen, postura de la reina) y envía un semáforo **VERDE · AMARILLO · NARANJA · ROJO** con la
acción de la semana por **WhatsApp, correo o ambos**, solo con autorización de datos
(Ley 1581 de 2012).

- Guía completa (Antigravity, Earth Engine, Sheets, Apps Script, AppSheet, Looker Studio):
  [`mvp_aceleralab/README.md`](mvp_aceleralab/README.md)
- Skill del agente: [`.agents/skills/abejaverde-riesgo-apicola/SKILL.md`](.agents/skills/abejaverde-riesgo-apicola/SKILL.md)
- Reglas en Python: `src/alertas/semaforo.py` · envío por canal: `src/alertas/notificaciones.py`
- En la app: pestaña **Diagnóstico → 📲 Recibir esta alerta por WhatsApp o correo**

```bash
python -m pytest tests/test_semaforo.py -v
python -m src.alertas.enviar_alertas_semanales mvp_aceleralab/sheets/BD_AbejaVerde_EO_Bitacora_Colmenas.csv --simular --sin-gemini
```

---

## Instalación

```bash
git clone https://github.com/TU_USUARIO/abejaverde-eo.git
cd abejaverde-eo
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Complete las credenciales en .env
```

---

## Ejecución del dashboard

```bash
streamlit run app/dashboard.py
```

## Ejecución de la API móvil

```bash
uvicorn app.mobile_api.main:app --reload
```

---

## Estructura del proyecto

```
abejaverde-eo/
├── data/               # Datos (raw en .gitignore, processed en repo)
├── src/
│   ├── ingesta/        # Descarga de datos Copernicus, IDEAM e IoT
│   ├── procesamiento/  # Anomalías, IRA, fenología, agua
│   ├── alertas/        # Motor de alertas y notificaciones
│   └── visualizacion/  # Mapas, gráficas y paneles
├── app/
│   ├── dashboard.py        # Dashboard Streamlit
│   └── mobile_api/         # API FastAPI para app móvil
├── notebooks/          # Exploración y validación de datos
├── tests/              # Tests unitarios
└── docs/               # Documentación del proyecto
```

Ver [docs/AbejaVerde_EO_PlanTrabajo.md](docs/AbejaVerde_EO_PlanTrabajo.md) para el plan de trabajo completo.

---

## Fuentes de datos

| Dataset | Fuente | Uso |
|---|---|---|
| Sentinel-2 L2A | Copernicus CDSE | NDVI, EVI |
| Land Surface Phenology | CLMS | Índice fenológico, calendario floral |
| ERA5-Land | Copernicus CDS | Temperatura, precipitación, ET |
| Global Surface Water | JRC / Copernicus | Agua histórica cerca del apiario |
| Water Bodies | CLMS | Agua superficial activa |
| Red de estaciones | IDEAM / datos.gov.co | Clima local Cundinamarca |
| Colmena inteligente IoT | Datos reales ★ | T° y HR interna colmena |
| BEEP Base | Open data | Referencia biológica colmenas |

---

## Equipo

| Perfil | Rol |
|---|---|
| Científica de Datos + Abogada | Pipeline satelital, IRA, dashboard, marco regulatorio |
| Ingeniera Química + Apicultora | Datos IoT reales, validación biológica, interpretación |

---

*AbejaVerde·EO — CopernicusLAC Hackathon 2026*
