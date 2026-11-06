# =============================================================================
# AtletismoPro — Cliente REST para Supabase Postgres (Fase B1)
# Implementa la misma API pública que database.py pero hablando contra
# el endpoint REST (PostgREST) de Supabase, sin dependencias nuevas:
# solo usa `requests` (ya en requirements.txt).
#
# Uso:
#   cfg = {"supabase_url": "...", "supabase_key": "...", "active_competition_id": "..."}
#   db = SupabaseDB(cfg)
#   db.get_events() -> lista de dicts (mismo formato que database.get_events)
# =============================================================================

import os
import json
import time
import requests
from urllib3.exceptions import ProtocolError
from datetime import datetime
import database


class SupabaseDB:
    """Wrapper REST sobre Supabase PostgREST con la misma firma que database.py."""

    def __init__(self, config=None):
        cfg = config or database.load_config()
        self.url = (cfg.get("supabase_url", "") or "").rstrip("/")
        self.key = cfg.get("supabase_key", "")
        self.competition_id = cfg.get("active_competition_id")
        self._base_headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    def _headers(self, prefer=None):
        h = dict(self._base_headers)
        if prefer:
            h["Prefer"] = prefer
        return h

    def _retry_request(self, method, url, headers, **kwargs):
        """Ejecuta una petición HTTP con reintentos ante fallos de red remota."""
        last_exc = None
        for intento in range(4):
            try:
                resp = method(url, headers=headers, timeout=20, **kwargs)
                resp.raise_for_status()
                return resp
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    ProtocolError) as exc:
                last_exc = exc
                if intento < 3:
                    espera = 2 ** (intento + 1)  # 2s, 4s, 8s
                    time.sleep(espera)
        raise last_exc

    def _get(self, table, params=None):
        url = f"{self.url}/rest/v1/{table}"
        resp = self._retry_request(
            requests.get, url, self._headers(), params=params,
        )
        return resp.json()

    def _post(self, table, data, prefer="representation"):
        url = f"{self.url}/rest/v1/{table}"
        headers = self._headers(prefer=f"return={prefer}")
        resp = self._retry_request(
            requests.post, url, headers, json=data,
        )
        if prefer == "representation":
            return resp.json()
        return None

    def _patch(self, table, filters, data, prefer="representation"):
        url = f"{self.url}/rest/v1/{table}"
        headers = self._headers(prefer=f"return={prefer}")
        resp = self._retry_request(
            requests.patch, url, headers, params=filters, json=data,
        )
        if prefer == "representation":
            return resp.json()
        return None

    def _delete(self, table, filters):
        url = f"{self.url}/rest/v1/{table}"
        resp = requests.delete(url, headers=self._headers(), params=filters, timeout=20)
        resp.raise_for_status()
        return resp.status_code in (200, 204)

    def _comp_filter(self):
        """Filtro por competencia activa si está configurada."""
        if self.competition_id:
            return {"competition_id": f"eq.{self.competition_id}"}
        return {}

    def _merge_params(self, base, extra):
        p = dict(base)
        if extra:
            p.update(extra)
        return p

    def set_competition(self, competition_id):
        """Establece la competencia activa y la guarda en config.json."""
        self.competition_id = competition_id
        cfg = database.load_config()
        cfg["active_competition_id"] = competition_id
        database.save_config(cfg)

    # ------------------------------------------------------------------
    # Competitions
    # ------------------------------------------------------------------
    def init_db(self):
        """En Supabase las tablas se crean con schema.sql. Aquí solo
        verificamos conectividad y devolvemos True si responde el endpoint."""
        try:
            self._get("competitions", params={"select": "id", "limit": "1"})
            return True
        except Exception:
            return False

    def get_competition_dates(self):
        """Devuelve la competencia activa o la primera disponible."""
        params = {"limit": "1"}
        if self.competition_id:
            # competitions usa 'id' como PK, no 'competition_id'
            params["id"] = f"eq.{self.competition_id}"
        comps = self._get("competitions", params=params)
        if comps:
            c = comps[0]
            return {
                "competition_name": c.get("name", ""),
                "start_date": c.get("start_date", "") or "",
                "end_date": c.get("end_date", "") or "",
            }
        return {"competition_name": "", "start_date": "", "end_date": ""}

    def get_competitions(self):
        """Devuelve todas las competencias para el selector de competencia activa."""
        comps = self._get("competitions", params={"select": "id,name,start_date,end_date", "order": "name.asc"})
        return comps or []

    def delete_competition(self, competition_id):
        """Elimina una competencia y todos sus datos relacionados (cascada via FK)."""
        return self._delete("competitions", {"id": f"eq.{competition_id}"})

    def save_competition_dates(self, start_date, end_date, competition_name=""):
        """Crea o actualiza la competencia activa."""
        if self.competition_id:
            self._patch(
                "competitions",
                {"id": f"eq.{self.competition_id}"},
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "name": competition_name,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
        else:
            created = self._post(
                "competitions",
                {
                    "name": competition_name,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )
            if created:
                self.set_competition(created[0]["id"])

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def get_events(self):
        params = self._merge_params(
            self._comp_filter(),
            {"order": "name.asc"},
        )
        return self._get("events", params=params) or []

    def add_event(self, name, event_type, category, gender, lanes=8, round_type='Final', sport=None):
        if sport is None:
            sport = 'Natación' if event_type == 'Piscina' else 'Atletismo'
        data = {
            "name": name,
            "type": event_type,
            "category": category,
            "gender": gender,
            "lanes": lanes,
            "round": round_type,
            "sport": sport,
        }
        if self.competition_id:
            data["competition_id"] = self.competition_id
        created = self._post("events", data)
        return created[0]["id"] if created else None

    def delete_event(self, event_id):
        return self._delete("events", {"id": f"eq.{event_id}"})

    def update_event(self, event_id, name, event_type, category, gender, lanes, round_type, sport=None):
        if sport is None:
            sport = 'Natación' if event_type == 'Piscina' else 'Atletismo'
        return self._patch(
            "events",
            {"id": f"eq.{event_id}"},
            {
                "name": name,
                "type": event_type,
                "category": category,
                "gender": gender,
                "lanes": lanes,
                "round": round_type,
                "sport": sport,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

    # ------------------------------------------------------------------
    # Athletes
    # ------------------------------------------------------------------
    def get_athletes(self):
        params = self._merge_params(
            self._comp_filter(),
            {"order": "name.asc"},
        )
        return self._get("athletes", params=params) or []

    def add_athlete(self, name, club, category, gender, birth_date=None, bib_number=None):
        data = {
            "name": name,
            "club": club,
            "category": category,
            "gender": gender,
            "birth_date": birth_date,
            "bib_number": bib_number,
        }
        if self.competition_id:
            data["competition_id"] = self.competition_id
        created = self._post("athletes", data)
        return created[0]["id"] if created else None

    def delete_athlete(self, athlete_id):
        return self._delete("athletes", {"id": f"eq.{athlete_id}"})

    def update_athlete_bib(self, athlete_id, bib_number):
        return self._patch(
            "athletes",
            {"id": f"eq.{athlete_id}"},
            {"bib_number": bib_number, "updated_at": datetime.utcnow().isoformat()},
        )

    def update_athlete_category(self, athlete_id, category):
        return self._patch(
            "athletes",
            {"id": f"eq.{athlete_id}"},
            {"category": category, "updated_at": datetime.utcnow().isoformat()},
        )

    def update_athlete_full(self, athlete_id, name, club, category, gender, birth_date):
        return self._patch(
            "athletes",
            {"id": f"eq.{athlete_id}"},
            {
                "name": name,
                "club": club,
                "category": category,
                "gender": gender,
                "birth_date": birth_date,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

    # ------------------------------------------------------------------
    # Registrations / results / seeding
    # ------------------------------------------------------------------
    def get_registrations_for_event(self, event_id):
        params = self._merge_params(
            self._comp_filter(),
            {
                "event_id": f"eq.{event_id}",
                "order": "heat_number.asc.nullsfirst,lane_number.asc.nullsfirst,order_number.asc.nullsfirst",
            },
        )
        return self._get("registrations", params=params) or []

    def register_athlete_to_event(self, athlete_id, event_id):
        try:
            self._post(
                "registrations",
                {
                    "athlete_id": athlete_id,
                    "event_id": event_id,
                },
            )
            return True
        except requests.HTTPError:
            return False  # ya inscrito (unique constraint)

    def unregister_athlete_from_event(self, athlete_id, event_id):
        return self._delete(
            "registrations",
            {
                "competition_id": f"eq.{self.competition_id}" if self.competition_id else "is.not.null",
                "athlete_id": f"eq.{athlete_id}",
                "event_id": f"eq.{event_id}",
            },
        )

    def update_registration_seeding(self, reg_id, heat_number, lane_number, order_number):
        return self._patch(
            "registrations",
            {"id": f"eq.{reg_id}"},
            {
                "heat_number": heat_number,
                "lane_number": lane_number,
                "order_number": order_number,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

    def reset_event_seeding(self, event_id):
        return self._patch(
            "registrations",
            {
                "competition_id": f"eq.{self.competition_id}" if self.competition_id else "is.not.null",
                "event_id": f"eq.{event_id}",
            },
            {
                "heat_number": None,
                "lane_number": None,
                "order_number": None,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

    def update_result(
        self,
        reg_id,
        result_str,
        result_value,
        is_disqualified=0,
        status='Normal',
        attempts=None,
        wind_speed=None,
    ):
        if status != 'Normal':
            result_value = None
            result_str = status
            is_disqualified = 1 if status == 'DQ' else 0

        attempts_json = None
        if attempts:
            attempts_json = json.dumps(attempts)

        data = {
            "result": result_str,
            "result_value": result_value,
            "is_disqualified": is_disqualified,
            "status": status,
            "wind_speed": wind_speed,
            "attempts": attempts_json,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if attempts and len(attempts) >= 6:
            for i in range(1, 7):
                data[f"attempt{i}"] = attempts[i - 1] if i - 1 < len(attempts) else None

        return self._patch(
            "registrations",
            {"id": f"eq.{reg_id}"},
            data,
        )

    def has_results(self, event_id):
        rows = self._get(
            "registrations",
            params=self._merge_params(
                self._comp_filter(),
                {
                    "event_id": f"eq.{event_id}",
                    "result_value": "is.not.null",
                    "select": "id",
                },
            ),
        )
        return bool(rows)

    def get_registrations_with_pb(self, event_id):
        params = self._merge_params(
            self._comp_filter(),
            {
                "event_id": f"eq.{event_id}",
                "personal_best": "is.not.null",
                "order": "personal_best.asc.nullslast",
            },
        )
        return self._get("registrations", params=params) or []

    def update_personal_best(self, reg_id, personal_best):
        return self._patch(
            "registrations",
            {"id": f"eq.{reg_id}"},
            {"personal_best": personal_best, "updated_at": datetime.utcnow().isoformat()},
        )

    def get_athlete_history(self, athlete_id):
        params = self._merge_params(
            self._comp_filter(),
            {
                "athlete_id": f"eq.{athlete_id}",
                "order": "events.name.asc",
            },
        )
        return self._get("registrations", params=params) or []

    # ------------------------------------------------------------------
    # Medals / podium
    # ------------------------------------------------------------------
    def get_podium_for_event(self, event_id):
        # Lógica de negocio (desempates de Campo, relevos) idéntica a SQLite;
        # solo cambia el origen de los rows. Se reusa sort_field_results.
        import database
        rows = self.get_registrations_for_event(event_id)
        # Filtrar solo con resultado válido y no descalificado para el podio base
        valid = [
            r for r in rows
            if r.get("result_value") is not None
            and (r.get("status") in ('Normal', None) or r.get("status") == '')
            and r.get("is_disqualified") in (0, None, False)
        ]
        # Obtener nombre del evento para tipo
        events = self.get_events()
        ev = next((e for e in events if e["id"] == event_id), None)
        if not ev:
            return []
        event_type = ev.get("type", "")
        event_name = ev.get("name", "")

        order_by = "ASC" if event_type in ("Pista", "Piscina") else "DESC"

        def sort_key(r):
            val = r.get("result_value")
            if val is None:
                return (0,)
            return (val,)

        valid.sort(key=sort_key, reverse=(order_by == "DESC"))

        if event_type == "Campo":
            valid = database.sort_field_results(valid, event_name)

        if database.is_relay_event(event_name):
            relay_members = self.get_relay_members(event_id)
            clubs_seen = set()
            podium = []
            for r in valid:
                club = r.get("athlete_club", "")
                if club in clubs_seen:
                    continue
                clubs_seen.add(club)
                members = relay_members.get(club, "")
                r["athlete_name"] = members if members else f"{club}"
                r["relay_members_display"] = members or "Sin nombres registrados"
                podium.append(r)
                if len(podium) >= 3:
                    break
            return podium[:3]

        return valid[:3]

    def get_medal_table(self, gender_filter=None):
        # Implementación simplificada: leer todos los eventos y calcular
        # medallas en Python (misma lógica que database.get_medal_table).
        import database
        events = self.get_events()
        if gender_filter:
            events = [e for e in events if e.get("gender") == gender_filter]

        club_medals = {}

        for event in events:
            event_id = event["id"]
            event_type = event.get("type", "")
            event_name = event.get("name", "").lower()
            is_relay = "relevo" in event_name or "4x" in event_name

            order_by = "ASC" if event_type in ("Pista", "Piscina") else "DESC"

            results = self._get(
                "registrations",
                params=self._merge_params(
                    self._comp_filter(),
                    {
                        "event_id": f"eq.{event_id}",
                        "result_value": "is.not.null",
                        "status": f"in.('Normal',)",
                        "is_disqualified": "eq.0",
                        "order": f"result_value.{order_by}",
                    },
                ),
            ) or []

            if not results:
                continue

            if event_type == "Campo":
                results = database.sort_field_results(results, event["name"])
            else:
                for r in results:
                    r["_sort_key"] = r.get("result_value")

            medals_awarded = set()
            current_val = results[0].get("_sort_key")
            current_rank = 1
            athletes_at_rank = 0

            for row in results:
                club = row.get("club", "")
                val = row.get("_sort_key")

                if val != current_val:
                    current_rank += athletes_at_rank
                    current_val = val
                    athletes_at_rank = 1
                else:
                    athletes_at_rank += 1

                if current_rank > 3:
                    break

                if is_relay and club in medals_awarded:
                    continue

                if club not in club_medals:
                    club_medals[club] = {"oro": 0, "plata": 0, "bronce": 0}

                if current_rank == 1:
                    club_medals[club]["oro"] += 1
                elif current_rank == 2:
                    club_medals[club]["plata"] += 1
                elif current_rank == 3:
                    club_medals[club]["bronce"] += 1

                if is_relay:
                    medals_awarded.add(club)

        medal_table = []
        for club, medals in club_medals.items():
            total = medals["oro"] + medals["plata"] + medals["bronce"]
            if total > 0:
                medal_table.append({
                    "club": club,
                    "oro": medals["oro"],
                    "plata": medals["plata"],
                    "bronce": medals["bronce"],
                    "total": total,
                })

        medal_table.sort(key=lambda x: (x["oro"], x["plata"], x["bronce"]), reverse=True)
        for i, row in enumerate(medal_table):
            row["position"] = i + 1
        return medal_table

    # ------------------------------------------------------------------
    # Jornadas / schedule
    # ------------------------------------------------------------------
    def get_jornadas(self):
        params = self._merge_params(
            self._comp_filter(),
            {"order": "display_order.asc,id.asc"},
        )
        return self._get("jornadas", params=params) or []

    def add_jornada(self, name, display_order=0):
        data = {"name": name, "display_order": display_order}
        if self.competition_id:
            data["competition_id"] = self.competition_id
        created = self._post("jornadas", data)
        return created[0]["id"] if created else None

    def delete_jornada(self, jornada_id):
        return self._delete("jornadas", {"id": f"eq.{jornada_id}"})

    def update_jornada(self, jornada_id, name, display_order):
        return self._patch(
            "jornadas",
            {"id": f"eq.{jornada_id}"},
            {
                "name": name,
                "display_order": display_order,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

    def get_schedules_for_jornada(self, jornada_id):
        params = self._merge_params(
            self._comp_filter(),
            {
                "jornada_id": f"eq.{jornada_id}",
                "order": "event_time.asc,display_order.asc",
            },
        )
        return self._get("event_schedule", params=params) or []

    def add_schedule_entry(
        self,
        jornada_id,
        event_id=None,
        combined_event_id=None,
        sub_event_index=None,
        sub_event_label=None,
        start_accred='',
        end_accred='',
        entry_time='',
        event_time='',
        display_order=0,
    ):
        data = {
            "jornada_id": jornada_id,
            "event_id": event_id,
            "combined_event_id": combined_event_id,
            "sub_event_index": sub_event_index,
            "sub_event_label": sub_event_label,
            "start_accred": start_accred,
            "end_accred": end_accred,
            "entry_time": entry_time,
            "event_time": event_time,
            "display_order": display_order,
        }
        if self.competition_id:
            data["competition_id"] = self.competition_id
        created = self._post("event_schedule", data)
        return created[0]["id"] if created else None

    def delete_schedule_entry(self, entry_id):
        return self._delete("event_schedule", {"id": f"eq.{entry_id}"})

    def update_schedule_entry(self, entry_id, start_accred, end_accred, entry_time, event_time, display_order=0):
        return self._patch(
            "event_schedule",
            {"id": f"eq.{entry_id}"},
            {
                "start_accred": start_accred,
                "end_accred": end_accred,
                "entry_time": entry_time,
                "event_time": event_time,
                "display_order": display_order,
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

    def get_schedule_for_event(self, event_id):
        params = self._merge_params(
            self._comp_filter(),
            {"event_id": f"eq.{event_id}", "order": "event_time.asc"},
        )
        return self._get("event_schedule", params=params) or []

    def get_assigned_event_ids(self):
        rows = self._get(
            "event_schedule",
            params=self._merge_params(
                self._comp_filter(),
                {"event_id": "is.not.null", "select": "event_id"},
            ),
        )
        ids = set()
        for r in rows or []:
            if r.get("event_id"):
                ids.add(r["event_id"])
        rows2 = self._get(
            "event_schedule",
            params=self._merge_params(
                self._comp_filter(),
                {"combined_event_id": "is.not.null", "select": "combined_event_id"},
            ),
        )
        for r in rows2 or []:
            if r.get("combined_event_id"):
                ids.add(r["combined_event_id"])
        return ids

    def get_assigned_combined_sub_indices(self, combined_event_id):
        rows = self._get(
            "event_schedule",
            params=self._merge_params(
                self._comp_filter(),
                {
                    "combined_event_id": f"eq.{combined_event_id}",
                    "sub_event_index": "is.not.null",
                    "select": "sub_event_index",
                },
            ),
        )
        return {r["sub_event_index"] for r in (rows or []) if r.get("sub_event_index") is not None}

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------
    def add_category(self, name, min_age, max_age):
        data = {"name": name, "min_age": min_age, "max_age": max_age}
        if self.competition_id:
            data["competition_id"] = self.competition_id
        try:
            self._post("categories", data)
            return True, "Categoría agregada."
        except requests.HTTPError as e:
            return False, "Ya existe una categoría con ese nombre."

    def get_categories(self):
        params = self._merge_params(
            self._comp_filter(),
            {"order": "min_age.asc"},
        )
        return self._get("categories", params=params) or []

    def delete_category(self, cat_id):
        return self._delete("categories", {"id": f"eq.{cat_id}"})

    def calculate_category_from_birthdate(self, birth_date_str):
        # Lógica idéntica a database.py, usa get_categories() de Supabase
        try:
            from datetime import date
            birth = date.fromisoformat(birth_date_str)
            today = date.today()
            cfg = database.load_config()
            mode = cfg.get("age_mode", "calendario")
            if mode == "cumplida":
                ref_date = date(today.year - 1, 12, 31)
                age = ref_date.year - birth.year - ((ref_date.month, ref_date.day) < (birth.month, birth.day))
            else:
                age = today.year - birth.year

            categories = self.get_categories()
            individual_cats = [c for c in categories if "relevo" not in c["name"].lower() and "relay" not in c["name"].lower()]
            for cat in individual_cats:
                if cat["min_age"] <= age <= cat["max_age"]:
                    return cat["name"], age
            for cat in categories:
                if cat["min_age"] <= age <= cat["max_age"]:
                    return cat["name"], age
            return "Libre", age
        except (ValueError, TypeError):
            return None, None

    # ------------------------------------------------------------------
    # Relay members
    # ------------------------------------------------------------------
    def save_relay_members(self, event_id, club, members_text):
        existing = self._get(
            "relay_members",
            params=self._merge_params(
                self._comp_filter(),
                {"event_id": f"eq.{event_id}", "club": f"eq.{club}", "select": "id"},
            ),
        ) or []
        if existing:
            return self._patch(
                "relay_members",
                {"id": f"eq.{existing[0]['id']}"},
                {"members_text": members_text},
            )
        data = {"event_id": event_id, "club": club, "members_text": members_text}
        if self.competition_id:
            data["competition_id"] = self.competition_id
        self._post("relay_members", data)
        return True

    def get_relay_members(self, event_id):
        rows = self._get(
            "relay_members",
            params=self._merge_params(
                self._comp_filter(),
                {"event_id": f"eq.{event_id}"},
            ),
        ) or []
        return {r["club"]: r["members_text"] for r in rows}

    # ------------------------------------------------------------------
    # Vertical heights
    # ------------------------------------------------------------------
    def save_vertical_heights(self, event_id, heights_list):
        import json
        return self._patch(
            "events",
            {"id": f"eq.{event_id}"},
            {"vertical_heights": json.dumps(heights_list), "updated_at": datetime.utcnow().isoformat()},
        )

    def get_vertical_heights(self, event_id):
        import json
        rows = self._get(
            "events",
            params=self._merge_params(
                self._comp_filter(),
                {"id": f"eq.{event_id}", "select": "vertical_heights"},
            ),
        ) or []
        if rows and rows[0].get("vertical_heights"):
            try:
                return json.loads(rows[0]["vertical_heights"])
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    # ------------------------------------------------------------------
    # Clubs count
    # ------------------------------------------------------------------
    def get_athletes_count_per_club(self):
        # PostgREST no hace GROUP BY nativo; lo hacemos en Python.
        athletes = self.get_athletes()
        counts = {}
        for a in athletes:
            club = a.get("club", "")
            counts[club] = counts.get(club, 0) + 1
        result = [{"club": c, "total": t} for c, t in counts.items()]
        result.sort(key=lambda x: (-x["total"], x["club"]))
        return result

    # ------------------------------------------------------------------
    # Combined marks
    # ------------------------------------------------------------------
    def init_combined_marks_table(self):
        """No-op en Supabase: la tabla se crea con schema.sql."""
        return True

    def save_combined_mark(self, event_id, athlete_id, event_index, mark_value):
        existing = self._get(
            "combined_marks",
            params=self._merge_params(
                self._comp_filter(),
                {
                    "event_id": f"eq.{event_id}",
                    "athlete_id": f"eq.{athlete_id}",
                    "event_index": f"eq.{event_index}",
                    "select": "id",
                },
            ),
        ) or []
        data = {"mark_value": mark_value, "updated_at": datetime.utcnow().isoformat()}
        if existing:
            return self._patch(
                "combined_marks",
                {"id": f"eq.{existing[0]['id']}"},
                data,
            )
        data["event_id"] = event_id
        data["athlete_id"] = athlete_id
        data["event_index"] = event_index
        if self.competition_id:
            data["competition_id"] = self.competition_id
        self._post("combined_marks", data)
        return True

    def get_combined_marks(self, event_id, athlete_id):
        rows = self._get(
            "combined_marks",
            params=self._merge_params(
                self._comp_filter(),
                {
                    "event_id": f"eq.{event_id}",
                    "athlete_id": f"eq.{athlete_id}",
                    "order": "event_index.asc",
                },
            ),
        ) or []
        return {r["event_index"]: r["mark_value"] for r in rows}

    def get_all_combined_marks_for_event(self, event_id):
        rows = self._get(
            "combined_marks",
            params=self._merge_params(
                self._comp_filter(),
                {"event_id": f"eq.{event_id}", "order": "athlete_id.asc,event_index.asc"},
            ),
        ) or []
        result = {}
        for r in rows:
            aid = r["athlete_id"]
            result.setdefault(aid, {})[r["event_index"]] = r["mark_value"]
        return result

    # ------------------------------------------------------------------
    # Backups (no-op en Supabase; SQLite mantiene su propia lógica)
    # ------------------------------------------------------------------
    def create_backup(self, db_path=None):
        return False, "", "Backup no disponible en modo Supabase"

    def get_last_backup_info(self):
        return None

    # ------------------------------------------------------------------
    # Alias para compatibilidad con database.py
    # ------------------------------------------------------------------
    def get_db_name(self):
        return "supabase"

    def get_age_mode(self):
        cfg = database.load_config()
        return cfg.get("age_mode", "calendario")

    def set_age_mode(self, mode):
        cfg = database.load_config()
        cfg["age_mode"] = mode
        database.save_config(cfg)


# =============================================================================
# SupabaseConnection — wrapper para database.get_connection() en modo Supabase
# main.py usa get_connection().cursor().execute()/fetchall()/commit()/close().
# Esta clase traduce esos patrones a llamadas REST contra Supabase.
# =============================================================================
class _SupabaseCursor:
    def __init__(self, db: "SupabaseDB"):
        self._db = db
        self._rows = []
        self._row_index = 0

    def execute(self, sql, params=None):
        """Traduce patrones SQL usados por main.py a llamadas REST."""
        sql_clean = " ".join(sql.split()) if sql else ""
        upper = sql_clean.upper()

        # SELECT ... FROM athletes ... ORDER BY ...
        if "FROM ATHLETES" in upper:
            athletes = self._db.get_athletes()
            if "WHERE" in upper:
                # Filtros simples: name = X, club = X, id = X
                for cond in self._split_where(sql_clean):
                    key, val = self._parse_cond(cond)
                    if key == "id":
                        athletes = [a for a in athletes if str(a.get("id")) == val]
                    elif key == "name":
                        athletes = [a for a in athletes if val.lower() in a.get("name", "").lower()]
                    elif key == "club":
                        athletes = [a for a in athletes if val.lower() in a.get("club", "").lower()]
            if "ORDER BY CLUB ASC" in upper:
                athletes.sort(key=lambda a: a.get("club", ""))
            elif "ORDER BY NAME ASC" in upper:
                athletes.sort(key=lambda a: a.get("name", ""))
            self._rows = athletes
            self._row_index = 0
            return self

        # SELECT ... FROM registrations WHERE event_id = X ...
        if "FROM REGISTRATIONS" in upper:
            event_id = None
            athlete_id = None
            if params:
                event_id = params[0] if len(params) > 0 else None
            regs = self._db.get_registrations_for_event(event_id) if event_id else []
            if "WHERE" in upper:
                for cond in self._split_where(sql_clean):
                    key, val = self._parse_cond(cond)
                    if key == "athlete_id":
                        regs = [r for r in regs if str(r.get("athlete_id")) == val]
                    elif key == "event_id":
                        regs = [r for r in regs if str(r.get("event_id")) == val]
                    elif key == "result_value":
                        regs = [r for r in regs if r.get("result_value") is not None]
            self._rows = regs
            self._row_index = 0
            return self

        # Fallback: devolver vacío
        self._rows = []
        self._row_index = 0
        return self

    def fetchall(self):
        return self._rows

    def _split_where(self, sql):
        """Extrae condiciones simples del WHERE."""
        idx = sql.upper().find(" WHERE ")
        if idx < 0:
            return []
        clause = sql[idx + 7:]
        # Quitar ORDER BY si existe
        for sep in [" ORDER BY", " LIMIT", " OFFSET"]:
            pos = clause.upper().find(sep)
            if pos >= 0:
                clause = clause[:pos]
        return [c.strip() for c in clause.split(" AND ") if c.strip()]

    def _parse_cond(self, cond):
        """'campo = 'valor'' o 'campo = valor' → (campo, valor)."""
        cond = cond.strip()
        for op in [" = ", "=", " IS NOT NULL", " IS NULL"]:
            if op in cond.upper():
                parts = cond.split(op, 1)
                key = parts[0].strip()
                val = parts[1].strip() if len(parts) > 1 else ""
                val = val.strip("'").strip('"')
                return key, val
        return cond, ""


class SupabaseConnection:
    """Objeto parecido a sqlite3.Connection para usarse con get_connection()."""

    def __init__(self, db: SupabaseDB):
        self._db = db

    def cursor(self):
        return _SupabaseCursor(self._db)

    def commit(self):
        pass

    def close(self):
        pass
