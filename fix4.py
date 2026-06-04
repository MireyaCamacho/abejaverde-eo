content = open('app/app_apicultor.py', encoding='utf-8').read() 
content = content.replace("str(iot['timestamp'])[:16]('%d %b %Y, %H:%M')", "str(iot['timestamp'])[:16]") 
open('app/app_apicultor.py', 'w', encoding='utf-8').write(content) 
print('Listo') 
