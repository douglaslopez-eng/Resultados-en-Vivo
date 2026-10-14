import os

file_path = "main.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# We want to replace the `def print_swimming_report(self):` block up to `if __name__ == "__main__":`

new_methods = """
    def print_swimming_seeding(self):
        \"\"\"Genera un reporte de siembra HTML estilo Meet Manager para eventos de natación.\"\"\"
        import os
        import webbrowser
        import datetime

        comp_data = database.get_competition_dates()
        comp_name = comp_data.get("competition_name") or "Competencia de Natación"

        conn = database.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, category, gender, type, round FROM events ORDER BY name ASC")
        events = [dict(r) for r in cursor.fetchall()]

        def swim_sort_key(e):
            g = str(e.get("gender", "")).lower()
            is_male = 1 if any(w in g for w in ["masculino", "varón", "varon", "niño", "nino", "hombre"]) else 0
            return (is_male, e.get("category", ""), e.get("name", ""))

        events.sort(key=swim_sort_key)

        css = (
            "body{font-family:'Courier New',Courier,monospace;padding:20px;background:#fff;color:#000;font-size:12px;line-height:1.2;}"
            "h1{text-align:center;font-size:16px;margin-bottom:2px;font-family:Arial,sans-serif;}"
            ".subtitle{text-align:center;font-size:12px;margin-bottom:20px;font-family:Arial,sans-serif;}"
            ".event-title{font-size:13px;font-weight:bold;margin-top:15px;margin-bottom:2px;border-bottom:1px solid #000;}"
            "table{width:100%;border-collapse:collapse;margin-bottom:5px;table-layout:fixed;}"
            "th{border-bottom:1px solid #000;padding:2px 4px;text-align:left;font-size:12px;font-weight:normal;}"
            "td{padding:1px 4px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}"
            ".col-lane{width:5%;}"
            ".col-name{width:40%;}"
            ".col-age{width:10%;}"
            ".col-team{width:25%;}"
            ".col-seed{width:20%;}"
            ".heat-title{font-weight:bold;margin-top:10px;margin-bottom:2px;}"
            ".no-print{text-align:right;margin-bottom:10px;}"
            ".no-print button{padding:6px 12px;font-size:12px;background:#0284c7;color:white;border:none;cursor:pointer;}"
            "@media print{.no-print{display:none;} body{padding:0;} @page{margin:1cm;}}"
        )

        lines = [
            "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>",
            f"<title>Siembras Natacion - {comp_name}</title>",
            f"<style>{css}</style></head><body>",
            "<div class='no-print'><button onclick='window.print()'>&#128424; Imprimir Siembras</button></div>",
            "<h1>Reporte de Siembras (Meet Program)</h1>",
            f"<p class='subtitle'>{comp_name}</p>",
        ]

        event_counter = 0
        for event in events:
            event_id = event["id"]
            cursor.execute(
                \"\"\"
                SELECT r.*, a.name AS athlete_name, a.club AS athlete_club,
                       a.bib_number AS athlete_bib, a.birth_date
                FROM registrations r
                JOIN athletes a ON a.id = r.athlete_id
                WHERE r.event_id = ?
                ORDER BY r.heat_number ASC, r.lane_number ASC
                \"\"\",
                (event_id,)
            )
            results = [dict(r) for r in cursor.fetchall()]

            if not results:
                continue

            event_counter += 1
            ev_gender = event.get("gender", "")
            ev_category = event.get("category", "")
            ev_name = event.get("name", "")
            ev_round = event.get("round") or "Prelims"
            event_title = f"Event {event_counter} {ev_gender} {ev_category} {ev_name} - {ev_round}"

            lines.append(f"<div class='event-title'>{event_title}</div>")
            
            # Agrupar por Heat
            heats = {}
            for r in results:
                h = r.get("heat_number") or 1
                if h not in heats:
                    heats[h] = []
                heats[h].append(r)
                
            for h in sorted(heats.keys()):
                lines.append(f"<div class='heat-title'>Heat {h}</div>")
                lines.append("<table><thead><tr>")
                lines.append("<th class='col-lane'>Lane</th><th class='col-name'>Name</th><th class='col-age'>Age</th><th class='col-team'>Team</th><th class='col-seed'>Seed Time</th>")
                lines.append("</tr></thead><tbody>")
                
                for r in heats[h]:
                    lane_str = str(r.get("lane_number") or "-")
                    
                    age_str = ""
                    birth_raw = r.get("birth_date", "")
                    if birth_raw:
                        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                            try:
                                birth_dt = datetime.datetime.strptime(str(birth_raw), fmt)
                                age_str = str(datetime.datetime.now().year - birth_dt.year)
                                break
                            except ValueError:
                                continue
                                
                    name = r.get("athlete_name", "")
                    club = r.get("athlete_club", "")
                    seed = r.get("seed_time", "") or "NT"
                    
                    lines.append(f"<tr><td class='col-lane'>{lane_str}</td><td class='col-name'>{name}</td><td class='col-age'>{age_str}</td><td class='col-team'>{club}</td><td class='col-seed'>{seed}</td></tr>")
                
                lines.append("</tbody></table>")

        conn.close()
        lines.append("<script>window.onload = function() { setTimeout(function(){ window.print(); }, 500); }</script>")
        lines.append("</body></html>")

        file_path_html = os.path.join(os.path.expanduser("~"), "siembras_natacion.html")
        try:
            with open(file_path_html, "w", encoding="utf-8") as f:
                f.write("\\n".join(lines))
            webbrowser.open("file:///" + file_path_html.replace("\\\\", "/"))
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"No se pudo generar el reporte: {e}")

    def print_swimming_report(self):
        \"\"\"Genera un reporte HTML estilo Meet Manager para eventos de natación.\"\"\"
        import os
        import webbrowser
        import datetime

        comp_data = database.get_competition_dates()
        comp_name = comp_data.get("competition_name") or "Competencia de Natación"

        conn = database.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, category, gender, type, round FROM events ORDER BY name ASC")
        events = [dict(r) for r in cursor.fetchall()]

        def swim_sort_key(e):
            g = str(e.get("gender", "")).lower()
            is_male = 1 if any(w in g for w in ["masculino", "varón", "varon", "niño", "nino", "hombre"]) else 0
            return (is_male, e.get("category", ""), e.get("name", ""))

        events.sort(key=swim_sort_key)

        css = (
            "body{font-family:'Courier New',Courier,monospace;padding:20px;background:#fff;color:#000;font-size:12px;line-height:1.2;}"
            "h1{text-align:center;font-size:16px;margin-bottom:2px;font-family:Arial,sans-serif;}"
            ".subtitle{text-align:center;font-size:12px;margin-bottom:20px;font-family:Arial,sans-serif;}"
            ".event-title{font-size:13px;font-weight:bold;margin-top:15px;margin-bottom:2px;border-bottom:1px solid #000;}"
            "table{width:100%;border-collapse:collapse;margin-bottom:15px;table-layout:fixed;}"
            "th{border-bottom:1px solid #000;padding:2px 4px;text-align:left;font-size:12px;font-weight:normal;}"
            "td{padding:1px 4px;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}"
            ".col-rank{width:5%;}"
            ".col-name{width:40%;}"
            ".col-age{width:10%;}"
            ".col-team{width:25%;}"
            ".col-time{width:20%;}"
            ".no-print{text-align:right;margin-bottom:10px;}"
            ".no-print button{padding:6px 12px;font-size:12px;background:#0284c7;color:white;border:none;cursor:pointer;}"
            "@media print{.no-print{display:none;} body{padding:0;} @page{margin:1cm;}}"
        )

        lines = [
            "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>",
            f"<title>Resultados Natacion - {comp_name}</title>",
            f"<style>{css}</style></head><body>",
            "<div class='no-print'><button onclick='window.print()'>&#128424; Imprimir Resultados</button></div>",
            "<h1>Resultados Oficiales (Meet Results)</h1>",
            f"<p class='subtitle'>{comp_name}</p>",
        ]

        event_counter = 0
        for event in events:
            event_id = event["id"]
            cursor.execute(
                \"\"\"
                SELECT r.*, a.name AS athlete_name, a.club AS athlete_club,
                       a.bib_number AS athlete_bib, a.birth_date
                FROM registrations r
                JOIN athletes a ON a.id = r.athlete_id
                WHERE r.event_id = ?
                ORDER BY r.is_disqualified ASC, r.result_value ASC
                \"\"\",
                (event_id,)
            )
            results = [dict(r) for r in cursor.fetchall()]

            if not results:
                continue

            event_counter += 1
            ev_gender = event.get("gender", "")
            ev_category = event.get("category", "")
            ev_name = event.get("name", "")
            ev_round = event.get("round") or "Final"
            event_title = f"Event {event_counter} {ev_gender} {ev_category} {ev_name} - {ev_round}"

            lines.append(f"<div class='event-title'>{event_title}</div>")
            lines.append("<table><thead><tr>")
            lines.append("<th class='col-rank'>Rank</th><th class='col-name'>Name</th><th class='col-age'>Age</th><th class='col-team'>Team</th><th class='col-time'>Finals Time</th>")
            lines.append("</tr></thead><tbody>")

            rank = 0
            for r in results:
                is_dq = bool(r.get("is_disqualified"))
                if not is_dq:
                    rank += 1
                    rank_str = str(rank)
                else:
                    rank_str = "DQ"

                age_str = ""
                birth_raw = r.get("birth_date", "")
                if birth_raw:
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            birth_dt = datetime.datetime.strptime(str(birth_raw), fmt)
                            age_str = str(datetime.datetime.now().year - birth_dt.year)
                            break
                        except ValueError:
                            continue

                result_display = r.get("result", "-") or "-"
                name = r.get("athlete_name", "")
                club = r.get("athlete_club", "")

                lines.append(f"<tr><td class='col-rank'>{rank_str}</td><td class='col-name'>{name}</td><td class='col-age'>{age_str}</td><td class='col-team'>{club}</td><td class='col-time'>{result_display}</td></tr>")
                
            lines.append("</tbody></table>")

        conn.close()
        lines.append("<script>window.onload = function() { setTimeout(function(){ window.print(); }, 500); }</script>")
        lines.append("</body></html>")

        file_path_html = os.path.join(os.path.expanduser("~"), "resultados_natacion.html")
        try:
            with open(file_path_html, "w", encoding="utf-8") as f:
                f.write("\\n".join(lines))
            webbrowser.open("file:///" + file_path_html.replace("\\\\", "/"))
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Error", f"No se pudo generar el reporte: {e}")
"""

import re
pattern = re.compile(r"    def print_swimming_report\(self\):.*?if __name__ == \"__main__\":", re.DOTALL)
new_content = pattern.sub(new_methods + '\\n\\nif __name__ == "__main__":', content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)
print("Patch applied to main.py")
