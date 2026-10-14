import sys
import os

sys.path.insert(0, r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app")

import cloud_sync
import github_publisher
from web_template import HTML_TEMPLATE

web_dir = r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app\dist\web_results"
os.makedirs(web_dir, exist_ok=True)

# Use dist config
os.chdir(r"c:\Users\Douglas Lopez\.gemini\antigravity-ide\scratch\atletismo_app\dist")

s_cfg = cloud_sync.get_supabase_config()
s_url = ""
if s_cfg.get("url") and s_cfg.get("bucket"):
    s_url = f"{s_cfg['url'].rstrip('/')}/storage/v1/object/public/{s_cfg['bucket']}"

_tpl_final = HTML_TEMPLATE.replace("{{SUPABASE_URL}}", s_url)
html_path = os.path.join(web_dir, "index.html")
with open(html_path, "w", encoding="utf-8") as f:
    f.write(_tpl_final)

ok, msg, url = github_publisher.publish_to_github(web_dir)
print(f"Success: {ok}")
print(f"Message: {msg}")
print(f"URL: {url}")
