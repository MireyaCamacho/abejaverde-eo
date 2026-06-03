# Evidencia de funcionamiento — Nodo IoT de la colmena

> Componente de **bioindicación apícola** de AbejaVerde·EO.  
> Apiario piloto: San Juan de Rioseco, Cundinamarca (4.875° N, -74.635° O).  
> Fecha de verificación: 2 de junio de 2026.

Este documento registra la evidencia de que el nodo de monitoreo de la colmena **captura y transmite datos reales en operación**. Es el componente terrestre que complementa la observación satelital (Sentinel-2 NDVI, Sentinel-1 SAR, ERA5) con respuesta biológica medida en campo.

---

## Hardware del nodo (confirmado por inspección física)

| Componente | Descripción |
|---|---|
| Microcontrolador + radio | Heltec WiFi LoRa 32 V3 (ESP32-S3 + SX1262) |
| Multiplexor | CD74HC4067 (16 canales analógico) |
| Amplificadores | 2× HX711 (24-bit ADC) |
| Sensores de peso — colmena superior | 2 celdas de carga (peso total) |
| Sensores de peso — colmena inferior | 20 celdas de carga (10 marcos × 2 extremos) |
| Sensor ambiental exterior | DHT22/SHT31 en cápsula exterior roja |
| Energía | LiPo 3.7V 4000 mAh + TP4056 + regulador DC-DC BAOTER |
| Comunicación | LoRa 915 MHz → gateway LILYGO LoRa32 |
| Antena | Externa, conector SMA, resorte helicoidal |

**Topología completa:**
```
22 celdas de carga → multiplexor CD74HC4067 → 2× HX711 → Heltec V3 → LoRa 915 MHz → gateway LILYGO
Sensor exterior (cápsula roja) → Heltec V3 → LoRa 915 MHz → gateway LILYGO
```

**Arquitectura de sensores de peso confirmada:**
- 2 celdas miden el **peso total de la colmena superior** (báscula completa).
- 20 celdas miden el **peso por marco** (10 marcos × 1 celda en cada extremo del marco). El peso de cada marco = suma de sus dos celdas extremas.

---

## Comportamiento del firmware

El nodo opera en ciclos de bajo consumo (~33 segundos por ciclo):

1. Despierta de Deep Sleep.
2. Inicializa LoRa y el multiplexor.
3. Recorre los 22 canales de celdas vía los 2 HX711.
4. Lee el sensor exterior (temperatura y humedad ambiente).
5. Transmite dos paquetes JSON por LoRa y espera respuesta 10 s.
6. Entra en Deep Sleep ~30 s y repite.

---

## Paquetes JSON — estructura confirmada

### Paquete `"t"` — sensor exterior (cápsula roja)

```
{"t":[ID, voltaje_bat_V, temp_exterior_C, hum_exterior_pct, contador, campo5]}
```

**Confirmado por prueba física:** al cubrir la cápsula roja con la mano, la temperatura subió de 22.3°C a 26.8°C y la humedad llegó a 100%. Al soltar, los valores volvieron al valor ambiente. Respuesta inequívoca de sensor de temperatura/humedad exterior.

| Campo | Descripción | Valor típico |
|---|---|---|
| 0 | ID del nodo | `1` |
| 1 | Voltaje batería LiPo | ~2.58–2.62 V |
| 2 | **Temperatura exterior (°C)** | ~22.3°C |
| 3 | **Humedad exterior (%)** | ~66% |
| 4 | Contador interno | creciente |
| 5 | Variable adicional | ~2990 |

### Paquete `"p"` — pesos y sensor interior

```
{"p":[ID, temp_interior_C, hum_interior_pct,
      total_A, total_B,
      M1a, M1b, M2a, M2b, M3a, M3b, M4a, M4b, M5a, M5b,
      M6a, M6b, M7a, M7b, M8a, M8b, M9a, M9b, M10a, M10b]}
```

| Campos | Descripción |
|---|---|
| 0 | ID del nodo |
| 1–2 | Temperatura y humedad interior del nodo |
| 3–4 | `total_A`, `total_B` — celdas de peso total colmena superior |
| 5–24 | 20 celdas por marco: `M1a, M1b` ... `M10a, M10b` |

---

## Evidencia: capturas reales del script de captura

Datos capturados automáticamente con `captura_colmena.py` el 2 de junio de 2026.

### Sensor exterior — muestra de 4 ciclos

```
[2026-06-02T19:56:13] EXTERIOR  Temp: 22.3°C  Hum: 66.8%  Bat: 2.61V
[2026-06-02T19:57:00] EXTERIOR  Temp: 22.3°C  Hum: 66.5%  Bat: 2.62V
[2026-06-02T19:57:46] EXTERIOR  Temp: 22.3°C  Hum: 66.4%  Bat: 2.59V
[2026-06-02T19:58:32] EXTERIOR  Temp: 22.3°C  Hum: 66.4%  Bat: 2.59V
```

### Pesos — colmena vacía (valores de tara registrados)

```
[2026-06-02T20:09:36] PESOS (ciclo 6)
  Interior  : 22.3°C  66.2%
  Total neto: -43.2 uds brutas   ← ~0 con tara aplicada, correcto
  Sin marcos detectados (colmena vacía)
```

### Prueba de respuesta del sensor exterior

```
Sin mano:  Temp: 22.3°C  Hum: 66.5%
Con mano:  Temp: 24.3°C  Hum: 100.0%  ← sube con calor corporal
Con mano:  Temp: 25.9°C  Hum: 100.0%
Con mano:  Temp: 26.8°C  Hum: 100.0%
Sin mano:  Temp: 22.6°C  Hum: 67.8%   ← vuelve al valor ambiente
```

### Calibración de tara (colmena vacía, 2 junio 2026)

Archivo `calibracion_tara.csv` generado automáticamente con 5 ciclos promediados:

```
total_B: 5623.2 uds brutas
M5b:     4343.6 uds brutas
M6a:     7506.8 uds brutas
```

Los demás canales tienen offset < 100 uds brutas (ruido de fondo).

---

## Estado de arranque verificado

```
ESP-ROM:esp32s3-20210327
Build:Mar 27 2021
rst:0x1 (POWERON),boot:0x3c (SPI_FAST_FLASH_BOOT)
```

---

## Integración con AbejaVerde·EO

Este nodo aporta la **capa de bioindicación terrestre** del sistema.

| Dato del nodo | Dato Copernicus complementario | Cruce analítico |
|---|---|---|
| Peso por marco (entrada de néctar) | NDVI Sentinel-2 (vegetación activa) | ¿Hay floración disponible y las abejas la están aprovechando? |
| Temperatura exterior | ERA5 (temperatura superficial) | Validación local vs dato satelital regional |
| Humedad exterior | ERA5 (precipitación) | Correlación humedad campo vs clima satelital |
| Peso total colmena | Serie temporal NDVI | Tendencia de producción vs disponibilidad de recursos |

La hipótesis central: **las colmenas registran estrés ecosistémico antes de que sea visible en la producción agrícola.** Una caída de peso en los marcos precede a la caída de NDVI — la colmena lo siente antes de que el satélite lo vea.

---

## Estado del desarrollo al 2 de junio de 2026

| Elemento | Estado |
|---|---|
| Hardware identificado completamente | ✅ Confirmado |
| Firmware funcionando (lectura + transmisión) | ✅ Confirmado |
| 22 celdas de carga operativas | ✅ Confirmado |
| Sensor exterior temperatura/humedad | ✅ Confirmado y verificado |
| Voltaje de batería en telemetría | ✅ Disponible |
| Script de captura automática a CSV | ✅ Operativo |
| Tara de colmena vacía registrada | ✅ 2 junio 2026 |
| Transmisión LoRa 915 MHz | ✅ Funcional |
| Gateway receptor LILYGO | ✅ Operativo |
| Calibración en gramos (factor de escala) | ⏳ Pendiente — requiere peso conocido |
| Mapeo celda física ↔ canal JSON | ⏳ Pendiente — confirmar con ingeniera |
| Gateway → backend → IRA | ⏳ Fase 2 |
