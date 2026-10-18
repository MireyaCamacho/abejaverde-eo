# Prompts para Google Antigravity — AbejaVerde·EO

Abra Google Antigravity con la cuenta Google AI Pro del proyecto, haga clic en
**Open Agent Manager** y seleccione la carpeta de este repositorio (`abejaverde-eo`).
En **Settings → Advanced Settings → Artifact Review Policy** elija **Request Review**,
para que Antigravity muestre el plan y espere su aprobación antes de crear archivos.

La Skill ya está en `.agents/skills/abejaverde-riesgo-apicola/SKILL.md`: Antigravity la lee
automáticamente al abrir la carpeta.

---

## 1. Prompt maestro (pegar en el Agent Manager)

```
Hola Antigravity. No soy programadora y voy a presentar el MVP de "AbejaVerde-EO" en
Acelera Lab. Es una herramienta de alerta temprana para apicultores que cruza el NDVI del
satélite Copernicus con una bitácora semanal de 3 preguntas sobre la colmena y envía un
semáforo de 4 colores por WhatsApp o correo.

Usa la Skill .agents/skills/abejaverde-riesgo-apicola/SKILL.md y los archivos de la
carpeta mvp_aceleralab/. Por favor ejecuta este plan paso a paso y muéstrame los Artifacts:

1. Revisa que las reglas del semáforo sean idénticas en:
   - src/alertas/semaforo.py
   - mvp_aceleralab/apps_script/motor_alertas_abejaverde.gs
   - mvp_aceleralab/simulador_mapa_abejaverde.html
   y ejecuta: python -m pytest tests/test_semaforo.py -v
2. Abre mvp_aceleralab/simulador_mapa_abejaverde.html en tu navegador integrado y
   demuéstrame con el Browser Subagent que API-01 Pacho sale ROJO, API-02 Fusagasugá
   sale VERDE, API-03 San Juan de Rioseco sale NARANJA y API-04 La Mesa sale AMARILLO
   sin envío por falta de autorización. Pulsa "Simular envío semanal" y toma captura.
3. Ejecuta en modo simulación el motor en Python:
   python -m src.alertas.enviar_alertas_semanales mvp_aceleralab/sheets/BD_AbejaVerde_EO_Bitacora_Colmenas.csv --simular --sin-gemini
   y muéstrame la tabla de resultados.
4. Explícame en español sencillo qué debo pegar en Google Earth Engine, en Apps Script
   y en AppSheet, siguiendo mvp_aceleralab/README.md.
```

## 2. Prompt para actualizar el motor de alertas (si se cambia una regla)

```
Actualiza la regla del semáforo de AbejaVerde-EO: [describa el cambio].
Aplícala igual en src/alertas/semaforo.py, mvp_aceleralab/apps_script/motor_alertas_abejaverde.gs,
mvp_aceleralab/simulador_mapa_abejaverde.html y en la sección 1 del SKILL.md.
Agrega un caso de prueba en tests/test_semaforo.py, ejecuta las pruebas y muéstrame la evidencia.
```

## 3. Prompt para preparar la demostración del día de la final

```
Prepara la demostración de AbejaVerde-EO: abre el simulador en el navegador integrado,
deja seleccionado API-01 Pacho con la alerta ROJA visible y genera una captura de pantalla
para la presentación. Luego abre la app con: streamlit run app/app_apicultor.py
y muéstrame la pestaña Diagnóstico con el panel "Recibir esta alerta por WhatsApp o correo".
```
