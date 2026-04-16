import socket
import os

def obtener_ipv4_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # No necesita conexión real, solo para detectar la interfaz activa
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def actualizar_configuracion():
    ip_actual = obtener_ipv4_local()
    ruta_config = os.path.join("frontend", "assets", "config.js")
    
    contenido = f'// Actualizado automáticamente\nconst API_BASE_URL = "http://{ip_actual}:8000";'
    
    with open(ruta_config, "w", encoding="utf-8") as f:
        f.write(contenido)
    
    print(f"✅ Configuración actualizada: {ip_actual}")

if __name__ == "__main__":
    actualizar_configuracion()