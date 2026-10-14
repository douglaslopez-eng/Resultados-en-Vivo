import sys
import os
import json

sys.path.insert(0, r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app")

from web_template import HTML_TEMPLATE

# Load dist config for supabase url
dist_config = json.load(open(r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app\dist\config.json", encoding="utf-8"))
s_url = ""
if dist_config.get("supabase_url") and dist_config.get("supabase_bucket"):
    s_url = f"{dist_config['supabase_url'].rstrip('/')}/storage/v1/object/public/{dist_config['supabase_bucket']}"

web_dir = r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app\dist\web_results"
os.makedirs(web_dir, exist_ok=True)

_tpl_final = HTML_TEMPLATE.replace("{{SUPABASE_URL}}", s_url)
html_path = os.path.join(web_dir, "index.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(_tpl_final)

print("Generated HTML successfully!")
