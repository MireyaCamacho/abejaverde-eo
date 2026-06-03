"""
AbejaVerde·EO — Calibración de celdas de carga en gramos
=========================================================
Ejecutar este script con el nodo conectado al gateway.

INSTRUCCIONES:
1. Coloque un peso CONOCIDO sobre la celda a calibrar
   (recomendado: 2 litros de agua = 2,000 gramos exactos)
2. Ejecute el script y anote el ADC medido
3. El factor de calibración se calcula automáticamente

TARA REGISTRADA (colmena vacía, 2 jun 2026):
   c1  (total_B): 5,623 ADC
   c11 (M5a)    : 4,344 ADC
   c12 (M5b)    : 7,507 ADC

FACTOR PROVISIONAL (hasta calibración real):
   450 ADC por kilogramo
   (válido para celdas de carga de 5kg con HX711 gain=128)
"""

# ── TARA REGISTRADA ───────────────────────────────────────────────────────────
TARA = {
    "c1_total_B": 5623.2,
    "c11_M5a":    4343.6,
    "c12_M5b":    7506.8,
}

# ── FACTOR PROVISIONAL ────────────────────────────────────────────────────────
# Basado en HX711 24-bit, gain=128, celdas de carga 5kg
# SE AJUSTARÁ cuando se realice la calibración con peso conocido
FACTOR_PROVISIONAL_ADC_POR_KG = 450.0

# Nota: para celdas de 20kg el factor típico es ~180 ADC/kg
# Si los valores de peso parecen muy altos, ajustar a 200 ADC/kg


def adc_a_gramos(adc_actual: float, canal: str, factor: float = None) -> float:
    """
    Convierte un valor ADC crudo a gramos.

    Args:
        adc_actual: valor ADC leído por el HX711
        canal:      nombre del canal ("c1_total_B", "c11_M5a", "c12_M5b")
        factor:     ADC por kg (usa FACTOR_PROVISIONAL si None)

    Returns:
        peso en gramos (0.0 si la lectura es menor que la tara)
    """
    tara   = TARA.get(canal, 0)
    factor = factor or FACTOR_PROVISIONAL_ADC_POR_KG
    delta  = adc_actual - tara
    gramos = (delta / factor) * 1000
    return max(0.0, round(gramos, 1))


def calcular_factor_calibracion(
    canal:           str,
    adc_con_peso:    float,
    peso_conocido_g: float,
) -> float:
    """
    Calcula el factor de calibración real a partir de un peso conocido.

    Uso:
        Poner 2,000g sobre la celda → leer ADC → llamar esta función

    Args:
        canal:           nombre del canal
        adc_con_peso:    valor ADC con el peso conocido encima
        peso_conocido_g: peso real en gramos del objeto de calibración

    Returns:
        factor en ADC/kg
    """
    tara  = TARA.get(canal, 0)
    delta = adc_con_peso - tara
    if delta <= 0:
        raise ValueError(f"ADC con peso ({adc_con_peso}) debe ser mayor que tara ({tara})")
    factor = (delta / peso_conocido_g) * 1000
    return round(factor, 2)


def peso_marco_estimado(adc_a: float, adc_b: float, canal_a: str, canal_b: str) -> dict:
    """
    Estima el peso de un marco midiendo las dos celdas en sus extremos.
    El peso del marco = celda_a + celda_b

    Args:
        adc_a, adc_b:    lecturas ADC de los dos extremos del marco
        canal_a, canal_b: nombres de los canales

    Returns:
        dict con peso_g, estado_marco, porcentaje_lleno
    """
    g_a = adc_a_gramos(adc_a, canal_a)
    g_b = adc_a_gramos(adc_b, canal_b)
    peso_total = g_a + g_b

    # Referencia para marcos Langstroth estándar
    # (ajustar según el tipo de marco real del apiario)
    MARCO_VACIO_G   = 300    # marco de madera sin cera
    MARCO_CON_CERA_G = 600   # marco con cera estirada
    MARCO_LLENO_G   = 2800   # marco lleno de miel

    if peso_total < MARCO_VACIO_G:
        estado = "sin_cera"
        pct    = 0
    elif peso_total < MARCO_CON_CERA_G:
        estado = "con_cera_vacia"
        pct    = 10
    elif peso_total < MARCO_LLENO_G * 0.5:
        estado = "medio_lleno"
        pct    = round((peso_total - MARCO_CON_CERA_G) /
                       (MARCO_LLENO_G - MARCO_CON_CERA_G) * 100)
    elif peso_total < MARCO_LLENO_G * 0.8:
        estado = "casi_lleno"
        pct    = round((peso_total - MARCO_CON_CERA_G) /
                       (MARCO_LLENO_G - MARCO_CON_CERA_G) * 100)
    else:
        estado = "lleno"
        pct    = min(100, round((peso_total / MARCO_LLENO_G) * 100))

    return {
        "peso_g":          peso_total,
        "celda_a_g":       g_a,
        "celda_b_g":       g_b,
        "estado_marco":    estado,
        "porcentaje_lleno": pct,
        "listo_para_cosechar": pct >= 80,
    }


# ── DEMO ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  AbejaVerde·EO — Calibración de celdas de carga")
    print("  FACTOR PROVISIONAL: 450 ADC/kg")
    print("  (ajustar cuando la colmena tenga marcos)")
    print("=" * 55)

    print("\nTara registrada (colmena vacía, 2 jun 2026):")
    for canal, val in TARA.items():
        print(f"   {canal:15s}: {val:.1f} ADC → 0g (tara)")

    print("\nSimulación con marcos en distintos estados:")
    escenarios = [
        ("Marco vacío madera",      4479, 4344, "c12_M5b", "c11_M5a"),
        ("Marco con cera vacía",    4614, 4479, "c12_M5b", "c11_M5a"),
        ("Marco a mitad de miel",   5307, 5172, "c12_M5b", "c11_M5a"),
        ("Marco casi lleno (80%)",  5877, 5742, "c12_M5b", "c11_M5a"),
        ("Marco lleno de miel",     6771, 6636, "c12_M5b", "c11_M5a"),
    ]

    for nombre, adc_a, adc_b, canal_a, canal_b in escenarios:
        r = peso_marco_estimado(adc_a, adc_b, canal_a, canal_b)
        cosechar = " ← COSECHAR" if r["listo_para_cosechar"] else ""
        print(f"   {nombre:32s}: {r['peso_g']:5.0f}g  {r['porcentaje_lleno']:3d}%  [{r['estado_marco']}]{cosechar}")

    print("\nPara calibrar con peso real:")
    print("   1. Ponga 2,000g (2L de agua) sobre la celda c12_M5b")
    print("   2. Lea el ADC en el Serial Monitor o captura_colmena.py")
    print("   3. factor = calcular_factor_calibracion('c12_M5b', adc_leido, 2000)")
    print("   4. Actualizar FACTOR_PROVISIONAL_ADC_POR_KG con el valor calculado")
    print("\nSALVEDAD: los pesos son estimados hasta la calibración real.")
    print("El sistema seguirá funcionando con el factor provisional.")
