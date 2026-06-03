"""
AbejaVerde·EO — Captura de datos del nodo IoT v3
-------------------------------------------------
Arquitectura confirmada:
  "t": [ID, voltaje_bat, temp_exterior, hum_exterior, contador, campo5]
  "p": [ID, temp_interior, hum_interior, total_A, total_B,
        M1a,M1b, M2a,M2b, M3a,M3b, M4a,M4b, M5a,M5b,
        M6a,M6b, M7a,M7b, M8a,M8b, M9a,M9b, M10a,M10b]

Al arrancar, captura los primeros N ciclos como TARA y los guarda
en calibracion_tara.csv. Los datos de pesos se guardan en bruto
Y también con la tara restada (peso neto).

Uso: python captura_colmena.py
Requisitos: pip install pyserial
"""

import serial, json, csv, os, datetime

PUERTO = "COM5"
BAUD   = 115200
CICLOS_TARA = 5  # primeros ciclos para calcular tara promedio

NOMBRES_CELDAS = [
    "total_A","total_B",
    "M1a","M1b","M2a","M2b","M3a","M3b","M4a","M4b","M5a","M5b",
    "M6a","M6b","M7a","M7b","M8a","M8b","M9a","M9b","M10a","M10b"
]

CABECERA_T = ["timestamp","nodo_id","voltaje_bat_V",
              "temp_exterior_C","hum_exterior_pct","contador","campo5"]

CABECERA_P = (["timestamp","nodo_id","temp_interior_C","hum_interior_pct"]
              + NOMBRES_CELDAS
              + [n+"_neto" for n in NOMBRES_CELDAS])

CABECERA_TARA = ["timestamp_tara","ciclos_promediados"] + NOMBRES_CELDAS

def escribir_cab(f, cab):
    with open(f,"w",newline="",encoding="utf-8") as fp:
        csv.writer(fp).writerow(cab)

def guardar_fila(f, fila):
    with open(f,"a",newline="",encoding="utf-8") as fp:
        csv.writer(fp).writerow(fila)

def parsear(linea, ts):
    try:
        if '"p":' in linea:
            v = json.loads(linea[linea.find('{"p":'):])["p"]
            fila = [ts]+v
            while len(fila)<4+len(NOMBRES_CELDAS): fila.append(0)
            return ("p", fila[:4+len(NOMBRES_CELDAS)])
        elif '"t":' in linea:
            v = json.loads(linea[linea.find('{"t":'):])["t"]
            fila = [ts]+v
            while len(fila)<len(CABECERA_T): fila.append("")
            return ("t", fila[:len(CABECERA_T)])
    except: pass
    return None

def calcular_tara(muestras_tara):
    """Promedia los ciclos de tara para cada celda."""
    n = len(muestras_tara)
    tara = []
    num_celdas = len(NOMBRES_CELDAS)
    for i in range(num_celdas):
        vals = []
        for m in muestras_tara:
            try: vals.append(float(m[i]))
            except: pass
        tara.append(sum(vals)/len(vals) if vals else 0)
    return tara

def guardar_tara(tara, n_ciclos):
    f = "calibracion_tara.csv"
    existe = os.path.exists(f)
    if not existe:
        escribir_cab(f, CABECERA_TARA)
    ts = datetime.datetime.now().isoformat()
    guardar_fila(f, [ts, n_ciclos] + [round(t,2) for t in tara])
    print(f"\nTara guardada en {f}")
    print("Valores de offset por celda:")
    for nombre, val in zip(NOMBRES_CELDAS, tara):
        if val > 100:
            print(f"  {nombre}: {round(val,1)} uds brutas")
    print()

def main():
    fp = "lecturas_pesos.csv"
    fe = "lecturas_exterior.csv"

    if not os.path.exists(fp):
        escribir_cab(fp, CABECERA_P); print(f"Creado: {fp}")
    if not os.path.exists(fe):
        escribir_cab(fe, CABECERA_T); print(f"Creado: {fe}")

    print(f"\nConectando a {PUERTO} a {BAUD} baud...")
    print(f"Capturando tara en los primeros {CICLOS_TARA} ciclos...")
    print("Ctrl+C para detener.\n" + "-"*70)

    tara = None
    muestras_tara = []
    ciclo_p = 0

    try:
        with serial.Serial(PUERTO, BAUD, timeout=2) as ser:
            print("Conectado. Esperando datos...\n")
            while True:
                try:
                    linea = ser.readline().decode("utf-8",errors="ignore").strip()
                    if not linea: continue
                    ts = datetime.datetime.now().isoformat()
                    r = parsear(linea, ts)
                    if r:
                        tipo, fila = r
                        if tipo == "p":
                            ciclo_p += 1
                            celdas = fila[4:]  # los 22 valores de celdas

                            # Acumular tara
                            if tara is None:
                                muestras_tara.append(celdas)
                                print(f"  Ciclo de tara {len(muestras_tara)}/{CICLOS_TARA}...")
                                if len(muestras_tara) >= CICLOS_TARA:
                                    tara = calcular_tara(muestras_tara)
                                    guardar_tara(tara, CICLOS_TARA)
                                continue  # no guardar los ciclos de tara en el CSV

                            # Calcular netos
                            netos = []
                            for i, c in enumerate(celdas):
                                try: netos.append(round(float(c) - tara[i], 1))
                                except: netos.append(0)

                            # Guardar fila completa (bruto + neto)
                            fila_completa = fila + netos
                            guardar_fila(fp, fila_completa)

                            # Mostrar en pantalla
                            ti = fila[2]; hi = fila[3]
                            try:
                                total_neto = round(netos[0] + netos[1], 1)
                            except: total_neto = 0

                            marcos = []
                            for i in range(10):
                                try:
                                    neto = netos[2+i*2] + netos[3+i*2]
                                    if abs(neto) > 300:
                                        marcos.append(f"M{i+1}:{round(neto,0)}")
                                except: pass

                            print(f"[{ts[:19]}] PESOS (ciclo {ciclo_p})")
                            print(f"  Interior  : {ti}°C  {hi}%")
                            print(f"  Total neto: {total_neto} uds brutas")
                            if marcos:
                                print(f"  Marcos con peso: {' | '.join(marcos)}")
                            else:
                                print(f"  Sin marcos detectados (normal si colmena vacía)")
                            print()

                        elif tipo == "t":
                            guardar_fila(fe, fila)
                            volt=fila[2]; te=fila[3]; he=fila[4]
                            print(f"[{ts[:19]}] EXTERIOR")
                            print(f"  Temp: {te}°C  Hum: {he}%  Bat: {volt}V")
                            print()
                    elif linea and not linea.startswith("..."):
                        print(f"  [nodo] {linea}")
                except UnicodeDecodeError: continue

    except serial.SerialException as e:
        print(f"\nError puerto: {e}")
        print("Verifica que la placa esté conectada y el Serial Monitor cerrado.")
    except KeyboardInterrupt:
        print(f"\nDetenido. Archivos guardados:")
        print(f"  {fp}  — pesos brutos + netos por marco")
        print(f"  {fe}  — temperatura y humedad exterior")
        print(f"  calibracion_tara.csv  — offsets de cada celda")

if __name__ == "__main__":
    main()
