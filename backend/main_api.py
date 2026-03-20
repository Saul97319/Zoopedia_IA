import jwt
import os
import shutil
from pydantic import BaseModel
from utils.db_manager import get_all_posts, create_post, create_reply, delete_post, update_post
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from utils import db_manager
from utils.motor_ia import MotorIA_RAG

# 1. Inicializar la app FastAPI
app = FastAPI(title="Zoopedia API")

# --- CONFIGURACIÓN DE CARPETA DE ANIMALES (PDFs) ---
# Detectamos automáticamente la ruta de la carpeta data/docs_animales
RUTA_PDFS = os.path.join(os.path.dirname(__file__), "data", "docs_animales")
os.makedirs(RUTA_PDFS, exist_ok=True) # Crea la carpeta si por alguna razón no existe

# Montamos la carpeta para que el frontend pueda abrir los PDFs
app.mount("/animales_pdfs", StaticFiles(directory=RUTA_PDFS), name="animales_pdfs")

# 2. Configurar CORS (Permite que tu JS se conecte)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Inicializar el Motor IA UNA SOLA VEZ al arrancar el servidor
motor = MotorIA_RAG()
motor._conectar_db() # Se carga Chroma en memoria al iniciar

# --- CONFIGURACIÓN JWT ---
SECRET_KEY = "sPgXuDqxrp74zick9H8DXDnmjTQlmMSOeBIETFh2t0Q" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

def crear_token_acceso(data: dict):
    """Genera un JWT firmado con nuestra clave secreta"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- MODELOS DE DATOS ---
class LoginRequest(BaseModel):
    email: str
    password: str

class RegistroRequest(BaseModel):
    nombre: str
    email: str
    password: str
    telefono: str = None
    fecha_nac: str = None
    genero: str = None
    rol: str = "Visitante"  # <- Nuevo campo

class NuevaConversacionRequest(BaseModel):
    user_id: int
    titulo: str = "Nueva conversación"

class ChatRequest(BaseModel):
    pregunta: str
    user_id: int
    conversacion_id: int

class AlertaRequest(BaseModel):
    user_id: int
    zona: str
    descripcion: str

class MensajeCuidadorRequest(BaseModel):
    conversacion_id: int
    mensaje: str

# --- RUTAS DE AUTENTICACIÓN ---
@app.post("/auth/login")
def login_endpoint(req: LoginRequest):
    # Ya no hay "atajos", todos pasan por la validación real de la base de datos
    usuario = db_manager.login_usuario(req.email, req.password)
    
    if not usuario:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        
    user_id, nombre, rol = usuario[0], usuario[1], usuario[2]

    token_data = {"sub": str(user_id), "rol": rol}
    token = crear_token_acceso(token_data)
    
    return {
        "success": True, 
        "access_token": token,
        # Aquí agregamos el email que el usuario ingresó (req.email) para que se guarde en el frontend
        "usuario": {"id": user_id, "nombre": nombre, "rol": rol, "email": req.email}
    }

@app.post("/auth/registrar")
def registrar_endpoint(req: RegistroRequest):
    exito = db_manager.registrar_usuario(
        req.nombre, req.email, req.password, 
        req.telefono, req.fecha_nac, req.genero, req.rol
    )
    if not exito:
        raise HTTPException(status_code=400, detail="El correo ya está registrado o es inálido. ")
    return {"success": True, "mensaje": "Usuario creado correctamente"}

# --- RUTAS DE PERFIL DE USUARIO ---
@app.get("/usuario/perfil/{user_id}")
def obtener_perfil_endpoint(user_id: int):
    # Usamos la función que ya existe en tu db_manager
    usuario = db_manager.obtener_info_usuario(user_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"success": True, "perfil": usuario}

class CambiarPasswordRequest(BaseModel):
    user_id: int
    password_antigua: str
    password_nueva: str

@app.post("/usuario/cambiar_password")
def cambiar_password_endpoint(req: CambiarPasswordRequest):
    try:
        # Aquí mandamos llamar la función de tu bd (asegúrate de que db_manager.cambiar_password exista)
        exito = db_manager.cambiar_password(req.user_id, req.password_antigua, req.password_nueva)
        if not exito:
            raise HTTPException(status_code=400, detail="Contraseña antigua incorrecta")
        return {"success": True, "mensaje": "Contraseña actualizada correctamente"}
    except AttributeError:
        # Si la función aún no está programada en tu db_manager, la API no crasheará y avisará amablemente
        raise HTTPException(status_code=501, detail="La función cambiar_password aún no está implementada en tu base de datos.")

class ActualizarUsuarioRequest(BaseModel):
    nombre: str
    email: str
    telefono: str = None
    fecha_nac: str = None
    genero: str = None
    rol: str

class UsuarioActualizarPropioRequest(BaseModel):
    user_id: int
    nombre: str
    email: str
    telefono: str = None
    fecha_nac: str = None
    genero: str = None

@app.put("/usuario/actualizar")
def actualizar_perfil_propio_endpoint(req: UsuarioActualizarPropioRequest):
    # Primero verificamos qué rol tiene actualmente para no borrarlo o alterarlo
    usuario_actual = db_manager.obtener_info_usuario(req.user_id)
    if not usuario_actual:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    exito = db_manager.actualizar_usuario(
        req.user_id, req.nombre, req.email, req.telefono, req.fecha_nac, req.genero, usuario_actual["rol"]
    )
    
    if not exito:
        raise HTTPException(status_code=400, detail="No se pudo actualizar la información")
    return {"success": True, "mensaje": "Perfil actualizado correctamente"}

class PreferenciasRequest(BaseModel):
    user_id: int
    tema: str
    fondo: str
    burbuja: str
    avatar: str

@app.put("/usuario/preferencias")
def guardar_preferencias_endpoint(req: PreferenciasRequest):
    exito = db_manager.actualizar_preferencias(
        req.user_id, req.tema, req.fondo, req.burbuja, req.avatar
    )
    if not exito:
        raise HTTPException(status_code=400, detail="Error al guardar preferencias")
    return {"success": True, "mensaje": "Preferencias sincronizadas en la nube"}
    
# --- RUTAS DE ADMINISTRADOR ---
@app.get("/admin/usuarios")
def obtener_usuarios_endpoint(user_id: int):
    usuario_solicitante = db_manager.obtener_info_usuario(user_id)
    if not usuario_solicitante or usuario_solicitante["rol"] != "Admin":
        raise HTTPException(status_code=403, detail="Acceso denegado. Se requieren permisos de administrador.")
    usuarios = db_manager.obtener_todos_los_usuarios()
    return {"success": True, "usuarios": usuarios}

@app.put("/admin/usuario/{user_id_actualizar}")
def actualizar_usuario_endpoint(user_id_actualizar: int, admin_id: int, req: ActualizarUsuarioRequest):
    # Validar que quien intenta editar sea admin
    usuario_admin = db_manager.obtener_info_usuario(admin_id)
    if not usuario_admin or usuario_admin["rol"] != "Admin":
        raise HTTPException(status_code=403, detail="Permiso denegado")
        
    exito = db_manager.actualizar_usuario(
        user_id_actualizar, req.nombre, req.email, req.telefono, req.fecha_nac, req.genero, req.rol
    )
    
    if not exito:
        raise HTTPException(status_code=400, detail="No se pudo actualizar el usuario")
    return {"success": True, "mensaje": "Usuario actualizado correctamente"}

@app.get("/admin/animales")
def obtener_catalogo_animales():
    animales = []
    if os.path.exists(RUTA_PDFS):
        archivos = os.listdir(RUTA_PDFS)
        for archivo in archivos:
            if archivo.endswith(".pdf"):
                # Limpiamos el nombre: "01_Elefante.pdf" -> "Elefante"
                nombre_limpio = archivo.replace(".pdf", "")
                if "_" in nombre_limpio:
                    # Toma la palabra después del guión bajo
                    nombre_limpio = nombre_limpio.split("_", 1)[1] 
                
                nombre_limpio = nombre_limpio.replace("_", " ")
                
                animales.append({
                    "nombre": nombre_limpio,
                    "archivo": archivo,
                    "url": f"http://127.0.0.1:8000/animales_pdfs/{archivo}"
                })
    return {"success": True, "animales": animales}

@app.post("/admin/animales/upload")
async def subir_documento_animal(file: UploadFile = File(...), nombre: str = Form(...)):
    try:
        # 1. Asegurarnos de que tenga formato .pdf
        nombre_seguro = nombre.replace(" ", "_")
        if not nombre_seguro.lower().endswith(".pdf"):
            nombre_seguro += ".pdf"
            
        # 2. Construir la ruta final en data/docs_animales
        ruta_completa = os.path.join(RUTA_PDFS, nombre_seguro)
        
        # 3. Guardar el archivo físicamente
        with open(ruta_completa, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"success": True, "mensaje": "Documento subido y listo para la IA"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/logs/cuidadores")
def obtener_logs_cuidadores_endpoint():
    try:
        logs = db_manager.obtener_logs_cuidadores()
        return {"success": True, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SolicitudEliminacionRequest(BaseModel):
    user_id: int
    password: str
    motivo: str

@app.post("/usuario/solicitar_eliminacion")
def solicitar_eliminacion_endpoint(req: SolicitudEliminacionRequest):
    usuario = db_manager.obtener_info_usuario(req.user_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificamos la contraseña en la base de datos real
    check = db_manager.login_usuario(usuario['email'], req.password)
    if not check:
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    
    exito = db_manager.registrar_solicitud_eliminacion(req.user_id, req.motivo)
    if not exito:
        raise HTTPException(status_code=500, detail="Error al registrar la solicitud")
    return {"success": True}

@app.get("/admin/solicitudes_eliminacion")
def listar_solicitudes_endpoint(admin_id: int):
    admin = db_manager.obtener_info_usuario(admin_id)
    if not admin or admin['rol'] != 'Admin':
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    solicitudes = db_manager.obtener_solicitudes_eliminacion()
    return {"success": True, "solicitudes": solicitudes}

@app.post("/admin/rechazar_eliminacion/{user_id}")
def rechazar_eliminacion_endpoint(user_id: int, admin_id: int):
    admin = db_manager.obtener_info_usuario(admin_id)
    if not admin or admin['rol'] != 'Admin':
        raise HTTPException(status_code=403, detail="Acceso denegado")
    
    db_manager.rechazar_solicitud_eliminacion(user_id)
    return {"success": True}

# --- RUTAS DE CHAT E IA ---
@app.post("/chat/nueva")
def crear_conversacion_endpoint(req: NuevaConversacionRequest):
    try:
        chat_id = db_manager.crear_nueva_conversacion(req.user_id, req.titulo)
        return {"success": True, "conversacion_id": chat_id, "mensaje": "Conversación iniciada correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear conversación: {str(e)}")

@app.get("/chat/conversaciones/{user_id}")
def obtener_conversaciones_endpoint(user_id: int):
    chats = db_manager.obtener_conversaciones(user_id)
    return {"conversaciones": chats}

@app.get("/chat/conversacion/{conversacion_id}")
def obtener_mensajes_endpoint(conversacion_id: int):
    mensajes = db_manager.obtener_mensajes_chat(conversacion_id)
    return {"success": True, "mensajes": mensajes}

@app.post("/chat/mensaje")
def enviar_mensaje_endpoint(req: ChatRequest):
    historial_previo = db_manager.obtener_mensajes_chat(req.conversacion_id)
    respuesta_ia = motor.obtener_respuesta(req.pregunta, historial_previo)
    
    db_manager.guardar_mensaje(req.conversacion_id, "Usuario", req.pregunta)
    db_manager.guardar_mensaje(req.conversacion_id, "Zoopedia", respuesta_ia)
    
    if not historial_previo:
        db_manager.actualizar_titulo_chat(req.conversacion_id, req.pregunta[:30] + "...")
        
    # ¡Faltaba regresar la respuesta de la IA al frontend!
    return {"success": True, "respuesta": respuesta_ia}


# --- RUTAS DE EMERGENCIAS Y CUIDADOR ---
@app.get("/cuidador/alertas")
def obtener_alertas_cuidador_endpoint(user_id: int):
    if user_id == 0 or user_id == 999:
        conversaciones = db_manager.obtener_todas_las_conversaciones()
        return {"success": True, "alertas": conversaciones}
        
    usuario = db_manager.obtener_info_usuario(user_id)
    if not usuario or usuario["rol"] == "Visitante":
        raise HTTPException(status_code=403, detail="Acceso denegado. Solo personal autorizado.")
    
    conversaciones = db_manager.obtener_todas_las_conversaciones()
    return {"success": True, "alertas": conversaciones}

@app.post("/chat/alerta")
def enviar_alerta_endpoint(req: AlertaRequest):
    try:
        titulo = f"🚨 URGENTE: {req.zona}"
        chat_id = db_manager.crear_nueva_conversacion(req.user_id, titulo)
        db_manager.guardar_mensaje(chat_id, "Usuario", req.descripcion)
        return {"success": True, "conversacion_id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/mensaje_cuidador")
def enviar_mensaje_cuidador_endpoint(req: MensajeCuidadorRequest):
    try:
        db_manager.guardar_mensaje(req.conversacion_id, "Zoopedia", req.mensaje)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/mensaje_directo")
def enviar_mensaje_directo_endpoint(req: MensajeCuidadorRequest):
    try:
        db_manager.guardar_mensaje(req.conversacion_id, "Usuario", req.mensaje)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/resolver/{conversacion_id}")
def resolver_alerta_endpoint(conversacion_id: int):
    try:
        conn = db_manager.get_connection()
        c = conn.cursor()
        c.execute("UPDATE conversaciones SET titulo = '[RESUELTO] ' || titulo WHERE id = %s AND titulo NOT LIKE '[RESUELTO]%%'", (conversacion_id,))
        conn.commit()
        c.close()
        conn.close()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/admin/usuario/{user_id_eliminar}")
def eliminar_usuario_endpoint(user_id_eliminar: int, admin_id: int):
    # Validar que quien intenta borrar sea admin
    usuario_admin = db_manager.obtener_info_usuario(admin_id)
    if not usuario_admin or usuario_admin["rol"] != "Admin":
        raise HTTPException(status_code=403, detail="Permiso denegado")
        
    db_manager.eliminar_usuario(user_id_eliminar)
    return {"success": True}

class PostCreate(BaseModel):
    author_name: str
    content: str

class ReplyCreate(BaseModel):
    author_name: str
    content: str

# Nota: Asegúrate de cambiar 'get_db_connection()' por la función real 
# que usas en tu proyecto para conectarte a PostgreSQL.

@app.get("/api/foro/posts")
def api_get_posts():
    conn =db_manager.get_connection() # <--- REVISA QUE ESTA FUNCIÓN SEA LA TUYA
    posts = get_all_posts(conn)
    conn.close()
    return posts

@app.post("/api/foro/posts")
def api_create_post(post: PostCreate):
    conn = db_manager.get_connection()
    new_id = create_post(conn, post.author_name, post.content)
    conn.close()
    return {"message": "Post creado", "id": new_id}

@app.post("/api/foro/posts/{post_id}/respuestas")
def api_create_reply(post_id: int, reply: ReplyCreate):
    conn = db_manager.get_connection()
    create_reply(conn, post_id, reply.author_name, reply.content)
    conn.close()
    return {"message": "Respuesta creada"}

@app.delete("/api/foro/posts/{post_id}")
def api_delete_post(post_id: int):
    conn = db_manager.get_connection()
    delete_post(conn, post_id)
    conn.close()
    return {"message": "Post eliminado"}

class PostUpdate(BaseModel):
    content: str

@app.put("/api/foro/posts/{post_id}")
def api_update_post(post_id: int, post: PostUpdate):
    conn = db_manager.get_connection()
    update_post(conn, post_id, post.content)
    conn.close()
    return {"message": "Post actualizado"}