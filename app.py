# =============================================================================
# AtletismoPro — Pagina Web Publica de Consulta
# Copyright (c) 2025-2026 Douglas Jose Lopez Lopez
# Todos los derechos reservados.
#
# Lee datos desde Supabase Storage (nube) cuando DATA_URL esta configurado,
# o desde la base de datos SQLite local para desarrollo.
# =============================================================================

import os
import sys
import base64
import json
import requests
import streamlit as st
import pandas as pd
from datetime import datetime

DATA_URL = os.environ.get("ATLETISMO_DATA_URL", "")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Carga de datos: nube o local
# ---------------------------------------------------------------------------
@st.cache_data(ttl=30)
def load_data(db_name=None):
    """Carga los datos desde Supabase Storage (DATA_URL) o desde SQLite local."""
    if DATA_URL:
        try:
            resp = requests.get(DATA_URL, timeout=10)
            resp.raise_for_status()
            return resp.json(), None
        except Exception as e:
            return None, f"Error al cargar datos desde la nube: {e}"
    else:
        # Modo local: leer de SQLite
        try:
            import database
            original_path = database.DB_PATH
            if db_name:
                new_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name)
                database.DB_PATH = new_path
            try:
                database.init_db()
                database.init_combined_marks_table()
                result = _build_from_local_db()
            finally:
                # Restaurar el path original para no afectar al resto de la app
                database.DB_PATH = original_path
            return result, None
        except Exception as e:
            return None, f"Error al leer base de datos local: {e}"


def _build_from_local_db():
    import database
    comp       = database.get_competition_dates()
    all_events = database.get_events()
    jornadas   = database.get_jornadas()

    ev_jornada = {}
    for j in jornadas:
        for s in database.get_schedules_for_jornada(j["id"]):
            eid = s.get("event_id")
            if eid:
                ev_jornada[eid] = j["name"]

    events_out = []
    for ev in all_events:
        regs      = database.get_registrations_for_event(ev["id"])
        order_asc = ev["type"] == "Pista"
        valid_regs = [r for r in regs if r.get("result_value") is not None]
        valid_regs.sort(key=lambda r: r.get("result_value", 0), reverse=not order_asc)
        results_out = []
        for i, r in enumerate(valid_regs):
            results_out.append({
                "rank": i+1 if not r.get("is_disqualified") else None,
                "athlete_name": r.get("athlete_name",""),
                "athlete_club": r.get("athlete_club",""),
                "athlete_category": r.get("athlete_category",""),
                "bib": r.get("athlete_bib",""),
                "result": r.get("result",""),
                "wind_speed": r.get("wind_speed"),
                "is_disqualified": bool(r.get("is_disqualified")),
                "status": r.get("status") or "Normal",
            })
        seedings_out = []
        for r in regs:
            seedings_out.append({
                "athlete_name": r.get("athlete_name",""),
                "athlete_club": r.get("athlete_club",""),
                "athlete_category": r.get("athlete_category",""),
                "bib": r.get("athlete_bib",""),
                "heat_number": r.get("heat_number"),
                "lane_number": r.get("lane_number"),
                "order_number": r.get("order_number"),
                "personal_best": r.get("personal_best"),
            })
        events_out.append({
            "id": ev["id"], "name": ev["name"], "category": ev["category"],
            "gender": ev["gender"], "type": ev["type"],
            "round": ev.get("round") or "Final",
            "jornada": ev_jornada.get(ev["id"],""),
            "results": results_out,
            "seedings": seedings_out,
            "podium": [r for r in results_out[:3] if not r["is_disqualified"]],
            "has_results": len(results_out) > 0,
        })
    schedule_out = []
    for j in jornadas:
        evs_in_j = []
        for s in database.get_schedules_for_jornada(j["id"]):
            eid = s.get("event_id")
            if not eid: continue
            ev_info = next((e for e in all_events if e["id"]==eid), None)
            if ev_info:
                evs_in_j.append({"name":ev_info["name"],"category":ev_info["category"],"gender":ev_info["gender"],"type":ev_info["type"],"round":ev_info.get("round") or "Final","time":s.get("event_time","")})
        schedule_out.append({"name":j["name"],"events":evs_in_j})
    db_name = database.get_db_name()
    if db_name.endswith(".db"): db_name=db_name[:-3]
    return {
        "meta": {"generated_at": datetime.now().isoformat(), "db_name": db_name},
        "competition_info": {"competition_name": comp.get("competition_name") or db_name, "start_date": comp.get("start_date",""), "end_date": comp.get("end_date","")},
        "events": events_out,
        "medal_table": database.get_medal_table(None),
        "schedule": schedule_out,
        "clubs": database.get_athletes_count_per_club(),
    }


# ---------------------------------------------------------------------------
# Configuracion pagina
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AtletismoPro — Resultados", page_icon="🏃", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Outfit:wght@400;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
.stApp{background:#f1f5f9;}

/* Sidebar */
[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid #e2e8f0;}
[data-testid="stSidebar"] *{color:#0f172a !important;}
[data-testid="stSidebar"] .stRadio label{color:#475569 !important;font-weight:500;}
[data-testid="stSidebar"] .stRadio [data-checked="true"] label{color:#2563eb !important;font-weight:700;}
[data-testid="stSidebar"] button{background:#2563eb !important;color:#fff !important;border:none !important;border-radius:10px !important;font-weight:600 !important;}
[data-testid="stSidebar"] button:hover{background:#1d4ed8 !important;}
hr{border-color:#e2e8f0 !important;}

/* Hero */
.hero-banner{background:linear-gradient(135deg,#1e3a8a 0%,#2563eb 60%,#4f46e5 100%);border-radius:18px;padding:2.5rem 2.5rem;margin-bottom:1.8rem;box-shadow:0 8px 24px rgba(37,99,235,0.25);}
.hero-title{font-family:'Outfit',sans-serif;font-size:2.4rem;font-weight:900;color:#ffffff;margin:0 0 0.3rem 0;letter-spacing:-0.5px;}
.hero-subtitle{font-size:1rem;color:rgba(255,255,255,0.8);margin:0;font-weight:500;}
.hero-dates{font-size:0.9rem;color:rgba(255,255,255,0.7);margin-top:0.6rem;font-weight:500;}

/* Stat cards */
.stat-card{background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:1.4rem 1.5rem;text-align:center;margin-bottom:0.8rem;box-shadow:0 1px 3px rgba(0,0,0,0.06);transition:box-shadow .2s;}
.stat-card:hover{box-shadow:0 4px 12px rgba(0,0,0,0.08);}
.stat-number{font-family:'Outfit',sans-serif;font-size:2.5rem;font-weight:900;color:#2563eb;line-height:1;letter-spacing:-1px;}
.stat-label{font-size:0.8rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.06em;font-weight:600;margin-top:4px;}

/* Section titles */
.section-title{font-family:'Outfit',sans-serif;font-size:1.4rem;font-weight:800;color:#0f172a;border-left:4px solid #2563eb;padding-left:0.8rem;margin:1.8rem 0 1rem 0;}

/* Chips */
.chip{background:#eff6ff;color:#2563eb;border-radius:20px;padding:3px 12px;font-size:0.78rem;font-weight:600;border:1px solid #bfdbfe;}
.chip-f{background:#fdf2f8;color:#9333ea;border:1px solid #e9d5ff;}

/* Rows */
.sched-row{display:flex;align-items:center;gap:1.2rem;padding:0.85rem 1.2rem;border-radius:10px;margin-bottom:0.5rem;background:#ffffff;border:1px solid #e2e8f0;box-shadow:0 1px 2px rgba(0,0,0,0.04);}
.sched-time{font-family:'Outfit',sans-serif;font-size:1.3rem;font-weight:800;color:#2563eb;min-width:5rem;text-align:center;}
.medal-row{display:flex;align-items:center;gap:1rem;padding:0.75rem 1.2rem;border-radius:10px;margin-bottom:0.4rem;background:#ffffff;border:1px solid #e2e8f0;box-shadow:0 1px 2px rgba(0,0,0,0.04);}
.medal-pos{font-family:'Outfit',sans-serif;font-size:1.1rem;font-weight:900;color:#94a3b8;min-width:2rem;text-align:center;}
.medal-club{flex:1;font-weight:700;color:#0f172a;font-size:0.95rem;}

/* Podio cards */
.event-card{background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;transition:transform .2s,box-shadow .2s;box-shadow:0 1px 3px rgba(0,0,0,0.06);margin-bottom:1rem;}
.event-card:hover{transform:translateY(-3px);box-shadow:0 10px 15px -3px rgba(0,0,0,0.1),0 4px 6px -4px rgba(0,0,0,0.1);}
.event-card-header{padding:16px 20px;background:#f8fafc;border-bottom:1px solid #e2e8f0;}
.event-card-name{font-weight:800;font-size:1.05rem;color:#0f172a;}
.event-card-detail{font-size:0.82rem;color:#64748b;margin-top:4px;}
.podium-row{display:flex;align-items:center;gap:14px;padding:12px 20px;border-bottom:1px solid #e2e8f0;}
.podium-row:last-child{border-bottom:none;}
.p-name{font-weight:700;color:#0f172a;flex:1;font-size:0.95rem;}
.p-club{font-size:0.82rem;color:#64748b;}
.p-mark{font-weight:900;color:#2563eb;background:#eff6ff;padding:4px 12px;border-radius:8px;font-size:0.95rem;}

/* Divider */
.divider{height:1px;background:#e2e8f0;margin:1.8rem 0;}

/* Dataframe overrides */
[data-testid="stDataFrame"]{border:1px solid #e2e8f0 !important;border-radius:12px !important;overflow:hidden;}
.stDataFrame [data-testid="stDataFrame"] th { background:#f8fafc !important; color:#475569 !important; }
.stDataFrame [data-testid="stDataFrame"] td { color:#0f172a !important; }

/* Expanders */
[data-testid="stExpander"] { background:#ffffff !important; border:1px solid #e2e8f0 !important; border-radius:12px !important; }
[data-testid="stExpander"] summary { color:#0f172a !important; }

/* Text input */
.stTextInput > div > div > input { background:#ffffff !important; border:1px solid #e2e8f0 !important; color:#0f172a !important; border-radius:10px !important; }

/* Info / Warning */
.stAlert { background:#f8fafc !important; border:1px solid #e2e8f0 !important; border-radius:10px !important; color:#475569 !important; }

footer,#MainMenu,.stDeployButton{display:none!important;}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------


def gc(gender):
    if gender=="Femenino": return '<span class="chip chip-f">Femenino</span>'
    if gender=="Masculino": return '<span class="chip">Masculino</span>'
    return '<span class="chip">Mixto</span>'

def fmt_date(d):
    try: return datetime.strptime(d,"%Y-%m-%d").strftime("%d/%m/%Y")
    except: return d or ""

def get_logo_b64():
    p=os.path.join(os.path.dirname(os.path.abspath(__file__)),"logo.png")
    if os.path.exists(p):
        with open(p,"rb") as f: return base64.b64encode(f.read()).decode()
    return None

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
logo_b64 = get_logo_b64()
with st.sidebar:
    if logo_b64:
        st.markdown(f'<div style="text-align:center;margin-bottom:0.5rem;"><img src="data:image/png;base64,{logo_b64}" style="width:70px;border-radius:8px;"></div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;font-family:Outfit,sans-serif;font-size:1.1rem;font-weight:800;color:#0f172a;margin:0 0 0.2rem 0;">AtletismoPro</p>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;font-size:0.75rem;color:#94a3b8;margin:0 0 1.2rem 0;">Resultados en vivo</p>', unsafe_allow_html=True)
    st.markdown('<hr style="border:none;border-top:1px solid #e2e8f0;margin:0 0 1rem 0;">', unsafe_allow_html=True)
    nav = st.radio("Seccion", ["🏟️ Inicio","📅 Programa","🌱 Siembras","🏅 Resultados","🏆 Medalleria","👥 Clubes"], label_visibility="collapsed")
    st.markdown('<hr style="border:none;border-top:1px solid #e2e8f0;margin:1rem 0 0.5rem 0;">', unsafe_allow_html=True)
    if DATA_URL:
        st.markdown(f'<p style="font-size:0.68rem;color:#059669;text-align:center;font-weight:600;">🟢 Conectado a nube</p>', unsafe_allow_html=True)
        selected_db = None
    else:
        st.markdown('<p style="font-size:0.68rem;color:#d97706;text-align:center;font-weight:600;">🟡 Modo local</p>', unsafe_allow_html=True)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_dir = os.path.join(base_dir, "Eventos")
        if not os.path.exists(db_dir):
            db_dir = base_dir
        
        db_files = [f for f in os.listdir(db_dir) if f.endswith('.db') and f not in ('auth.db', 'atletismo_empty.db')]
        if db_files:
            import database
            curr = database.get_db_name()
            idx = db_files.index(curr) if curr in db_files else 0
            st.markdown('<p style="font-size:0.8rem;color:#0f172a;font-weight:700;margin-top:1rem;text-align:center;">Evento / Competencia</p>', unsafe_allow_html=True)
            selected_db = st.selectbox("Evento", db_files, index=idx, label_visibility="collapsed")
            if db_dir != base_dir:
                selected_db = os.path.join("Eventos", selected_db)
        else:
            selected_db = None

    st.markdown(f'<p style="font-size:0.65rem;color:#94a3b8;text-align:center;">Actualizado cada 30s</p>', unsafe_allow_html=True)
    if st.button("🔄 Recargar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown('<hr style="border:none;border-top:1px solid #e2e8f0;margin:0.8rem 0;">', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.75rem;color:#0f172a;font-weight:700;text-align:center;margin-bottom:0.3rem;">☁️ Publicar en la Web</p>', unsafe_allow_html=True)
    if st.button("📤 Sincronizar a Supabase", use_container_width=True):
        with st.spinner("Subiendo datos a la nube..."):
            try:
                import cloud_sync
                if selected_db:
                    import database as _db
                    original = _db.DB_PATH
                    _db.DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), selected_db)
                ok, msg, url = cloud_sync.upload_to_supabase()
                if selected_db:
                    _db.DB_PATH = original
                if ok:
                    st.success(f"✅ {msg}")
                    if url:
                        st.markdown(f'<p style="font-size:0.7rem;word-break:break-all;color:#059669;">{url}</p>', unsafe_allow_html=True)
                else:
                    st.error(f"❌ {msg}")
            except Exception as e:
                st.error(f"Error: {e}")

# ---------------------------------------------------------------------------
# Cargar datos
# ---------------------------------------------------------------------------
data, error = load_data(selected_db if not DATA_URL else None)

# ---------------------------------------------------------------------------
# Hero banner
# ---------------------------------------------------------------------------
if error:
    st.error(error)
    st.stop()

ci        = data.get("competition_info", {})
comp_name = ci.get("competition_name") or "Competencia de Atletismo"
start_dt  = fmt_date(ci.get("start_date",""))
end_dt    = fmt_date(ci.get("end_date",""))
dates_str = f"📅 {start_dt}" + (f" — {end_dt}" if end_dt and end_dt!=start_dt else "") if start_dt else ""

all_events  = data.get("events", [])
jornadas    = data.get("schedule", [])
medal_table = data.get("medal_table", [])
clubs_data  = data.get("clubs", [])
meta        = data.get("meta", {})

st.markdown(f"""
<div class="hero-banner">
    <p class="hero-title">🏃 {comp_name}</p>
    <p class="hero-subtitle">Resultados oficiales · Siembras · Programacion</p>
    {"<p class='hero-dates'>" + dates_str + "</p>" if dates_str else ""}
</div>
""", unsafe_allow_html=True)

# ===========================================================================
# INICIO
# ===========================================================================
if nav == "🏟️ Inicio":
    total_athletes = sum(c["total"] for c in clubs_data)
    results_count  = sum(1 for e in all_events if e.get("has_results"))
    col1,col2,col3,col4 = st.columns(4)
    with col1: st.markdown(f'<div class="stat-card"><div class="stat-number">{len(all_events)}</div><div class="stat-label">Pruebas</div></div>', unsafe_allow_html=True)
    with col2: st.markdown(f'<div class="stat-card"><div class="stat-number">{total_athletes}</div><div class="stat-label">Atletas</div></div>', unsafe_allow_html=True)
    with col3: st.markdown(f'<div class="stat-card"><div class="stat-number">{len(clubs_data)}</div><div class="stat-label">Clubes</div></div>', unsafe_allow_html=True)
    with col4: st.markdown(f'<div class="stat-card"><div class="stat-number">{results_count}</div><div class="stat-label">Con Resultados</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">🏅 Últimas pruebas con resultados</p>', unsafe_allow_html=True)
    evs_with_res = [e for e in all_events if e.get("has_results")]
    if not evs_with_res:
        st.info("Aun no hay resultados. Vuelve pronto.")
    else:
        for ev in evs_with_res[-8:][::-1]:
            top3 = ev.get("podium",[])[:3]
            with st.expander(f"**{ev['name']}** — {ev['category']} · {ev['gender']}", expanded=False):
                st.markdown(f'<div style="margin-bottom:0.6rem;">{gc(ev["gender"])} <span class="chip">{ev["type"]}</span> <span class="chip">{ev["round"]}</span></div>', unsafe_allow_html=True)
                medals = ["🥇","🥈","🥉"]
                for i,r in enumerate(top3):
                    st.markdown(f'<div class="sched-row"><span style="font-size:1.3rem;">{medals[i]}</span><span style="flex:1;color:#0f172a;font-weight:700;">{r.get("athlete_name","")}</span><span style="color:#64748b;font-size:0.85rem;">{r.get("athlete_club","")}</span><span style="color:#2563eb;font-weight:800;background:#eff6ff;padding:3px 10px;border-radius:8px;">{r.get("result","")}</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<p class="section-title">🏆 Top 5 Medalleria</p>', unsafe_allow_html=True)
    if medal_table:
        for row in medal_table[:5]:
            st.markdown(f'<div class="medal-row"><span class="medal-pos">{row["position"]}</span><span class="medal-club">{row["club"]}</span><span style="min-width:3rem;text-align:center;color:#f5c842;font-weight:700;">🥇 {row["oro"]}</span><span style="min-width:3rem;text-align:center;color:#c0c8d8;font-weight:700;">🥈 {row["plata"]}</span><span style="min-width:3rem;text-align:center;color:#cd7f32;font-weight:700;">🥉 {row["bronce"]}</span></div>', unsafe_allow_html=True)
    else:
        st.info("La medalleria aparecera cuando haya resultados.")
    if meta.get("generated_at"):
        try:
            t = datetime.fromisoformat(meta["generated_at"]).strftime("%d/%m/%Y %H:%M:%S")
            st.markdown(f'<p style="text-align:right;color:#3a5070;font-size:0.7rem;margin-top:2rem;">Ultima actualizacion: {t}</p>', unsafe_allow_html=True)
        except: pass

# ===========================================================================
# PROGRAMA
# ===========================================================================
elif nav == "📅 Programa":
    st.markdown('<p class="section-title">📅 Programa de Competencias</p>', unsafe_allow_html=True)
    if not jornadas:
        st.info("No hay jornadas programadas aun.")
    else:
        for j in jornadas:
            st.markdown(f'<p style="font-family:Outfit,sans-serif;font-size:1.1rem;font-weight:700;color:#c8deff;margin:1.2rem 0 0.5rem 0;">📆 {j["name"]}</p>', unsafe_allow_html=True)
            if not j.get("events"):
                st.caption("Sin pruebas asignadas.")
                continue
            for s in j["events"]:
                g_chip = gc(s.get("gender","")) if s.get("gender") else ""
                st.markdown(f'<div class="sched-row"><span class="sched-time">{s.get("time","")}</span><span style="flex:1;"><span style="font-weight:700;color:#d0e4ff;">{s.get("name","")}</span><br><span style="font-size:0.78rem;color:#5a7aaa;">{s.get("category","")} {g_chip} <span class="chip">{s.get("round","Final")}</span></span></span></div>', unsafe_allow_html=True)
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ===========================================================================
# SIEMBRAS
# ===========================================================================
elif nav == "🌱 Siembras":
    st.markdown('<p class="section-title">🌱 Listados de Salida (Siembras)</p>', unsafe_allow_html=True)
    st.markdown('<p style="color:#64748b;font-size:0.88rem;margin-bottom:1rem;">Consulta en qué heat y carril participa tu familiar. Las siembras son permanentes aunque ya haya resultados.</p>', unsafe_allow_html=True)

    # Filtro de búsqueda
    search_q = st.text_input("🔍 Buscar atleta o prueba...", placeholder="Nombre, prueba, categoría...", label_visibility="collapsed")

    events_with_seed = [e for e in all_events if e.get("seedings") and any(
        s.get("heat_number") or s.get("lane_number") or s.get("order_number") for s in e["seedings"]
    )]

    if search_q:
        q = search_q.lower()
        events_with_seed = [
            e for e in events_with_seed
            if q in e["name"].lower() or q in e.get("category","").lower()
            or any(q in s.get("athlete_name","").lower() or q in s.get("athlete_club","").lower() for s in e["seedings"])
        ]

    if not events_with_seed:
        st.info("No hay siembras asignadas en este evento aún.")
    else:
        for ev in events_with_seed:
            has_res = ev.get("has_results", False)
            status_icon = "✅" if has_res else "⏳"
            with st.expander(f"{status_icon} **{ev['name']}** — {ev['category']} · {ev['gender']}", expanded=False):
                st.markdown(f'<div style="margin-bottom:0.6rem;">{gc(ev["gender"])} <span class="chip">{ev["type"]}</span> <span class="chip">{ev["round"]}</span></div>', unsafe_allow_html=True)
                seedings = ev.get("seedings", [])

                def _seed_sort_s(r):
                    if ev["type"] == "Pista":
                        h = r.get("heat_number")
                        l = r.get("lane_number")
                        return (int(h) if h and str(h).isdigit() else 999, int(l) if l and str(l).isdigit() else 999)
                    else:
                        o = r.get("order_number")
                        return (int(o) if o and str(o).isdigit() else 999,)

                sorted_seedings = sorted(seedings, key=_seed_sort_s)
                rows = []
                for r in sorted_seedings:
                    if ev["type"] == "Pista":
                        rows.append({"Serie": r.get("heat_number") or "—", "Carril": r.get("lane_number") or "—", "Atleta": r.get("athlete_name", ""), "Club": r.get("athlete_club", ""), "N°": r.get("bib", "") or "—", "Marca P.": r.get("personal_best") or "—"})
                    else:
                        rows.append({"Orden": r.get("order_number") or "—", "Atleta": r.get("athlete_name", ""), "Club": r.get("athlete_club", ""), "N°": r.get("bib", "") or "—", "Marca P.": r.get("personal_best") or "—"})
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ===========================================================================
# RESULTADOS
# ===========================================================================
elif nav == "🏅 Resultados":
    st.markdown('<p class="section-title">🏅 Resultados por Prueba</p>', unsafe_allow_html=True)
    if not all_events:
        st.info("No hay pruebas registradas.")
    else:
        col_f1,col_f2,col_f3 = st.columns(3)
        with col_f1:
            cats = sorted({e["category"] for e in all_events})
            cat_f = st.selectbox("Categoria",["Todas"]+cats)
        with col_f2:
            gen_f = st.selectbox("Genero",["Todos","Masculino","Femenino","Mixto"])
        with col_f3:
            typ_f = st.selectbox("Tipo",["Todos","Pista","Campo"])
        filt = all_events
        if cat_f!="Todas": filt=[e for e in filt if e["category"]==cat_f]
        if gen_f!="Todos": filt=[e for e in filt if e["gender"]==gen_f]
        if typ_f!="Todos": filt=[e for e in filt if e["type"]==typ_f]
        if not filt:
            st.warning("No hay pruebas con ese filtro.")
        else:
            for ev in filt:
                has_res = ev.get("has_results",False)
                with st.expander(f"{'✅' if has_res else '⏳'} **{ev['name']}** — {ev['category']} · {ev['gender']}", expanded=False):
                    st.markdown(f'<div style="margin-bottom:0.6rem;">{gc(ev["gender"])} <span class="chip">{ev["type"]}</span> <span class="chip">{ev["round"]}</span></div>', unsafe_allow_html=True)
                    if has_res:
                        results = ev.get("results",[])
                        if not results:
                            st.caption("Sin resultados.")
                        else:
                            rows=[]
                            rank=1
                            for r in results:
                                dq=r.get("is_disqualified",False)
                                sta=r.get("status","Normal")
                                w=r.get("wind_speed")
                                ws=f"({'+' if w and w>0 else ''}{w}m/s)" if w else ""
                                pos="DQ" if dq else (sta if sta!="Normal" else str(rank))
                                rows.append({"Pos":pos,"Atleta":r.get("athlete_name",""),"Club":r.get("athlete_club",""),"Cat":r.get("athlete_category",""),"N°":r.get("bib","") or "—","Resultado":f'{r.get("result","") or sta} {ws}'.strip()})
                                if not dq and sta=="Normal": rank+=1
                            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
                    else:
                        st.caption("Resultados pendientes. Ve a la sección 'Siembras' para ver el listado de salida.")

# ===========================================================================
# MEDALLERIA
# ===========================================================================
elif nav == "🏆 Medalleria":
    st.markdown('<p class="section-title">🏆 Tabla de Medalleria Oficial</p>', unsafe_allow_html=True)
    if not medal_table:
        st.info("La medalleria aparecera cuando haya resultados.")
    else:
        st.markdown('<div style="display:flex;gap:1rem;padding:0.5rem 1rem;color:#5a7aaa;font-size:0.75rem;font-weight:600;text-transform:uppercase;"><span style="min-width:2rem">Pos</span><span style="flex:1">Club</span><span style="min-width:4rem;text-align:center">🥇</span><span style="min-width:4rem;text-align:center">🥈</span><span style="min-width:4rem;text-align:center">🥉</span><span style="min-width:4rem;text-align:center">Total</span></div>', unsafe_allow_html=True)
        for row in medal_table:
            p=row["position"]
            ps="color:#f5c842;" if p==1 else ("color:#c0c8d8;" if p==2 else ("color:#cd7f32;" if p==3 else "color:#8aabdf;"))
            st.markdown(f'<div class="medal-row"><span class="medal-pos" style="{ps}">{p}</span><span class="medal-club">{row["club"]}</span><span style="min-width:4rem;text-align:center;font-weight:700;color:#f5c842;">{row["oro"]}</span><span style="min-width:4rem;text-align:center;font-weight:700;color:#c0c8d8;">{row["plata"]}</span><span style="min-width:4rem;text-align:center;font-weight:700;color:#cd7f32;">{row["bronce"]}</span><span style="min-width:4rem;text-align:center;color:#8aabdf;font-weight:600;">{row["total"]}</span></div>', unsafe_allow_html=True)

# ===========================================================================
# CLUBES
# ===========================================================================
elif nav == "👥 Clubes":
    st.markdown('<p class="section-title">👥 Participacion por Club</p>', unsafe_allow_html=True)
    if not clubs_data:
        st.info("Sin datos de clubes.")
    else:
        total = sum(c["total"] for c in clubs_data)
        for c in clubs_data:
            pct=(c["total"]/total*100) if total else 0
            st.markdown(f'<div class="medal-row"><span class="medal-club">{c["club"]}</span><span style="color:#64a0ff;font-weight:700;min-width:3rem;text-align:right;">{c["total"]}</span><span style="color:#3a5070;font-size:0.8rem;min-width:4rem;text-align:right;">{pct:.1f}%</span></div>', unsafe_allow_html=True)
            st.progress(pct/100)
        st.markdown(f'<p style="text-align:right;color:#5a7aaa;font-size:0.85rem;">Total atletas: <strong style="color:#c0d4f0;">{total}</strong></p>', unsafe_allow_html=True)

st.markdown(f'<div class="divider"></div><p style="text-align:center;color:#94a3b8;font-size:0.75rem;">AtletismoPro 2025-2026 · Douglas José López López</p>', unsafe_allow_html=True)
