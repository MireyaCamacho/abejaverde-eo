# Diccionario de Variables — AbejaVerde·EO

| Variable | Fuente | Unidad | Rango normal | Alerta | Descripción |
|---|---|---|---|---|---|
| NDVI | Sentinel-2 L2A | Adimensional (−1 a 1) | 0.30 – 0.70 | < 0.30 sostenido | Verdor de vegetación. Proxy de floración activa. |
| EVI | Sentinel-2 L2A | Adimensional | 0.20 – 0.60 | — | Índice de vegetación mejorado. Complemento NDVI en zonas densas. |
| SOS | LSP CLMS | Día del año | Variable | Retraso > 15 días | Inicio de temporada floral (Start of Season). |
| POS | LSP CLMS | Día del año | Variable | — | Pico de temporada floral (Peak of Season). |
| EOS | LSP CLMS | Día del año | Variable | — | Fin de temporada floral (End of Season). |
| AMPL | LSP CLMS | Adimensional | > 0.15 | < 0.10 | Amplitud de floración. AMPL bajo = cosecha pobre. |
| LST | ERA5-Land / Sentinel-3 | °C | Contextual | Anomalía > +3°C | Temperatura superficial terrestre. |
| Precipitación | ERA5-Land + IDEAM | mm | Variable | Déficit > 40% en 15 días | Lluvia acumulada zona del apiario. |
| SWI | CLMS | % (0–100) | 30 – 70 % | < 20% | Índice de agua en el suelo. |
| FAPAR Anomalía | GDO Copernicus | Adimensional | 0 (sin anomalía) | < −0.10 | Estrés hídrico vegetal. Negativo = estrés. |
| Agua_500m | JRC GSW + Water Bodies | % del histórico | > 80% | < 50% | Cobertura de cuerpos de agua activos en radio 500m. |
| T_colmena ★ | Colmena IoT (REAL) | °C | 34.5 – 35.5 | < 34.0 o > 37.0 | Temperatura interna zona de cría. Bioindicador clave. |
| HR_colmena ★ | Colmena IoT (REAL) | % | 40 – 65 | > 75 | Humedad relativa interna. Afecta maduración de miel. |
| IRA | Calculado | 0 – 100 | 0 – 33 (bajo) | > 67 (alto) | Índice de Riesgo Apícola-Ecosistémico. Score integrado. |
