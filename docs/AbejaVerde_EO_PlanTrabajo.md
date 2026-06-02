# AbejaVerde·EO — Plan de Trabajo y Diseño Metodológico
**CopernicusLAC Hackathon 2026 | Caso piloto: San Juan de Rioseco, Cundinamarca**
*Versión 2 — Incluye fuentes complementarias, alerta de agua y app móvil*

---

## 1. Estructura del Proyecto

```
abejaverde-eo/
│
├── data/
│   ├── raw/
│   │   ├── copernicus/
│   │   │   ├── sentinel2/         # Imágenes Sentinel-2 L2A (bandas B4, B8 para NDVI/EVI)
│   │   │   ├── era5_land/         # Temperatura superficial, precipitación, ET
│   │   │   ├── sentinel3/         # LST (Land Surface Temperature)
│   │   │   ├── land_phenology/    # LSP global — índice fenológico (inicio/pico/fin temporada)
│   │   │   ├── water_bodies/      # CLMS Water Bodies — cuerpos de agua activos (300m/10días)
│   │   │   └── global_surface_water/  # JRC Global Surface Water — presencia histórica de agua
│   │   ├── ideam/
│   │   │   └── estaciones/        # Datos DHIME — temperatura y precipitación local Cundinamarca
│   │   ├── iot/
│   │   │   ├── colmena_real/      # CSV/JSON colmena inteligente (1 semana datos reales)
│   │   │   └── beep_base/         # Dataset abierto BEEP Base — referencia biológica colmenas
│   │   └── datos_gov_co/
│   │       ├── eva_apicola/       # EVA — Evaluaciones Agropecuarias Municipales (MADR)
│   │       └── actividad_apicola/ # Actividad Apícola Cauca — variables productivas
│   │
│   ├── processed/
│   │   ├── ndvi_series.csv           # Serie temporal NDVI calculada zona San Juan de Rioseco
│   │   ├── fenologia_series.csv      # Índice fenológico: inicio, pico y fin de temporada floral
│   │   ├── agua_superficial.csv      # Cuerpos de agua activos en radio 500m de cada apiario
│   │   ├── anomalias.csv             # Anomalías de cada variable vs. línea base histórica
│   │   ├── ira_scores.csv            # Historial IRA por apiario y fecha
│   │   └── alertas_log.csv           # Registro histórico de alertas generadas
│   │
│   └── reference/
│       ├── linea_base/               # Promedios históricos 2022–2024 por variable y quincena
│       ├── floraciones_sjr.csv       # Calendario floral San Juan de Rioseco (construido con LSP)
│       ├── apiarios_geo.geojson      # Coordenadas y metadata de apiarios piloto
│       └── cuerpos_agua_500m.geojson # Cuerpos de agua en radio 500m de cada apiario
│
├── src/
│   ├── ingesta/
│   │   ├── copernicus_api.py         # Descarga y autenticación Copernicus CDSE
│   │   ├── sentinel2_ndvi.py         # Cálculo NDVI/EVI desde bandas B4 y B8
│   │   ├── land_phenology.py         # Descarga y parsing LSP global (inicio/pico/fin temporada)
│   │   ├── era5_land.py              # Temperatura, precipitación, ET desde CDS API
│   │   ├── water_bodies.py           # Descarga CLMS Water Bodies + JRC Global Surface Water
│   │   ├── ideam_dhime.py            # Lectura estaciones IDEAM cercanas a San Juan de Rioseco
│   │   ├── iot_parser.py             # Lectura y estandarización datos colmena IoT real
│   │   └── beep_base_parser.py       # Lectura dataset BEEP Base como referencia biológica
│   │
│   ├── procesamiento/
│   │   ├── anomalias.py              # Cálculo de anomalías vs. línea base histórica
│   │   ├── fenologia.py              # Extracción de eventos fenológicos y calendario floral
│   │   ├── agua_disponibilidad.py    # Análisis disponibilidad de agua en radio del apiario
│   │   ├── ira.py                    # Fórmula IRA y clasificación de riesgo
│   │   └── linea_base.py             # Construcción y actualización de líneas base
│   │
│   ├── alertas/
│   │   ├── motor_alertas.py          # Lógica central de generación de alertas
│   │   ├── alerta_alimentacion.py    # Alerta: cuándo alimentar las abejas
│   │   ├── alerta_agua.py            # Alerta: suficiencia/insuficiencia de agua cerca
│   │   ├── alerta_visita_reina.py    # Alerta: cuándo revisar la reina
│   │   ├── alerta_reubicacion.py     # Alerta: cuándo cambiar de ubicación el apiario
│   │   └── notificaciones.py         # Envío WhatsApp / push móvil / email
│   │
│   └── visualizacion/
│       ├── mapa.py                   # Mapa Folium: apiarios, NDVI, agua, zonas IRA
│       ├── series_temporales.py      # Gráficas Plotly: NDVI, fenología, T°colmena, HR
│       ├── panel_iot.py              # Panel T° y HR en tiempo real con semáforo
│       ├── panel_agua.py             # Panel disponibilidad de agua cerca del apiario
│       └── heatmap.py                # Heatmap territorial de riesgo IRA
│
├── app/
│   ├── dashboard.py                  # Dashboard Streamlit — versión técnica / jueces
│   └── mobile_api/
│       ├── main.py                   # API FastAPI — backend para la app móvil
│       ├── endpoints/
│       │   ├── alertas.py            # GET /alertas/{apiario_id}
│       │   ├── ira.py                # GET /ira/{apiario_id}
│       │   └── recomendaciones.py    # GET /recomendaciones/{apiario_id}
│       └── schemas.py                # Modelos Pydantic de respuesta
│
├── mobile/
│   └── README_mobile.md              # Instrucciones para conectar app móvil a la API
│
├── notebooks/
│   ├── 01_exploracion_copernicus.ipynb
│   ├── 02_exploracion_fenologia.ipynb
│   ├── 03_exploracion_agua.ipynb
│   ├── 04_exploracion_iot_beep.ipynb
│   ├── 05_calculo_ira.ipynb
│   └── 06_validacion_alertas.ipynb
│
├── tests/
│   ├── test_ira.py
│   ├── test_alertas.py
│   ├── test_agua.py
│   └── test_ingesta.py
│
├── docs/
│   ├── AbejaVerde_EO_Propuesta.docx
│   ├── Colmena_Inteligente_Formulacion.docx
│   ├── AbejaVerde_EO_PlanTrabajo.md      # Este documento
│   └── diccionario_variables.md
│
├── .env.example
├── requirements.txt
├── README.md
└── LICENSE
```

---

## 2. Mapa Completo de Fuentes de Datos

| # | Variable | Dataset | Fuente | Resolución | Cobertura Colombia |
|---|---|---|---|---|---|
| 1 | Verdor / floración activa | NDVI — Sentinel-2 L2A | Copernicus CDSE | 10 m / 5 días | ✅ |
| 2 | **Índice fenológico** | **Land Surface Phenology (LSP) global** | **CLMS / Copernicus** | **300 m / anual** | **✅** |
| 3 | Temperatura territorial | ERA5-Land | Copernicus CDS | ~25 km / horario | ✅ |
| 4 | Precipitación | ERA5-Land | Copernicus CDS | ~25 km / horario | ✅ |
| 5 | Evapotranspiración | AgERA5 | Copernicus CDS | ~25 km / diario | ✅ |
| 6 | Estrés hídrico suelo | SWI — Soil Water Index | CLMS | 12.5 km / diario | ✅ |
| 7 | Estrés hídrico vegetal | FAPAR Anomaly | Copernicus GDO | 500 m / 10 días | ✅ |
| 8 | Agua superficial histórica | JRC Global Surface Water | JRC / Copernicus | 30 m | ✅ |
| 9 | Agua superficial activa | Water Bodies CLMS | CLMS | 300 m / 10 días | ✅ |
| 10 | Temperatura superficial tierra | LST — Sentinel-3 | Copernicus CDSE | ~1 km | ✅ |
| 11 | Clima local estaciones | DHIME red de estaciones | IDEAM / datos.gov.co | Puntual / horario | ✅ |
| 12 | Producción apícola municipal | EVA Agropecuaria | MADR / datos.gov.co | Municipal | ✅ |
| 13 | Variables apícolas Cauca | Actividad Apícola | Sec. Agricultura Cauca | Municipal | ✅ |
| 14 | Bioindicador T° colmena | IoT colmena inteligente | **REAL — 1 semana** | Cada 10–15 min | ✅ |
| 15 | Bioindicador HR colmena | IoT colmena inteligente | **REAL — 1 semana** | Cada 10–15 min | ✅ |
| 16 | Referencia biológica colmenas | BEEP Base open data | Países Bajos | Cada hora | Referencia global |

---

## 3. Diseño Metodológico

### 3.1 Enfoque general — Doble evidencia

AbejaVerde·EO usa una metodología de **detección de anomalías por doble evidencia**: una alerta solo se activa cuando hay señal convergente tanto del satélite (indicador territorial) como de la colmena (bioindicador biológico). Esto reduce drásticamente los falsos positivos.

```
SEÑAL SATELITAL (Copernicus + IDEAM)        SEÑAL BIOLÓGICA (Colmena IoT + BEEP)
         ↓                                              ↓
  Anomalía NDVI                               Anomalía T° colmena
  Evento fenológico (LSP)                     Anomalía HR
  Déficit precipitación / SWI
  Escasez agua superficial
         ↓                                              ↓
               ──────── IRA (0–100) ────────
                             ↓
               Clasificación de riesgo
                             ↓
               Tipo de alerta específica
                             ↓
           Recomendación accionable al apicultor
           (Dashboard Streamlit + App móvil)
```

---

### 3.2 Rol del índice fenológico (LSP)

El índice fenológico es la columna vertebral del calendario de floraciones. Sin él, el sistema no puede distinguir si una caída de NDVI es porque terminó la temporada floral (normal) o porque hay estrés hídrico inesperado (anormal).

**Qué entrega el LSP de CLMS para San Juan de Rioseco:**

| Métrica LSP | Qué significa para la apicultura |
|---|---|
| **SOS** — Start of Season | Inicio de floración: momento en que la colmena debería empezar a ganar peso |
| **POS** — Peak of Season | Pico de floración: máxima oferta de néctar, no alimente, prepare alzas |
| **EOS** — End of Season | Fin de floración: inicia el período de escasez, prepare alimentación suplementaria |
| **LOS** — Length of Season | Duración total de la temporada floral: permite comparar año a año |
| **AMPL** — Amplitude | Intensidad de la floración: años con AMPL bajo predicen cosechas pobres |

**Cómo se usa en las alertas:**

```
SI fecha_actual está entre SOS y POS   →  Floración activa → NO alimente
SI fecha_actual está entre POS y EOS   →  Floración declinando → Monitoree peso
SI fecha_actual está después de EOS    →  Temporada terminada → Alimente si HR y T° son anómalas
SI SOS de este año llega con > 15 días de retraso vs. histórico → Alerta: temporada retrasada
```

---

### 3.3 Variables del sistema y línea base

**Construcción de la línea base histórica:**
- Período de referencia: 2022–2024 (disponible en Copernicus y BEEP Base)
- Granularidad: ventanas de 15 días por variable, por mes y por quincena
- Estadísticos: media y desviación estándar

```
Anomalía_X = (X_observado − X_media_histórica) / σ_histórica
```

**Estrategia para los datos IoT (solo 1 semana real):**
Los datos de BEEP Base actúan como referencia biológica externa para validar
que el comportamiento de la colmena inteligente es normal. El IoT real aporta
la señal actual; BEEP aporta el contexto histórico de cómo se comportan colmenas
sanas bajo condiciones similares.

---

### 3.4 Fórmula IRA — versión actualizada con fenología y agua

```
IRA = (w₁ × f_NDVI) + (w₂ × f_Fenologia) + (w₃ × f_Tsup) +
      (w₄ × f_Tcolmena) + (w₅ × f_HR) + (w₆ × f_Precip) + (w₇ × f_Agua)
```

| Variable | Fuente | Interpretación | Peso |
|---|---|---|---|
| **f_NDVI** | Sentinel-2 L2A | Variación de vegetación vs. media histórica (–15 días) | **25%** |
| **f_Fenologia** | LSP global CLMS | Posición dentro del ciclo estacional: ¿estamos en floración, declive o escasez? | **15%** |
| **f_Tsup** | ERA5-Land / Sentinel-3 | Anomalía de temperatura superficial terrestre | **20%** |
| **f_Tcolmena ★ REAL** | Colmena IoT | Desviación de temperatura interna vs. homeostasis (~35°C) | **20%** |
| **f_HR ★ REAL** | Colmena IoT | Humedad relativa interna anómala | **8%** |
| **f_Precip** | ERA5-Land + IDEAM | Déficit o exceso vs. promedio histórico mensual | **7%** |
| **f_Agua** | Water Bodies + JRC GSW | Disponibilidad de agua superficial en radio 500m del apiario | **5%** |

**Clasificación de riesgo:**

| Nivel | IRA | Interpretación | Acción |
|---|---|---|---|
| 🟢 BAJO | 0–33 | Ecosistema estable | Sin acción inmediata |
| 🟡 MEDIO | 34–66 | Señales de alerta emergente | Monitoreo intensificado |
| 🔴 ALTO | 67–100 | Estrés ecosistémico activo | Alerta urgente al apicultor |

---

## 4. Lógica de Alertas

### 4.1 Alerta de Alimentación — "¿Debo alimentar mis abejas?"

```
ALERTA ROJA — Alimente ya:
  SI NDVI_actual < NDVI_histórico − 15%          →  Floración en declive
     Y LSP indica: después de EOS (fuera de temporada)
     Y precipitación_déficit_15días > 20%
     Y T_colmena fuera de rango (< 34.5°C o > 35.5°C)
  ENTONCES:
     Mensaje: "Escasez de néctar detectada. Inicie alimentación
               suplementaria en los próximos 3 días."

ALERTA VERDE — No alimente:
  SI NDVI_actual > NDVI_histórico + 10%
     Y LSP indica: entre SOS y POS (plena floración)
     Y T_colmena estable entre 34.5–35.5°C
  ENTONCES:
     Mensaje: "Floración activa. Su colmena está produciendo.
               No alimente. Prepare alzas si aún no las tiene."

ESTADO NEUTRO:
  SI ninguna de las condiciones anteriores se cumple
  ENTONCES:
     Mensaje: "Período de transición. Revise en 5 días."
```

---

### 4.2 Alerta de Agua — "¿Hay agua suficiente cerca de la colmena?"

Las abejas necesitan mínimo 1 litro de agua por colmena por día. Esta alerta cruza la disponibilidad de agua superficial en el territorio con las condiciones climáticas actuales.

```
PASO 1 — Mapear cuerpos de agua en radio 500m alrededor del apiario
         Fuente: JRC Global Surface Water (presencia histórica, 30m)

PASO 2 — Verificar si esos cuerpos están activos HOY
         Fuente: CLMS Water Bodies (actualización cada 10 días, 300m)

PASO 3 — Cruzar con déficit de precipitación y temperatura alta
         Fuente: ERA5-Land precipitación + LST + SWI

ALERTA ROJA — Escasez de agua:
  SI cuerpos_agua_activos_500m < 50% de la presencia histórica normal
     Y precipitación_acumulada_15días < 40% del promedio
     Y temperatura_superficial > media_histórica + 2°C
  ENTONCES:
     Mensaje: "Posible escasez de agua cerca de su apiario.
               Verifique que cada colmena tenga al menos 1 litro
               de agua fresca disponible. Si no hay fuentes naturales
               activas, instale bebedero artificial a menos de 200m."

ALERTA AMARILLA — Monitoreo:
  SI cuerpos_agua_activos_500m entre 50–80% del histórico
     Y déficit de precipitación moderado (20–40%)
  ENTONCES:
     Mensaje: "Nivel de agua en la zona disminuyendo.
               Revise las fuentes de agua cercanas esta semana."

ESTADO NORMAL:
  SI agua superficial activa normal Y precipitación sin déficit
  ENTONCES:
     Mensaje: "Disponibilidad de agua normal en su zona."
```

---

### 4.3 Alerta de Visita — Revisión de reina

```
ALERTA URGENTE — Visite la colmena (problema de reina o colonia):
  SI T_colmena < 34.0°C sostenida por > 4 horas
     O T_colmena > 37.0°C sostenida por > 2 horas
     O HR_interna > 75% sostenida por > 6 horas
     Y estas condiciones se repiten en > 2 días consecutivos
  ENTONCES:
     Mensaje: "Su colmena no está manteniendo su temperatura normal.
               Esto puede indicar reina débil, colonia pequeña,
               orfandad o enfermedad. Visite en las próximas 24–48h.
               Revise: postura de la reina, población, signos de
               loque o varroasis."
```

---

### 4.4 Alerta de Reubicación del apiario

```
ALERTA — Evalúe traslado:
  SI NDVI_zona_actual < 0.30 sostenido por > 10 días
     Y LSP indica: temporada terminada (después de EOS)
     Y NDVI_promedio_4semanas < línea_base − 20%
     Y precipitación_acumulada_15días < 50% del promedio
  ENTONCES:
     Mensaje: "Su zona de pastoreo está agotada para esta temporada.
               Evalúe trasladar el apiario. En el mapa encontrará
               zonas con NDVI > 0.45 en un radio de 10 km."
     [Mapa incluido con zonas sugeridas]
```

---

### 4.5 Matriz de alertas — resumen

| Alerta | Variables detonantes principales | Fuentes clave | Mensaje al apicultor |
|---|---|---|---|
| 🍯 Alimente YA | NDVI↓ + LSP fuera de temporada + T°colmena anómala | Sentinel-2 + LSP + IoT | "Escasez detectada. Alimente en 3 días." |
| ✅ No alimente | NDVI↑ + LSP en floración + T°colmena estable | Sentinel-2 + LSP + IoT | "Floración activa. Prepare alzas." |
| 💧 Revise agua | Water Bodies↓ + Precip déficit + LST alta | JRC GSW + Water Bodies + ERA5 | "Posible escasez de agua. Verifique bebederos." |
| 👑 Revise reina | T°colmena fuera de homeostasis sostenida | IoT | "Colonia inestable. Visite en 24–48h." |
| 📍 Reubicar | NDVI bajo prolongado + LSP fin temporada | Sentinel-2 + LSP | "Zona sin floración. Ver mapa de zonas sugeridas." |
| ☀️ Ola de calor | LST + T°colmena altas simultáneas | ERA5 + Sentinel-3 + IoT | "Ola de calor. Garantice sombra y agua." |

---

## 5. Arquitectura del Sistema — Dashboard + App Móvil

```
                    ┌─────────────────────────────┐
                    │     FUENTES DE DATOS         │
                    │  Copernicus · IDEAM · IoT    │
                    │  BEEP Base · datos.gov.co    │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │     PIPELINE DE DATOS        │
                    │  src/ingesta/ + procesamiento│
                    │  Anomalías · IRA · Alertas   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │       BASE DE DATOS          │
                    │  PostgreSQL / CSV procesados │
                    └──────┬───────────────┬───────┘
                           │               │
          ┌────────────────▼──┐     ┌──────▼──────────────────┐
          │  DASHBOARD        │     │  API FastAPI             │
          │  Streamlit Cloud  │     │  /alertas/{id}           │
          │  (jueces y admin) │     │  /ira/{id}               │
          └───────────────────┘     │  /recomendaciones/{id}   │
                                    └──────────┬───────────────┘
                                               │
                                    ┌──────────▼───────────────┐
                                    │  APP MÓVIL               │
                                    │  (apicultor en campo)    │
                                    │  Alertas push            │
                                    │  Semáforo IRA            │
                                    │  Recomendaciones simples │
                                    └──────────────────────────┘
```

**Diferencia entre el dashboard y la app móvil:**

| Funcionalidad | Dashboard Streamlit | App Móvil |
|---|---|---|
| Usuario | Jueces, técnicos, administradores | Apicultor en campo |
| Lenguaje | Técnico (gráficas, series, mapas) | Simple (semáforo, frases cortas) |
| Mapas | Folium interactivo completo | Mapa básico con pin del apiario |
| Datos | Todas las variables y fuentes | Solo la alerta y la recomendación |
| Acceso | URL pública Streamlit Cloud | APK / PWA instalable en celular |
| Notificaciones | No (bajo demanda) | Sí — push automático cuando IRA > 60 |
| Conexión requerida | Sí | Mínima (solo recibir alertas) |

---

## 6. Plan de Trabajo — 3 Semanas

### Semana 1 — Pipeline de datos (Días 1–7)

| Día | Tarea | Entregable |
|---|---|---|
| 1 | Registro y prueba de acceso Copernicus CDSE + CDS API | Credenciales activas, primer query exitoso |
| 1 | Exportar datos IoT colmena: CSV de T° y HR con timestamps | `iot_raw_colmena.csv` limpio |
| 2 | Descargar Sentinel-2 L2A zona San Juan de Rioseco (2022–2025) | Imágenes en `data/raw/copernicus/sentinel2/` |
| 2 | Calcular NDVI y EVI desde bandas B4 y B8 | `ndvi_series.csv` |
| 3 | Descargar LSP global CLMS — índice fenológico zona de estudio | `fenologia_series.csv` con SOS, POS, EOS, AMPL |
| 3 | Construir calendario floral de San Juan de Rioseco desde LSP | `floraciones_sjr.csv` |
| 4 | Descargar ERA5-Land: temperatura, precipitación y ET (2022–2025) | Archivos NetCDF en `data/raw/copernicus/era5_land/` |
| 4 | Descargar JRC Global Surface Water + CLMS Water Bodies zona estudio | `agua_superficial.csv` |
| 5 | Descargar datos IDEAM DHIME — estaciones cercanas Cundinamarca | Datos locales de temperatura y precipitación |
| 5 | Descargar BEEP Base open data — referencia biológica de colmenas | `beep_base_clean.csv` |
| 5–6 | Limpiar y estandarizar datos IoT + BEEP Base (timestamps, nulos, unidades) | `iot_clean.csv` + `beep_reference.csv` |
| 6 | Construir línea base histórica (media y σ por variable, por quincena) | `data/reference/linea_base/` completo |
| 6–7 | Calcular primeras anomalías. Validar coherencia biológica con la apicultora | `anomalias.csv` validado |
| 7 | Commit del pipeline completo en GitHub con README de datos | Repositorio público con pipeline documentado |

---

### Semana 2 — IRA + Alertas + Dashboard + API (Días 8–14)

| Día | Tarea | Entregable |
|---|---|---|
| 8 | Implementar `ira.py`: fórmula completa con 7 componentes ponderados | IRA calculado para datos históricos |
| 8 | Validar IRA: ¿los períodos de sequía 2023–2024 dan IRA alto? | Reporte de validación |
| 9 | Implementar motor de alertas: alimentación, agua, reina, reubicación | `motor_alertas.py` con tests |
| 9–10 | Construir mapa Folium: apiarios, capas NDVI, fenología, agua y zonas IRA | Mapa interactivo funcional |
| 10 | Construir panel IoT en Streamlit: T° y HR con semáforo y referencia BEEP | Panel con datos reales |
| 10 | Construir panel de agua: cuerpos activos en 500m + nivel de alerta | Panel de agua funcional |
| 11 | Construir gráficas Plotly: NDVI, fenología, T°colmena, HR, agua | Series temporales interactivas |
| 11–12 | Integrar todos los componentes en `dashboard.py` | Dashboard completo local |
| 12 | Implementar API FastAPI: endpoints de alertas, IRA y recomendaciones | API corriendo localmente |
| 13 | Desplegar dashboard en Streamlit Cloud — URL pública | URL pública funcional |
| 13 | Desplegar API en Railway o Render (capa gratuita) | API pública con URL |
| 13–14 | Prueba completa del sistema con escenario de alerta real | Sistema validado end-to-end |

---

### Semana 3 — App Móvil + Demo + Presentación (Días 15–21)

| Día | Tarea | Entregable |
|---|---|---|
| 15 | Definir el mejor escenario de alerta real para la demo | Escenario documentado |
| 15–16 | Construir app móvil (PWA o React Native básica) consumiendo la API | App instalable en celular |
| 16 | Implementar notificaciones push en la app para IRA > 60 | Alerta push funcionando en celular |
| 16–17 | Pulir UI del dashboard: branding AbejaVerde·EO, textos claros | Dashboard con identidad visual |
| 17 | Redactar mensajes de alerta en lenguaje natural para el apicultor | Textos de 6 tipos de alerta finalizados |
| 17 | Construir heatmap territorial de riesgo IRA sobre el corredor agrícola | Heatmap integrado al dashboard |
| 18 | Redactar README técnico completo: arquitectura, instrucciones, IRA | README en GitHub |
| 18–19 | Preparar slides del pitch (problema, propuesta, demo, impacto, escala) | Presentación de 5 minutos |
| 19–20 | Ensayos del pitch con demo en vivo — dashboard + app móvil | Pitch ensayado |
| 20 | Revisión final de todos los entregables | Checklist completo |
| 21 | Entrega final + publicación del repositorio GitHub | ✅ Proyecto entregado |

---

## 7. Entregables Finales — Checklist

- [ ] Dashboard Streamlit desplegado con URL pública y demo funcional
- [ ] API FastAPI desplegada — backend para la app móvil
- [ ] App móvil (PWA) instalable en celular con alertas push
- [ ] Datos Sentinel-2 (NDVI/EVI) procesados para San Juan de Rioseco
- [ ] Índice fenológico (LSP) integrado — calendario floral construido
- [ ] JRC Global Surface Water + Water Bodies CLMS integrados
- [ ] ERA5-Land + IDEAM integrados
- [ ] Datos IoT apícolas reales integrados + BEEP Base como referencia
- [ ] IRA calculado con 7 variables para al menos 1 apiario piloto
- [ ] 6 tipos de alerta funcionando (alimentación, agua, reina, reubicación, ola de calor, neutro)
- [ ] Escenario de alerta real demostrable con doble evidencia (satélite + biológico)
- [ ] Repositorio GitHub público documentado
- [ ] Pitch de 5 minutos con demo en vivo (dashboard + app móvil)

---

## 8. Riesgos y Planes de Contingencia

| Riesgo | Probabilidad | Contingencia |
|---|---|---|
| Copernicus API lenta o con cuotas | Media | Predescargar todos los datos en Semana 1. Tener copia local. |
| LSP global sin datos recientes para Colombia | Media | Calcular fenología directamente desde serie NDVI de Sentinel-2 con análisis de picos |
| Datos IoT con gaps o timestamps inconsistentes | Alta | Protocolo de imputación: media móvil de 3 periodos. BEEP Base como respaldo biológico. |
| Sin cuerpos de agua detectables en 500m del apiario | Media | Ampliar radio a 1 km. Usar SWI + precipitación como proxy de disponibilidad hídrica. |
| JRC GSW no tiene datos recientes (solo hasta 2021) | Alta | Complementar con Water Bodies CLMS (actualización 10 días) para estado actual. |
| Streamlit Cloud con límites de memoria | Baja | Usar CSVs preprocesados en el dashboard, no imágenes satelitales crudas. |
| Nubosidad alta en San Juan de Rioseco | Alta | Filtrar imágenes Sentinel-2 con cobertura de nubes < 20%. Interpolar con valor anterior si no hay imagen limpia. |
| Tiempo insuficiente para app móvil completa | Media | Priorizar PWA (Progressive Web App) que funciona en cualquier celular sin instalación desde la tienda. |

---

*Documento de trabajo interno — AbejaVerde·EO — CopernicusLAC Hackathon 2026*
*Versión 2 — Mayo 2026*
