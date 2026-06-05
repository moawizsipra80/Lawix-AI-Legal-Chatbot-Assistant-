from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from rag_engine import RAGEngine
import os
import json
from fastapi.responses import FileResponse 
# pyrefly: ignore [missing-import]
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import UploadFile, File, BackgroundTasks
import pypdf
import io
load_dotenv()

app = FastAPI()
rag = RAGEngine()
# ---- LLM provider configuration -------------------------------------------
# Choose the backend with the LLM_PROVIDER env var: "groq" or "gemini".
# Groq (GroqCloud) is OpenAI-compatible and has a generous free tier, so it's
# the default. Gemini's free tier for gemini-2.5-flash is only ~20 requests/day.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()

groq_client = None
gemini_model = None

if LLM_PROVIDER == "groq":
    from groq import Groq
    MODEL_NAME = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
else:  # gemini
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    gemini_model = genai.GenerativeModel(MODEL_NAME)


def _generate_once(prompt: str) -> str:
    """Run a single (non-retried) generation against the configured provider."""
    if LLM_PROVIDER == "groq":
        resp = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
        )
        return (resp.choices[0].message.content or "").strip()
    resp = gemini_model.generate_content(prompt)
    return resp.text.strip()


dataset_path = os.path.join(os.path.dirname(__file__), "law_firm_dataset.json")
if os.path.exists(dataset_path):
    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            law_docs = json.load(f)
            existing = rag.get_all_documents()
            existing_titles = {d["title"] for d in existing}
            for doc in law_docs:
                title = doc.get("title", "Untitled")
                if title not in existing_titles:
                    meta_fields = doc.get("metadata", {})
                    meta_fields["category"] = doc.get("category", "General")
                    rag.add_document(
                        content=doc.get("content", ""),
                        title=title,
                        metadata_dict=meta_fields
                    )
    except Exception as e:
        print(f"Error loading dataset: {e}")
else:
    docs = [
        "Our law firm represents clients in Intellectual Property, Contracts, and Corporate Litigation.",
        "The standard confidentiality period for our mutual NDAs is five (5) years.",
        "Under GDPR regulations, EU citizens have the right to erase their personal data from our systems.",
        "The statute of limitations for civil breach of contract claims is typically four (4) years."
    ]
    rag.add_documents(docs)


import time
import re

# Cap how long a single request may sleep while waiting out a per-minute throttle,
# so the HTTP request never hangs for minutes.
MAX_RETRY_SLEEP_SECONDS = 30.0


class QuotaExceededError(Exception):
    """Raised when the Gemini quota is exhausted.

    kind == "daily"  -> daily free-tier cap hit; retrying today is pointless.
    kind == "minute" -> per-minute throttle that survived all retries.
    """
    def __init__(self, kind: str, raw_message: str):
        self.kind = kind
        self.raw_message = raw_message
        super().__init__(raw_message)


def _is_rate_limit_error(err_msg: str) -> bool:
    low = err_msg.lower()
    return "429" in err_msg or "quota" in low or "resourceexhausted" in low


def _is_daily_quota_error(err_msg: str) -> bool:
    # e.g. quota_id: "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
    normalized = err_msg.lower().replace("_", "").replace(" ", "")
    return "perday" in normalized


def generate_with_retry(prompt, retries=3):
    for i in range(retries):
        try:
            return _generate_once(prompt)
        except Exception as ex:
            err_msg = str(ex)
            if not _is_rate_limit_error(err_msg):
                raise

            # Daily free-tier cap: the quota won't reset for hours, so sleeping
            # and retrying just wastes the user's time and still fails. Bail out now.
            if _is_daily_quota_error(err_msg):
                print("Gemini API daily quota exhausted (429). Not retrying.")
                raise QuotaExceededError("daily", err_msg)

            # Per-minute throttle: parse the suggested delay and wait it out,
            # but only if we still have attempts left.
            if i < retries - 1:
                delay = 15.0  # Default fallback
                match1 = re.search(r"Please retry in ([\d\.]+)s", err_msg)
                match2 = re.search(r"seconds:\s*(\d+)", err_msg)
                if match1:
                    delay = float(match1.group(1)) + 1.5
                elif match2:
                    delay = float(match2.group(1)) + 1.5
                delay = min(delay, MAX_RETRY_SLEEP_SECONDS)
                print(f"Gemini API rate limit hit (429). Sleeping for {delay:.2f} seconds before retrying... (Attempt {i+1}/{retries})")
                time.sleep(delay)
                continue

            # Out of retries on a per-minute throttle.
            raise QuotaExceededError("minute", err_msg)

@app.get("/chat")
def chat(query: str, session_id: str = "default_session"):
    history = rag.get_chat_history(session_id)
    
    search_query = query

    results = rag.search(search_query, n_results=5)
    
    print(f"\n--- Retrieved {len(results)} chunks for search query '{search_query}':")
    for idx, doc in enumerate(results):
        print(f"  [{idx + 1}] Title: {doc['metadata'].get('title', 'Untitled')} | Length: {len(doc['content'])} chars")
    print("--------------------------------------------------\n")
    
    context_chunks = []
    for doc in results:
        context_chunks.append(f"Document: {doc['metadata'].get('title', 'Untitled')}\nContent: {doc['content']}")
    context = "\n\n".join(context_chunks)

    history_context = ""
    if len(history) > 0:
        history_lines = [f"{msg['role']}: {msg['content']}" for msg in history]
        history_context = "Recent Conversation History:\n" + "\n".join(history_lines) + "\n\n"

    prompt = f"""You are a professional legal assistant for a law firm.
Answer the user's question clearly, professionally, and accurately using the context provided below.
If the answer is not in the context, politely state that you do not have that information in your database.

Context:
{context}

{history_context}Question: {query}
Answer:"""

    generation_failed = False
    try:
        answer = generate_with_retry(prompt)
    except QuotaExceededError as qe:
        generation_failed = True
        if qe.kind == "daily":
            answer = (
                "⚠️ The AI model's daily free-tier limit has been reached "
                "(Gemini's free tier allows only 20 requests/day for gemini-2.5-flash). "
                "The quota resets after about 24 hours. To keep chatting now, enable billing "
                "on your Google AI Studio project or switch to a model with a higher free quota."
            )
        else:
            answer = (
                "⚠️ The AI model is busy right now (too many requests in a short time). "
                "Please wait a few seconds and try again."
            )
    except Exception as ex:
        generation_failed = True
        answer = f"Error generating response: {str(ex)}"

    rag.add_chat_message(session_id, "User", query)
    # Don't persist transient error messages into the conversation history.
    if not generation_failed:
        rag.add_chat_message(session_id, "Assistant", answer)

    sources = []
    for doc in results:
        meta = doc["metadata"]
        sources.append({
            "title": meta.get("title", "Untitled Document"),
            "category": meta.get("category", "General"),
            "practice_area": meta.get("practice_area", "General"),
            "confidentiality": meta.get("confidentiality", "Standard")
        })

    return {
        "answer": answer,
        "sources": sources
    }

@app.get("/history")
def get_history(session_id: str = "default_session"):
    history = rag.get_chat_history(session_id)
    return {"history": history}

@app.get("/sessions")
def get_sessions():
    sessions = rag.get_all_sessions()
    return {"sessions": sessions}

#delete route
@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    rag.clear_chat_history(session_id)
    return {"message": "session deleted successfully"}

# Store processing status of uploaded documents
upload_status = {}

def process_pdf_in_background(file_bytes: bytes, filename: str):
    try:
        upload_status[filename] = "processing"
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        
        # 1. Extract all text to generate a global summary
        all_text_list = []
        for page in pdf_reader.pages:
            t = page.extract_text()
            if t:
                all_text_list.append(t)
        all_text = "\n".join(all_text_list)
        
        # 2. Store page-by-page chunks
        chunk_size = 800
        total_chunks = 0
        for page_num, page in enumerate(pdf_reader.pages):
            text = page.extract_text()
            if not text:
                continue
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                rag.add_document(
                    content=chunk,
                    title=f"{filename} (Page {page_num + 1})",
                    metadata_dict={
                        "source": filename,
                        "category": "uploaded pdf",
                        "page_number": page_num + 1
                    }
                )
                total_chunks += 1
                
        upload_status[filename] = f"completed:{total_chunks}"
    except Exception as e:
        print(f"Error processing PDF: {e}")
        upload_status[filename] = f"failed:{str(e)}"

#uploading 
@app.post("/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        # Initialize status
        upload_status[file.filename] = "uploaded"
        # Dispatch background processing task
        background_tasks.add_task(process_pdf_in_background, file_bytes, file.filename)
        return {"filename": file.filename, "status": "processing"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/upload/status/{filename}")
def get_upload_status(filename: str):
    status_str = upload_status.get(filename, "unknown")
    if ":" in status_str:
        status, details = status_str.split(":", 1)
        return {"filename": filename, "status": status, "details": details}
    return {"filename": filename, "status": status_str}

app.mount("/static", StaticFiles(directory="db/chroma_storage/static"), name="static")
@app.get("/",response_class=FileResponse)
def serve_frontend():
    return FileResponse("db/chroma_storage/static/index.html")

HOST = "127.0.0.1"
PORT = 8000


def _is_port_in_use(host: str, port: int) -> bool:
    """Return True if something is already listening on host:port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def free_port(host: str, port: int) -> None:
    """Kill any orphaned process still holding host:port.

    On Windows, closing the terminal window (instead of Ctrl+C) leaves the
    uvicorn process running, so the next `python app.py` can't bind the port.
    This finds and terminates those orphans so startup always succeeds.
    """
    if not _is_port_in_use(host, port):
        return

    import sys
    import subprocess
    import time

    if sys.platform.startswith("win"):
        try:
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "TCP"], text=True
            )
        except Exception as e:
            print(f"Could not inspect port {port}: {e}")
            return
        pids = set()
        needle = f"{host}:{port}"
        for line in out.splitlines():
            parts = line.split()
            # Format: Proto  Local-Address  Foreign-Address  State  PID
            if len(parts) >= 5 and parts[1].endswith(needle) and parts[3] == "LISTENING":
                pids.add(parts[-1])
        for pid in pids:
            if pid == "0":
                continue
            print(f"Port {port} is held by an orphaned process (PID {pid}). Terminating it...")
            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
    else:
        # POSIX: use fuser if available.
        subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)

    # Give the OS a moment to release the socket.
    for _ in range(10):
        if not _is_port_in_use(host, port):
            print(f"Port {port} is now free.")
            return
        time.sleep(0.3)
    print(f"Warning: port {port} still appears to be in use.")


if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time

    # Make sure no stale instance is squatting on the port before we start.
    free_port(HOST, PORT)

    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://{HOST}:{PORT}/")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app:app", host=HOST, port=PORT, reload=False)
