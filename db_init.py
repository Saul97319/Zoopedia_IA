import sqlite3
import os
from datetime import datetime

# Definimos la ruta donde se guardará la base de datos
# Se guardará dentro de la carpeta 'data'
DB_PATH = os.path.join("data", "zoopedia.db")

def create_database():
    # Nos aseguramos de que la carpeta 'data' exista
    os.makedirs("data", exist_ok=True)
    
    # Conectamos a la base de datos (se crea si no existe)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"Conectando a la base de datos en: {DB_PATH}")

    # ---------------------------------------------------------
    # 1. CREACIÓN DE TABLAS (Según tu Diagrama ER)
    # ---------------------------------------------------------
    
    # Tabla USUARIOS [cite: 501]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,
            telefono TEXT,
            fecha_registro DATE DEFAULT CURRENT_DATE,
            fecha_nac DATE, 
            genero TEXT,
            lugar_nacimiento TEXT,
            nacionalidad TEXT,
            edad INTEGER,
            domicilio TEXT
        )
    ''')

    # Tabla CATALOGO_ANIMALES [cite: 507]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS CATALOGO_ANIMALES (
        id_animal INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_comun TEXT NOT NULL,
        zona_zoologico TEXT
    )
    ''')

    # Tabla ALERTAS [cite: 536]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ALERTAS (
        id_alerta INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
        descripcion_emergencia TEXT NOT NULL,
        estado TEXT DEFAULT 'Pendiente' CHECK(estado IN ('Pendiente', 'En Revision', 'Resuelto')),
        id_usuario INTEGER,
        id_animal INTEGER,
        FOREIGN KEY (id_usuario) REFERENCES USUARIOS(id_usuario),
        FOREIGN KEY (id_animal) REFERENCES CATALOGO_ANIMALES(id_animal)
    )
    ''')
    
    # Tabla LOGS_CHAT [cite: 537]
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS LOGS_CHAT (
        id_log INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
        pregunta_usuario TEXT,
        respuesta_ia TEXT,
        id_usuario INTEGER,
        FOREIGN KEY (id_usuario) REFERENCES USUARIOS(id_usuario)
    )
    ''')

    print("Tablas creadas correctamente.")

    # ---------------------------------------------------------
    # 2. INSERCIÓN DE DATOS DE PRUEBA (Datos Semilla)
    # ---------------------------------------------------------
    
    # Insertar ANIMALES (Ejemplos iniciales)
    animales = [
        ("Tigre de Bengala", "Zona Norte"), # [cite: 518]
        ("Jirafa Reticulada", "Sabana Africana"), # [cite: 518]
        ("León Africano", "Sabana Africana"),
        ("Elefante", "Zona Asia"),
        ("Cocodrilo", "Herpetario")
    ]
    cursor.executemany("INSERT OR IGNORE INTO CATALOGO_ANIMALES (nombre_comun, zona_zoologico) VALUES (?, ?)", animales)

    # Insertar USUARIOS DE PRUEBA (La contraseña es '1234' simulada)
    usuarios = [
        ("Diego Silva", "diego@zoopedia.com", "hash_simulado_1234", "3312345678", "2000-01-01", "M", "Visitante"),
        ("Luis Mendoza", "cuidador@zoopedia.com", "hash_simulado_1234", "3398765432", "1995-05-20", "M", "Cuidador") # [cite: 171]
    ]
    # Nota: Usamos INSERT OR IGNORE para no duplicar si corres el script varias veces
    cursor.executemany('''
        INSERT OR IGNORE INTO USUARIOS (nombre_completo, email, password_hash, telefono, fecha_nacimiento, genero, rol) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', usuarios)

    # Insertar ALERTAS FALSAS (Como pide el cronograma para probar el panel) 
    # Asumimos que el usuario 1 (Diego) reporta sobre el animal 1 (Tigre)
    alertas = [
        (datetime.now(), "El tigre se ve muy decaído y no se mueve.", "Pendiente", 1, 1),
        (datetime.now(), "Hay un niño intentando saltar la valla de las jirafas.", "En Revision", 1, 2)
    ]
    cursor.executemany('''
        INSERT INTO ALERTAS (fecha_hora, descripcion_emergencia, estado, id_usuario, id_animal) 
        VALUES (?, ?, ?, ?, ?)
    ''', alertas)
    
    print("Datos de prueba insertados.")

    conn.commit()
    conn.close()
    print("Base de datos inicializada con éxito en data/zoopedia.db")

if __name__ == "__main__":
    create_database()