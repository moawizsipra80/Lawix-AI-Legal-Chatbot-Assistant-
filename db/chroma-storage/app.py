from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from rag_engine import RAGEngine
import os
from fastapi.responses import FileResponse 
# pyrefly: ignore [missing-import]
import google.generativeai as genai
app = FastAPI()
rag = RAGEngine()
genai.configure(api_key="XXXXXX")

model = genai.GenerativeModel("gemini-2.5-flash")


docs = [
    "We offer 24/7 customer support.",
    "Refunds are available within 7 days.",
    "Delivery takes 3–5 business days.",
    "Contact support via email or WhatsApp."
]

rag.add_documents(docs)


@app.get("/chat")
def chat(query: str):
#retrive 
    context = rag.search(query)

    prompt = f"""You are a customer support assistant.Context:{context} Question: {query}
       Answer clearly and professionally. 
    """
    try:
        response=model.generate_content(prompt) 
        answer=response.text.strip()
    except Exception as ex:
        answer=f"Error generating response: {str(ex)}"


    return {"answer": answer}
app.mount("/static", StaticFiles(directory="db/chroma_storage/static"), name="static")
@app.get("/",response_class=FileResponse)
def serve_frontend():
    return FileResponse("db/chroma_storage/static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)

