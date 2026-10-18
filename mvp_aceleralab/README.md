# AbejaVerde·EO — MVP Acelera Lab (Google AI Pro + Antigravity)

Kit del **Proyecto 4 del Manual Técnico Acelera Lab** (Gobernación de Cundinamarca · OEI),
actualizado con **alertas por WhatsApp o correo electrónico**.

> El satélite mira el **supermercado** (la floración del territorio).
> La apicultora mira la **despensa** (lo que hay dentro de la colmena).
> El agente de IA detecta el desfase y avisa con días de anticipación.

## Arquitectura

```
 Copernicus Sentinel-2 ──► Google Earth Engine ──► NDVI por apiario ─┐
                                                                      ▼
 Apicultor (celular) ──► AppSheet: 3 preguntas ──► Google Sheets: BD_AbejaVerde_EO
                                                                      │
                          Skill abejaverde-riesgo-apicola (Antigravity)
                                                                      ▼
                    Apps Script: reglas del semáforo + Gemini (redacta la acción)
                                     │                         │
                         WhatsApp Cloud API (Meta)       Gmail (MailApp)
                                     └──────────┬──────────────┘
                                                ▼
                       Apicultor recibe: semáforo + acción de la semana
                                                │
                      Looker Studio: mapa territorial de riesgo apícola
```

La app de Streamlit (`app/app_apicultor.py`) y el motor en Python
(`src/alertas/`) usan **exactamente las mismas reglas**, así que el resultado es igual en
Google Sheets, en la app y en el simulador.

## Contenido de esta carpeta

| Archivo | Para qué sirve |
|---|---|
| `../.agents/skills/abejaverde-riesgo-apicola/SKILL.md` | La habilidad que lee Antigravity: matriz del semáforo, formato de la acción y reglas de envío |
| `prompt_maestro_antigravity.md` | Los prompts para pegar en el Agent Manager de Antigravity |
| `earth_engine/copernicus_ndvi_cundinamarca.js` | NDVI Sentinel-2 por apiario, serie mensual del piloto y exportación a Drive |
| `sheets/BD_AbejaVerde_EO_Bitacora_Colmenas.csv` | Plantilla de la hoja con 4 apiarios de prueba |
| `apps_script/motor_alertas_abejaverde.gs` | Motor de alertas v2: semáforo, Gemini, WhatsApp, correo, Ley 1581, envío semanal |
| `appsheet/configuracion_appsheet.md` | Cómo armar la bitácora de 3 preguntas en el celular (funciona sin señal) |
| `looker_studio/mapa_riesgo_apicola.md` | Cómo armar el mapa territorial de riesgo |
| `simulador_mapa_abejaverde.html` | Demo visual del semáforo de 4 colores, el mapa y la alerta (se abre en el navegador) |

## Paso a paso

### 1. Hoja de Google Sheets
1. Cree una hoja llamada `BD_AbejaVerde_EO` con una pestaña `Bitacora_Colmenas`.
2. **Archivo → Importar → Subir** `sheets/BD_AbejaVerde_EO_Bitacora_Colmenas.csv`
   → *Reemplazar hoja actual*.
3. Cambie `tu_correo@ejemplo.com` y `3000000000` por su correo y su celular reales para la prueba.

### 2. Earth Engine (NDVI de Copernicus)
1. Abra `code.earthengine.google.com` con la cuenta del proyecto.
2. Pegue `earth_engine/copernicus_ndvi_cundinamarca.js` y pulse **Run**.
3. Copie los valores `NDVI_Satelite_Copernicus` de la consola a la hoja
   (o ejecute la tarea de la pestaña **Tasks** para recibir el CSV en Drive).

### 3. Motor de alertas en Apps Script
1. En la hoja: **Extensiones → Apps Script**, pegue completo
   `apps_script/motor_alertas_abejaverde.gs` y guarde.
2. Recargue la hoja. Aparece el menú **AbejaVerde·EO**:
   1. **Preparar hoja**: crea las listas desplegables.
   2. **Configurar claves**: API Key de Gemini, token y Phone number ID de WhatsApp.
   3. **Probar WhatsApp**: envía el "Hello World" de Meta.
   4. **Evaluar y enviar alertas**.
   5. **Programar envío semanal** (lunes 7 a.m.).

### 4. WhatsApp (Meta)
- **Demostración (gratis):** developers.facebook.com → crear app *Business* → producto
  **WhatsApp** → número de prueba → agregar los celulares destinatarios → copiar
  *Phone number ID* y generar el *token temporal* (vence pronto: genérelo el día de la demo).
- **Plantilla** (WhatsApp Manager → Plantillas, categoría *Utilidad*, idioma español),
  nombre `alerta_semaforo_abejaverde`:
  ```
  AbejaVerde·EO – Apiario {{1}} ({{2}}). Semáforo: {{3}}.
  Acción recomendada esta semana: {{4}}
  Si necesita apoyo, comuníquese con su técnico de AbejaVerde.
  ```
- **Piloto:** número propio de WhatsApp Business, negocio verificado y token permanente de
  usuario del sistema (permisos `whatsapp_business_messaging` y `whatsapp_business_management`).
- Cada plantilla de utilidad tiene un costo por mensaje según la tarifa de Meta para Colombia.

### 5. AppSheet y Looker Studio
Siga `appsheet/configuracion_appsheet.md` y `looker_studio/mapa_riesgo_apicola.md`.

### 6. Antigravity
Abra esta carpeta en Antigravity y pegue el prompt maestro de `prompt_maestro_antigravity.md`.

## Prueba en vivo para la mentoría

| Apiario | Datos | Semáforo | Envío |
|---|---|---|---|
| API-01 Pacho | NDVI 0.28 · población Alta · reservas Bajas · reina Activa | **ROJO** | WhatsApp + correo |
| API-02 Fusagasugá | NDVI 0.74 · Media · Medias · Activa | **VERDE** | Correo |
| API-03 San Juan de Rioseco | NDVI 0.31 · Media · Medias · Activa | **NARANJA** (cuenta regresiva) | WhatsApp |
| API-04 La Mesa | NDVI 0.70 · Baja · Medias · Detenida | **AMARILLO** | No se envía: sin autorización Ley 1581 |

Sin Google ni Meta configurados, se puede probar todo en el computador:

```bash
# Pruebas automáticas del semáforo y del envío
python -m pytest tests/test_semaforo.py -v

# Motor en Python sobre la plantilla, sin enviar nada
python -m src.alertas.enviar_alertas_semanales mvp_aceleralab/sheets/BD_AbejaVerde_EO_Bitacora_Colmenas.csv --simular --sin-gemini

# Simulador visual: abrir en el navegador
mvp_aceleralab/simulador_mapa_abejaverde.html
```

## Datos personales (Ley 1581 de 2012)
Ningún canal envía mensajes si `Autoriza_Datos_Ley1581` no es `SI`. Texto sugerido de
autorización:

> Autorizo a AbejaVerde·EO a tratar mi nombre, número de celular, correo electrónico y la
> ubicación de mi apiario con la única finalidad de enviarme alertas y recomendaciones
> apícolas por WhatsApp y/o correo. Sé que puedo conocer, actualizar, rectificar o revocar
> esta autorización en cualquier momento escribiendo a [correo de contacto del proyecto].
