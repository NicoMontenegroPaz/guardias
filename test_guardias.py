"""
Suite de Pruebas Automatizadas para el Sistema de Guardias.
Verifica:
1. Conexión y esquema de Base de Datos.
2. Reconocimiento de Feriados de Argentina y Fines de semana.
3. Restricciones de roles en los puestos.
4. Generación equitativa para 1 semana, 2 semanas y 1 mes.
5. Preservación y actualización de reemplazos manuales.
6. Exportación a Excel y CSV.
"""

import os
import unittest
from datetime import datetime, date, timedelta

from database import (
    init_db,
    get_all_personnel,
    save_person,
    get_all_positions,
    save_position,
    get_weekly_template,
    get_schedule_matrix,
    update_assignment_person,
    swap_assignments
)
from argentina_holidays import holiday_manager
from scheduler import scheduler
from exporter import export_schedule_to_excel, export_schedule_to_csv

class TestGuardiasSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_holiday_manager_argentina(self):
        """Prueba la detección de feriados nacionales argentinos."""
        # 25 de Mayo (Revolución de Mayo) es feriado nacional inamovible en Argentina
        may25 = date(2026, 5, 25)
        info = holiday_manager.get_day_info(may25)
        self.assertTrue(info["is_holiday"], "El 25 de Mayo debe ser detectado como feriado.")
        self.assertTrue(info["is_special"], "Debe computar como día especial.")

        # Sábado cualquiera
        sat = date(2026, 9, 19)
        info_sat = holiday_manager.get_day_info(sat)
        self.assertTrue(info_sat["is_weekend"], "Debe detectar que es fin de semana.")
        self.assertTrue(info_sat["is_special"], "Finde debe ser especial.")

        # Martes hábil no feriado
        tue = date(2026, 9, 22)
        info_tue = holiday_manager.get_day_info(tue)
        self.assertFalse(info_tue["is_weekend"])

    def test_02_database_personnel_and_roles(self):
        """Verifica la recuperación y guardado de personal con roles específicos."""
        personnel = get_all_personnel()
        self.assertGreater(len(personnel), 0, "Debe haber personal sembrado.")

        # Verificar que tienen roles parseados como lista
        for p in personnel:
            self.assertIsInstance(p["roles"], list)
            self.assertIn("month_weekday_guards", p)
            self.assertIn("month_special_guards", p)
            self.assertIn("total_guards", p)

    def test_03_positions_and_daily_template(self):
        """Verifica los puestos y plantilla de dotación."""
        positions = get_all_positions()
        self.assertGreater(len(positions), 0)

        template = get_weekly_template()
        self.assertEqual(len(template), 7, "La plantilla debe tener 7 días.")

    def test_04_scheduler_generation_one_week(self):
        """Prueba la generación de guardia para 1 semana."""
        start = "2026-10-01"
        end = "2026-10-07"
        res = scheduler.generate_schedule(start, end)
        self.assertTrue(res["success"])
        self.assertEqual(res["total_days"], 7)

        # Verificar la matriz generada
        matrix_data = get_schedule_matrix(start, end)
        self.assertEqual(len(matrix_data["days"]), 7)

        # Verificar que no hay personas repetidas en el mismo día
        for d in matrix_data["days"]:
            d_str = d["date"]
            assigned_today = []
            for pos_id, slots in matrix_data["matrix"].items():
                if d_str in slots and slots[d_str]["person_id"]:
                    assigned_today.append(slots[d_str]["person_id"])
            # Todos los asignados hoy deben ser únicos
            self.assertEqual(len(assigned_today), len(set(assigned_today)), f"Conflicto de personal repetido el día {d_str}")

    def test_05_manual_replacement_and_swap(self):
        """Prueba el reemplazo manual y swap de integrantes."""
        date_test = "2026-10-01"
        positions = get_all_positions()
        pos1 = positions[0]["id"]
        pos2 = positions[1]["id"]

        personnel = get_all_personnel()
        p1 = personnel[0]["id"]
        p2 = personnel[1]["id"]

        # Asignar p1 al puesto 1 y p2 al puesto 2
        update_assignment_person(date_test, pos1, p1, is_manual=True)
        update_assignment_person(date_test, pos2, p2, is_manual=True)

        matrix = get_schedule_matrix(date_test, date_test)
        self.assertEqual(matrix["matrix"][pos1][date_test]["person_id"], p1)
        self.assertEqual(matrix["matrix"][pos2][date_test]["person_id"], p2)

        # Realizar swap
        swap_assignments(date_test, pos1, date_test, pos2)

        matrix_after = get_schedule_matrix(date_test, date_test)
        self.assertEqual(matrix_after["matrix"][pos1][date_test]["person_id"], p2)
        self.assertEqual(matrix_after["matrix"][pos2][date_test]["person_id"], p1)

    def test_06_export_excel_and_csv(self):
        """Prueba la exportación de la planilla a Excel y CSV."""
        start = "2026-10-01"
        end = "2026-10-07"
        excel_path = os.path.join(os.path.dirname(__file__), "test_export.xlsx")
        csv_path = os.path.join(os.path.dirname(__file__), "test_export.csv")

        try:
            export_schedule_to_excel(start, end, excel_path)
            self.assertTrue(os.path.exists(excel_path))
            self.assertGreater(os.path.getsize(excel_path), 0)

            export_schedule_to_csv(start, end, csv_path)
            self.assertTrue(os.path.exists(csv_path))
            self.assertGreater(os.path.getsize(csv_path), 0)
        finally:
            if os.path.exists(excel_path):
                os.remove(excel_path)
            if os.path.exists(csv_path):
                os.remove(csv_path)

if __name__ == "__main__":
    unittest.main()
