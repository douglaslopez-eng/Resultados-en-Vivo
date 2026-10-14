import sys

def patch_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    replacements = [
        ('if ev["type"] == "Pista":', 'if ev["type"] in ("Pista", "Piscina"):'),
        ('if event["type"] == "Pista":', 'if event["type"] in ("Pista", "Piscina"):'),
        ('if event_type == "Pista":', 'if event_type in ("Pista", "Piscina"):'),
        ('if ev_type == "Pista":', 'if ev_type in ("Pista", "Piscina"):'),
        ('if item["event_type"] == "Pista":', 'if item["event_type"] in ("Pista", "Piscina"):'),
        ('event_type == "Pista" else', 'event_type in ("Pista", "Piscina") else'),
        ('ev["type"] == "Pista"', 'ev["type"] in ("Pista", "Piscina")')
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

patch_file('main.py')
patch_file('seeding.py')
patch_file('test_export.py')
