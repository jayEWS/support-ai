import os

# Nama folder utama proyek
ROOT_DIR = "support-portal-ai"

# Struktur file dan kontennya
files = {
    # File Konfigurasi
    ".env": """# Konfigurasi AI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Konfigurasi WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=whatsapp:+14155238886

# Keamanan
API_SECRET_KEY=your-secure-secret-key-here
""",

    "requirements.txt": """fastapi==0.111.0
uvicorn==0.30.1
python-dotenv==1.0.1
langchain==0.2.11
langchain-openai==0.1.20
langchain-community==0.2.11
langchain-chroma==0.1.2
chromadb==0.5.5
pypdf==4.3.1
httpx==0.27.0
python-multipart==0.0.9
jinja2==3.1.4
""",

    # Source Code Utama
    "main.py": """import os
import shutil
import logging
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

# Load Env
load_dotenv()

# Import Modul Lokal
from rag_engine import rag_engine
from whatsapp import wa_handler

# Setup
logging.basicConfig(level=logging.INFO)
app = FastAPI(title="Support Portal AI RAG")
templates = Jinja2Templates(directory="templates")

# === ROUTES ===

@app.get("/", response_class=HTMLResponse)
async def portal_dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/chat")
async def chat_directly(request: Request):
    data = await request.json()
    query = data.get("message")
    if not query:
        return JSONResponse({"error": "Message is required"}, status_code=400)
    if rag_engine:
        answer = rag_engine.ask(query)
    else:
        answer = "RAG Engine tidak terinisialisasi."
    return {"answer": answer}

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    return await wa_handler.process_message(request, rag_engine)

@app.post("/api/upload-knowledge")
async def upload_knowledge(file: UploadFile = File(...)):
    file_location = f"data/knowledge/{file.filename}"
    os.makedirs("data/knowledge", exist_ok=True)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    if rag_engine:
        rag_engine.ingest_documents()
    return {"status": "success", "message": f"File {file.filename} berhasil dipelajari."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
""",

    "rag_engine.py": """import os
import logging
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = "data/knowledge"
DB_DIR = "data/db_storage"

class RAGEngine:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings()
        self.llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)
        self.vector_store = None
        self.initialize_knowledge_base()

    def initialize_knowledge_base(self):
        if os.path.exists(DB_DIR) and os.listdir(DB_DIR):
            logger.info("✅ Memuat Knowledge Base yang sudah ada...")
            self.vector_store = Chroma(persist_directory=DB_DIR, embedding_function=self.embeddings)
        else:
            logger.info("🔧 Inisialisasi Knowledge Base pertama kali...")
            self.ingest_documents()

    def ingest_documents(self):
        documents = []
        if not os.path.exists(KNOWLEDGE_DIR):
            os.makedirs(KNOWLEDGE_DIR)
            logger.warning(f"Folder {KNOWLEDGE_DIR} dibuat.")
            return

        for file in os.listdir(KNOWLEDGE_DIR):
            file_path = os.path.join(KNOWLEDGE_DIR, file)
            try:
                if file.endswith(".pdf"):
                    loader = PyPDFLoader(file_path)
                    documents.extend(loader.load())
                elif file.endswith(".txt"):
                    loader = TextLoader(file_path, encoding='utf-8')
                    documents.extend(loader.load())
            except Exception as e:
                logger.error(f"Error loading {file}: {e}")

        if not documents:
            logger.warning("⚠️ Tidak ada dokumen ditemukan.")
            return

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(documents)
        self.vector_store = Chroma.from_documents(documents=texts, embedding=self.embeddings, persist_directory=DB_DIR)
        logger.info(f"✅ {len(texts)} potongan informasi berhasil dipelajari.")

    def ask(self, query: str) -> str:
        if not self.vector_store:
            return "Maaf, sistem AI belum siap."
        qa_chain = RetrievalQA.from_chain_type(llm=self.llm, chain_type="stuff", retriever=self.vector_store.as_retriever(search_kwargs={"k": 3}))
        try:
            result = qa_chain.invoke({"query": query})
            return result['result']
        except Exception as e:
            return f"Error: {str(e)}"

try:
    rag_engine = RAGEngine()
except Exception as e:
    print(f"Fatal Error: {e}")
    rag_engine = None
""",

    "whatsapp.py": """import os
import httpx
import logging
from fastapi import Request
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class WhatsAppHandler:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.my_number = os.getenv("TWILIO_PHONE_NUMBER")

    async def process_message(self, request: Request, rag_engine):
        form_data = await request.form()
        incoming_msg = form_data.get("Body")
        sender_id = form_data.get("From")
        logger.info(f"📩 Pesan masuk dari {sender_id}: {incoming_msg}")

        if not incoming_msg: return "No message", 400
        
        if rag_engine: ai_response = rag_engine.ask(incoming_msg)
        else: ai_response = "AI tidak aktif."
        
        await self.send_reply(sender_id, ai_response)
        return "OK", 200

    async def send_reply(self, to_number: str, message: str):
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        if not self.auth_token or "your_token" in self.auth_token:
            logger.info(f"⚠️ SIMULASI BALAS: {message[:50]}...")
            return

        payload = {'From': self.my_number, 'To': to_number, 'Body': message}
        async with httpx.AsyncClient() as client:
            await client.post(url, data=payload, auth=(self.account_sid, self.auth_token))

wa_handler = WhatsAppHandler()
""",

    # Templates
    "templates/index.html": """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support Portal AI</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .chat-bubble-user { background-color: #3b82f6; color: white; border-radius: 1rem 1rem 0 1rem; }
        .chat-bubble-ai { background-color: #f3f4f6; color: #1f2937; border-radius: 1rem 1rem 1rem 0; }
    </style>
</head>
<body class="bg-gray-100 h-screen flex flex-col">
    <nav class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 py-3 flex justify-between items-center">
            <h1 class="text-xl font-bold text-gray-800">Support Portal <span class="text-blue-600">AI</span></h1>
            <div class="flex items-center space-x-2">
                <span class="h-2 w-2 bg-green-500 rounded-full animate-pulse"></span>
                <span class="text-sm text-gray-500">System Online</span>
            </div>
        </div>
    </nav>

    <div class="flex flex-1 overflow-hidden max-w-7xl mx-auto w-full">
        <aside class="w-1/3 bg-white border-r p-6 flex flex-col">
            <h2 class="text-lg font-semibold text-gray-700 mb-2">Knowledge Base</h2>
            <p class="text-xs text-gray-400 mb-4">Upload file untuk memperbarui pengetahuan AI.</p>
            <form action="/api/upload-knowledge" method="post" enctype="multipart/form-data" class="space-y-3">
                <div class="border-2 border-dashed border-gray-200 rounded-lg p-6 flex flex-col items-center justify-center hover:border-blue-400 transition">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                    <input type="file" name="file" accept=".pdf,.txt" class="mt-2 text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"/>
                </div>
                <button type="submit" class="w-full bg-gray-800 hover:bg-gray-900 text-white text-sm font-bold py-2.5 px-4 rounded-lg transition">Train AI</button>
            </form>
        </aside>

        <main class="w-2/3 flex flex-col bg-gray-50">
            <div id="chatbox" class="flex-1 p-6 overflow-y-auto space-y-4">
                <div class="text-center py-10">
                    <h2 class="text-2xl font-bold text-gray-700 mb-2">Selamat Datang</h2>
                    <p class="text-gray-400">Saya adalah asisten virtual berbasis data Anda. Silakan bertanya.</p>
                </div>
            </div>
            <div class="p-4 bg-white border-t">
                <form id="chat-form" class="flex gap-3">
                    <input type="text" id="user-input" placeholder="Ketik pertanyaan tentang produk..." class="flex-1 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"/>
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl transition">Kirim</button>
                </form>
            </div>
        </main>
    </div>

    <script>
        const chatForm = document.getElementById('chat-form');
        const chatbox = document.getElementById('chatbox');
        const userInput = document.getElementById('user-input');

        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = userInput.value.trim();
            if(!message) return;
            addMessage(message, 'user');
            userInput.value = '';
            try {
                const res = await fetch('/api/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: message}) });
                const data = await res.json();
                addMessage(data.answer, 'ai');
            } catch (err) { addMessage("Koneksi error.", 'ai'); }
        });

        function addMessage(text, type) {
            const wrapper = document.createElement('div');
            wrapper.className = `flex ${type === 'user' ? 'justify-end' : 'justify-start'}`;
            const bubble = document.createElement('div');
            bubble.className = `p-3 max-w-md shadow-sm ${type === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'}`;
            bubble.innerText = text;
            wrapper.appendChild(bubble);
            chatbox.appendChild(wrapper);
            chatbox.scrollTop = chatbox.scrollHeight;
        }
    </script>
</body>
</html>
"""
}

def create_project():
    print(f"🚀 Membuat proyek di folder: {ROOT_DIR}...")
    
    # Buat folder utama
    if not os.path.exists(ROOT_DIR):
        os.makedirs(ROOT_DIR)

    # Buat subfolder
    os.makedirs(os.path.join(ROOT_DIR, "data", "knowledge"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "data", "db_storage"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "templates"), exist_ok=True)

    # Tulis semua file
    for file_path, content in files.items():
        full_path = os.path.join(ROOT_DIR, file_path)
        # Pastikan folder induk ada (untuk file di subfolder)
        parent_dir = os.path.dirname(full_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
            
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ File dibuat: {full_path}")

    print("\n✨ PROYEK BERHASIL DIBUAT!")
    print("Langkah selanjutnya:")
    print(f"1. Masuk ke folder: cd {ROOT_DIR}")
    print("2. Install library: pip install -r requirements.txt")
    print("3. Isi API Key di file .env")
    print("4. Jalankan: python main.py")

if __name__ == "__main__":
    create_project()