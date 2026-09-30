"""
Módulo de Exportación e Impresión de Guardias.
Permite generar planillas en Excel (.xlsx), CSV y formatos de impresión oficiales,
con soporte para servicios semanales (Jueves a Miércoles) y guardias diarias ordinarias.
"""

import os
import csv
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd
from database import get_schedule_matrix, get_all_personnel

def export_schedule_to_excel(start_date: str, end_date: str, output_path: str) -> str:
    """
    Exporta el cuadrante de guardias y el resumen de personal a un archivo de Excel (.xlsx).
    """
    data = get_schedule_matrix(start_date, end_date)
    days = data["days"]
    positions = data["positions"]
    matrix = data["matrix"]

    # 1. Preparar datos de la Hoja de Cuadrante
    col_headers = ["Puesto / Servicio", "Tipo", "Rol Requerido"]
    for d in days:
        day_label = f"{d['weekday_name'][:3]} {d['date'][8:10]}/{d['date'][5:7]}"
        if d["is_holiday"]:
            day_label += f" [FERIADO: {d['holiday_name']}]"
        elif d["is_weekend"]:
            day_label += " [FINDE]"
        col_headers.append(day_label)

    matrix_rows = []
    for pos in positions:
        pos_id = pos["id"]
        is_weekly = pos.get("is_weekly", 0) == 1
        pos_type = "SEMANA (Jue-Mié)" if is_weekly else "DIARIO"
        row_data = [pos["name"], pos_type, pos["required_role"].upper()]
        for d in days:
            d_str = d["date"]
            slot = matrix.get(pos_id, {}).get(d_str)
            if slot and slot.get("person_id"):
                cell_text = f"{slot['person_name']} ({slot['person_rank']})" if slot['person_rank'] else slot['person_name']
                if slot.get("is_manual"):
                    cell_text += " *"
            else:
                cell_text = "—"
            row_data.append(cell_text)
        matrix_rows.append(row_data)

    df_matrix = pd.DataFrame(matrix_rows, columns=col_headers)

    # 2. Preparar datos de la Hoja de Personal y Equidad
    month_str = start_date[:7]
    personnel = get_all_personnel(month=month_str)
    personnel_rows = []
    for p in personnel:
        personnel_rows.append({
            "Nombre y Apellido": p["name"],
            "Jerarquía": p["rank"] or "—",
            "DNI / Legajo": p["dni"] or "—",
            "Roles Admitidos": ", ".join(p["roles"]),
            "Semanas Realizadas (Mes)": p.get("month_weekly_services", 0),
            "Total Semanas Histórico": p.get("total_weekly_services", 0),
            "Guardias Días Hábiles (Mes)": p.get("month_weekday_guards", 0),
            "Guardias Finde / Feriado (Mes)": p.get("month_special_guards", 0),
            "Total Guardias Diarias (Mes)": p.get("month_total_guards", 0),
            "Total Histórico Días Hábiles": p.get("total_weekday_guards", 0),
            "Total Histórico Finde / Feriado": p.get("total_special_guards", 0),
            "Total Histórico General Guardias": p.get("total_guards", 0),
            "Estado": "Activo" if p["is_active"] else "Inactivo / Licencia"
        })
    df_personnel = pd.DataFrame(personnel_rows)

    # 3. Guardar en Excel con múltiples hojas
    try:
        with pd.ExcelWriter(output_path) as writer:
            df_matrix.to_excel(writer, sheet_name="Cuadrante de Guardias", index=False)
            df_personnel.to_excel(writer, sheet_name="Resumen de Personal y Equidad", index=False)
    except Exception:
        # Fallback a CSV si openpyxl no estuviera disponible
        csv_fallback = output_path.replace(".xlsx", ".csv")
        export_schedule_to_csv(start_date, end_date, csv_fallback)
        return csv_fallback

    return output_path


def export_schedule_to_csv(start_date: str, end_date: str, output_path: str) -> str:
    """Exporta el cuadrante a archivo CSV estándar."""
    data = get_schedule_matrix(start_date, end_date)
    days = data["days"]
    positions = data["positions"]
    matrix = data["matrix"]

    headers = ["Puesto", "Tipo", "Rol"] + [f"{d['weekday_name'][:3]} {d['date']}" for d in days]

    with open(output_path, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for pos in positions:
            pos_id = pos["id"]
            is_weekly = pos.get("is_weekly", 0) == 1
            pos_type = "SEMANAL" if is_weekly else "DIARIO"
            row = [pos["name"], pos_type, pos["required_role"]]
            for d in days:
                slot = matrix.get(pos_id, {}).get(d["date"])
                if slot and slot.get("person_id"):
                    row.append(slot["person_name"])
                else:
                    row.append("")
            writer.writerow(row)

    return output_path
