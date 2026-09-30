"""
Script de verificación de servidor local, endpoints de API y archivos de interfaz.
"""

import urllib.request
import urllib.parse
import json
import threading
import time
from http.server import HTTPServer
from app import CustomHandler, PORT, find_free_port, init_db

def run_checks():
    init_db()
    actual_port = find_free_port(55555)
    server = HTTPServer(("127.0.0.1", actual_port), CustomHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    base_url = f"http://127.0.0.1:{actual_port}"
    print(f"[*] Servidor de prueba corriendo en: {base_url}")

    # 1. Probar que index.html responde 200
    with urllib.request.urlopen(f"{base_url}/index.html") as response:
        assert response.status == 200
        content = response.read().decode('utf-8')
        assert "SISTEMA DE GUARDIAS" in content
        print("[+] UI index.html responde correctamente (HTTP 200).")

    # 2. Probar CSS
    with urllib.request.urlopen(f"{base_url}/css/style.css") as response:
        assert response.status == 200
        print("[+] CSS style.css responde correctamente (HTTP 200).")

    # 3. Probar API get_personnel
    req = urllib.request.Request(
        f"{base_url}/api/get_personnel",
        data=json.dumps({"month": "2026-10"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        data = json.loads(response.read().decode('utf-8'))
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"[+] API get_personnel responde correctamente ({len(data)} integrantes).")

    # 4. Probar API get_positions
    req = urllib.request.Request(
        f"{base_url}/api/get_positions",
        data=json.dumps({}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        positions = json.loads(response.read().decode('utf-8'))
        assert isinstance(positions, list)
        print(f"[+] API get_positions responde correctamente ({len(positions)} puestos).")

    # 5. Probar API generate_schedule para 1 mes
    req = urllib.request.Request(
        f"{base_url}/api/generate_schedule",
        data=json.dumps({"start_date": "2026-10-01", "end_date": "2026-10-31", "overwrite_manual": True}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        gen_res = json.loads(response.read().decode('utf-8'))
        assert gen_res["success"] is True
        print(f"[+] API generate_schedule generó {gen_res['assignments_count']} puestos para {gen_res['total_days']} días.")

    # 6. Probar API get_schedule matrix
    req = urllib.request.Request(
        f"{base_url}/api/get_schedule",
        data=json.dumps({"start_date": "2026-10-01", "end_date": "2026-10-31"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        matrix_data = json.loads(response.read().decode('utf-8'))
        assert len(matrix_data["days"]) == 31
        print("[+] API get_schedule retornó la matriz completa de 31 días.")

    # 7. Probar API get_holidays_for_year
    req = urllib.request.Request(
        f"{base_url}/api/get_holidays_for_year",
        data=json.dumps({"year": 2026}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        assert response.status == 200
        hols = json.loads(response.read().decode('utf-8'))
        assert len(hols) > 0
        print(f"[+] API get_holidays_for_year retornó {len(hols)} feriados de Argentina para 2026.")

    server.shutdown()
    print("\n[OK] TODAS LAS PRUEBAS DE SERVIDOR Y ENDPOINTS COMPLETADAS CON EXITO.")

if __name__ == "__main__":
    run_checks()
