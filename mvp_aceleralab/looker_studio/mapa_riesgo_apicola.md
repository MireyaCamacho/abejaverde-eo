# Looker Studio — Mapa Territorial de Riesgo Apícola

1. Entre a **lookerstudio.google.com → Crear → Informe → Google Sheets** y elija
   `BD_AbejaVerde_EO` → `Bitacora_Colmenas`.
2. En la fuente de datos, cambie el tipo de `Coordenadas_GPS` a **Geográfico → Latitud, longitud**
   (el formato "4.875, -74.635" funciona tal cual).
3. **Agregar un gráfico → Mapa de burbujas de Google Maps**:
   - Ubicación: `Coordenadas_GPS`
   - Información sobre la herramienta: `ID_Apiario`, `Municipio`
   - Color: `Semaforo_IA` → en **Estilo**, asigne ROJO #E06A5A, NARANJA #F2994A,
     AMARILLO #F2C94C, VERDE #8CC98C.
4. Agregue una **tabla** con ID_Apiario, Municipio, NDVI_Satelite_Copernicus, Semaforo_IA,
   Accion_Recomendada_IA y Estado_Envio, y un **gráfico de anillo** con el número de apiarios
   por color.
5. Agregue un **control de filtro** por Municipio.
6. **Compartir → Obtener enlace**: ese enlace es el tablero para la Secretaría o la
   asociación (no muestra teléfonos ni correos si no agrega esas columnas).
