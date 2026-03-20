=============== BIENVENIDO AL PROYECTO DE LA ZOOPEDIA =================================

Zoopedia IA es una plataforma inteligente diseñada para mejorar la experiencia en el Zoológico de Guadalajara. Combina un asistente virtual conversacional impulsado por Inteligencia Artificial (basado en arquitectura RAG) con un sistema integral de gestión que conecta a visitantes, cuidadores y administradores a través de diferentes interfaces web.
 
 Características Principales

* Asistente Virtual Educativo (RAG):** Un bot interactivo capaz de responder preguntas sobre animales, horarios y reglas del zoológico, basando sus respuestas estrictamente en documentos oficiales en PDF.
* Sistema de Roles y Autenticación:** Cuentas protegidas mediante tokens JWT para Visitantes, Cuidadores y Administradores, cada uno con permisos y vistas específicas.
* Gestión de Emergencias:** Sistema de alertas en tiempo real que permite a los visitantes reportar incidentes por zona directamente al personal autorizado.
* Catálogo Dinámico:** Panel administrativo para subir y actualizar las guías de los animales en formato PDF, las cuales reentrenan automáticamente la memoria de la IA.
* Foro Comunitario:** Espacio interactivo para que los usuarios publicen dudas y compartan respuestas.

 Tecnologías Utilizadas

* Backend: FastAPI, Uvicorn, PyJWT, Pydantic.
* Frontend (Interfaz de Usuario):** HTML5, CSS3 y JavaScript (Vanilla) comunicándose con la API a través de peticiones asíncronas (fetch).
* Inteligencia Artificial:** LangChain y LangChain Google GenAI. Modelos de Google (Generación de texto) y HuggingFace (Sentence Transformers para Embeddings multilingües).
* Bases de Datos:
  * ChromaDB (Base de datos vectorial para el motor de conocimiento RAG).
  * SQLite / PostgreSQL para la gestión relacional. El proyecto cuenta con un script que inicializa una base de datos local en `data/zoopedia.db`.

 Estructura del Proyecto

El repositorio está dividido lógicamente en Backend (Lógica y API) y Frontend (Vistas de usuario).

Zoopedia_IA/
├── backend/
│   ├── main_api.py          # Enrutamiento principal de la API RESTful
│   ├── utils/
│   │   ├── motor_ia.py      # Lógica del sistema RAG, embeddings y modelo generativo
│   │   └── db_manager.py    # Controladores de la base de datos relacional
│   └── data/
│       ├── docs_animales/   # Guías en PDF que nutren el conocimiento de la IA
│       └── chroma_db/       # Archivos de persistencia de la base de datos vectorial
├── frontend/
│   ├── index.html           # Página principal / Login / Registro
│   ├── chat_visitante.html  # Interfaz del usuario visitante con el asistente RAG
│   ├── chat_cuidador.html   # Tablero de control y gestión de alertas para cuidadores
│   ├── admin_panel.html     # Panel para gestión de usuarios y subida de PDFs
│   ├── foro_dudas.html      # Interfaz del foro comunitario
│   └── assets/              # Imágenes, iconos y recursos visuales (logos, fondos)
├── db_init.py               # Script para crear la base de datos SQLite y datos semilla
├── requirements.txt         # Dependencias de Python para el Backend
└── README.md
```

 Instalación y Configuración

 1. Clonar el repositorio
Descarga el proyecto e ingresa a la carpeta raíz.

 2. Inicializar la Base de Datos Relacional
Ejecuta el script de inicialización para crear el archivo `zoopedia.db` en la carpeta `data/` y generar las tablas necesarias (`usuarios`, `CATALOGO_ANIMALES`, `ALERTAS`, `LOGS_CHAT`) junto con los datos de prueba.

python db_init.py


 3. Configurar el Backend
Se recomienda utilizar un entorno virtual de Python. Ejecuta el siguiente comando para instalar las librerías necesarias:

pip install -r backend/requirements.txt


 4. Variables de Entorno
Crea un archivo `.env` en el directorio `backend/` con tus credenciales. Es indispensable contar con tu clave de API de Google para que el motor conversacional funcione:

GOOGLE_API_KEY=tu_clave_de_api_aqui

(Nota: El proyecto utiliza la clave secreta interna preconfigurada `SECRET_KEY=sPgXuDqxrp74zick9H8DXDnmjTQlmMSOeBIETFh2t0Q` para la firma de tokens JWT)*.

 5. Ejecución de la API (Backend)
Levanta el servidor FastAPI para habilitar los endpoints. Desde la raíz del proyecto, ejecuta:

uvicorn backend.main_api:app --reload

La API estará disponible por defecto en `http://127.0.0.1:8000`.

 6. Ejecución del Frontend
Al ser código estático (HTML/CSS/JS), no necesitas compilar nada. Puedes desplegarlo de dos maneras:
* Uso en Desarrollo: Abre la carpeta `frontend/` en VS Code y utiliza la extensión **Live Server** para levantar los archivos en un servidor local.
* Apertura Directa: Simplemente haz doble clic en `frontend/index.html` para abrirlo en tu navegador de preferencia (Asegúrate de que la API esté corriendo en el puerto correcto para que el fetch de JS funcione).

 Cuentas de Usuario de Prueba

Para probar los diferentes roles en la plataforma, puedes utilizar las siguientes credenciales preconfiguradas:

Visitantes:
 `prueba2@gmail.com` | Password: `273769291`
 `prueba3@gmail.com` | Password: `273769291`
 `enriquemartinez89@hotmail.com` | Password: `273769291`
 `test@outlook.com` | Password: `273769291`

Cuidadores:
 `cuidador1@zoopedia.com` | Password: `273769291`
 `krarenliz69@zoopedia.com` | Password: `273769291`

Administradores:
 `admin@zoopedia.com` | Password: `zoopedia2026.`

Notas sobre el Motor de IA

Para la extracción de contexto, el sistema lee los documentos en la carpeta `backend/data/docs_animales/`, los divide en fragmentos de texto y los convierte en vectores utilizando el modelo `paraphrase-multilingual-MiniLM-L12-v2`.
Si agregas nuevos PDFs manualmente a la carpeta, debes asegurarte de llamar a la función de recarga en `motor_ia.py` o, preferiblemente, subirlos mediante el endpoint administrativo desde el `admin_panel.html`. Además, la IA cuenta con una función de reformulación de preguntas que toma en cuenta los últimos mensajes de la base de datos para mantener el contexto de la conversación activa.

