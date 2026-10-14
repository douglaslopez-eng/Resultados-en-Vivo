import sys, os  
sys.path.insert(0, '.')  
from web_template import HTML_TEMPLATE  
dest = r'dist\web_results\index.html'  
open(dest,'w',encoding='utf-8').write(HTML_TEMPLATE)  
print('OK', os.path.getsize(dest), 'bytes') 
