import pandas as pd 
import csv 
rows_fixed = [] 
with open('lecturas_pesos.csv', 'r', encoding='utf-8') as f: 
    reader = csv.reader(f) 
    header = next(reader) 
    rows_fixed.append(header) 
    for row in reader: 
        if len(row) >= 4 and row[1] == 'p': 
            rows_fixed.append(row[:25]) 
        elif len(row) >= 3 and row[1] not in ['p','t','e','tipo']: 
            new_row = [row[0], 'p', '1'] + row[1:22] 
            rows_fixed.append(new_row[:25]) 
with open('lecturas_pesos.csv', 'w', newline='', encoding='utf-8') as f: 
    csv.writer(f).writerows(rows_fixed) 
print('Filas guardadas:', len(rows_fixed)-1) 
