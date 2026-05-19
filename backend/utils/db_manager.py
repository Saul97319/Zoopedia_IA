import psycopg2
import hashlib
import os
import json
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

# 1. Actualiza la función registrar_usuario para aceptar el PIN
def registrar_usuario(nombre, email, password, telefono, fecha_nac, genero, rol='Visitante', pin=None, nacionalidad=None, lugar_nacimiento=None, domicilio=None):
    email_clean = email.strip().lower()
    if email_clean == 'admin':
        return False 
        
    conn = get_connection()
    c = conn.cursor()
    password_cifrada = _hash_password(password)
    pin_cifrado = _hash_password(pin) if pin else None

    try:
        # 1. Insertamos en la tabla principal y pedimos que nos devuelva su ID (RETURNING id)
        c.execute('''
            INSERT INTO usuarios (nombre, email, password, telefono, fecha_nac, genero, rol, pin)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (nombre, email, password_cifrada, telefono, str(fecha_nac), genero, rol, pin_cifrado))
        
        nuevo_usuario_id = c.fetchone()[0]

        # 2. Si el rol es Cuidador, guardamos sus datos exclusivos en la tabla anexa
        if rol == 'Cuidador':
            c.execute('''
                INSERT INTO datos_cuidador (usuario_id, nacionalidad, lugar_nacimiento, domicilio)
                VALUES (%s, %s, %s, %s)
            ''', (nuevo_usuario_id, nacionalidad, lugar_nacimiento, domicilio))

        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

# 2. Añade esta NUEVA función al final de la sección de usuarios
def login_pin(email, pin):
    """Verifica el inicio de sesión usando correo y PIN encriptado"""
    conn = get_connection()
    c = conn.cursor()
    
    email_clean = email.strip().lower() 
    pin_cifrado = _hash_password(pin) # Encriptamos el PIN ingresado para compararlo
    
    query = "SELECT id, nombre, rol FROM usuarios WHERE LOWER(email) = %s AND pin = %s"
    c.execute(query, (email_clean, pin_cifrado))
    
    usuario = c.fetchone()
    c.close()
    conn.close()
    return usuario

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

def verificar_metodos_login(email):
    """Verifica si un usuario tiene PIN o Rostro configurado dado su correo."""
    conn = get_connection()
    c = conn.cursor()
    email_clean = email.strip().lower()
    
    c.execute("SELECT pin, rostro_encoding FROM usuarios WHERE LOWER(email) = %s", (email_clean,))
    usuario = c.fetchone()
    c.close()
    conn.close()
    
    if usuario:
        return {
            "tiene_pin": True if usuario[0] else False,
            "tiene_rostro": True if usuario[1] else False
        }
    return None

def obtener_todos_los_usuarios():
    """Obtiene la lista de usuarios combinando la tabla base y los datos de cuidador"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.nombre, u.email, u.telefono, u.fecha_nac, u.genero, u.rol,
               d.nacionalidad, d.lugar_nacimiento, d.domicilio
        FROM usuarios u
        LEFT JOIN datos_cuidador d ON u.id = d.usuario_id
        ORDER BY u.id DESC
    """)
    usuarios = c.fetchall()
    c.close()
    conn.close()
    
    lista_usuarios = []
    for u in usuarios:
        lista_usuarios.append({
            "id": u[0], "nombre": u[1], "email": u[2], 
            "telefono": u[3], "fecha_nac": str(u[4]) if u[4] else None, 
            "genero": u[5], "rol": u[6],
            "nacionalidad": u[7], "lugar_nacimiento": u[8], "domicilio": u[9]
        })
    return lista_usuarios

def actualizar_usuario(user_id, nombre, email, telefono, fecha_nac, genero, rol, nacionalidad=None, lugar_nacimiento=None, domicilio=None):
    """Actualiza datos base y datos exclusivos de cuidador simultáneamente"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Actualizar tabla base
        c.execute('''
            UPDATE usuarios 
            SET nombre = %s, email = %s, telefono = %s, fecha_nac = %s, genero = %s, rol = %s
            WHERE id = %s
        ''', (nombre, email, telefono, str(fecha_nac) if fecha_nac else None, genero, rol, user_id))
        
        # 2. Actualizar o insertar tabla cuidador
        if rol == 'Cuidador':
            c.execute('''
                INSERT INTO datos_cuidador (usuario_id, nacionalidad, lugar_nacimiento, domicilio)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (usuario_id) 
                DO UPDATE SET nacionalidad = EXCLUDED.nacionalidad, 
                              lugar_nacimiento = EXCLUDED.lugar_nacimiento, 
                              domicilio = EXCLUDED.domicilio
            ''', (user_id, nacionalidad, lugar_nacimiento, domicilio))
        else:
            # Si le cambian el rol a visitante, limpiamos sus datos exclusivos por seguridad
            c.execute('DELETE FROM datos_cuidador WHERE usuario_id = %s', (user_id,))
            
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
    # Añadimos pin y rostro_encoding a la consulta
    c.execute("SELECT id, nombre, email, telefono, fecha_nac, genero, rol, tema, fondo, burbuja, avatar, pin, rostro_encoding FROM usuarios WHERE id = %s", (user_id,))
    usuario = c.fetchone()
    c.close()
    conn.close()
    if usuario:
        return {
            "id": usuario[0], "nombre": usuario[1], "email": usuario[2],
            "telefono": usuario[3], "fecha_nac": usuario[4], "genero": usuario[5], "rol": usuario[6],
            "tema": usuario[7], "fondo": usuario[8], "burbuja": usuario[9], "avatar": usuario[10],
            # Evaluamos si existen o son None/Null
            "tiene_pin": True if usuario[11] else False,
            "tiene_rostro": True if usuario[12] else False
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
        
def cambiar_pin(user_id, pin_antiguo, pin_nuevo):
    """Actualiza el PIN del usuario verificando primero el antiguo."""
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Ciframos el PIN antiguo que ingresó el usuario
    pin_antiguo_cifrado = _hash_password(pin_antiguo)
    
    # 2. Obtenemos el PIN actual registrado en la base de datos
    c.execute("SELECT pin FROM usuarios WHERE id = %s", (user_id,))
    resultado = c.fetchone()
    
    # Verificamos si la cuenta existe y si el PIN coincide
    if not resultado or resultado[0] != pin_antiguo_cifrado:
        c.close()
        conn.close()
        return False # Retorna falso si el PIN antiguo no es el correcto
        
    # 3. Si coincide, ciframos el nuevo PIN y lo guardamos
    pin_nuevo_cifrado = _hash_password(pin_nuevo)
    try:
        c.execute("UPDATE usuarios SET pin = %s WHERE id = %s", (pin_nuevo_cifrado, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al cambiar PIN: {e}")
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

def verificar_email_existente(email):
    """Comprueba rápidamente si un correo ya está en la base de datos"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM usuarios WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
    existe = c.fetchone() is not None
    c.close()
    conn.close()
    return existe

# --- FUNCIONES PARA EL CHAT ACTUALIZADAS ---
def crear_nueva_conversacion(user_id, titulo="Nueva conversación", tipo="ia"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO conversaciones (usuario_id, titulo, tipo, estado) VALUES (%s, %s, %s, 'abierto') RETURNING id", (user_id, titulo, tipo))
    chat_id = c.fetchone()[0]
    conn.commit()
    c.close()
    conn.close()
    return chat_id

def obtener_conversaciones_ia(user_id, busqueda=None):
    """Obtiene el historial de chats del usuario. Si hay búsqueda, filtra por título y contenido del mensaje."""
    conn = get_connection()
    # Usamos RealDictCursor para que el resultado sea un diccionario en lugar de una tupla
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) 
    
    try:
        if busqueda:
            # Los comodines % permiten buscar la palabra en cualquier parte del texto
            termino = f"%{busqueda}%"
            # Usamos fecha_creacion, usuario_id y contenido
            c.execute("""
                SELECT DISTINCT c.id, c.titulo, c.fecha_creacion 
                FROM conversaciones c
                LEFT JOIN mensajes m ON c.id = m.conversacion_id
                WHERE c.usuario_id = %s AND c.tipo = 'ia'
                AND (c.titulo ILIKE %s OR m.contenido ILIKE %s)
                ORDER BY c.fecha_creacion DESC
            """, (user_id, termino, termino))
        else:
            # Comportamiento normal si no hay búsqueda
            c.execute("""
                SELECT id, titulo, fecha_creacion 
                FROM conversaciones 
                WHERE usuario_id = %s AND tipo = 'ia'
                ORDER BY fecha_creacion DESC
            """, (user_id,))
            
        resultados = c.fetchall()
        
        # Formateamos las fechas y pasamos la clave "fecha" que espera el frontend
        chats_formateados = []
        for fila in resultados:
            chats_formateados.append({
                "id": fila["id"],
                "titulo": fila["titulo"],
                "fecha": fila["fecha_creacion"].strftime('%Y-%m-%d %H:%M') if hasattr(fila["fecha_creacion"], 'strftime') else str(fila["fecha_creacion"])
            })
            
        return chats_formateados
    except Exception as e:
        print(f"Error al obtener conversaciones IA: {e}")
        return []
    finally:
        c.close()
        conn.close()

def obtener_alertas_usuario(user_id):
    """Trae exclusivamente los reportes de un visitante"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, titulo, estado, fecha_creacion FROM conversaciones WHERE usuario_id = %s AND tipo = 'alerta' ORDER BY id DESC", (user_id,))
    chats = c.fetchall()
    c.close()
    conn.close()
    return [{"id": c[0], "titulo": c[1], "estado": c[2], "fecha": str(c[3])} for c in chats]

def obtener_todas_las_alertas():
    """Trae TODAS las alertas para la pantalla del Cuidador"""
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT c.id, c.titulo, c.estado, c.fecha_creacion, u.nombre 
        FROM conversaciones c
        JOIN usuarios u ON c.usuario_id = u.id
        WHERE c.tipo = 'alerta'
        ORDER BY c.estado ASC, c.fecha_creacion DESC
    """
    c.execute(query)
    chats = c.fetchall()
    c.close()
    conn.close()
    return [{"id": row[0], "titulo": row[1], "estado": row[2], "fecha": str(row[3]), "usuario": row[4]} for row in chats]

def resolver_alerta(conversacion_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE conversaciones SET estado = 'resuelto' WHERE id = %s", (conversacion_id,))
    conn.commit()
    c.close()
    conn.close()
    return True
    
def obtener_mensajes_chat(conversacion_id):
    conn = get_connection()
    c = conn.cursor()
    # Añadimos imagen_base64 a la consulta SQL
    c.execute("SELECT rol, contenido, imagen_base64 FROM mensajes WHERE conversacion_id = %s ORDER BY id ASC", (conversacion_id,))
    mensajes = c.fetchall()
    c.close()
    conn.close()
    return [{"role": m[0], "content": m[1], "imagen_base64": m[2]} for m in mensajes]

def guardar_mensaje(conversacion_id, rol, contenido):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO mensajes (conversacion_id, rol, contenido) VALUES (%s, %s, %s) RETURNING id", (conversacion_id, rol, contenido))
    msg_id = c.fetchone()[0]
    conn.commit()
    c.close()
    conn.close()
    return msg_id

def guardar_imagen_chat(mensaje_id, imagen_base64):
    """Guarda la imagen enviada por el usuario asociada a su mensaje en la BD"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # Intenta actualizar el mensaje para agregarle la imagen en base64
        c.execute("UPDATE mensajes SET imagen_base64 = %s WHERE id = %s", (imagen_base64, mensaje_id))
        conn.commit()
        return True
    except Exception as e:
        # Si la columna 'imagen_base64' no existe en tu tabla de Postgres u ocurre un error,
        # lo atrapamos para que la aplicación no se caiga y Gemini siga respondiendo.
        print(f"Advertencia al guardar imagen en historial: {e}")
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

def actualizar_titulo_chat(conversacion_id, nuevo_titulo):
    """Actualiza el título de un chat específico en la base de datos."""
    conn = get_connection()
    c = conn.cursor()
    try:
        # Actualizamos solo la fila que coincida con el ID del chat
        c.execute("UPDATE conversaciones SET titulo = %s WHERE id = %s", (nuevo_titulo, conversacion_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al actualizar el título del chat: {e}")
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

def eliminar_conversacion(conversacion_id):
    """Elimina permanentemente una conversación y todos sus mensajes."""
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Primero debemos borrar los mensajes (y sus imágenes) vinculados a este chat
        # para que la base de datos no arroje un error de llave foránea (Foreign Key)
        c.execute("DELETE FROM imagenes_chat WHERE mensaje_id IN (SELECT id FROM mensajes WHERE conversacion_id = %s)", (conversacion_id,))
        c.execute("DELETE FROM mensajes WHERE conversacion_id = %s", (conversacion_id,))
        
        # 2. Luego borramos la conversación principal
        c.execute("DELETE FROM conversaciones WHERE id = %s", (conversacion_id,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al eliminar el chat: {e}")
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()
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
    
def guardar_rostro(user_id, encoding_list):
    """Guarda el mapa biométrico del rostro en la BD"""
    conn = get_connection()
    c = conn.cursor()
    try:
        # Convertimos la lista de 128 números a texto JSON
        encoding_str = json.dumps(encoding_list)
        c.execute("UPDATE usuarios SET rostro_encoding = %s WHERE id = %s", (encoding_str, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error al guardar rostro en BD: {e}")
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

def obtener_datos_rostro(email):
    """Obtiene el mapa biométrico de un usuario dado su correo"""
    conn = get_connection()
    c = conn.cursor()
    email_clean = email.strip().lower()
    
    c.execute("SELECT id, nombre, rol, rostro_encoding FROM usuarios WHERE LOWER(email) = %s", (email_clean,))
    usuario = c.fetchone()
    c.close()
    conn.close()
    return usuario

# --- FUNCIONES DE AVATARES PERSONALIZADOS ---
def obtener_avatares_personalizados(user_id):
    """Obtiene los avatares subidos por el usuario (máximo 5)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, imagen_base64 FROM avatares_personalizados WHERE usuario_id = %s ORDER BY fecha_creacion DESC", (user_id,))
    avatares = c.fetchall()
    c.close()
    conn.close()
    return [{"id": a[0], "imagen_base64": a[1]} for a in avatares]

def guardar_avatar_personalizado(user_id, imagen_base64):
    """Guarda un nuevo avatar verificando el límite de 5."""
    conn = get_connection()
    c = conn.cursor()
    
    # Verificamos cuántos tiene actualmente
    c.execute("SELECT COUNT(*) FROM avatares_personalizados WHERE usuario_id = %s", (user_id,))
    total = c.fetchone()[0]
    
    if total >= 5:
        c.close()
        conn.close()
        return False, "Límite alcanzado"
        
    try:
        c.execute("INSERT INTO avatares_personalizados (usuario_id, imagen_base64) VALUES (%s, %s) RETURNING id", (user_id, imagen_base64))
        nuevo_id = c.fetchone()[0]
        conn.commit()
        return True, nuevo_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        c.close()
        conn.close()

def eliminar_avatar_personalizado(avatar_id, user_id):
    """Elimina un avatar asegurando que pertenezca al usuario."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM avatares_personalizados WHERE id = %s AND usuario_id = %s", (avatar_id, user_id))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False
    finally:
        c.close()
        conn.close()

def obtener_perfil_cuidador(user_id):
    """Obtiene los datos base del usuario + los datos exclusivos de cuidador"""
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT u.nombre, u.email, u.telefono, u.fecha_nac,
               d.lugar_nacimiento, d.nacionalidad, d.domicilio, d.foto_perfil
        FROM usuarios u
        LEFT JOIN datos_cuidador d ON u.id = d.usuario_id
        WHERE u.id = %s
    """
    c.execute(query, (user_id,))
    row = c.fetchone()
    c.close()
    conn.close()
    
    if row:
        return {
            "nombre": row[0],
            "email": row[1],
            "telefono": row[2],
            "fecha_nac": row[3],
            "lugar_nacimiento": row[4],
            "nacionalidad": row[5],
            "domicilio": row[6],
            "foto_perfil": row[7]
        }
    return None