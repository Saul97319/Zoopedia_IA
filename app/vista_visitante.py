import streamlit as st
import time
# Importamos las funciones de base de datos
from utils.db_manager import (
    obtener_info_usuario,
    crear_nueva_conversacion,
    obtener_conversaciones,
    guardar_mensaje,
    obtener_mensajes_chat,
    actualizar_titulo_chat
)
# Importamos el motor de IA
from utils.motor_ia import MotorIA_RAG

# --- 0. CACHÉ DE LA IA (CRUCIAL PARA VELOCIDAD) ---
# Usamos cache_resource para que el modelo solo se cargue UNA vez
# y no cada vez que el usuario escribe un mensaje.
@st.cache_resource
def obtener_motor_ia():
    print("🚀 Iniciando Motor de IA...")
    return MotorIA_RAG()

def app():
    # --- 1. VALIDACIÓN DE SEGURIDAD ---
    if 'usuario_id' not in st.session_state:
        st.error("Acceso denegado. Por favor inicia sesión.")
        return

    user_id = st.session_state['usuario_id']
    datos_usuario = obtener_info_usuario(user_id)
    
    if not datos_usuario:
        st.warning("No se pudieron cargar los datos del usuario.")
        return

    nombre_completo = datos_usuario['nombre']
    nombre_mostrar = nombre_completo.split(" ")[0]
    
    # Inicializamos el motor de IA
    motor_ia = obtener_motor_ia()

    # --- 2. GESTIÓN DE ESTADO (SESSION STATE) ---
    # Variable para saber en qué conversación estamos (None = Nueva conversación)
    if 'chat_actual_id' not in st.session_state:
        st.session_state.chat_actual_id = None
    
    # Lista de mensajes visuales (para el refresco inmediato)
    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # --- 3. LOGICA DE CARGA DE MENSAJES ---
    # Si tenemos un ID de chat seleccionado y la lista está vacía (por recarga), la llenamos desde la DB
    if st.session_state.chat_actual_id is not None and not st.session_state.messages:
        historial_db = obtener_mensajes_chat(st.session_state.chat_actual_id)
        if historial_db:
            # Convertimos roles de DB a roles de Streamlit si es necesario
            # En tu DB guardas 'user' y 'assistant' (o similar), nos aseguramos de mapear
            st.session_state.messages = historial_db
        else:
             # Si el chat existe en DB pero no tiene mensajes (raro, pero posible), mensaje default
             st.session_state.messages = [{"role": "assistant", "content": f"¡Hola de nuevo {nombre_mostrar}! ¿En qué nos quedamos?"}]
    
    # Si es nueva conversación (None) y no hay mensajes, ponemos el saludo inicial
    elif st.session_state.chat_actual_id is None and not st.session_state.messages:
        st.session_state.messages = [
            {"role": "assistant", "content": f"¡Hola {nombre_mostrar}! Bienvenido a Zoopedia. 🦒 Soy tu asistente virtual. Pregúntame sobre horarios, animales o reglas."}
        ]

    # --- 4. ESTILOS CSS (Tu diseño original + arreglos) ---
    st.markdown("""
    <style>
        /* --- LIMPIEZA INTERFAZ --- */
        [data-testid="stAppViewContainer"] { background-color: #FFFFFF !important; }
        header, [data-testid="stHeader"] { background-color: rgba(0,0,0,0) !important; }
        .stDeployButton { display: none; }

        /* --- TIPOGRAFÍA --- */
        html, body, [class*="css"] { font-family: 'Helvetica', sans-serif !important; }
        
        .main-title {
            color: #2E7D32;
            font-size: 3rem;
            font-weight: 700;
            margin-top: -40px; 
        }

        /* --- SIDEBAR --- */
        section[data-testid="stSidebar"] {
            background-color: #f9f9f9;
            border-right: 1px solid #ddd;
        }

        /* Botones del historial en sidebar */
        div.stButton > button.history-btn {
            text-align: left;
            border: 1px solid #eee;
            background-color: white;
            color: #555;
            margin-bottom: 5px;
        }
        div.stButton > button.history-btn:hover {
            border-color: #2E7D32;
            color: #2E7D32;
        }
        
        /* --- CHAT --- */
        .stChatMessage { background-color: #f1f8e9; border-radius: 15px; }
        
        /* Botón Nueva Conversación (Cuadrado y + grande) */
        div[data-testid="stSidebar"] .stButton button {
            border-radius: 8px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # --- 5. SIDEBAR: HISTORIAL DE CONVERSACIONES ---
    with st.sidebar:
        st.header("Tus Conversaciones")
        
        col_new, col_search = st.columns([1, 4])
        with col_new:
            # BOTÓN NUEVA CONVERSACIÓN
            if st.button("➕", help="Nueva Conversación"):
                st.session_state.chat_actual_id = None
                st.session_state.messages = [] # Limpiamos para que se regenere el saludo
                st.rerun()

        with col_search:
            st.text_input("Buscar chats...", placeholder="🔍 Buscar...", label_visibility="collapsed")
        
        st.divider()
        st.caption("Historial")
        
        # Cargar historial desde DB
        chats_usuario = obtener_conversaciones(user_id) # Retorna [(id, titulo), ...]
        
        with st.container(height=400, border=False):
            if not chats_usuario:
                st.info("Aún no tienes conversaciones guardadas.")
            
            for chat_id, titulo in chats_usuario:
                # Usamos una key única para cada botón
                if st.button(f"💬 {titulo}", key=f"chat_{chat_id}", use_container_width=True):
                    st.session_state.chat_actual_id = chat_id
                    st.session_state.messages = [] # Forzamos recarga desde DB en el siguiente ciclo
                    st.rerun()

    # --- 6. CABECERA ---
    col_title, col_spacer, col_profile = st.columns([5, 1, 3])
    with col_title:
        st.markdown('<h1 class="main-title">🌿 Zoopedia Chat</h1>', unsafe_allow_html=True)
    
    with col_profile:
        # Popover de perfil (simplificado para el ejemplo)
        with st.popover(f"👤 {nombre_mostrar}", use_container_width=True):
            if st.button("Cerrar Sesión", type="primary", use_container_width=True):
                st.session_state['logged_in'] = False
                st.session_state['rol'] = None
                st.rerun()

    # --- 7. AREA DE CHAT ---
    st.divider()
    chat_container = st.container()

    # Renderizar mensajes anteriores
    with chat_container:
        for message in st.session_state.messages:
            avatar = "🦁" if message["role"] == "assistant" or message["role"] == "Zoopedia" else "👤"
            # Unificar nombres de roles para Streamlit
            role_st = "assistant" if message["role"] in ["assistant", "Zoopedia"] else "user"
            
            with st.chat_message(role_st, avatar=avatar):
                st.markdown(message["content"])

    # --- 8. LÓGICA DE ENVÍO Y RESPUESTA IA ---
    if prompt := st.chat_input("Escribe tu duda sobre el zoológico aquí..."):
        
        # 8.1. Mostrar mensaje del usuario inmediatamente
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

        # 8.2. Gestión de Primera Vez (Crear Chat en DB)
        if st.session_state.chat_actual_id is None:
            # Usamos los primeros 30 caracteres como título
            titulo_chat = (prompt[:30] + '..') if len(prompt) > 30 else prompt
            nuevo_id = crear_nueva_conversacion(user_id, titulo=titulo_chat)
            st.session_state.chat_actual_id = nuevo_id
            
            # Guardamos también el mensaje de bienvenida inicial en la DB si queremos que persista
            # (Opcional, pero recomendado para coherencia)
            guardar_mensaje(nuevo_id, "assistant", f"¡Hola {nombre_mostrar}! Bienvenido a Zoopedia. 🦒 Soy tu asistente virtual.")

        # 8.3. Guardar mensaje de usuario en DB
        guardar_mensaje(st.session_state.chat_actual_id, "user", prompt)

        # 8.4. Obtener respuesta de la IA
        try:
            with st.spinner("Zoopedia está pensando... 🧠"):
                # Llamamos a tu motor de IA
                respuesta_ia = motor_ia.obtener_respuesta(prompt)
            
            # 8.5. Mostrar respuesta IA
            st.session_state.messages.append({"role": "assistant", "content": respuesta_ia})
            with chat_container:
                with st.chat_message("assistant", avatar="🦁"):
                    st.markdown(respuesta_ia)
            
            # 8.6. Guardar respuesta IA en DB
            guardar_mensaje(st.session_state.chat_actual_id, "assistant", respuesta_ia)
            
            # Pequeño rerun para actualizar el sidebar si acabamos de crear un chat nuevo
            # (Para que aparezca el botón nuevo en la lista)
            # Solo si acabamos de crearlo (podemos comprobarlo contando mensajes o flag)
            if len(st.session_state.messages) <= 3: 
                time.sleep(0.5) # Pequeña pausa para que se guarde bien
                st.rerun()

        except Exception as e:
            st.error(f"Error al conectar con la IA: {e}")