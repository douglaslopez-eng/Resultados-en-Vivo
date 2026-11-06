-- =============================================================================
-- AtletismoPro — Esquema Supabase Postgres (Fase B1)
-- Espejo lógico de database.py (SQLite) con scopes por competencia.
-- Ejecutar una vez en el Editor SQL de Supabase.
-- =============================================================================

create extension if not exists "uuid-ossp";

-- -----------------------------------------------------------
-- Competencias (una por torneo/evento)
-- -----------------------------------------------------------
create table if not exists competitions (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    start_date text,
    end_date text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Atletas (pertenecen a una competencia)
-- -----------------------------------------------------------
create table if not exists athletes (
    id uuid primary key default uuid_generate_v4(),
    competition_id uuid not null references competitions(id) on delete cascade,
    name text not null,
    club text not null,
    category text not null,
    gender text not null check(gender in ('Masculino', 'Femenino', 'Mixto')),
    birth_date text,
    bib_number text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Pruebas / Eventos (pertenecen a una competencia)
-- -----------------------------------------------------------
create table if not exists events (
    id uuid primary key default uuid_generate_v4(),
    competition_id uuid not null references competitions(id) on delete cascade,
    name text not null,
    type text not null,
    category text not null,
    gender text not null check(gender in ('Masculino', 'Femenino', 'Mixto')),
    lanes integer default 8,
    sport text default 'Atletismo',
    round text default 'Final',
    vertical_heights text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Inscripciones / Resultados / Siembras
-- -----------------------------------------------------------
create table if not exists registrations (
    id uuid primary key default uuid_generate_v4(),
    competition_id uuid not null references competitions(id) on delete cascade,
    athlete_id uuid not null references athletes(id) on delete cascade,
    event_id uuid not null references events(id) on delete cascade,
    heat_number integer,
    lane_number integer,
    order_number integer,
    result text,
    result_value real,
    is_disqualified integer default 0 check(is_disqualified in (0, 1)),
    status text default 'Normal',
    attempt1 text,
    attempt2 text,
    attempt3 text,
    attempt4 text,
    attempt5 text,
    attempt6 text,
    wind_speed real,
    personal_best real,
    attempts text,
    unique(athlete_id, event_id),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Jornadas
-- -----------------------------------------------------------
create table if not exists jornadas (
    id uuid primary key default uuid_generate_v4(),
    competition_id uuid not null references competitions(id) on delete cascade,
    name text not null,
    display_order integer default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Horarios por jornada
-- -----------------------------------------------------------
create table if not exists event_schedule (
    id uuid primary key default uuid_generate_v4(),
    competition_id uuid not null references competitions(id) on delete cascade,
    jornada_id uuid not null references jornadas(id) on delete cascade,
    event_id uuid references events(id) on delete cascade,
    combined_event_id uuid references events(id) on delete cascade,
    sub_event_index integer,
    sub_event_label text,
    start_accred text,
    end_accred text,
    entry_time text,
    event_time text not null,
    display_order integer default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Categorías dinámicas
-- -----------------------------------------------------------
create table if not exists categories (
    id uuid primary key default uuid_generate_v4(),
    competition_id uuid not null references competitions(id) on delete cascade,
    name text not null,
    min_age integer not null,
    max_age integer not null,
    unique(competition_id, name),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Miembros de relevos
-- -----------------------------------------------------------
create table if not exists relay_members (
    id uuid primary key default uuid_generate_v4(),
    competition_id uuid not null references competitions(id) on delete cascade,
    event_id uuid not null references events(id) on delete cascade,
    club text not null,
    members_text text not null,
    unique(event_id, club),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Marcas de pruebas combinadas
-- -----------------------------------------------------------
create table if not exists combined_marks (
    id uuid primary key default uuid_generate_v4(),
    competition_id uuid not null references competitions(id) on delete cascade,
    event_id uuid not null references events(id) on delete cascade,
    athlete_id uuid not null references athletes(id) on delete cascade,
    event_index integer not null,
    mark_value text,
    unique(event_id, athlete_id, event_index),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- -----------------------------------------------------------
-- Índices para consultas frecuentes
-- -----------------------------------------------------------
create index if not exists idx_athletes_competition on athletes(competition_id);
create index if not exists idx_events_competition on events(competition_id);
create index if not exists idx_registrations_competition on registrations(competition_id);
create index if not exists idx_registrations_event on registrations(event_id);
create index if not exists idx_registrations_athlete on registrations(athlete_id);
create index if not exists idx_jornadas_competition on jornadas(competition_id);
create index if not exists idx_event_schedule_competition on event_schedule(competition_id);
create index if not exists idx_event_schedule_jornada on event_schedule(jornada_id);
create index if not exists idx_relay_members_event on relay_members(event_id);
create index if not exists idx_combined_marks_event on combined_marks(event_id);
create index if not exists idx_categories_competition on categories(competition_id);

-- -----------------------------------------------------------
-- Comentarios de documentación
-- -----------------------------------------------------------
comment on table competitions is 'Competencias / torneos (una por Eventos/*.db migrado)';
comment on table athletes is 'Atletas inscritos en una competencia';
comment on table events is 'Pruebas de atletismo de una competencia';
comment on table registrations is 'Inscripciones, siembras y resultados de atletas en pruebas';
comment on table jornadas is 'Jornadas/días de una competencia';
comment on table event_schedule is 'Horario de pruebas por jornada';
