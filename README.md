# Lawix AI- Legal Assistant Chatbot
 It is a Legal Chatbot assistant for lawyers in which lawyers upload their cases with the help of pdf and  the whole chatbot which uses chroma db stores and reads the all of the topics in the pdf and store  in the form of chunks in datbase.So,it is convinient for the lawyers to solve and all of the cases by reading it and answering and questioning from that chatbot. 
A minimal, scalable starter for an Legal Chatbot Assistant  built with:
- **Python** (Flask backend API)
- **ChromaDB** (knowledge retrieval)
- **HTML/CSS/JavaScript** (`app.js` frontend)

## Features
- Clean chat UI (`static/index.html`, `static/style.css`, `static/app.js`)
- Backend chat API (`POST /api/chat`)
- Health check API (`GET /api/health`)
- ChromaDB persistent storage (`./chroma_data`) with starter customer-support knowledge
- Graceful fallback responses if ChromaDB is not available

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open: `http://127.0.0.1:5000`

## API example
```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is your return policy?"}'
```
