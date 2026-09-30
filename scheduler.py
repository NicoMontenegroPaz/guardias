"""
Motor de Generación y Distribución Equitativa de Guardias y Servicios de Semana.
Garantiza:
1. Asignación completa de Servicios de Semana (Oficial de Semana, Suboficial de Semana, Conductor de Turno)
   con ciclo continuo de Jueves a Miércoles.
2. Regla de Exclusividad: Al integrante asignado a un servicio de semana en cualquier semana del mes,
   le corresponde quedar libre de guardias diarias durante todo el resto del mes.
3. Contabilización y balance independiente de Semanas vs Guardias Diarias (Hábiles y Finde/Feriados).
4. Balance estricto de turnos ordinarios entre integrantes disponibles, descansos mínimos y equidad acumulativa.
"""

from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
import random
import json

from database import (
    get_all_personnel,
    get_all_positions,
    get_required_positions_for_date,
    update_assignment_person,
    get_thursday_week_start,
    get_thursday_to_wednesday_blocks,
    get_db_connection
)
from argentina_holidays import holiday_manager

class GuardScheduler:
    """Motor de optimización y asignación equitativa de guardias y servicios semanales."""

    def __init__(self):
        pass

    def generate_schedule(
        self,
        start_date_str: str,
        end_date_str: str,
        overwrite_manual: bool = False
    ) -> Dict[str, Any]:
        """
        Genera el cuadrante equitativo para el rango de fechas indicado.
        start_date_str: 'YYYY-MM-DD'
        end_date_str: 'YYYY-MM-DD'
        overwrite_manual: Si es False, preserva los reemplazos manuales preexistentes.
        """
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        if start_dt > end_dt:
            raise ValueError("La fecha de inicio no puede ser posterior a la de fin.")

        # 1. Obtener personal activo
        month_str = start_dt.strftime("%Y-%m")
        all_personnel = get_all_personnel(month=month_str)
        active_personnel = [p for p in all_personnel if p["is_active"] == 1]

        if not active_personnel:
            raise ValueError("No hay personal activo registrado para generar la guardia.")

        # 2. Obtener puestos activos y separarlos en semanales y diarios
        all_positions = get_all_positions()
        active_positions = {p["id"]: p for p in all_positions if p["is_active"] == 1}
        
        weekly_positions = [p for p in active_positions.values() if p.get("is_weekly", 0) == 1]
        weekly_positions.sort(key=lambda x: x.get("sort_order", 0))

        daily_positions = [p for p in active_positions.values() if p.get("is_weekly", 0) == 0]
        daily_positions.sort(key=lambda x: x.get("sort_order", 0))

        # 3. Mapear roles por persona y contadores de guardias / semanas
        person_state: Dict[int, Dict[str, Any]] = {}
        for p in active_personnel:
            pid = p["id"]
            person_state[pid] = {
                "id": pid,
                "name": p["name"],
                "rank": p["rank"],
                "roles": set(p["roles"]),
                "month_weekly": p.get("month_weekly_services", 0),
                "total_weekly": p.get("total_weekly_services", 0),
                "month_weekday": p.get("month_weekday_guards", 0),
                "month_special": p.get("month_special_guards", 0),
                "total_weekday": p.get("total_weekday_guards", 0),
                "total_special": p.get("total_special_guards", 0),
                "total_guards": p.get("total_guards", 0),
                "last_assigned_date": None,
                "assigned_dates": set(),
                "assigned_weekly_this_month": False,  # Exento de guardias diarias en el mes
                "weekly_shifts_count": 0
            }

        # 4. Cargar asignaciones históricas recientes previas al rango para calcular descansos
        conn = get_db_connection()
        cursor = conn.cursor()
        lookback_date = (start_dt - timedelta(days=7)).strftime("%Y-%m-%d")
        cursor.execute("""
            SELECT person_id, date
            FROM assignments
            WHERE date >= ? AND date < ? AND person_id IS NOT NULL
        """, (lookback_date, start_date_str))
        for row in cursor.fetchall():
            pid = row["person_id"]
            assigned_dt = datetime.strptime(row["date"], "%Y-%m-%d").date()
            if pid in person_state:
                person_state[pid]["assigned_dates"].add(assigned_dt)
                if not person_state[pid]["last_assigned_date"] or assigned_dt > person_state[pid]["last_assigned_date"]:
                    person_state[pid]["last_assigned_date"] = assigned_dt

        # Cargar asignaciones existentes dentro del rango si no se sobreescriben las manuales
        existing_assignments = {}
        if not overwrite_manual:
            cursor.execute("""
                SELECT a.date, a.position_id, a.person_id, a.is_manual, pos.is_weekly
                FROM assignments a
                JOIN positions pos ON a.position_id = pos.id
                WHERE a.date >= ? AND a.date <= ? AND a.is_manual = 1 AND a.person_id IS NOT NULL
            """, (start_date_str, end_date_str))
            for row in cursor.fetchall():
                existing_assignments[(row["date"], row["position_id"])] = row["person_id"]
                pid = row["person_id"]
                adt = datetime.strptime(row["date"], "%Y-%m-%d").date()
                if pid in person_state:
                    person_state[pid]["assigned_dates"].add(adt)
                    if row["is_weekly"] == 1:
                        person_state[pid]["assigned_weekly_this_month"] = True
        conn.close()

        new_assignments_to_save: List[Dict[str, Any]] = []
        unfilled_slots: List[Dict[str, Any]] = []

        # =========================================================================
        # FASE 1: ASIGNACIÓN DE SERVICIOS SEMANALES (JUEVES A MIÉRCOLES)
        # =========================================================================
        # Calculamos los bloques semanales (Jueves a Miércoles) que tocan el período
        weekly_blocks = get_thursday_to_wednesday_blocks(start_dt, end_dt)

        for thu_dt, wed_dt in weekly_blocks:
            # Lista de fechas de esta semana
            week_days = [thu_dt + timedelta(days=i) for i in range(7)]
            
            for wpos in weekly_positions:
                pos_id = wpos["id"]
                req_role = wpos["required_role"]
                pos_name = wpos["name"]

                # Verificar si ya existe una asignación manual preservada para este puesto en esta semana
                manual_person_for_week = None
                has_any_manual = False
                for day_dt in week_days:
                    d_str = day_dt.strftime("%Y-%m-%d")
                    if (d_str, pos_id) in existing_assignments:
                        manual_person_for_week = existing_assignments[(d_str, pos_id)]
                        has_any_manual = True
                        break

                if has_any_manual and manual_person_for_week:
                    # Preservar asignación manual para los días de esta semana dentro del rango
                    for day_dt in week_days:
                        if start_dt <= day_dt <= end_dt:
                            d_str = day_dt.strftime("%Y-%m-%d")
                            new_assignments_to_save.append({
                                "date": d_str,
                                "position_id": pos_id,
                                "person_id": manual_person_for_week,
                                "is_manual": True
                            })
                    if manual_person_for_week in person_state:
                        pdata = person_state[manual_person_for_week]
                        pdata["assigned_weekly_this_month"] = True
                        pdata["weekly_shifts_count"] += 1
                        for day_dt in week_days:
                            pdata["assigned_dates"].add(day_dt)
                    continue

                # Filtrar candidatos elegibles para el servicio semanal:
                # 1. Tener el rol requerido (ej. oficial_servicio, sargento, chofer)
                # 2. No estar asignado a otra semana este mes (assigned_weekly_this_month = False)
                # 3. No tener guardias diarias asignadas previamente en este mes
                eligible_weekly_candidates = []
                for pid, pdata in person_state.items():
                    if req_role not in pdata["roles"]:
                        continue
                    if pdata["assigned_weekly_this_month"]:
                        continue
                    # Verificar si tiene fechas asignadas en esta semana
                    overlap = any(day_dt in pdata["assigned_dates"] for day_dt in week_days)
                    if overlap:
                        continue
                    eligible_weekly_candidates.append(pdata)

                # Si no hay candidatos libres de semanas, relajar únicamente si hay extrema escasez
                if not eligible_weekly_candidates:
                    for pid, pdata in person_state.items():
                        if req_role in pdata["roles"]:
                            overlap = any(day_dt in pdata["assigned_dates"] for day_dt in week_days)
                            if not overlap:
                                eligible_weekly_candidates.append(pdata)

                if not eligible_weekly_candidates:
                    # No hay personal apto disponible para este servicio semanal
                    for day_dt in week_days:
                        if start_dt <= day_dt <= end_dt:
                            d_str = day_dt.strftime("%Y-%m-%d")
                            unfilled_slots.append({
                                "date": d_str,
                                "position_id": pos_id,
                                "position_name": pos_name,
                                "reason": f"No hay personal disponible con rol '{req_role}' para servicio semanal"
                            })
                            new_assignments_to_save.append({
                                "date": d_str,
                                "position_id": pos_id,
                                "person_id": None,
                                "is_manual": False
                            })
                    continue

                # Puntuación de Equidad para Servicios Semanales
                # Priorizar a quien menos semanas de servicio lleva en el mes y en el histórico
                scored_weekly = []
                for cand in eligible_weekly_candidates:
                    score = 0.0
                    score += cand["month_weekly"] * 2000.0
                    score += cand["total_weekly"] * 200.0
                    score += cand["total_guards"] * 5.0
                    score += cand["weekly_shifts_count"] * 5000.0
                    score += random.uniform(0.0, 1.0)
                    scored_weekly.append((score, cand))

                scored_weekly.sort(key=lambda x: x[0])
                best_cand = scored_weekly[0][1]
                chosen_pid = best_cand["id"]

                # Asignar los 7 días de la semana completa
                best_cand["assigned_weekly_this_month"] = True
                best_cand["weekly_shifts_count"] += 1
                best_cand["month_weekly"] += 1
                best_cand["total_weekly"] += 1

                for day_dt in week_days:
                    best_cand["assigned_dates"].add(day_dt)
                    if not best_cand["last_assigned_date"] or day_dt > best_cand["last_assigned_date"]:
                        best_cand["last_assigned_date"] = day_dt

                    # Solo guardar en la base de datos los días que correspondan al rango generado
                    if start_dt <= day_dt <= end_dt:
                        d_str = day_dt.strftime("%Y-%m-%d")
                        new_assignments_to_save.append({
                            "date": d_str,
                            "position_id": pos_id,
                            "person_id": chosen_pid,
                            "is_manual": False
                        })

        # =========================================================================
        # FASE 2: ASIGNACIÓN DE GUARDIAS DIARIAS ORDINARIAS
        # =========================================================================
        curr_dt = start_dt
        while curr_dt <= end_dt:
            date_str = curr_dt.strftime("%Y-%m-%d")
            day_info = holiday_manager.get_day_info(curr_dt)
            is_special = day_info["is_special"]  # Weekend o Feriado

            # Puestos requeridos para este día (filtrando solo los puestos diarios)
            all_required_posts = get_required_positions_for_date(curr_dt)
            daily_required_posts = [p for p in all_required_posts if p["position_id"] in [dp["id"] for dp in daily_positions]]

            # Ordenar los puestos: primero los más restrictivos
            def post_priority(post):
                req_role = post["required_role"]
                # Candidatos que tienen el rol y NO están de semana este mes
                eligible_count = sum(
                    1 for p in person_state.values()
                    if req_role in p["roles"] and not p["assigned_weekly_this_month"]
                )
                return (eligible_count, post["sort_order"])

            sorted_daily_posts = sorted(daily_required_posts, key=post_priority)

            # Personas ya asignadas en el día de hoy (incluyendo semanales y manuales)
            assigned_today_pids: Set[int] = set()

            # Registrar quién está asignado hoy en puestos semanales
            for item in new_assignments_to_save:
                if item["date"] == date_str and item["person_id"] is not None:
                    assigned_today_pids.add(item["person_id"])

            # Revisar manuales diarios fijos hoy
            for post in sorted_daily_posts:
                pos_id = post["position_id"]
                if (date_str, pos_id) in existing_assignments:
                    assigned_today_pids.add(existing_assignments[(date_str, pos_id)])

            for post in sorted_daily_posts:
                pos_id = post["position_id"]
                req_role = post["required_role"]
                pos_name = post["position_name"]

                # Si ya tiene una asignación manual preservada
                if (date_str, pos_id) in existing_assignments:
                    fixed_pid = existing_assignments[(date_str, pos_id)]
                    new_assignments_to_save.append({
                        "date": date_str,
                        "position_id": pos_id,
                        "person_id": fixed_pid,
                        "is_manual": True
                    })
                    continue

                # Filtrar candidatos elegibles para guardia diaria:
                # Regla Estricta: Quien entró de semana este mes queda LIBRE el resto del mes
                eligible_daily_candidates = []
                for pid, pdata in person_state.items():
                    # Condición 1: Rol admitido
                    if req_role not in pdata["roles"]:
                        continue
                    # Condición 2: No estar asignado ya hoy
                    if pid in assigned_today_pids:
                        continue
                    # Condición 3 (Exclusividad): No haber sido asignado a un servicio semanal en el mes
                    if pdata["assigned_weekly_this_month"]:
                        continue
                    eligible_daily_candidates.append(pdata)

                # Fallback de emergencia solo si no hay personal alguno disponible sin violar roles
                if not eligible_daily_candidates:
                    for pid, pdata in person_state.items():
                        if req_role in pdata["roles"] and pid not in assigned_today_pids:
                            eligible_daily_candidates.append(pdata)

                if not eligible_daily_candidates:
                    unfilled_slots.append({
                        "date": date_str,
                        "position_id": pos_id,
                        "position_name": pos_name,
                        "reason": f"No hay personal disponible con rol '{req_role}' para guardia diaria"
                    })
                    new_assignments_to_save.append({
                        "date": date_str,
                        "position_id": pos_id,
                        "person_id": None,
                        "is_manual": False
                    })
                    continue

                # Puntuación de Equidad para Guardia Diaria
                scored_candidates = []
                for cand in eligible_daily_candidates:
                    pid = cand["id"]
                    score = 0.0

                    # 1. Componente de Equidad Mensual e Histórica
                    if is_special:
                        score += cand["month_special"] * 100.0
                        score += cand["total_special"] * 15.0
                        score += cand["month_weekday"] * 10.0
                    else:
                        score += cand["month_weekday"] * 100.0
                        score += cand["total_weekday"] * 15.0
                        score += cand["month_special"] * 10.0

                    # 2. Total general acumulado como factor de desempate
                    score += cand["total_guards"] * 5.0

                    # 3. Penalización por proximidad / Descanso
                    yesterday = curr_dt - timedelta(days=1)
                    if yesterday in cand["assigned_dates"]:
                        score += 5000.0  # Penalización por guardia consecutiva

                    two_days_ago = curr_dt - timedelta(days=2)
                    if two_days_ago in cand["assigned_dates"]:
                        score += 80.0

                    three_days_ago = curr_dt - timedelta(days=3)
                    if three_days_ago in cand["assigned_dates"]:
                        score += 20.0

                    # 4. Conservación de perfiles polivalentes
                    if len(cand["roles"]) > 1 and req_role == "soldado":
                        score += 15.0

                    # Si estaba en servicio semanal este mes (caso fallback extremo), penalizar fuertemente
                    if cand["assigned_weekly_this_month"]:
                        score += 10000.0

                    score += random.uniform(0.0, 1.5)
                    scored_candidates.append((score, cand))

                scored_candidates.sort(key=lambda x: x[0])
                best_candidate = scored_candidates[0][1]
                chosen_pid = best_candidate["id"]

                # Asignar y actualizar estado
                assigned_today_pids.add(chosen_pid)
                best_candidate["assigned_dates"].add(curr_dt)
                best_candidate["last_assigned_date"] = curr_dt
                best_candidate["total_guards"] += 1

                if is_special:
                    best_candidate["month_special"] += 1
                    best_candidate["total_special"] += 1
                else:
                    best_candidate["month_weekday"] += 1
                    best_candidate["total_weekday"] += 1

                new_assignments_to_save.append({
                    "date": date_str,
                    "position_id": pos_id,
                    "person_id": chosen_pid,
                    "is_manual": False
                })

            curr_dt += timedelta(days=1)

        # 6. Guardar todas las asignaciones en la base de datos
        for item in new_assignments_to_save:
            update_assignment_person(
                date_str=item["date"],
                position_id=item["position_id"],
                person_id=item["person_id"],
                is_manual=item["is_manual"]
            )

        # 7. Resumen de equidad post-generación
        final_summary = []
        for pid, pdata in person_state.items():
            final_summary.append({
                "id": pid,
                "name": pdata["name"],
                "rank": pdata["rank"],
                "month_weekly": pdata["month_weekly"],
                "total_weekly": pdata["total_weekly"],
                "month_weekday": pdata["month_weekday"],
                "month_special": pdata["month_special"],
                "month_total": pdata["month_weekday"] + pdata["month_special"],
                "total_guards": pdata["total_guards"],
                "assigned_weekly_this_month": pdata["assigned_weekly_this_month"]
            })

        final_summary.sort(key=lambda x: (x["month_weekly"], x["month_total"], x["total_guards"]), reverse=True)

        return {
            "success": True,
            "start_date": start_date_str,
            "end_date": end_date_str,
            "total_days": (end_dt - start_dt).days + 1,
            "assignments_count": len(new_assignments_to_save),
            "unfilled_slots": unfilled_slots,
            "personnel_summary": final_summary
        }


# Instancia utilitaria global
scheduler = GuardScheduler()
