# AI-Customer-chatbot-assistant

A minimal, scalable starter for an AI customer chatbot built with:
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
