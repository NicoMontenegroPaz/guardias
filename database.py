"""
Capa de Base de Datos SQLite para el Sistema de Gestión de Guardias.
Maneja persistencia de Personal, Puestos, Dotación Diaria, Feriados y Turnos Asignados.
"""

import sqlite3
import json
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from argentina_holidays import holiday_manager

import sys

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(APP_DIR, "guardias.db")

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Inicializa el esquema de la base de datos y datos por defecto si está vacía."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabla de Roles / Especialidades
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT
    )
    """)

    # Tabla de Personal
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS personnel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        dni TEXT,
        rank TEXT,
        roles TEXT NOT NULL DEFAULT '[]', -- JSON array of role codes, e.g. ["sargento", "cabo", "soldado"]
        is_active INTEGER NOT NULL DEFAULT 1,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabla de Puestos de Guardia
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        required_role TEXT NOT NULL, -- Código de rol requerido
        sort_order INTEGER NOT NULL DEFAULT 0,
        is_weekly INTEGER NOT NULL DEFAULT 0, -- 1 = Servicio Semanal (Jueves a Miércoles), 0 = Guardia Diaria
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """)

    # Migración: Verificar si la columna is_weekly existe en positions
    cursor.execute("PRAGMA table_info(positions)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if "is_weekly" not in existing_cols:
        cursor.execute("ALTER TABLE positions ADD COLUMN is_weekly INTEGER NOT NULL DEFAULT 0")

    # Plantilla de Dotación Diaria por defecto (0=Lunes ... 6=Domingo)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_template (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_of_week INTEGER NOT NULL, -- 0=Lunes, 6=Domingo
        position_id INTEGER NOT NULL,
        is_enabled INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
        UNIQUE(day_of_week, position_id)
    )
    """)

    # Excepciones de dotación para fechas específicas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS date_overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, -- YYYY-MM-DD
        position_id INTEGER NOT NULL,
        is_enabled INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
        UNIQUE(date, position_id)
    )
    """)

    # Feriados Personalizados / Institucionales
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS custom_holidays (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE NOT NULL, -- YYYY-MM-DD
        name TEXT NOT NULL,
        year INTEGER NOT NULL
    )
    """)

    # Historial de Guardias / Asignaciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, -- YYYY-MM-DD
        position_id INTEGER NOT NULL,
        person_id INTEGER,
        is_weekend_or_holiday INTEGER NOT NULL DEFAULT 0,
        day_type TEXT NOT NULL, -- 'weekday', 'weekend', 'holiday'
        is_manual INTEGER NOT NULL DEFAULT 0,
        notes TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (position_id) REFERENCES positions(id) ON DELETE CASCADE,
        FOREIGN KEY (person_id) REFERENCES personnel(id) ON DELETE SET NULL,
        UNIQUE(date, position_id)
    )
    """)

    # Índices para consultas de alto rendimiento
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_date ON assignments(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assignments_person ON assignments(person_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_personnel_active ON personnel(is_active)")

    conn.commit()

    # Sembrado inicial si la base de datos es nueva o faltan puestos/roles
    _seed_initial_data(conn)
    conn.close()


def _seed_initial_data(conn: sqlite3.Connection):
    cursor = conn.cursor()

    # Verificar si ya existen roles
    cursor.execute("SELECT COUNT(*) as count FROM roles")
    if cursor.fetchone()["count"] == 0:
        roles = [
            ("oficial_servicio", "Oficial de Servicio / Oficial de Semana", "Oficial a cargo de la guardia o de semana"),
            ("sargento", "Sargento de Guardia / Suboficial de Semana", "Suboficial de mayor jerarquía a cargo de guardia o semana"),
            ("cabo", "Cabo de Cuarto", "Control de relevos y cuartos de guardia"),
            ("soldado", "Soldado / Centinela", "Puestos de seguridad, centinela y vigilancia"),
            ("chofer", "Chofer de Guardia / Conductor de Turno", "Conductor asignado al vehículo de guardia o semana"),
            ("enfermero", "Enfermero / Sanidad", "Personal de primeros auxilios y sanidad")
        ]
        cursor.executemany("INSERT INTO roles (code, name, description) VALUES (?, ?, ?)", roles)

    # Verificar si ya existen puestos
    cursor.execute("SELECT COUNT(*) as count FROM positions")
    if cursor.fetchone()["count"] == 0:
        positions = [
            # Servicios Semanales (Jueves a Miércoles)
            ("Oficial de Semana", "oficial_servicio", 1, 1),
            ("Suboficial de Semana", "sargento", 2, 1),
            ("Conductor de Turno", "chofer", 3, 1),
            # Guardias Diarias
            ("Sargento de Guardia", "sargento", 4, 0),
            ("Cabo de Cuarto", "cabo", 5, 0),
            ("Centinela Puesto 1 (Acceso Principal)", "soldado", 6, 0),
            ("Centinela Puesto 2 (Perímetro Norte)", "soldado", 7, 0),
            ("Centinela Puesto 3 (Parque Automotor)", "soldado", 8, 0),
            ("Chofer de Guardia", "chofer", 9, 0)
        ]
        cursor.executemany("INSERT INTO positions (name, required_role, sort_order, is_weekly) VALUES (?, ?, ?, ?)", positions)
    else:
        # Asegurar que existan los 3 puestos de semana en bases de datos existentes
        weekly_positions_to_ensure = [
            ("Oficial de Semana", "oficial_servicio", 1, 1),
            ("Suboficial de Semana", "sargento", 2, 1),
            ("Conductor de Turno", "chofer", 3, 1)
        ]
        for wname, wrole, wsort, wis_weekly in weekly_positions_to_ensure:
            cursor.execute("SELECT id FROM positions WHERE name = ?", (wname,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO positions (name, required_role, sort_order, is_weekly) VALUES (?, ?, ?, ?)",
                    (wname, wrole, wsort, wis_weekly)
                )

    # Configurar plantilla semanal para puestos que aún no estén en daily_template
    cursor.execute("SELECT id, name, sort_order, is_weekly FROM positions WHERE is_active = 1 ORDER BY sort_order")
    pos_list = cursor.fetchall()

    for day in range(7):
        for pos in pos_list:
            pos_id = pos["id"]
            is_weekly = pos["is_weekly"] if "is_weekly" in pos.keys() else 0
            sort = pos["sort_order"]
            
            # Los puestos semanales siempre están habilitados todos los días
            if is_weekly == 1:
                enabled = 1
            elif day < 4:  # Días de semana (Lunes a Jueves)
                enabled = 1 if sort <= 7 else 0
            else:          # Fin de semana (Viernes a Domingo)
                enabled = 1

            cursor.execute(
                "INSERT OR IGNORE INTO daily_template (day_of_week, position_id, is_enabled) VALUES (?, ?, ?)",
                (day, pos_id, enabled)
            )

    # Sembrar personal de ejemplo si no hay nadie
    cursor.execute("SELECT COUNT(*) as count FROM personnel")
    if cursor.fetchone()["count"] == 0:
        sample_personnel = [
            # Oficiales (para Oficial de Semana)
            ("Martínez, Lucas", "30.123.456", "Teniente", json.dumps(["oficial_servicio"]), 1),
            ("Romero, Pablo", "31.456.789", "Subteniente", json.dumps(["oficial_servicio"]), 1),
            ("Álvarez, Gonzalo", "29.987.654", "Teniente 1ro", json.dumps(["oficial_servicio"]), 1),
            ("Castro, Matías", "31.876.543", "Subteniente", json.dumps(["oficial_servicio"]), 1),

            # Suboficiales / Sargentos (pueden cubrir suboficial de semana, sargento de guardia, cabo y soldado)
            ("Gómez, Carlos", "32.145.890", "Sargento 1ro", json.dumps(["sargento", "cabo", "soldado"]), 1),
            ("Rodríguez, Martín", "33.567.123", "Sargento", json.dumps(["sargento", "cabo", "soldado"]), 1),
            ("Fernández, Juan", "34.890.456", "Sargento", json.dumps(["sargento", "cabo", "soldado"]), 1),
            ("López, Walter", "35.234.789", "Cabo 1ro", json.dumps(["sargento", "cabo", "soldado"]), 1),
            ("Ruiz, Marcelo", "34.112.233", "Sargento", json.dumps(["sargento", "cabo", "soldado"]), 1),
            ("Sosa, Daniel", "35.445.566", "Sargento", json.dumps(["sargento", "cabo", "soldado"]), 1),

            # Cabos (pueden cubrir cabo de cuarto, soldado y chofer si aplica)
            ("Díaz, Lucas", "36.456.012", "Cabo", json.dumps(["cabo", "soldado"]), 1),
            ("Benítez, Fernando", "37.678.234", "Cabo", json.dumps(["cabo", "soldado", "chofer"]), 1),
            ("Romero, Sergio", "38.901.456", "Cabo", json.dumps(["cabo", "soldado"]), 1),

            # Choferes / Conductores
            ("Torres, Rodrigo", "43.654.321", "Soldado Vol.", json.dumps(["soldado", "chofer"]), 1),
            ("Herrera, Facundo", "44.543.210", "Soldado Vol.", json.dumps(["soldado", "chofer"]), 1),
            ("Morales, Tomás", "44.678.234", "Soldado Vol.", json.dumps(["soldado", "chofer"]), 1),
            ("Gutiérrez, Cristian", "45.111.222", "Soldado Vol.", json.dumps(["soldado", "chofer"]), 1),
            ("Domínguez, Javier", "46.333.444", "Soldado Vol.", json.dumps(["soldado", "chofer"]), 1),

            # Soldados
            ("Pérez, Marcos", "39.123.678", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Acosta, Esteban", "40.234.890", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Alvarez, Diego", "41.345.901", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Vázquez, Matías", "42.456.012", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Castillo, Nicolás", "43.567.123", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Suárez, Franco", "45.789.345", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Navarro, Gabriel", "40.987.654", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Mendoza, Agustín", "41.876.543", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Silva, Brian", "42.765.432", "Soldado Vol.", json.dumps(["soldado"]), 1),
            ("Ríos, Emanuel", "45.432.109", "Soldado Vol.", json.dumps(["soldado"]), 1),
        ]
        cursor.executemany(
            "INSERT INTO personnel (name, dni, rank, roles, is_active) VALUES (?, ?, ?, ?, ?)",
            sample_personnel
        )
    else:
        # Asegurar que existan oficiales en la base de datos si no hay ninguno
        cursor.execute("SELECT id FROM personnel WHERE roles LIKE '%oficial_servicio%'")
        if not cursor.fetchone():
            sample_officers = [
                ("Martínez, Lucas", "30.123.456", "Teniente", json.dumps(["oficial_servicio"]), 1),
                ("Romero, Pablo", "31.456.789", "Subteniente", json.dumps(["oficial_servicio"]), 1),
                ("Álvarez, Gonzalo", "29.987.654", "Teniente 1ro", json.dumps(["oficial_servicio"]), 1),
                ("Castro, Matías", "31.876.543", "Subteniente", json.dumps(["oficial_servicio"]), 1)
            ]
            cursor.executemany(
                "INSERT INTO personnel (name, dni, rank, roles, is_active) VALUES (?, ?, ?, ?, ?)",
                sample_officers
            )

    conn.commit()


# ==========================================
# Funciones Auxiliares de Ciclos Semanales (Jueves a Miércoles)
# ==========================================

def get_week_start_day() -> int:
    config_path = os.path.join(APP_DIR, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("week_start_day", 3) # 3 = Jueves por defecto
        except:
            pass
    return 3

def set_week_start_day(day: int):
    config_path = os.path.join(APP_DIR, "config.json")
    data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    data["week_start_day"] = day
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def get_thursday_week_start(d: date) -> date:
    """
    Retorna la fecha del día inicial correspondiente a la semana de guardia (Por defecto Jueves).
    En Python weekday(): 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo.
    """
    start_day = get_week_start_day()
    offset = (d.weekday() - start_day) % 7
    return d - timedelta(days=offset)

def get_thursday_to_wednesday_blocks(start_date: date, end_date: date) -> List[Tuple[date, date]]:
    """
    Retorna la lista de bloques (jueves_inicio, miercoles_fin) que cubren el rango de fechas indicado.
    """
    first_thu = get_thursday_week_start(start_date)
    last_thu = get_thursday_week_start(end_date)
    blocks = []
    curr = first_thu
    while curr <= last_thu or curr <= end_date:
        wed = curr + timedelta(days=6)
        blocks.append((curr, wed))
        curr += timedelta(days=7)
    return blocks


# ==========================================
# CRUD de Roles y Personal
# ==========================================

def get_all_roles() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM roles ORDER BY id")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def add_role(code: str, name: str, description: str = "") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO roles (code, name, description) VALUES (?, ?, ?)",
        (code.strip().lower(), name.strip(), description.strip())
    )
    role_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return role_id

def get_all_personnel(month: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retorna todo el personal junto con sus métricas diferenciadas:
    - Servicios Semanales (del mes y acumulado histórico).
    - Guardias Diarias en días hábiles (del mes y acumulado histórico).
    - Guardias Diarias en fines de semana / feriados (del mes y acumulado histórico).
    - Total de guardias y última asignación.
    """
    if not month:
        month = datetime.now().strftime("%Y-%m")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener lista básica de personal
    cursor.execute("SELECT * FROM personnel ORDER BY is_active DESC, name ASC")
    personnel_list = [dict(r) for r in cursor.fetchall()]

    # Parsear roles JSON
    for p in personnel_list:
        try:
            p["roles"] = json.loads(p["roles"]) if p["roles"] else []
        except Exception:
            p["roles"] = []

    # 1. Guardias Diarias del mes (puestos donde is_weekly = 0)
    month_prefix = f"{month}-%"
    cursor.execute("""
        SELECT
            a.person_id,
            SUM(CASE WHEN a.is_weekend_or_holiday = 0 THEN 1 ELSE 0 END) as month_weekday_guards,
            SUM(CASE WHEN a.is_weekend_or_holiday = 1 THEN 1 ELSE 0 END) as month_special_guards,
            COUNT(*) as month_total_guards
        FROM assignments a
        JOIN positions pos ON a.position_id = pos.id
        WHERE a.person_id IS NOT NULL AND pos.is_weekly = 0 AND a.date LIKE ?
        GROUP BY a.person_id
    """, (month_prefix,))
    month_daily_stats = {r["person_id"]: dict(r) for r in cursor.fetchall()}

    # 2. Guardias Diarias históricas totales (puestos donde is_weekly = 0)
    cursor.execute("""
        SELECT
            a.person_id,
            SUM(CASE WHEN a.is_weekend_or_holiday = 0 THEN 1 ELSE 0 END) as total_weekday_guards,
            SUM(CASE WHEN a.is_weekend_or_holiday = 1 THEN 1 ELSE 0 END) as total_special_guards,
            COUNT(*) as total_guards,
            MAX(a.date) as last_guard_date
        FROM assignments a
        JOIN positions pos ON a.position_id = pos.id
        WHERE a.person_id IS NOT NULL AND pos.is_weekly = 0
        GROUP BY a.person_id
    """)
    total_daily_stats = {r["person_id"]: dict(r) for r in cursor.fetchall()}

    # 3. Servicios Semanales (puestos donde is_weekly = 1)
    cursor.execute("""
        SELECT a.person_id, a.date, a.position_id
        FROM assignments a
        JOIN positions pos ON a.position_id = pos.id
        WHERE a.person_id IS NOT NULL AND pos.is_weekly = 1
    """)
    weekly_rows = cursor.fetchall()

    # Contabilizar bloques semanales (jueves a miércoles) únicos por persona
    person_weekly_blocks: Dict[int, Set[date]] = {}
    person_month_weekly_blocks: Dict[int, Set[date]] = {}
    person_last_assigned: Dict[int, str] = {}

    for row in weekly_rows:
        pid = row["person_id"]
        d_str = row["date"]
        d = datetime.strptime(d_str, "%Y-%m-%d").date()
        thu_start = get_thursday_week_start(d)

        if pid not in person_weekly_blocks:
            person_weekly_blocks[pid] = set()
            person_month_weekly_blocks[pid] = set()

        person_weekly_blocks[pid].add(thu_start)

        # Si el jueves de inicio o el día caen en el mes analizado
        if thu_start.strftime("%Y-%m") == month or d.strftime("%Y-%m") == month:
            person_month_weekly_blocks[pid].add(thu_start)

        if pid not in person_last_assigned or d_str > person_last_assigned[pid]:
            person_last_assigned[pid] = d_str

    # Unificar estadísticas
    for p in personnel_list:
        pid = p["id"]
        m_daily = month_daily_stats.get(pid, {})
        t_daily = total_daily_stats.get(pid, {})

        p["month_weekly_services"] = len(person_month_weekly_blocks.get(pid, set()))
        p["total_weekly_services"] = len(person_weekly_blocks.get(pid, set()))

        p["month_weekday_guards"] = m_daily.get("month_weekday_guards", 0)
        p["month_special_guards"] = m_daily.get("month_special_guards", 0)
        p["month_total_guards"] = m_daily.get("month_total_guards", 0)

        p["total_weekday_guards"] = t_daily.get("total_weekday_guards", 0)
        p["total_special_guards"] = t_daily.get("total_special_guards", 0)
        p["total_guards"] = t_daily.get("total_guards", 0)

        last_d = t_daily.get("last_guard_date", None)
        last_w = person_last_assigned.get(pid, None)
        if last_w and (not last_d or last_w > last_d):
            p["last_guard_date"] = last_w
        else:
            p["last_guard_date"] = last_d

    conn.close()
    return personnel_list

def save_person(person_data: Dict[str, Any]) -> int:
    """Crea o actualiza una persona."""
    conn = get_db_connection()
    cursor = conn.cursor()

    name = person_data.get("name", "").strip()
    dni = person_data.get("dni", "").strip()
    rank = person_data.get("rank", "").strip()
    roles = json.dumps(person_data.get("roles", []))
    is_active = 1 if person_data.get("is_active", True) else 0
    notes = person_data.get("notes", "")

    person_id = person_data.get("id")
    if person_id:
        cursor.execute("""
            UPDATE personnel
            SET name = ?, dni = ?, rank = ?, roles = ?, is_active = ?, notes = ?
            WHERE id = ?
        """, (name, dni, rank, roles, is_active, notes, person_id))
    else:
        cursor.execute("""
            INSERT INTO personnel (name, dni, rank, roles, is_active, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, dni, rank, roles, is_active, notes))
        person_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return person_id

def delete_person(person_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM personnel WHERE id = ?", (person_id,))
    conn.commit()
    conn.close()


# ==========================================
# CRUD de Puestos y Plantilla de Dotación
# ==========================================

def get_all_positions() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM positions ORDER BY sort_order ASC, id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def save_position(pos_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    name = pos_data.get("name", "").strip()
    required_role = pos_data.get("required_role", "").strip()
    sort_order = int(pos_data.get("sort_order", 0))
    is_weekly = 1 if pos_data.get("is_weekly", 0) else 0
    is_active = 1 if pos_data.get("is_active", True) else 0

    pos_id = pos_data.get("id")
    if pos_id:
        cursor.execute("""
            UPDATE positions
            SET name = ?, required_role = ?, sort_order = ?, is_weekly = ?, is_active = ?
            WHERE id = ?
        """, (name, required_role, sort_order, is_weekly, is_active, pos_id))
    else:
        cursor.execute("""
            INSERT INTO positions (name, required_role, sort_order, is_weekly, is_active)
            VALUES (?, ?, ?, ?, ?)
        """, (name, required_role, sort_order, is_weekly, is_active))
        pos_id = cursor.lastrowid

        # Insertar por defecto en plantilla diaria
        for day in range(7):
            cursor.execute("""
                INSERT OR IGNORE INTO daily_template (day_of_week, position_id, is_enabled)
                VALUES (?, ?, 1)
            """, (day, pos_id))

    conn.commit()
    conn.close()
    return pos_id

def delete_position(pos_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM positions WHERE id = ?", (pos_id,))
    conn.commit()
    conn.close()

def get_weekly_template() -> Dict[int, List[Dict[str, Any]]]:
    """Retorna la configuración semanal por día (0=Lunes...6=Domingo)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT dt.day_of_week, dt.position_id, dt.is_enabled,
               p.name as position_name, p.required_role, p.sort_order
        FROM daily_template dt
        JOIN positions p ON dt.position_id = p.id
        WHERE p.is_active = 1
        ORDER BY dt.day_of_week ASC, p.sort_order ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    result = {i: [] for i in range(7)}
    for r in rows:
        result[r["day_of_week"]].append(dict(r))
    return result

def update_weekly_template(template_data: List[Dict[str, Any]]):
    """Actualiza la plantilla semanal. Cada elemento: {day_of_week, position_id, is_enabled}."""
    conn = get_db_connection()
    cursor = conn.cursor()
    for item in template_data:
        cursor.execute("""
            INSERT INTO daily_template (day_of_week, position_id, is_enabled)
            VALUES (?, ?, ?)
            ON CONFLICT(day_of_week, position_id) DO UPDATE SET is_enabled = excluded.is_enabled
        """, (item["day_of_week"], item["position_id"], 1 if item["is_enabled"] else 0))
    conn.commit()
    conn.close()

def get_required_positions_for_date(target_date: date) -> List[Dict[str, Any]]:
    """
    Obtiene los puestos requeridos para una fecha específica,
    considerando excepciones (date_overrides) o la plantilla del día de la semana.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    weekday = target_date.weekday()

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Verificar si hay excepciones explícitas para esta fecha
    cursor.execute("""
        SELECT do.position_id, do.is_enabled, p.name as position_name, p.required_role, p.sort_order
        FROM date_overrides do
        JOIN positions p ON do.position_id = p.id
        WHERE do.date = ? AND p.is_active = 1
        ORDER BY p.sort_order ASC
    """, (date_str,))
    overrides = cursor.fetchall()

    if overrides:
        positions = [dict(r) for r in overrides if r["is_enabled"] == 1]
    else:
        # 2. Usar plantilla del día de la semana
        cursor.execute("""
            SELECT dt.position_id, dt.is_enabled, p.name as position_name, p.required_role, p.sort_order
            FROM daily_template dt
            JOIN positions p ON dt.position_id = p.id
            WHERE dt.day_of_week = ? AND dt.is_enabled = 1 AND p.is_active = 1
            ORDER BY p.sort_order ASC
        """, (weekday,))
        positions = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return positions

def set_date_override(date_str: str, position_id: int, is_enabled: bool):
    """Establece una excepción de dotación para una fecha específica."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO date_overrides (date, position_id, is_enabled)
        VALUES (?, ?, ?)
        ON CONFLICT(date, position_id) DO UPDATE SET is_enabled = excluded.is_enabled
    """, (date_str, position_id, 1 if is_enabled else 0))
    conn.commit()
    conn.close()


# ==========================================
# Feriados Personalizados
# ==========================================

def get_custom_holidays(year: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if year:
        cursor.execute("SELECT * FROM custom_holidays WHERE year = ? ORDER BY date ASC", (year,))
    else:
        cursor.execute("SELECT * FROM custom_holidays ORDER BY date ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

def save_custom_holiday(date_str: str, name: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO custom_holidays (date, name, year)
        VALUES (?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET name = excluded.name, year = excluded.year
    """, (date_str, name.strip(), dt.year))
    hid = cursor.lastrowid
    conn.commit()
    conn.close()
    return hid

def delete_custom_holiday(holiday_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_holidays WHERE id = ?", (holiday_id,))
    conn.commit()
    conn.close()

# Conectar el proveedor de feriados personalizados al holiday_manager
def custom_holiday_lookup(dt: date) -> Optional[str]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM custom_holidays WHERE date = ?", (dt.strftime("%Y-%m-%d"),))
        row = cursor.fetchone()
        conn.close()
        return row["name"] if row else None
    except Exception:
        return None

holiday_manager.custom_holidays_provider = custom_holiday_lookup


# ==========================================
# Cuadrante de Guardias y Asignaciones
# ==========================================

def get_schedule_matrix(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Retorna la matriz de guardias en un rango de fechas.
    Formato:
    - days: Lista de metadatos de días (fecha, día semana, si es feriado/finde, nombre feriado, etc.)
    - positions: Lista de puestos activos
    - matrix: Diccionario de [position_id][date] -> Assignment info {person_id, person_name, rank, is_manual, etc.}
    """
    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Obtener todos los puestos activos
    cursor.execute("SELECT * FROM positions WHERE is_active = 1 ORDER BY sort_order ASC, id ASC")
    positions = [dict(r) for r in cursor.fetchall()]
    pos_map = {p["id"]: p for p in positions}

    # 2. Generar lista de días en el rango con información de feriados/findes
    days_info = []
    curr = start_dt
    while curr <= end_dt:
        info = holiday_manager.get_day_info(curr)
        days_info.append(info)
        curr += timedelta(days=1)

    # 3. Obtener asignaciones existentes en el rango
    cursor.execute("""
        SELECT a.*, p.name as person_name, p.rank as person_rank, p.roles as person_roles,
               pos.name as position_name, pos.required_role
        FROM assignments a
        JOIN positions pos ON a.position_id = pos.id
        LEFT JOIN personnel p ON a.person_id = p.id
        WHERE a.date >= ? AND a.date <= ?
    """, (start_date, end_date))
    assignments = cursor.fetchall()
    conn.close()

    # Mapear asignaciones por [position_id][date]
    assignments_map: Dict[int, Dict[str, Any]] = {p["id"]: {} for p in positions}
    for a in assignments:
        pos_id = a["position_id"]
        d_str = a["date"]
        if pos_id in assignments_map:
            p_roles = []
            if a["person_roles"]:
                try:
                    p_roles = json.loads(a["person_roles"])
                except Exception:
                    p_roles = []
            assignments_map[pos_id][d_str] = {
                "id": a["id"],
                "date": d_str,
                "position_id": pos_id,
                "position_name": a["position_name"],
                "required_role": a["required_role"],
                "person_id": a["person_id"],
                "person_name": a["person_name"] or "— Sin Asignar —",
                "person_rank": a["person_rank"] or "",
                "person_roles": p_roles,
                "is_weekend_or_holiday": a["is_weekend_or_holiday"],
                "day_type": a["day_type"],
                "is_manual": bool(a["is_manual"]),
                "notes": a["notes"] or ""
            }

    return {
        "start_date": start_date,
        "end_date": end_date,
        "days": days_info,
        "positions": positions,
        "matrix": assignments_map
    }

def update_assignment_person(date_str: str, position_id: int, person_id: Optional[int], is_manual: bool = True):
    """
    Actualiza o asigna una persona a un puesto en una fecha dada.
    Permite el reemplazo manual inmediato requerido por el usuario.
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    day_info = holiday_manager.get_day_info(dt)
    is_special = 1 if day_info["is_special"] else 0
    day_type = day_info["day_type"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO assignments (date, position_id, person_id, is_weekend_or_holiday, day_type, is_manual, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(date, position_id) DO UPDATE SET
            person_id = excluded.person_id,
            is_weekend_or_holiday = excluded.is_weekend_or_holiday,
            day_type = excluded.day_type,
            is_manual = excluded.is_manual,
            updated_at = CURRENT_TIMESTAMP
    """, (date_str, position_id, person_id, is_special, day_type, 1 if is_manual else 0))

    conn.commit()
    conn.close()

def assign_weekly_service(start_date_str: str, position_id: int, person_id: Optional[int], is_manual: bool = True):
    """
    Asigna a una persona a un puesto semanal durante los 7 días continuos del ciclo (Jueves a Miércoles).
    start_date_str puede ser cualquier fecha de la semana; la función calcula el jueves inicial.
    """
    dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    thursday = get_thursday_week_start(dt)
    for i in range(7):
        day_dt = thursday + timedelta(days=i)
        day_str = day_dt.strftime("%Y-%m-%d")
        update_assignment_person(day_str, position_id, person_id, is_manual=is_manual)

def swap_assignments(date1: str, pos1_id: int, date2: str, pos2_id: int):
    """Intercambia los integrantes asignados entre dos celdas."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT person_id FROM assignments WHERE date = ? AND position_id = ?", (date1, pos1_id))
    r1 = cursor.fetchone()
    p1 = r1["person_id"] if r1 else None

    cursor.execute("SELECT person_id FROM assignments WHERE date = ? AND position_id = ?", (date2, pos2_id))
    r2 = cursor.fetchone()
    p2 = r2["person_id"] if r2 else None

    conn.close()

    update_assignment_person(date1, pos1_id, p2, is_manual=True)
    update_assignment_person(date2, pos2_id, p1, is_manual=True)

def clear_month_assignments(month_str: str):
    """
    Borra todas las asignaciones de guardias para un mes determinado (YYYY-MM).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM assignments WHERE date LIKE ?", (f"{month_str}-%",))
    conn.commit()
    conn.close()

def clear_schedule_range(start_date: str, end_date: str):
    """Borra las asignaciones en un rango de fechas (útil para regenerar)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM assignments WHERE date >= ? AND date <= ?", (start_date, end_date))
    conn.commit()
    conn.close()
