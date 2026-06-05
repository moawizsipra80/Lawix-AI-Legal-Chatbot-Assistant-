from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from rag_engine import RAGEngine
import os
import json
from fastapi.responses import FileResponse 
# pyrefly: ignore [missing-import]
import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import UploadFile,File
import pypdf
import io
load_dotenv()

app = FastAPI()
rag = RAGEngine()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")


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


@app.get("/chat")
def chat(query: str, session_id: str = "default_session"):
    history = rag.get_chat_history(session_id)
    
    search_query = query
    if len(history) > 0:
        history_lines = [f"{msg['role']}: {msg['content']}" for msg in history]
        history_str = "\n".join(history_lines)
        
        rewrite_prompt = f"""Given the following conversation history and a follow-up question, rewrite the follow-up question to be a standalone query that can be used to search a database.
Do NOT include any introduction, explanations, or conversational text. Output ONLY the raw rewritten search query.

Conversation History:
{history_str}

Follow-up Question: {query}
Standalone Search Query:"""
        try:
            rewrite_response = model.generate_content(rewrite_prompt)
            rewritten_text = rewrite_response.text.strip()
            if rewritten_text:
                search_query = rewritten_text
                print(f"Rewrote query: '{query}' -> '{search_query}'")
        except Exception as e:
            print(f"Failed to rewrite query: {e}")

    
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

    try:
        response = model.generate_content(prompt) 
        answer = response.text.strip()
    except Exception as ex:
        answer = f"Error generating response: {str(ex)}"

    rag.add_chat_message(session_id, "User", query)
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

#uploading 
@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        
        # 1. Extract all text to generate a global summary
        all_text_list = []
        for page in pdf_reader.pages:
            t = page.extract_text()
            if t:
                all_text_list.append(t)
        all_text = "\n".join(all_text_list)
        
        # 2. Call Gemini to create a "crux" document summary
        if all_text.strip():
            summary_prompt = f"""You are a professional legal expert. Write a comprehensive, detailed legal summary and crux of the following document.
Identify the main parties, core background context, primary legal issues/arguments, and key conclusions or outcomes.
Do NOT include generic conversational text, explanations, or preambles. Output ONLY the structured summary.

Document Text:
{all_text[:25000]}"""
            try:
                summary_response = model.generate_content(summary_prompt)
                summary_text = summary_response.text.strip()
                if summary_text:
                    rag.add_document(
                        content=summary_text,
                        title=f"{file.filename} (Global Summary & Crux)",
                        metadata_dict={
                            "source": file.filename,
                            "category": "document_summary",
                            "is_summary": "True"
                        }
                    )
            except Exception as e:
                print(f"Failed to generate document summary: {e}")

        # 3. Store page-by-page chunks
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
                    title=f"{file.filename} (Page {page_num + 1})",
                    metadata_dict={
                        "source": file.filename,
                        "category": "uploaded pdf",
                        "page_number": page_num + 1
                    }
                )
                total_chunks += 1
                
        return {"filename": file.filename, "message": "file uploaded successfully", "chunks": total_chunks}
    except Exception as e:
        return {"error": str(e)}

app.mount("/static", StaticFiles(directory="db/chroma_storage/static"), name="static")
@app.get("/",response_class=FileResponse)
def serve_frontend():
    return FileResponse("db/chroma_storage/static/index.html")

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time

    def open_browser():
        time.sleep(1.5) 
        webbrowser.open("http://127.0.0.1:8000/")
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
