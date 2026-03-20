import psycopg2
import hashlib
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(override=True)
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """Crea y retorna una conexión a la base de datos PostgreSQL en Supabase"""
    return psycopg2.connect(DATABASE_URL)

# --- FUNCIONES DE USUARIOS ---
def _hash_password(password):
    return hashlib.sha256(str(password).encode('utf-8')).hexdigest()

def registrar_usuario(nombre, email, password, telefono, fecha_nac, genero, rol='Visitante'):
    email_clean = email.strip().lower()
    # Permitir correos @zoopedia si el admin está creando un Cuidador
    if email_clean == 'admin':
        return False 
        
    conn = get_connection()
    c = conn.cursor()
    password_cifrada = _hash_password(password)
    try:
        c.execute('''
            INSERT INTO usuarios (nombre, email, password, telefono, fecha_nac, genero, rol)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (nombre, email, password_cifrada, telefono, str(fecha_nac), genero, rol))
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

def eliminar_usuario(user_id):
    """Elimina un usuario y todas sus conversaciones asociadas"""
    conn = get_connection()
    c = conn.cursor()
    # Primero borramos sus mensajes por integridad de la base de datos
    c.execute("DELETE FROM mensajes WHERE conversacion_id IN (SELECT id FROM conversaciones WHERE usuario_id = %s)", (user_id,))
    c.execute("DELETE FROM conversaciones WHERE usuario_id = %s", (user_id,))
    # Finalmente borramos al usuario
    c.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
    conn.commit()
    c.close()
    conn.close()

def login_usuario(email, password):
    conn = get_connection()
    c = conn.cursor()
    
    # Mantenemos la limpieza de datos (esto es buena práctica)
    email_clean = email.strip().lower() 
    password_input_cifrada = _hash_password(password)
    
    # Usamos LOWER() en la consulta para asegurar compatibilidad total
    query = "SELECT id, nombre, rol FROM usuarios WHERE LOWER(email) = %s AND password = %s"
    c.execute(query, (email_clean, password_input_cifrada))
    
    usuario = c.fetchone()
    c.close()
    conn.close()
    return usuario

def obtener_todos_los_usuarios():
    """Obtiene la lista de todos los usuarios registrados para el panel de admin"""
    conn = get_connection()
    c = conn.cursor()
    # Seleccionamos todo excepto la contraseña por seguridad
    c.execute("SELECT id, nombre, email, telefono, fecha_nac, genero, rol FROM usuarios ORDER BY id DESC")
    usuarios = c.fetchall()
    c.close()
    conn.close()
    
    # Formateamos los datos en una lista de diccionarios
    lista_usuarios = []
    for u in usuarios:
        lista_usuarios.append({
            "id": u[0], "nombre": u[1], "email": u[2], 
            "telefono": u[3], "fecha_nac": u[4], "genero": u[5], "rol": u[6]
        })
    return lista_usuarios

def actualizar_usuario(user_id, nombre, email, telefono, fecha_nac, genero, rol):
    """Actualiza los datos de un usuario existente en Supabase"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE usuarios 
            SET nombre = %s, email = %s, telefono = %s, fecha_nac = %s, genero = %s, rol = %s
            WHERE id = %s
        ''', (nombre, email, telefono, str(fecha_nac) if fecha_nac else None, genero, rol, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al actualizar: {e}")
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

def obtener_info_usuario(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, nombre, email, telefono, fecha_nac, genero, rol, tema, fondo, burbuja, avatar FROM usuarios WHERE id = %s", (user_id,))
    usuario = c.fetchone()
    c.close()
    conn.close()
    if usuario:
        return {
            "id": usuario[0], "nombre": usuario[1], "email": usuario[2],
            "telefono": usuario[3], "fecha_nac": usuario[4], "genero": usuario[5], "rol": usuario[6],
            "tema": usuario[7], "fondo": usuario[8], "burbuja": usuario[9], "avatar": usuario[10]
        }
    return None

def actualizar_preferencias(user_id, tema, fondo, burbuja, avatar):
    """Guarda los colores y estilos favoritos del usuario"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE usuarios 
            SET tema = %s, fondo = %s, burbuja = %s, avatar = %s
            WHERE id = %s
        ''', (tema, fondo, burbuja, avatar, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al guardar preferencias: {e}")
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

def cambiar_password(user_id, password_antigua, password_nueva):
    """Actualiza la contraseña del usuario verificando primero la antigua."""
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Ciframos la contraseña antigua que ingresó el usuario para compararla
    password_antigua_cifrada = _hash_password(password_antigua)
    
    # 2. Obtenemos la contraseña actual registrada en la base de datos
    c.execute("SELECT password FROM usuarios WHERE id = %s", (user_id,))
    resultado = c.fetchone()
    
    # Verificamos si la cuenta existe y si la contraseña coincide
    if not resultado or resultado[0] != password_antigua_cifrada:
        c.close()
        conn.close()
        return False # Retorna falso si la contraseña antigua no es la correcta
        
    # 3. Si coincide, ciframos la nueva contraseña y la guardamos
    password_nueva_cifrada = _hash_password(password_nueva)
    try:
        c.execute("UPDATE usuarios SET password = %s WHERE id = %s", (password_nueva_cifrada, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al cambiar contraseña: {e}")
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()
def registrar_solicitud_eliminacion(user_id, motivo):
    """Marca la cuenta del usuario como pendiente de eliminación"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE usuarios SET solicitud_eliminar = TRUE, motivo_eliminar = %s WHERE id = %s", (motivo, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al registrar solicitud: {e}")
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

def obtener_solicitudes_eliminacion():
    """Trae la lista de usuarios que quieren darse de baja para el admin"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, nombre, email, motivo_eliminar FROM usuarios WHERE solicitud_eliminar = TRUE")
    solicitudes = c.fetchall()
    c.close()
    conn.close()
    return [{"id": s[0], "nombre": s[1], "email": s[2], "motivo": s[3]} for s in solicitudes]

def rechazar_solicitud_eliminacion(user_id):
    """El administrador cancela la baja y el usuario conserva su cuenta"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE usuarios SET solicitud_eliminar = FALSE, motivo_eliminar = NULL WHERE id = %s", (user_id,))
    conn.commit()
    c.close()
    conn.close()

# --- FUNCIONES PARA EL CHAT ---
def crear_nueva_conversacion(user_id, titulo="Nueva conversación"):
    conn = get_connection()
    c = conn.cursor()
    # En PostgreSQL usamos RETURNING id para obtener el ID recién creado
    c.execute("INSERT INTO conversaciones (usuario_id, titulo) VALUES (%s, %s) RETURNING id", (user_id, titulo))
    chat_id = c.fetchone()[0]
    conn.commit()
    c.close()
    conn.close()
    return chat_id

def obtener_conversaciones(user_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, titulo FROM conversaciones WHERE usuario_id = %s ORDER BY id DESC", (user_id,))
    chats = c.fetchall()
    c.close()
    conn.close()
    return chats

def guardar_mensaje(conversacion_id, rol, contenido):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO mensajes (conversacion_id, rol, contenido) VALUES (%s, %s, %s)", 
              (conversacion_id, rol, contenido))
    conn.commit()
    c.close()
    conn.close()

def obtener_mensajes_chat(conversacion_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT rol, contenido FROM mensajes WHERE conversacion_id = %s ORDER BY id ASC", (conversacion_id,))
    mensajes = c.fetchall()
    c.close()
    conn.close()
    return [{"role": m[0], "content": m[1]} for m in mensajes]

def actualizar_titulo_chat(conversacion_id, nuevo_titulo):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE conversaciones SET titulo = %s WHERE id = %s", (nuevo_titulo, conversacion_id))
    conn.commit()
    c.close()
    conn.close()

def obtener_todas_las_conversaciones():
    """Obtiene todas las conversaciones (alertas/chats) para la vista del cuidador"""
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT c.id, c.titulo, c.fecha_creacion, u.nombre 
        FROM conversaciones c
        JOIN usuarios u ON c.usuario_id = u.id
        ORDER BY c.fecha_creacion DESC
    """
    c.execute(query)
    chats = c.fetchall()
    c.close()
    conn.close()
    
    # Formatear la salida
    lista_chats = []
    for row in chats:
        lista_chats.append({
            "id": row[0],
            "titulo": row[1],
            "fecha": row[2].strftime("%d/%m/%Y %H:%M") if hasattr(row[2], 'strftime') else str(row[2]),
            "usuario": row[3]
        })
    return lista_chats

def obtener_logs_cuidadores():
    """Obtiene el historial de chat de las conversaciones entre cuidadores y visitantes (alertas)"""
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT c.id, c.titulo, u.nombre as visitante, m.rol, m.contenido, m.fecha
        FROM conversaciones c
        JOIN usuarios u ON c.usuario_id = u.id
        JOIN mensajes m ON c.id = m.conversacion_id
        WHERE c.titulo LIKE '🚨 URGENTE:%' OR c.titulo LIKE '[RESUELTO]%'
        ORDER BY c.id DESC, m.id ASC
    """
    c.execute(query)
    logs = c.fetchall()
    c.close()
    conn.close()

    lista_logs = []
    chat_actual = None
    
    for row in logs:
        conv_id = row[0]
        # Si es una conversación nueva en el ciclo, creamos su "tarjeta"
        if not chat_actual or chat_actual["id"] != conv_id:
            if chat_actual:
                lista_logs.append(chat_actual)
            chat_actual = {
                "id": conv_id,
                "titulo": row[1],
                "visitante": row[2],
                "mensajes": []
            }
        
        # Guardamos cada mensaje dentro de su respectiva conversación
        chat_actual["mensajes"].append({
            "rol": row[3],
            "contenido": row[4],
            "fecha": row[5].strftime("%d/%m/%Y %H:%M") if hasattr(row[5], 'strftime') else str(row[5])
        })
        
    if chat_actual:
        lista_logs.append(chat_actual)
        
    return lista_logs

# ========================================================
# NUEVAS FUNCIONES PARA EL FORO (POSTGRESQL)
# ========================================================

def get_all_posts(conn):
    """Obtiene todas las preguntas y sus respuestas"""
    cursor = conn.cursor()
    # Traemos las preguntas principales
    cursor.execute("SELECT id, author_name, content, created_at FROM foro_posts ORDER BY created_at DESC")
    posts = cursor.fetchall()
    
    resultado = []
    for post in posts:
        post_id = post[0]
        # Traemos las respuestas de cada pregunta
        cursor.execute("SELECT id, author_name, content, created_at FROM foro_respuestas WHERE post_id = %s ORDER BY created_at ASC", (post_id,))
        respuestas = cursor.fetchall()
        
        lista_respuestas = [
            {"id": r[0], "author_name": r[1], "content": r[2], "created_at": str(r[3])} 
            for r in respuestas
        ]
        
        resultado.append({
            "id": post_id,
            "authorName": post[1],
            "content": post[2],
            "createdAt": str(post[3]),
            "replies": lista_respuestas
        })
    return resultado

def create_post(conn, author_name, content):
    """Guarda una nueva pregunta en la BD"""
    cursor = conn.cursor()
    cursor.execute("INSERT INTO foro_posts (author_name, content) VALUES (%s, %s) RETURNING id", (author_name, content))
    new_id = cursor.fetchone()[0]
    conn.commit()
    return new_id

def create_reply(conn, post_id, author_name, content):
    """Guarda una respuesta a una pregunta existente"""
    cursor = conn.cursor()
    cursor.execute("INSERT INTO foro_respuestas (post_id, author_name, content) VALUES (%s, %s, %s)", (post_id, author_name, content))
    conn.commit()

def delete_post(conn, post_id):
    """Elimina una pregunta de la BD"""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM foro_posts WHERE id = %s", (post_id,))
    conn.commit()
    
def update_post(conn, post_id, content):
    """Actualiza el texto de una pregunta en la BD"""
    cursor = conn.cursor()
    cursor.execute("UPDATE foro_posts SET content = %s WHERE id = %s", (content, post_id))
    conn.commit()
