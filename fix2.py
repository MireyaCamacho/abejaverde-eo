import pandas as pd 
content = open('app/app_apicultor.py', encoding='utf-8').read() 
content = content.replace('"timestamp"].strftime', '"timestamp"]).strftime') 
content = content.replace("iot['timestamp'].strftime", "pd.Timestamp(iot['timestamp']).strftime") 
open('app/app_apicultor.py', 'w', encoding='utf-8').write(content) 
print('Listo') 
