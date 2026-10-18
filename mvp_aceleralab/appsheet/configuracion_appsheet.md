# AppSheet — Bitácora móvil de 3 preguntas

La app de AppSheet es lo que usa el apicultor en el celular. Escribe directamente en la
hoja `BD_AbejaVerde_EO` → pestaña `Bitacora_Colmenas`, y el motor de Apps Script toma
esos datos para calcular el semáforo y enviar la alerta.

## 1. Crear la app
1. En la hoja de Google Sheets: **Extensiones → AppSheet → Crear una app**.
2. AppSheet detecta las columnas. Revise los tipos en **Data → Bitacora_Colmenas → Columns**.

## 2. Tipos de columna

| Columna | Tipo en AppSheet | Valores / notas | ¿La ve el apicultor? |
|---|---|---|---|
| ID_Apiario | Text (Key) | API-01, API-02… | Sí (solo lectura) |
| Municipio | Text | | Sí |
| Coordenadas_GPS | LatLong | Botón para tomar la ubicación con el celular | Sí |
| Email_Apicultor | Email | | Sí |
| NDVI_Satelite_Copernicus | Decimal | Lo llena el equipo desde Earth Engine | No (oculta en el formulario) |
| Clima_Territorio | Text | | No |
| P1_Fuerza_Poblacion | Enum (botones) | Alta · Media · Baja | **Sí: pregunta 1** |
| P2_Reservas_Miel_Polen | Enum (botones) | Altas · Medias · Bajas | **Sí: pregunta 2** |
| P3_Postura_Reina | Enum (botones) | Activa · Detenida | **Sí: pregunta 3** |
| Semaforo_IA | Enum | VERDE · AMARILLO · NARANJA · ROJO | Sí (solo lectura) |
| Accion_Recomendada_IA | LongText | | Sí (solo lectura) |
| Telefono_WhatsApp | Phone | | Sí |
| Canal_Preferido | Enum (botones) | WhatsApp · Correo · Ambos | Sí |
| Autoriza_Datos_Ley1581 | Enum | SI · NO | Sí (obligatoria) |
| Fecha_Ultima_Alerta | DateTime | | Solo lectura |
| Estado_Envio | Text | | Solo lectura |

Para que las preguntas salgan como **botones grandes**: en cada columna Enum,
**Input mode → Buttons**.

## 3. Formulario semanal
- **UX → Views → New view** tipo **Form** sobre `Bitacora_Colmenas`, con el título
  "Bitácora semanal".
- Orden de los campos: ID_Apiario, P1, P2, P3 (y Canal/Teléfono/Autorización solo la primera vez).
- Texto de ayuda de `Autoriza_Datos_Ley1581`: "Autorizo a AbejaVerde·EO a usar mi celular,
  correo y la ubicación de mi apiario solo para enviarme alertas apícolas. Puedo revocar esta
  autorización cuando quiera."

## 4. Semáforo con colores
**UX → Format rules**: una regla por color sobre `Semaforo_IA`
(`[Semaforo_IA] = "ROJO"` → fondo #E06A5A, y así con NARANJA #F2994A, AMARILLO #F2C94C,
VERDE #8CC98C).

## 5. Funcionar sin señal
**Settings → Offline/Sync**: active **The app can run offline** y **Delayed sync**.
Los reportes se guardan en el celular y se suben cuando hay conexión.

## 6. Disparar la alerta al guardar (opcional)
El motor ya corre cada lunes. Si quieren que también corra apenas el apicultor guarda:
**Automation → Bots → New bot** → evento *Adds and updates* en `Bitacora_Colmenas` →
tarea **Call a script** → archivo de Apps Script → función `evaluarRiesgoApicolaYEnviarAlerta`.
