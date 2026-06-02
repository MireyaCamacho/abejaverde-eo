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
