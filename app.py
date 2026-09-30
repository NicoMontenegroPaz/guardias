"""
Aplicación Principal del Sistema de Gestión de Guardias.
Inicializa la base de datos, levanta el servidor local y ejecuta la ventana de escritorio con PyWebView.
"""

import sys
import os
import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, HTTPServer
import socket
from datetime import datetime, date

# Importar capas del sistema
from database import (
    init_db,
    get_all_roles,
    add_role,
    get_all_personnel,
    save_person,
    delete_person,
    get_all_positions,
    save_position,
    delete_position,
    get_weekly_template,
    update_weekly_template,
    get_required_positions_for_date,
    set_date_override,
    get_custom_holidays,
    save_custom_holiday,
    delete_custom_holiday,
    get_schedule_matrix,
    update_assignment_person,
    assign_weekly_service,
    swap_assignments
)
from scheduler import scheduler
from argentina_holidays import holiday_manager
from exporter import export_schedule_to_excel, export_schedule_to_csv

try:
    import webview
except ImportError:
    webview = None

PORT = 54321

if getattr(sys, 'frozen', False):
    BASE_DIR = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UI_DIR = os.path.join(BASE_DIR, "ui")

class Api:
    """API de Python expuesta a JavaScript para operaciones bidireccionales."""

    # Personal
    def get_personnel(self, month: str = ""):
        return get_all_personnel(month=month or datetime.now().strftime("%Y-%m"))

    def save_person(self, person_data: dict):
        pid = save_person(person_data)
        return {"success": True, "id": pid}

    def delete_person(self, person_id: int):
        delete_person(person_id)
        return {"success": True}

    # Roles
    def get_roles(self):
        return get_all_roles()

    def add_role(self, code: str, name: str, description: str = ""):
        rid = add_role(code, name, description)
        return {"success": True, "id": rid}

    # Puestos
    def get_positions(self):
        return get_all_positions()

    def save_position(self, pos_data: dict):
        pid = save_position(pos_data)
        return {"success": True, "id": pid}

    def delete_position(self, pos_id: int):
        delete_position(pos_id)
        return {"success": True}

    # Plantilla semanal y dotación
    def get_weekly_template(self):
        return get_weekly_template()

    def update_weekly_template(self, template_data: list):
        update_weekly_template(template_data)
        return {"success": True}

    def set_date_override(self, date_str: str, position_id: int, is_enabled: bool):
        set_date_override(date_str, position_id, is_enabled)
        return {"success": True}

    # Feriados
    def get_holidays_for_year(self, year: int):
        y = int(year)
        # Feriados oficiales
        official_holidays = []
        try:
            ar_holidays = holiday_manager._get_holidays_for_year(y)
            for d, name in ar_holidays.items():
                official_holidays.append({
                    "date": d.strftime("%Y-%m-%d"),
                    "name": name,
                    "is_custom": False
                })
        except Exception:
            pass

        # Feriados personalizados
        custom = get_custom_holidays(y)
        custom_list = [{
            "id": c["id"],
            "date": c["date"],
            "name": c["name"],
            "is_custom": True
        } for c in custom]

        all_hols = official_holidays + custom_list
        all_hols.sort(key=lambda x: x["date"])
        return all_hols

    def save_custom_holiday(self, date_str: str, name: str):
        hid = save_custom_holiday(date_str, name)
        return {"success": True, "id": hid}

    def delete_custom_holiday(self, holiday_id: int):
        delete_custom_holiday(holiday_id)
        return {"success": True}

    # Cuadrante y Asignaciones
    def get_schedule(self, start_date: str, end_date: str):
        return get_schedule_matrix(start_date, end_date)

    def generate_schedule(self, start_date: str, end_date: str, overwrite_manual: bool = False):
        try:
            result = scheduler.generate_schedule(start_date, end_date, overwrite_manual)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_assignment(self, date_str: str, position_id: int, person_id: any, is_manual: bool = True):
        pid = int(person_id) if person_id is not None and str(person_id).isdigit() else None
        update_assignment_person(date_str, int(position_id), pid, is_manual=is_manual)
        return {"success": True}

    def assign_weekly_service(self, start_date: str, position_id: int, person_id: any, is_manual: bool = True):
        pid = int(person_id) if person_id is not None and str(person_id).isdigit() else None
        assign_weekly_service(start_date, int(position_id), pid, is_manual=is_manual)
        return {"success": True}

    def swap_assignments(self, date1: str, pos1_id: int, date2: str, pos2_id: int):
        swap_assignments(date1, int(pos1_id), date2, int(pos2_id))
        return {"success": True}

    def clear_month_assignments(self, month_str: str):
        from database import clear_month_assignments
        clear_month_assignments(month_str)
        return {"success": True}

    def clear_schedule_range(self, start_date: str, end_date: str):
        from database import clear_schedule_range
        clear_schedule_range(start_date, end_date)
        return {"success": True}

    def get_config(self):
        from database import get_week_start_day
        return {"week_start_day": get_week_start_day()}

    def set_config(self, week_start_day: int):
        from database import set_week_start_day
        set_week_start_day(int(week_start_day))
        return {"success": True}

    # Exportación
    def export_excel(self, start_date: str, end_date: str):
        try:
            # Guardar en la carpeta del usuario o escritorio
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop_path):
                desktop_path = os.path.dirname(os.path.abspath(__file__))

            filename = f"Guardias_{start_date}_al_{end_date}.xlsx"
            full_path = os.path.join(desktop_path, filename)

            export_schedule_to_excel(start_date, end_date, full_path)
            return {"success": True, "path": full_path, "filename": filename}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_csv(self, start_date: str, end_date: str):
        try:
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop_path):
                desktop_path = os.path.dirname(os.path.abspath(__file__))

            filename = f"Guardias_{start_date}_al_{end_date}.csv"
            full_path = os.path.join(desktop_path, filename)

            export_schedule_to_csv(start_date, end_date, full_path)
            return {"success": True, "path": full_path, "filename": filename}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_app_version(self):
        return {"version": "1.0.0", "status": "online", "current_time": datetime.now().isoformat()}


class CustomHandler(SimpleHTTPRequestHandler):
    """Manejador HTTP para servir la interfaz estática y endpoints REST de respaldo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIR, **kwargs)

    def do_POST(self):
        """Manejador de llamadas API REST de respaldo si no se usa pywebview.api."""
        if self.path.startswith("/api/"):
            endpoint = self.path[5:]
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body) if body else {}

            api = Api()
            response_data = {"error": "Endpoint not found"}

            if hasattr(api, endpoint):
                func = getattr(api, endpoint)
                try:
                    if isinstance(data, dict):
                        response_data = func(**data)
                    elif isinstance(data, list):
                        response_data = func(*data)
                    else:
                        response_data = func()
                except Exception as e:
                    response_data = {"success": False, "error": str(e)}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data, default=str).encode("utf-8"))
        else:
            self.send_error(404, "File not found")

    def end_headers(self):
        # Deshabilitar caché durante el desarrollo y soporte de CORS
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        # Silenciar logs ruidosos en consola
        return


def find_free_port(start_port=54321):
    port = start_port
    while port < 60000:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
            port += 1
    return start_port

def start_server(port):
    server = HTTPServer(("127.0.0.1", port), CustomHandler)
    server.serve_forever()

def main():
    print("=========================================================")
    print("   SISTEMA DE GESTIÓN Y GENERACIÓN DE GUARDIAS")
    print("=========================================================")
    
    # 1. Inicializar base de datos SQLite
    print("[*] Inicializando base de datos local SQLite...")
    init_db()
    print("[+] Base de datos lista.")

    # 2. Iniciar servidor HTTP en segundo plano
    actual_port = find_free_port(PORT)
    server_thread = threading.Thread(target=start_server, args=(actual_port,), daemon=True)
    server_thread.start()
    app_url = f"http://127.0.0.1:{actual_port}/index.html"
    print(f"[+] Servidor web iniciado en: {app_url}")

    api = Api()

    # 3. Iniciar ventana nativa de PyWebView
    if webview is not None:
        try:
            print("[*] Abriendo ventana nativa de escritorio...")
            window = webview.create_window(
                title="Sistema de Gestión y Generación de Guardias - República Argentina",
                url=app_url,
                js_api=api,
                width=1380,
                height=880,
                min_size=(1024, 680),
                confirm_close=True,
                background_color="#0d1117"
            )
            webview.start(debug=False)
            sys.exit(0)
        except Exception as e:
            print(f"[!] PyWebView no pudo iniciar ventana nativa ({e}). Abriendo en navegador...")

    # Fallback si no hay soporte GUI directo
    print(f"[*] Abriendo aplicación en navegador predeterminado: {app_url}")
    webbrowser.open(app_url)
    print("\nPresiona CTRL+C para detener el servidor.")
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nServidor finalizado.")

if __name__ == "__main__":
    main()
