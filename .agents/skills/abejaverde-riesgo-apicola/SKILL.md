---
name: abejaverde-riesgo-apicola
description: Agente experto en apicultura y observación satelital que detecta desfases entre la floración del territorio (NDVI Copernicus) y las 3 respuestas de la bitácora del apicultor, emitiendo un semáforo de 4 colores, una acción preventiva y la alerta por WhatsApp o correo.
---

# Reglas del Agente de Alerta Temprana AbejaVerde-EO

Proyecto 4 del Manual Técnico Acelera Lab (Gobernación de Cundinamarca · OEI).
Proponente: Arelys Camacho Celis. Apiario piloto: San Juan de Rioseco (4.875, -74.635).

## 0. Idea central
El satélite mira el **supermercado** (la floración del territorio); el apicultor mira la
**despensa** (lo que hay dentro de la colmena). El agente detecta el **desfase** entre los
dos y avisa con días de anticipación.

## 1. Matriz de cruce Territorio (Copernicus) vs. Colmena (3 preguntas)
Entradas:
- `NDVI_Satelite_Copernicus` (Sentinel-2, radio de 1 km alrededor del apiario).
- `Clima_Territorio` (texto libre).
- `P1_Fuerza_Poblacion`: Alta | Media | Baja.
- `P2_Reservas_Miel_Polen`: Altas | Medias | Bajas.
- `P3_Postura_Reina`: Activa | Detenida.

Evalúa en este orden y detente en la primera regla que se cumpla:
1. **ROJO (riesgo crítico de hambruna o abandono):** NDVI < 0.35 y P2 = Bajas y
   (P1 = Alta/Media o P3 = Detenida). Muchas bocas y cero néctar afuera.
2. **NARANJA (alerta preventiva, cuenta regresiva):** NDVI < 0.35 (la colmena aún tiene
   reservas, pero el territorio ya no ofrece alimento).
3. **NARANJA:** NDVI < 0.50 y (P2 = Bajas o P3 = Detenida).
4. **NARANJA:** lluvias intensas o persistentes que impiden el pecoreo.
5. **AMARILLO (vigilancia, problema local):** hay floración pero P1 = Baja, P2 = Bajas o
   P3 = Detenida.
6. **AMARILLO:** colmena bien, pero NDVI < 0.60 (floración por debajo del óptimo).
7. **VERDE (equilibrio óptimo):** NDVI ≥ 0.60, buenas reservas y reina activa.

Las reglas deciden el color. La IA nunca cambia el color: solo redacta la acción.
Las mismas reglas están implementadas en `src/alertas/semaforo.py`,
`mvp_aceleralab/apps_script/motor_alertas_abejaverde.gs` y
`mvp_aceleralab/simulador_mapa_abejaverde.html`. Si cambias una, cambia las tres y corre
`python -m pytest tests/test_semaforo.py`.

## 2. Formato de la acción recomendada
- Una instrucción práctica, máximo 45 palabras, español sencillo de Colombia, sin saltos de línea.
- Incluye la dosis o el manejo exacto de esa semana: jarabe de azúcar 1:1, torta proteica,
  agua limpia cerca, reducir piquera por frío, unir colmenas débiles, colocar alza melaria
  o cosechar.
- Nunca inventes datos que no estén en la bitácora.

## 3. Canales de envío
- Envía por el canal que eligió el apicultor en `Canal_Preferido`: WhatsApp, Correo o Ambos.
- **Nunca envíes** si `Autoriza_Datos_Ley1581` no es `SI` (Ley 1581 de 2012).
- En WhatsApp usa solo la plantilla aprobada `alerta_semaforo_abejaverde`
  (parámetros: apiario, municipio, semáforo, acción).
- Si WhatsApp falla y el canal era solo WhatsApp, envía por correo.
- Registra el resultado en `Estado_Envio` y la fecha en `Fecha_Ultima_Alerta`.
- Las claves (Gemini, WhatsApp) van en Propiedades del script o en `.env`, nunca en el código.

## 4. Casos de prueba obligatorios
| Apiario | Datos | Resultado |
|---|---|---|
| API-01 Pacho | NDVI 0.28 · población Alta · reservas Bajas · reina Activa | ROJO |
| API-02 Fusagasugá | NDVI 0.74 · población Media · reservas Medias · reina Activa | VERDE |
| API-03 San Juan de Rioseco | NDVI 0.31 · población Media · reservas Medias · reina Activa | NARANJA |
| API-04 La Mesa | NDVI 0.70 · población Baja · reservas Medias · reina Detenida | AMARILLO (sin autorización: no se envía) |
