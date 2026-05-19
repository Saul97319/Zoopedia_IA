import os
import shutil
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv(override=True)

class MotorIA_RAG:
    def __init__(self):
        # 1. Configuración de Credenciales
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            raise ValueError("Falta la GOOGLE_API_KEY en el archivo .env")

        # --- CORRECCIÓN: RUTAS ABSOLUTAS Y SEGURAS ---
        # Buscamos la ruta real de la carpeta 'backend' dinámicamente
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.persist_directory = os.path.join(self.base_dir, "data", "chroma_db")
        self.docs_directory = os.path.join(self.base_dir, "data", "docs_animales")

        # 2. Configuración del Cerebro Local (Embeddings)
        print("⚙️ Configurando: Embeddings Locales + gemma-3-27b-it...")
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
        # 3. Configuración del LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemma-3-27b-it",
            google_api_key=self.google_api_key,
            temperature=0.2 
        )
        
        self.vectorstore = None

    def _conectar_db(self):
        """Conecta a la base de datos vectorial. Si no existe, la crea automáticamente."""
        if os.path.exists(self.persist_directory):
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory, 
                embedding_function=self.embeddings
            )
            return True
        else:
            # --- CORRECCIÓN: AUTO-ENTRENAMIENTO ---
            print("⚠️ Cerebro de IA no encontrado. Leyendo PDFs y entrenando ahora...")
            self.cargar_documentos_pdf()
            return self.vectorstore is not None

    def cargar_documentos_pdf(self):
        """Re-entrena la IA leyendo los PDFs de la carpeta"""
        print("--- INICIANDO PROCESO DE CARGA DE DOCUMENTOS ---")
        
        if os.path.exists(self.persist_directory):
            try:
                shutil.rmtree(self.persist_directory)
            except PermissionError:
                print("⚠️ Error: Cierra procesos que usen la carpeta chroma_db")
                return

        print("1. Leyendo PDFs de animales...")
        docs = []
        
        # Usamos la nueva ruta absoluta segura
        if not os.path.exists(self.docs_directory):
            print(f"❌ Carpeta no encontrada: {self.docs_directory}")
            os.makedirs(self.docs_directory, exist_ok=True)
            return

        for filename in os.listdir(self.docs_directory):
            if filename.lower().endswith('.pdf'):
                try:
                    loader = PyPDFLoader(os.path.join(self.docs_directory, filename))
                    docs.extend(loader.load())
                    print(f"   ✅ Leído: {filename}")
                except Exception as e:
                    print(f"   ❌ Error en {filename}: {e}")

        if not docs: 
            print("⚠️ No se encontraron PDFs para entrenar a la IA.")
            return

        print("2. Fragmentando textos...")
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        fragments = text_splitter.split_documents(docs)
        
        print("3. Guardando memoria en ChromaDB...")
        self.vectorstore = Chroma.from_documents(
            documents=fragments,
            embedding=self.embeddings,
            persist_directory=self.persist_directory
        )
        print("¡Memoria de la IA construida y guardada correctamente!")

    def _reformular_pregunta(self, pregunta_usuario, historial_chat):
        """
        Reescribe la pregunta del usuario usando el historial de PostgreSQL.
        """
        if not historial_chat:
            return pregunta_usuario # Si es la primera pregunta, no hacemos nada

        print("Contextualizando pregunta con historial de BD...")
        
        # Convertimos el historial de la BD al formato de texto para Gemini
        # Tomamos solo los últimos 6 mensajes para no gastar tokens extra
        mensajes_recientes = historial_chat[-6:]
        historial_texto = "\n".join([f"{msg['role']}: {msg['content']}" for msg in mensajes_recientes])
        
        template_reformulacion = """
        Dada la siguiente conversación y una pregunta de seguimiento, reescribe la pregunta de seguimiento 
        para que sea una pregunta independiente que contenga todo el contexto necesario.
        NO respondas la pregunta, solo reescríbela.
        
        Historial de chat:
        {historial}
        
        Pregunta de seguimiento: {pregunta}
        
        Pregunta independiente (reescrita):
        """
        
        prompt = PromptTemplate(
            template=template_reformulacion,
            input_variables=["historial", "pregunta"]
        )
        
        chain = prompt | self.llm | StrOutputParser()
        response = chain.invoke({"historial": historial_texto, "pregunta": pregunta_usuario})
        return response.strip()
    
    def obtener_respuesta(self, pregunta_usuario, historial_chat=[]):
        # 1. Intentar conectar a la memoria
        if self.vectorstore is None:
            if not self._conectar_db():
                return "Error: La base de datos no existe."

        # 2. Reformulación de la pregunta usando el historial de la BD
        pregunta_busqueda = self._reformular_pregunta(pregunta_usuario, historial_chat)
        
        if pregunta_busqueda != pregunta_usuario:
            print(f"🔄 Pregunta reescrita internamente: '{pregunta_busqueda}'")

        # 3. Búsqueda de Contexto
        print(f"🔍 Buscando contexto en Chroma...")
        docs = self.vectorstore.similarity_search(pregunta_busqueda, k=6)
        
        if not docs:
            return "No encontré información relevante en mis documentos."

        contexto_texto = "\n\n".join([doc.page_content for doc in docs])

        # 4. Prompt de Respuesta 
        template = """
        Eres Zoopedia, el experto oficial del Zoológico de Guadalajara. Tu tono es educativo, amable y profesional.
        Tu única fuente de verdad es el CONTEXTO OFICIAL provisto.
        
        CONTEXTO OFICIAL (Base de datos):
        {contexto}
        
        PREGUNTA DEL USUARIO:
        {pregunta}
        
        INSTRUCCIONES DE RAZONAMIENTO (CUMPLE AL 100%):
        1. BUSCA LA RESPUESTA EXACTA: Responde basándote ÚNICA Y EXCLUSIVAMENTE en el CONTEXTO OFICIAL.
        2. RESTRICCIÓN DE IGNORANCIA: Si la respuesta a la pregunta no aparece en el CONTEXTO OFICIAL, tu respuesta debe ser EXACTAMENTE y ÚNICAMENTE: "Lo siento, no tengo esa información en mis registros oficiales."
        3. PROHIBICIÓN ESTRICTA: Tienes estrictamente PROHIBIDO complementar con conocimiento externo. NO uses frases como "Sin embargo...", "Pero...", o "Te puedo decir que..." si la información no está en el contexto. 
        4. REGLAMENTO Y LOGÍSTICA: Si preguntan sobre tocar o alimentar, usa el Reglamento. Sé servicial con temas de baños o comida, basándote solo en lo que sepas del zoológico.
        5. LIMITACIÓN DE RESPUESTA: Si la pregunta está fuera de contexto del zoológico Guadalajara, responde "Lo siento, solo puedo responder preguntas relacionadas con el Zoológico de Guadalajara." No inventes excusas ni explicaciones adicionales.
        Respuesta:
        """
        
        prompt = PromptTemplate(template=template, input_variables=["contexto", "pregunta"])
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            # Retornamos directamente la respuesta, la API se encargará de guardar en BD
            respuesta = chain.invoke({"contexto": contexto_texto, "pregunta": pregunta_busqueda})
            return respuesta
        except Exception as e:
            return f"Error al conectar con Gemini: {e}"

# --- PRUEBA INTERACTIVA FINAL ---
if __name__ == "__main__":
    motor = MotorIA_RAG()
    
    # La carga de documentos ahora es 100% automática al buscar una respuesta
    
    print("\n🦁 BIENVENIDO A ZOOPEDIA IA (Consola de Prueba) 🦁")
    print("Escribe 'salir' para terminar.\n")
    
    while True:
        pregunta = input("Tú: ")
        if pregunta.lower() in ['salir', 'exit']:
            break
            
        respuesta = motor.obtener_respuesta(pregunta)
        print(f"🤖 Zoopedia: {respuesta}\n")