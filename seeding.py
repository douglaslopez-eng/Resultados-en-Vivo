# =============================================================================
# AtletismoPro — Módulo de Siembras
# Copyright (c) 2025-2026 Douglas José López López
# Todos los derechos reservados. All rights reserved.
#
# Este software es propiedad exclusiva de Douglas José López López.
# Queda prohibida su copia, distribución o modificación sin autorización
# expresa y por escrito del titular. Ver archivo LICENSE para más detalles.
# =============================================================================
import random
import math
from database import get_connection, get_registrations_for_event, update_registration_seeding, reset_event_seeding

def perform_seeding(event_id):
    """
    Realiza la siembra (distribución en series/heats y carriles/orden)
    para todos los atletas inscritos en una prueba específica.
    Los atletas se distribuyen aleatoriamente entre series (para justicia),
    pero dentro de cada serie los carriles se asignan SECUENCIALMENTE: 1, 2, 3...
    """
    # 1. Obtener la información de la prueba
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        return False, "La prueba no existe."

    event_type = event["type"]
    lanes_available = event["lanes"]
    conn.close()

    # 2. Obtener los atletas inscritos
    registrations = get_registrations_for_event(event_id)
    n_athletes = len(registrations)

    if n_athletes == 0:
        return False, "No hay atletas inscritos para esta prueba."

    # Limpiar datos de siembra anteriores para evitar datos obsoletos
    reset_event_seeding(event_id)

    # Mezclar atletas aleatoriamente para distribución justa entre series
    random.seed()
    shuffled_regs = list(registrations)
    random.shuffle(shuffled_regs)

    if event_type in ("Pista", "Piscina"):
        event_name = event["name"].lower()
        is_relay = "relevo" in event_name or "4x" in event_name

        if is_relay:
            teams = []
            club_athletes = {}
            for reg in shuffled_regs:
                club = reg.get("athlete_club", "")
                if club not in club_athletes:
                    club_athletes[club] = []
                club_athletes[club].append(reg)
            
            for club, athletes in club_athletes.items():
                chunk_size = 4
                for i in range(0, len(athletes), chunk_size):
                    teams.append(athletes[i:i+chunk_size])
            
            n_teams = len(teams)
            lanes = lanes_available if lanes_available and lanes_available > 0 else 8
            n_heats = math.ceil(n_teams / lanes) if n_teams > 0 else 1
            
            base_size = n_teams // n_heats if n_heats > 0 else 0
            extra_teams = n_teams % n_heats if n_heats > 0 else 0
            
            heat_sizes = []
            for i in range(n_heats):
                size = base_size + (1 if i < extra_teams else 0)
                heat_sizes.append(size)
                
            current_idx = 0
            for heat_idx, heat_size in enumerate(heat_sizes):
                heat_num = heat_idx + 1
                for lane_num in range(1, heat_size + 1):
                    team = teams[current_idx]
                    for reg in team:
                        update_registration_seeding(
                            reg_id=reg["id"],
                            heat_number=heat_num,
                            lane_number=lane_num,
                            order_number=lane_num
                        )
                    current_idx += 1
        else:
            # Determinar número de series necesarias
            lanes = lanes_available if lanes_available and lanes_available > 0 else 8
            n_heats = math.ceil(n_athletes / lanes)

            # Distribuir equitativamente: algunas series tendrán un atleta más
            base_size = n_athletes // n_heats
            extra_athletes = n_athletes % n_heats

            heat_sizes = []
            for i in range(n_heats):
                size = base_size + (1 if i < extra_athletes else 0)
                heat_sizes.append(size)

            # Asignar carriles SECUENCIALES: 1, 2, 3... dentro de cada serie
            current_idx = 0
            for heat_idx, heat_size in enumerate(heat_sizes):
                heat_num = heat_idx + 1
                for lane_num in range(1, heat_size + 1):
                    reg = shuffled_regs[current_idx]
                    update_registration_seeding(
                        reg_id=reg["id"],
                        heat_number=heat_num,
                        lane_number=lane_num,
                        order_number=lane_num
                    )
                    current_idx += 1

    elif event_type == "Campo":
        # Para pruebas de campo: orden de salida secuencial (ya están mezclados)
        for order_idx, reg in enumerate(shuffled_regs):
            update_registration_seeding(
                reg_id=reg["id"],
                heat_number=1,
                lane_number=None,
                order_number=order_idx + 1
            )

    return True, f"Siembra completada. Carriles asignados del 1 al {lanes_available} en orden secuencial."


def perform_seeding_by_marks(event_id):
    """
    Realiza la siembra por marcas personales usando el método serpentín.
    
    Lógica del Serpentín (estándar World Athletics):
    1. Los atletas se ordenan por su marca personal (personal_best en registrations)
    2. Los más lentos van a la primera serie, los más rápidos a la última
    3. Dentro de cada serie, se asignan carriles centrales a los mejores
    4. Atletas sin marca van a las primeras series
    
    Asignación de carriles (orden de prioridad para 8 carriles):
    Posición 1→Carril 4, Pos 2→C5, Pos 3→C3, Pos 4→C6, Pos 5→C2, Pos 6→C7, Pos 7→C1, Pos 8→C8
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        return False, "La prueba no existe."

    event_type = event["type"]
    lanes_available = event["lanes"]
    conn.close()

    # Obtener inscripciones con marca personal
    from database import get_registrations_with_pb
    registrations = get_registrations_with_pb(event_id)
    n_athletes = len(registrations)

    if n_athletes == 0:
        return False, "No hay atletas inscritos para esta prueba."

    # Verificar que al menos un atleta tenga marca personal
    has_any_pb = any(r.get("personal_best") is not None for r in registrations)
    if not has_any_pb:
        return False, "Ningún atleta tiene marca personal ingresada.\nIngresa al menos una marca antes de usar la siembra por marcas."

    # Limpiar datos de siembra anteriores para evitar datos obsoletos
    reset_event_seeding(event_id)

    # Separar atletas con y sin marca
    with_pb = [r for r in registrations if r.get("personal_best") is not None]
    without_pb = [r for r in registrations if r.get("personal_best") is None]

    if event_type in ("Pista", "Piscina"):
        event_name = event["name"].lower()
        is_relay = "relevo" in event_name or "4x" in event_name

        if is_relay:
            teams = []
            club_athletes = {}
            # Primero agrupar los que tienen marca
            for reg in with_pb:
                club = reg.get("athlete_club", "")
                if club not in club_athletes:
                    club_athletes[club] = []
                club_athletes[club].append(reg)
            # Agrupar los que no tienen marca
            for reg in without_pb:
                club = reg.get("athlete_club", "")
                if club not in club_athletes:
                    club_athletes[club] = []
                club_athletes[club].append(reg)
                
            for club, athletes in club_athletes.items():
                chunk_size = 4
                for i in range(0, len(athletes), chunk_size):
                    team = athletes[i:i+chunk_size]
                    # Para el equipo, la marca será la mejor marca (o None si no tienen)
                    team_pbs = [r.get("personal_best") for r in team if r.get("personal_best") is not None]
                    best_pb = min(team_pbs) if team_pbs else None
                    teams.append({"athletes": team, "pb": best_pb})
                    
            # Separar equipos con y sin marca
            teams_with_pb = [t for t in teams if t["pb"] is not None]
            teams_without_pb = [t for t in teams if t["pb"] is None]
            
            teams_with_pb.sort(key=lambda t: t["pb"])
            sorted_teams = teams_without_pb + teams_with_pb
            
            n_teams = len(sorted_teams)
            lanes = lanes_available if lanes_available and lanes_available > 0 else 8
            n_heats = math.ceil(n_teams / lanes) if n_teams > 0 else 1
            
            lane_priority = _generate_lane_priority(lanes)
            
            base_size = n_teams // n_heats if n_heats > 0 else 0
            extra = n_teams % n_heats if n_heats > 0 else 0
            heat_sizes = []
            for i in range(n_heats):
                heat_sizes.append(base_size + (1 if i < extra else 0))
                
            heats = [[] for _ in range(n_heats)]
            team_idx = 0
            for heat_idx in range(n_heats):
                for _ in range(heat_sizes[heat_idx]):
                    if team_idx < n_teams:
                        heats[heat_idx].append(sorted_teams[team_idx])
                        team_idx += 1
                        
            for heat_idx, heat_teams in enumerate(heats):
                heat_sorted = sorted(heat_teams, key=lambda t: t["pb"] if t["pb"] is not None else 99999)
                heat_num = heat_idx + 1
                for pos_idx, team_data in enumerate(heat_sorted):
                    lane = lane_priority[pos_idx] if pos_idx < len(lane_priority) else pos_idx + 1
                    for reg in team_data["athletes"]:
                        update_registration_seeding(
                            reg_id=reg["id"],
                            heat_number=heat_num,
                            lane_number=lane,
                            order_number=lane
                        )
        else:
            # Para pista: menor tiempo = mejor (ASC ya viene ordenado desde la query)
            # with_pb ya viene ordenado ASC por personal_best
            # without_pb se colocan al inicio (series más lentas)
            sorted_athletes = without_pb + with_pb  # Sin marca primero, luego de peor a mejor
    
            n_heats = math.ceil(n_athletes / lanes_available)
    
            # Generar orden de carriles centralizado
            # Para N carriles, el orden de prioridad es: centro → afuera
            lane_priority = _generate_lane_priority(lanes_available)
    
            # Distribuir equitativamente
            base_size = n_athletes // n_heats
            extra = n_athletes % n_heats
            heat_sizes = []
            for i in range(n_heats):
                heat_sizes.append(base_size + (1 if i < extra else 0))
    
            # Serpentín: llenar series de la primera a la última
            # Los más lentos en serie 1, los más rápidos en la última serie
            heats = [[] for _ in range(n_heats)]
            athlete_idx = 0
            for heat_idx in range(n_heats):
                for _ in range(heat_sizes[heat_idx]):
                    if athlete_idx < n_athletes:
                        heats[heat_idx].append(sorted_athletes[athlete_idx])
                        athlete_idx += 1
    
            # Dentro de cada serie, ordenar por marca (mejor marca → mejor carril)
            for heat_idx, heat_athletes in enumerate(heats):
                # Ordenar: atletas con mejor marca primero dentro de la serie
                heat_sorted = sorted(heat_athletes, key=lambda r: r["personal_best"] if r.get("personal_best") is not None else 99999)
                
                heat_num = heat_idx + 1
                for pos_idx, reg in enumerate(heat_sorted):
                    # Asignar carril según prioridad centralizada
                    lane = lane_priority[pos_idx] if pos_idx < len(lane_priority) else pos_idx + 1
                    update_registration_seeding(
                        reg_id=reg["id"],
                        heat_number=heat_num,
                        lane_number=lane,
                        order_number=lane
                    )

    elif event_type == "Campo":
        # Para campo: mayor distancia = mejor (ordenar DESC)
        with_pb_desc = sorted(with_pb, key=lambda r: r["personal_best"] or 0, reverse=True)
        sorted_athletes = without_pb + with_pb_desc  # Sin marca al inicio

        for order_idx, reg in enumerate(sorted_athletes):
            update_registration_seeding(
                reg_id=reg["id"],
                heat_number=1,
                lane_number=None,
                order_number=order_idx + 1
            )

    return True, f"Siembra por marcas (serpentín) completada.\nLos mejores atletas están en la última serie con carriles centrales."


def _generate_lane_priority(num_lanes):
    """
    Genera el orden de prioridad de carriles (centro → afuera).
    Para 8 carriles: [4, 5, 3, 6, 2, 7, 1, 8]
    Para 6 carriles: [3, 4, 2, 5, 1, 6]
    """
    center = num_lanes // 2  # Para 8: center=4, para 6: center=3
    priority = []
    for offset in range(num_lanes):
        if offset == 0:
            priority.append(center)
        elif offset % 2 == 1:
            # Hacia la derecha
            lane = center + (offset + 1) // 2
            if lane <= num_lanes:
                priority.append(lane)
        else:
            # Hacia la izquierda
            lane = center - offset // 2
            if lane >= 1:
                priority.append(lane)
    
    # Asegurar que todos los carriles estén representados
    all_lanes = set(range(1, num_lanes + 1))
    remaining = all_lanes - set(priority)
    priority.extend(sorted(remaining))
    
    return priority[:num_lanes]
